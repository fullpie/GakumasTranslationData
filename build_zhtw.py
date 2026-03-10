from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import requests
from opencc import OpenCC


RUBY_RE = re.compile(r"<r\\=(.*?)>(.*?)</r>", re.DOTALL)
HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30ff]")


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src_dir))


def has_kana(text: str) -> bool:
    return bool(text and HIRAGANA_KATAKANA_RE.search(text))


def should_preserve_single_line(text: str) -> bool:
    # 單行只有 kana 才強制保留
    return has_kana(text)


def load_custom_dictionary(base: Path) -> dict[str, str]:
    """
    可自訂的 zhTW 修正表。
    檔名：name_dictionary_zhTW.json
    格式：{"來源字串": "目標字串"}
    """
    path = base / "name_dictionary_zhTW.json"
    if not path.exists():
        return {}
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("name_dictionary_zhTW.json must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def apply_custom_replacements(text: str, replacements: dict[str, str]) -> str:
    """
    依長度由長到短替換，避免短詞先吃掉長詞。
    """
    if not text or not replacements:
        return text

    for src, dst in sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(src, dst)
    return text


def convert_multiline_mixed_text(text: str, cc: OpenCC, replacements: dict[str, str]) -> str:
    """
    多行歌詞 / 對照：
    - 含 kana 的行保留
    - 其他行直接轉繁
    - 最後套用自訂修正表
    """
    lines = text.splitlines()
    converted_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            converted_lines.append(line)
            continue

        if has_kana(stripped):
            new_line = line
        else:
            new_line = cc.convert(line)

        new_line = apply_custom_replacements(new_line, replacements)
        converted_lines.append(new_line)

    return "\n".join(converted_lines)


def iter_convert_json(obj: Any, cc: OpenCC, replacements: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: iter_convert_json(v, cc, replacements) for k, v in obj.items()}

    if isinstance(obj, list):
        return [iter_convert_json(x, cc, replacements) for x in obj]

    if isinstance(obj, str):
        if "\n" in obj:
            return convert_multiline_mixed_text(obj, cc, replacements)

        if should_preserve_single_line(obj):
            return apply_custom_replacements(obj, replacements)

        converted = cc.convert(obj)
        return apply_custom_replacements(converted, replacements)

    return obj


def convert_ruby_text(text: str, cc: OpenCC) -> str:
    """
    劇情資源：
    <r\\=JP>ZH</r>
    只轉右側 ZH，左側 JP 完全保留
    """
    def repl(m: re.Match[str]) -> str:
        jp = m.group(1)
        zh = m.group(2)
        zh_tw = cc.convert(zh)
        return f"<r\\={jp}>{zh_tw}</r>"

    return RUBY_RE.sub(repl, text)


def download_and_extract_repo_zip(repo: str, subdir: str | None = None) -> Path:
    """
    保留這個步驟，方便之後擴充。
    目前主要是讓流程一致，也可驗證上游可正常取得。
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="gakumas_upstream_"))
    zip_path = tmp_dir / "repo.zip"
    url = f"https://github.com/{repo}/archive/refs/heads/main.zip"

    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    extract_dir = tmp_dir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    roots = list(extract_dir.iterdir())
    if not roots:
        raise RuntimeError(f"Failed to extract repo archive: {repo}")

    root = roots[0]
    if subdir:
        root = root / subdir
    return root


def main() -> int:
    base = Path(".").resolve()
    local_files = base / "local-files"
    if not local_files.exists():
        raise FileNotFoundError("local-files not found. Please run merge.py first.")

    zh_tw_root = base / "local-files-zhTW"
    if zh_tw_root.exists():
        shutil.rmtree(zh_tw_root)
    shutil.copytree(local_files, zh_tw_root)

    cc = OpenCC("s2twp")
    replacements = load_custom_dictionary(base)

    # 保留抓上游，方便後續擴充 / 驗證流程
    print("Downloading upstream reference sources...", flush=True)
    download_and_extract_repo_zip("imas-tools/GakumasPreTranslation", "etc")
    download_and_extract_repo_zip("imas-tools/gakumas-generic-strings-translation", "translated")
    download_and_extract_repo_zip("imas-tools/gakumas-master-translation", "data")

    # 1) resource/*.txt：只轉 ruby 右側 ZH，保留左側 JP
    print("Converting resource/*.txt with ruby-safe mode...", flush=True)
    resource_dir = zh_tw_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            converted = apply_custom_replacements(converted, replacements)
            write_text(txt_file, converted)

    # 2) localization.json
    print("Converting localization.json...", flush=True)
    localization_file = zh_tw_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        save_json(localization_file, iter_convert_json(data, cc, replacements))

    # 3) genericTrans/*.json
    print("Converting genericTrans/*.json...", flush=True)
    generic_dir = zh_tw_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc, replacements))

    # 4) masterTrans/*.json
    print("Converting masterTrans/*.json...", flush=True)
    master_dir = zh_tw_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc, replacements))

    # 5) version.txt
    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, zh_tw_root / "version.txt")

    # 6) build marker
    marker_file = zh_tw_root / "_zhtw_build_marker.txt"
    write_text(
        marker_file,
        "build_zhtw.py marker: SIMPLE-PRESERVE-NAMES-V1\n"
    )

    # 7) 打包 zhTW zip
    print("Packing GakumasTranslationData_zhTW.zip...", flush=True)
    zip_dir(zh_tw_root, base / "GakumasTranslationData_zhTW.zip")

    print("Built GakumasTranslationData_zhTW.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
