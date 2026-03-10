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

# 小型保留表：只補純漢字日文專名/固定詞，不做大詞典
PRESERVE_TERM_MAP = {
    "初星學園": "初星学園",
    "株式會社": "株式会社",
    "初星學園通知表": "初星学園通知表",
}


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
    if not text:
        return False
    return bool(HIRAGANA_KATAKANA_RE.search(text))


def restore_preserve_terms(text: str) -> str:
    for tw_term, jp_term in PRESERVE_TERM_MAP.items():
        text = text.replace(tw_term, jp_term)
    return text


def should_preserve_single_line(text: str, upstream_reference: str | None = None) -> bool:
    if not text:
        return False

    # 只有 kana 才算強日文訊號
    if has_kana(text):
        return True

    # 與上游原文完全相同則保留
    if upstream_reference and text == upstream_reference:
        return True

    # 其他情況允許轉繁
    return False


def convert_multiline_mixed_text(text: str, cc: OpenCC) -> str:
    """
    多行歌詞/對照：
    - 含 kana 的行保留
    - 其他行直接轉繁
    """
    lines = text.splitlines()
    converted_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            converted_lines.append(line)
            continue

        if has_kana(stripped):
            converted_lines.append(restore_preserve_terms(line))
        else:
            converted_lines.append(restore_preserve_terms(cc.convert(line)))

    return "\n".join(converted_lines)


def iter_convert_json(obj: Any, cc: OpenCC, upstream_texts: set[str] | None = None) -> Any:
    if isinstance(obj, dict):
        return {k: iter_convert_json(v, cc, upstream_texts) for k, v in obj.items()}

    if isinstance(obj, list):
        return [iter_convert_json(x, cc, upstream_texts) for x in obj]

    if isinstance(obj, str):
        # 多行字串（歌詞/對照）優先逐行處理
        if "\n" in obj:
            return convert_multiline_mixed_text(obj, cc)

        upstream_match = obj if upstream_texts and obj in upstream_texts else None
        if should_preserve_single_line(obj, upstream_match):
            return restore_preserve_terms(obj)

        return restore_preserve_terms(cc.convert(obj))

    return obj


def convert_ruby_text(text: str, cc: OpenCC) -> str:
    def repl(m: re.Match[str]) -> str:
        jp = m.group(1)
        zh = m.group(2)
        zh_tw = cc.convert(zh)
        return f"<r\\={jp}>{zh_tw}</r>"

    return RUBY_RE.sub(repl, text)


def download_and_extract_repo_zip(repo: str, subdir: str | None = None) -> Path:
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


def build_json_source_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for p in root.rglob("*.json"):
        index[p.name] = p
        index[p.relative_to(root).as_posix()] = p
    return index


def collect_strings(obj: Any) -> set[str]:
    out: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            out.add(x)

    walk(obj)
    return out


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

    print("Downloading upstream reference sources...", flush=True)
    pretranslation_root = download_and_extract_repo_zip(
        "imas-tools/GakumasPreTranslation", "etc"
    )
    generic_root = download_and_extract_repo_zip(
        "imas-tools/gakumas-generic-strings-translation", "translated"
    )
    master_root = download_and_extract_repo_zip(
        "imas-tools/gakumas-master-translation", "data"
    )

    pretranslation_index = build_json_source_index(pretranslation_root)
    generic_index = build_json_source_index(generic_root)
    master_index = build_json_source_index(master_root)

    # 1) resource/*.txt：只轉 ruby 右側 ZH，保留左側 JP
    print("Converting resource/*.txt with ruby-safe mode...", flush=True)
    resource_dir = zh_tw_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            write_text(txt_file, converted)

    # 2) localization.json
    print("Converting localization.json...", flush=True)
    localization_file = zh_tw_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        upstream_file = (
            pretranslation_index.get("localization.json")
            or pretranslation_index.get("localization_full.json")
        )
        upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file else set()
        save_json(localization_file, iter_convert_json(data, cc, upstream_texts))

    # 3) genericTrans/*.json
    print("Converting genericTrans/*.json...", flush=True)
    generic_dir = zh_tw_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            rel = json_file.relative_to(generic_dir).as_posix()
            upstream_file = generic_index.get(rel) or generic_index.get(json_file.name)
            upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file else set()
            save_json(json_file, iter_convert_json(data, cc, upstream_texts))

    # 4) masterTrans/*.json
    print("Converting masterTrans/*.json...", flush=True)
    master_dir = zh_tw_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            rel = json_file.relative_to(master_dir).as_posix()
            upstream_file = master_index.get(rel) or master_index.get(json_file.name)
            upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file else set()
            save_json(json_file, iter_convert_json(data, cc, upstream_texts))

    # 5) version.txt
    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, zh_tw_root / "version.txt")

    # 6) 打包 zhTW zip
    print("Packing GakumasTranslationData_zhTW.zip...", flush=True)
    zip_dir(zh_tw_root, base / "GakumasTranslationData_zhTW.zip")

    print("Built GakumasTranslationData_zhTW.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
