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


def should_preserve_single_line(text: str) -> bool:
    if not text:
        return False
    # 只有 kana 才算強日文訊號
    return has_kana(text)


def convert_multiline_mixed_text(text: str, cc: OpenCC) -> str:
    """
    多行歌詞 / 對照：
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


def build_name_overrides_from_repo(base: Path, cc: OpenCC) -> dict[str, str]:
    """
    直接讀 repo 裡現成的 name_dictionary.json，
    把 value 從簡中轉成繁中，當成最終覆蓋表。
    """
    path = base / "name_dictionary.json"
    if not path.exists():
        return {}

    raw = load_json(path)
    name_map: dict[str, str] = {}

    for _, value in raw.items():
        if isinstance(value, str):
            name_map[value] = cc.convert(value)

    return name_map


def apply_name_overrides_to_text(text: str, name_map: dict[str, str]) -> str:
    if not name_map:
        return text

    for src, dst in sorted(name_map.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(src, dst)
    return text


def apply_name_overrides_to_json(obj: Any, name_map: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: apply_name_overrides_to_json(v, name_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [apply_name_overrides_to_json(x, name_map) for x in obj]
    if isinstance(obj, str):
        return apply_name_overrides_to_text(obj, name_map)
    return obj


def main() -> int:
    base = Path(".").resolve()
    local_files = base / "local-files"
    if not local_files.exists():
        raise FileNotFoundError("local-files not found. Please run merge.py first.")

    # 用暫存輸出目錄，最後直接打包成原本檔名
    out_root = base / "local-files-out"
    if out_root.exists():
        shutil.rmtree(out_root)
    shutil.copytree(local_files, out_root)

    cc = OpenCC("s2twp")
    name_overrides = build_name_overrides_from_repo(base, cc)

    # 1) resource/*.txt：只轉 ruby 右側 ZH，保留左側 JP
    print("Converting resource/*.txt with ruby-safe mode...", flush=True)
    resource_dir = out_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            converted = apply_name_overrides_to_text(converted, name_overrides)
            write_text(txt_file, converted)

    # 2) localization.json
    print("Converting localization.json...", flush=True)
    localization_file = out_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        data = iter_convert_json(data, cc)
        data = apply_name_overrides_to_json(data, name_overrides)
        save_json(localization_file, data)

    # 3) genericTrans/*.json
    print("Converting genericTrans/*.json...", flush=True)
    generic_dir = out_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            data = iter_convert_json(data, cc)
            data = apply_name_overrides_to_json(data, name_overrides)
            save_json(json_file, data)

    # 4) masterTrans/*.json
    print("Converting masterTrans/*.json...", flush=True)
    master_dir = out_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            data = iter_convert_json(data, cc)
            data = apply_name_overrides_to_json(data, name_overrides)
            save_json(json_file, data)

    # 5) version.txt
    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, out_root / "version.txt")

    # 6) build marker
    marker_file = out_root / "_zhtw_build_marker.txt"
    write_text(
        marker_file,
        "build_zhtw.py marker: FINAL-REPLACE-ORIGINAL-ZIP-NAME-DICT-FULL-20260310\n"
    )

    # 7) 直接輸出成原本檔名
    print("Packing GakumasTranslationData.zip...", flush=True)
    zip_dir(out_root, base / "GakumasTranslationData.zip")

    print("Built GakumasTranslationData.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
