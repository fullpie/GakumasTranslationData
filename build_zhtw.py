from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from opencc import OpenCC


RUBY_RE = re.compile(r"<r\\=(.*?)>(.*?)</r>", re.DOTALL)


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


def iter_convert_json(obj: Any, cc: OpenCC) -> Any:
    if isinstance(obj, dict):
        return {k: iter_convert_json(v, cc) for k, v in obj.items()}
    if isinstance(obj, list):
        return [iter_convert_json(x, cc) for x in obj]
    if isinstance(obj, str):
        return cc.convert(obj)
    return obj


def convert_ruby_text(text: str, cc: OpenCC) -> str:
    def repl(m: re.Match[str]) -> str:
        jp = m.group(1)
        zh = m.group(2)
        zh_tw = cc.convert(zh)
        return f"<r\\={jp}>{zh_tw}</r>"

    return RUBY_RE.sub(repl, text)


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(src_dir))


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

    # 1) resource/*.txt：只轉 ruby 右側 ZH，保留左側 JP
    resource_dir = zh_tw_root / "resource"
    if resource_dir.exists():
        for txt_file in resource_dir.glob("adv*.txt"):
            original = read_text(txt_file)
            converted = convert_ruby_text(original, cc)
            write_text(txt_file, converted)

    # 2) localization.json
    localization_file = zh_tw_root / "localization.json"
    if localization_file.exists():
        data = load_json(localization_file)
        save_json(localization_file, iter_convert_json(data, cc))

    # 3) genericTrans/*.json
    generic_dir = zh_tw_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc))

    # 4) masterTrans/*.json
    master_dir = zh_tw_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            data = load_json(json_file)
            save_json(json_file, iter_convert_json(data, cc))

    # 5) version.txt
    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, zh_tw_root / "version.txt")

    # 6) 打包 zhTW zip
    zip_dir(zh_tw_root, base / "GakumasTranslationData_zhTW.zip")

    print("Built GakumasTranslationData_zhTW.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
