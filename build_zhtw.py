from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from opencc import OpenCC


RUBY_RE = re.compile(r"<r\\=(.*?)>(.*?)</r>", re.DOTALL)
HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30ff]")
HASHTAG_RE = re.compile(r'#[^\s",<]+')

HASHTAG_FORCE_CONVERT = {
    "#Animate气氛活跃队",
    "#学马扭蛋随心抽",
    "#学马仕成绩单",
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


def convert_hashtags(text: str, cc: OpenCC) -> str:
    def repl(m: re.Match[str]) -> str:
        tag = m.group(0)
        if tag in HASHTAG_FORCE_CONVERT:
            return cc.convert(tag)
        return tag

    return HASHTAG_RE.sub(repl, text)


def should_preserve_single_line(text: str) -> bool:
    if not text:
        return False
    return has_kana(text)


def convert_multiline_mixed_text(text: str, cc: OpenCC) -> str:
    """
    多行歌詞/對照：
    - 含 kana 的行保留
    - 其他行先處理 hashtag，再轉繁
    """
    lines = text.splitlines()
    converted_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            converted_lines.append(line)
            continue

        line = convert_hashtags(line, cc)

        if has_kana(stripped):
            converted_lines.append(line)
        else:
            converted_lines.append(cc.convert(line))

    return "\n".join(converted_lines)


def iter_convert_json(obj: Any, cc: OpenCC) -> Any:
    if isinstance(obj, dict):
        return {k: iter_convert_json(v, cc) for k, v in obj.items()}

    if isinstance(obj, list):
        return [iter_convert_json(x, cc) for x in obj]

    if isinstance(obj, str):
        obj = convert_hashtags(obj, cc)

        if "\n" in obj:
            return convert_multiline_mixed_text(obj, cc)

        if should_preserve_single_line(obj):
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

    print("Converting resource/*.txt with ruby-safe mode...", flush=True)
    resource_dir = zh_tw_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            write_text(txt_file, converted)

    print("Converting localization.json...", flush=True)
    localization_file = zh_tw_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        save_json(localization_file, iter_convert_json(data, cc))

    print("Converting genericTrans/*.json...", flush=True)
    generic_dir = zh_tw_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc))

    print("Converting masterTrans/*.json...", flush=True)
    master_dir = zh_tw_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc))

    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, zh_tw_root / "version.txt")

    print("Packing GakumasTranslationData_zhTW.zip...", flush=True)
    zip_dir(zh_tw_root, base / "GakumasTranslationData_zhTW.zip")

    print("Built GakumasTranslationData_zhTW.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
