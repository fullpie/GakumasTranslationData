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
JP_STYLE_RE = re.compile(r"[々ヶ・ー]")

CHINESE_FUNCTIONALS = {
    "的", "了", "和", "是", "在", "這", "这", "個", "个",
    "嗎", "吗", "請", "请", "將", "将", "與", "与",
}

UPSTREAM_SOURCES = {
    "pretranslation": ("imas-tools/GakumasPreTranslation", "etc"),
    "generic_translation": ("imas-tools/gakumas-generic-strings-translation", "translated"),
    "master_translation": ("imas-tools/gakumas-master-translation", "data"),
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


def iter_strings(obj: Any):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_strings(v)
    elif isinstance(obj, str):
        yield obj


def collect_strings(obj: Any) -> set[str]:
    return {s for s in iter_strings(obj) if s}


def is_likely_japanese_or_mixed(text: str) -> bool:
    if not text:
        return False
    if HIRAGANA_KATAKANA_RE.search(text):
        return True
    if JP_STYLE_RE.search(text):
        return True
    return False


def is_likely_chinese_sentence(text: str) -> bool:
    if not text:
        return False
    score = sum(1 for token in CHINESE_FUNCTIONALS if token in text)
    return score >= 1


def should_preserve_text(text: str, upstream_texts: set[str] | None = None) -> bool:
    if not text:
        return False

    # 有明顯日文特徵：直接保留
    if is_likely_japanese_or_mixed(text):
        return True

    # 與上游原文字串完全相同：保留
    if upstream_texts and text in upstream_texts:
        return True

    # 看起來不像自然中文句：保守保留
    if not is_likely_chinese_sentence(text):
        return True

    return False


def iter_convert_json(obj: Any, cc: OpenCC, upstream_texts: set[str] | None = None) -> Any:
    if isinstance(obj, dict):
        return {k: iter_convert_json(v, cc, upstream_texts) for k, v in obj.items()}
    if isinstance(obj, list):
        return [iter_convert_json(x, cc, upstream_texts) for x in obj]
    if isinstance(obj, str):
        if should_preserve_text(obj, upstream_texts):
            return obj
        return cc.convert(obj)
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

    roots = [p for p in extract_dir.iterdir() if p.is_dir()]
    if not roots:
        raise RuntimeError(f"No extracted root found for {repo}")
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

    # 下載上游 JSON 來源，提供日文/原文對照
    print("[1/4] Downloading upstream JSON sources...", flush=True)
    pretranslation_root = download_and_extract_repo_zip(*UPSTREAM_SOURCES["pretranslation"])
    generic_root = download_and_extract_repo_zip(*UPSTREAM_SOURCES["generic_translation"])
    master_root = download_and_extract_repo_zip(*UPSTREAM_SOURCES["master_translation"])

    pretranslation_index = build_json_source_index(pretranslation_root)
    generic_index = build_json_source_index(generic_root)
    master_index = build_json_source_index(master_root)

    # 1) resource/*.txt：只轉 ruby 右側 ZH，保留左側 JP
    print("[2/4] Converting resource/*.txt (ruby-safe)...", flush=True)
    resource_dir = zh_tw_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            write_text(txt_file, converted)

    # 2) localization.json：先參考上游原文，疑似日文/混合日文就保留
    print("[3/4] Converting JSON files with upstream-aware preservation...", flush=True)
    localization_file = zh_tw_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        upstream_file = pretranslation_index.get("localization.json") or pretranslation_index.get("localization_full.json")
        upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file and upstream_file.exists() else set()
        save_json(localization_file, iter_convert_json(data, cc, upstream_texts))

    generic_dir = zh_tw_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            rel = json_file.relative_to(generic_dir).as_posix()
            upstream_file = generic_index.get(rel) or generic_index.get(json_file.name)
            upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file and upstream_file.exists() else set()
            save_json(json_file, iter_convert_json(data, cc, upstream_texts))

    master_dir = zh_tw_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            rel = json_file.relative_to(master_dir).as_posix()
            upstream_file = master_index.get(rel) or master_index.get(json_file.name)
            upstream_texts = collect_strings(load_json(upstream_file)) if upstream_file and upstream_file.exists() else set()
            save_json(json_file, iter_convert_json(data, cc, upstream_texts))

    # 3) version.txt
    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, zh_tw_root / "version.txt")

    # 4) 打包 zhTW zip
    print("[4/4] Packing zhTW zip...", flush=True)
    zip_dir(zh_tw_root, base / "GakumasTranslationData_zhTW.zip")

    print("Built GakumasTranslationData_zhTW.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
