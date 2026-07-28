from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from imas_tools.story.gakuen_parser import parse_messages
from opencc import OpenCC


RUBY_RE = re.compile(r"<r\\=(.*?)>(.*?)</r>", re.DOTALL)
RUBY_GUARD = "\u200b"
RUBY_GUARD_FILE = "ruby_guard.json"
KANA_RE = re.compile(r"[ぁ-んァ-ヶヴヷ-ヺ]")
VALIDATION_REPORT_FILE = "zhtw_validation_report.json"
EXACT_RULE_FILES = ("name_dictionary_zhTW.json", "term_dictionary_zhTW.json")
REGEX_RULE_FILE = "regex_dictionary_zhTW.json"
BOUNDARY_CHARS = {" ", "]", ">", "\n"}


@dataclass
class Replacement:
    old: str
    new: str
    length: int


@dataclass
class ValidationIssue:
    kind: str
    path: str
    detail: str


class ReplacementRules:
    def __init__(self, base: Path) -> None:
        self.exact = self._load_exact_rules(base)
        self.exact_items = sorted(self.exact.items(), key=lambda item: len(item[0]), reverse=True)
        self.regex_rules = self._load_regex_rules(base)
        self.forbidden_tokens = self._build_forbidden_tokens()

    def _load_exact_rules(self, base: Path) -> dict[str, str]:
        rules: dict[str, str] = {}
        for file_name in EXACT_RULE_FILES:
            path = base / file_name
            if not path.exists():
                continue
            data = load_json(path)
            if not isinstance(data, dict):
                raise ValueError(f"{file_name} must be a JSON object")
            for key, value in data.items():
                rules[str(key)] = str(value)
        return rules

    def _load_regex_rules(self, base: Path) -> list[tuple[re.Pattern[str], str]]:
        path = base / REGEX_RULE_FILE
        if not path.exists():
            return []
        data = load_json(path)
        if not isinstance(data, list):
            raise ValueError(f"{REGEX_RULE_FILE} must be a JSON array")

        rules: list[tuple[re.Pattern[str], str]] = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"{REGEX_RULE_FILE} items must be JSON objects")
            pattern = item.get("pattern")
            replacement = item.get("replacement")
            if not isinstance(pattern, str) or not isinstance(replacement, str):
                raise ValueError(f"{REGEX_RULE_FILE} items must define string pattern/replacement")
            rules.append((re.compile(pattern), replacement))
        return rules

    def _build_forbidden_tokens(self) -> list[str]:
        tokens = {
            key
            for key, value in self.exact.items()
            if key != value
        }
        for pattern, replacement in self.regex_rules:
            literal = pattern.pattern
            if literal == re.escape(literal) and literal != replacement:
                tokens.add(literal)
        return sorted(tokens, key=len, reverse=True)

    def apply_exact(self, text: str) -> str:
        for source, target in self.exact_items:
            text = text.replace(source, target)
        return text

    def apply_regex(self, text: str) -> str:
        for pattern, replacement in self.regex_rules:
            text = pattern.sub(replacement, text)
        return text

    def normalize_only(self, text: str) -> str:
        return self.apply_regex(self.apply_exact(text))

    def protect(self, text: str) -> tuple[str, dict[str, str]]:
        protected = text
        placeholders: dict[str, str] = {}
        placeholder_index = 0

        for source, target in self.exact_items:
            if source not in protected:
                continue
            token = f"__ZHTW_PROTECT_{placeholder_index}__"
            placeholder_index += 1
            protected = protected.replace(source, token)
            placeholders[token] = target

        return protected, placeholders

    def restore(self, text: str, placeholders: dict[str, str]) -> str:
        for token, target in placeholders.items():
            text = text.replace(token, target)
        return text

    def convert(self, text: str, cc: OpenCC) -> str:
        protected, placeholders = self.protect(text)
        converted = cc.convert(protected)
        converted = self.restore(converted, placeholders)
        return self.normalize_only(converted)


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def save_ruby_guard_json(path: Path, data: dict[str, str]) -> None:
    serialized = json.dumps(data, ensure_ascii=False, indent=2).replace(RUBY_GUARD, r"\u200b")
    write_text(path, serialized)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in src_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(src_dir))


def build_release_zip(base: Path, output_root: Path, zip_path: Path) -> None:
    version_file = base / "version.txt"

    with tempfile.TemporaryDirectory(prefix="zhtw_release_", dir=base) as staging_dir:
        package_root = Path(staging_dir)
        package_local_files = package_root / "local-files"
        shutil.copytree(output_root, package_local_files)

        nested_version = package_local_files / "version.txt"
        if nested_version.exists():
            nested_version.unlink()

        if version_file.exists():
            shutil.copy2(version_file, package_root / "version.txt")

        zip_dir(package_root, zip_path)


def has_kana(text: str) -> bool:
    return bool(text and KANA_RE.search(text))


def convert_text(text: str, cc: OpenCC, rules: ReplacementRules) -> str:
    if not text:
        return text

    parts = text.splitlines(keepends=True)
    if not parts:
        return rules.normalize_only(text)

    converted_parts: list[str] = []
    for part in parts:
        body = part.rstrip("\r\n")
        ending = part[len(body):]
        if has_kana(body):
            converted_parts.append(rules.normalize_only(body) + ending)
        else:
            converted_parts.append(rules.convert(body, cc) + ending)

    return "".join(converted_parts)


def convert_ruby_text(text: str, cc: OpenCC, rules: ReplacementRules) -> str:
    def repl(match: re.Match[str]) -> str:
        japanese = match.group(1)
        translated = match.group(2)
        return f"<r\\={japanese}>{convert_text(translated, cc, rules)}</r>"

    return RUBY_RE.sub(repl, text)


def convert_json_value(value: Any, cc: OpenCC, rules: ReplacementRules) -> Any:
    if isinstance(value, dict):
        return {key: convert_json_value(item, cc, rules) for key, item in value.items()}
    if isinstance(value, list):
        return [convert_json_value(item, cc, rules) for item in value]
    if isinstance(value, str):
        return convert_text(value, cc, rules)
    return value


def convert_resource_field(value: str, cc: OpenCC, rules: ReplacementRules) -> str:
    if RUBY_RE.search(value):
        return convert_ruby_text(value, cc, rules)
    return convert_text(value, cc, rules)


def add_resource_replacement(replacements: list[Replacement], attr: str, original: str | None, updated: str | None) -> None:
    if not original or updated is None or original == updated:
        return
    replacements.append(Replacement(old=f"{attr}={original}", new=f"{attr}={updated}", length=len(original)))


def apply_resource_replacements(text: str, replacements: list[Replacement]) -> str:
    ordered = sorted(replacements, key=lambda item: item.length, reverse=True)

    for replacement in ordered:
        position = text.find(replacement.old)
        if position == -1:
            continue

        end_position = position + len(replacement.old)
        if end_position < len(text) and text[end_position] not in BOUNDARY_CHARS:
            found = False
            search_start = position + 1
            while True:
                position = text.find(replacement.old, search_start)
                if position == -1:
                    break
                end_position = position + len(replacement.old)
                if end_position >= len(text) or text[end_position] in BOUNDARY_CHARS:
                    found = True
                    break
                search_start = position + 1
            if not found:
                continue

        text = text[:position] + replacement.new + text[end_position:]

    return text


def convert_resource_text(text: str, cc: OpenCC, rules: ReplacementRules) -> str:
    parsed = parse_messages(text)
    replacements: list[Replacement] = []

    for entry in parsed:
        tag = entry.get("__tag__")
        if tag in {"message", "narration"}:
            add_resource_replacement(replacements, "text", entry.get("text"), convert_resource_field(entry.get("text", ""), cc, rules))
            add_resource_replacement(replacements, "name", entry.get("name"), convert_text(entry.get("name", ""), cc, rules))
        elif tag == "title":
            add_resource_replacement(replacements, "title", entry.get("title"), convert_text(entry.get("title", ""), cc, rules))
        elif tag == "choicegroup":
            choices = entry.get("choices")
            if isinstance(choices, dict):
                choices = [choices]
            if isinstance(choices, list):
                for choice in choices:
                    add_resource_replacement(replacements, "text", choice.get("text"), convert_text(choice.get("text", ""), cc, rules))

    return apply_resource_replacements(text, replacements)


def validate_kana_lines(source_text: str, output_text: str, path: str, rules: ReplacementRules, issues: list[ValidationIssue]) -> None:
    source_lines = source_text.splitlines()
    output_lines = output_text.splitlines()

    if len(source_lines) != len(output_lines):
        if any(has_kana(line) for line in source_lines):
            issues.append(ValidationIssue("kana_line_count", path, "line count changed for kana-bearing text"))
        return

    for index, (source_line, output_line) in enumerate(zip(source_lines, output_lines), start=1):
        if not has_kana(source_line):
            continue
        expected = rules.normalize_only(source_line)
        if output_line != expected:
            issues.append(
                ValidationIssue(
                    "kana_preservation",
                    path,
                    f"line {index}: expected {expected!r}, got {output_line!r}",
                )
            )


def validate_json_value(source: Any, output: Any, path: str, rules: ReplacementRules, issues: list[ValidationIssue]) -> None:
    if isinstance(source, dict) and isinstance(output, dict):
        for key in source.keys() & output.keys():
            validate_json_value(source[key], output[key], f"{path}.{key}", rules, issues)
        return
    if isinstance(source, list) and isinstance(output, list):
        for index, (source_item, output_item) in enumerate(zip(source, output), start=1):
            validate_json_value(source_item, output_item, f"{path}[{index}]", rules, issues)
        return
    if isinstance(source, str) and isinstance(output, str):
        validate_kana_lines(source, output, path, rules, issues)


def validate_resource_file(source_path: Path, output_path: Path, rules: ReplacementRules, issues: list[ValidationIssue]) -> None:
    source_text = read_text(source_path)
    output_text = read_text(output_path)

    source_ruby = RUBY_RE.findall(source_text)
    output_ruby = RUBY_RE.findall(output_text)
    if len(source_ruby) != len(output_ruby):
        issues.append(
            ValidationIssue(
                "resource_ruby_count",
                output_path.relative_to(output_path.parents[1]).as_posix(),
                f"ruby block count changed from {len(source_ruby)} to {len(output_ruby)}",
            )
        )
    else:
        for index, ((source_jp, _), (output_jp, _)) in enumerate(zip(source_ruby, output_ruby), start=1):
            guard_count = output_jp.count(RUBY_GUARD)
            guard_position_invalid = (
                guard_count > 1
                or (guard_count == 1 and (output_jp.startswith(RUBY_GUARD) or output_jp.endswith(RUBY_GUARD)))
            )
            if guard_position_invalid or source_jp != output_jp.replace(RUBY_GUARD, ""):
                issues.append(
                    ValidationIssue(
                        "resource_japanese_changed",
                        output_path.relative_to(output_path.parents[1]).as_posix(),
                        f"ruby block {index} japanese text or guard position changed unexpectedly",
                    )
                )

    source_entries = parse_messages(source_text)
    output_entries = parse_messages(output_text)
    for index, (source_entry, output_entry) in enumerate(zip(source_entries, output_entries), start=1):
        entry_path = f"{output_path.relative_to(output_path.parents[1]).as_posix()}#{index}"

        for attr in ("name", "title"):
            source_value = source_entry.get(attr)
            output_value = output_entry.get(attr)
            if isinstance(source_value, str) and isinstance(output_value, str):
                validate_kana_lines(source_value, output_value, f"{entry_path}.{attr}", rules, issues)

        source_text_value = source_entry.get("text")
        output_text_value = output_entry.get("text")
        if (
            isinstance(source_text_value, str)
            and isinstance(output_text_value, str)
            and not RUBY_RE.search(source_text_value)
        ):
            validate_kana_lines(source_text_value, output_text_value, f"{entry_path}.text", rules, issues)

        if source_entry.get("__tag__") == "choicegroup":
            source_choices = source_entry.get("choices")
            output_choices = output_entry.get("choices")
            if isinstance(source_choices, dict):
                source_choices = [source_choices]
            if isinstance(output_choices, dict):
                output_choices = [output_choices]
            if isinstance(source_choices, list) and isinstance(output_choices, list):
                for choice_index, (source_choice, output_choice) in enumerate(zip(source_choices, output_choices), start=1):
                    source_choice_text = source_choice.get("text")
                    output_choice_text = output_choice.get("text")
                    if isinstance(source_choice_text, str) and isinstance(output_choice_text, str):
                        validate_kana_lines(source_choice_text, output_choice_text, f"{entry_path}.choice[{choice_index}]", rules, issues)


def iter_string_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_string_values(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from iter_string_values(item)
        return
    if isinstance(value, str):
        yield value


def collect_ruby_source_texts(resource_dir: Path) -> set[str]:
    """Collect text that the ADV ruby renderer can send to a TMP component."""
    ruby_texts: set[str] = set()
    if not resource_dir.exists():
        return ruby_texts

    for resource_path in resource_dir.glob("adv*.txt"):
        for entry in parse_messages(read_text(resource_path)):
            value = entry.get("text")
            if not isinstance(value, str):
                continue

            japanese_parts = [japanese for japanese, _ in RUBY_RE.findall(value) if japanese]
            if not japanese_parts:
                continue

            # TextMeshProUGUIRuby appends every ruby group and assigns the
            # composed string to its RubyTMP in one operation.
            ruby_texts.add("".join(japanese_parts))

    return ruby_texts


def load_translated_generic_keys(generic_dir: Path) -> set[str]:
    keys: set[str] = set()
    if not generic_dir.exists():
        return keys

    for json_path in sorted(generic_dir.rglob("*.json")):
        if json_path.name == RUBY_GUARD_FILE:
            continue
        data = load_json(json_path)
        if isinstance(data, dict):
            keys.update(key for key, value in data.items() if value != key)

    return keys


def find_ruby_generic_mappings(resource_dir: Path, generic_dir: Path) -> list[tuple[Path, str, Any]]:
    ruby_texts = collect_ruby_source_texts(resource_dir)
    if not ruby_texts or not generic_dir.exists():
        return []

    mappings: list[tuple[Path, str, Any]] = []
    for json_path in sorted(generic_dir.rglob("*.json")):
        data = load_json(json_path)
        if not isinstance(data, dict):
            continue

        for key in sorted(ruby_texts.intersection(data.keys())):
            mappings.append((json_path, key, data[key]))

    return mappings


def guard_ruby_field(value: str, generic_keys: set[str]) -> tuple[str, set[str], set[str], set[str]]:
    matches = RUBY_RE.findall(value)
    if not matches:
        return value, set(), set(), set()

    japanese_parts = [japanese.replace(RUBY_GUARD, "") for japanese, _ in matches]
    joined = "".join(japanese_parts)
    collisions = {joined} if joined in generic_keys else set()
    guard_part_index = next((index for index, part in enumerate(japanese_parts) if len(part) >= 2), None)

    guarded_parts = list(japanese_parts)
    skipped_collisions: set[str] = set()
    if collisions and guard_part_index is not None:
        part = guarded_parts[guard_part_index]
        guarded_parts[guard_part_index] = f"{part[0]}{RUBY_GUARD}{part[1:]}"
    elif collisions:
        skipped_collisions = collisions
        collisions = set()

    guarded_index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal guarded_index
        guarded_japanese = guarded_parts[guarded_index]
        guarded_index += 1
        return f"<r\\={guarded_japanese}>{match.group(2)}</r>"

    guarded_value = RUBY_RE.sub(repl, value)
    runtime_texts = {"".join(guarded_parts)} if collisions else set()
    return guarded_value, runtime_texts, collisions, skipped_collisions


def protect_ruby_text_from_generic_translation(resource_dir: Path, generic_dir: Path) -> tuple[int, int, int, int]:
    """Mark only colliding ADV ruby text without changing normal UI mappings.

    The zero-width guard remains part of the Japanese ruby string through any
    nested TMP hooks. A generated identity map makes exact lookup terminate at
    every hook while leaving the original, unguarded generic key available for
    ordinary UI text.
    """
    generic_keys = load_translated_generic_keys(generic_dir)
    guard_mappings: dict[str, str] = {}
    collision_keys: set[str] = set()
    skipped_collision_keys: set[str] = set()
    protected_messages = 0

    if resource_dir.exists():
        for resource_path in sorted(resource_dir.glob("adv*.txt")):
            resource_text = read_text(resource_path)
            replacements: list[Replacement] = []

            for entry in parse_messages(resource_text):
                if entry.get("__tag__") not in {"message", "narration"}:
                    continue
                value = entry.get("text")
                if not isinstance(value, str):
                    continue

                guarded_value, runtime_texts, collisions, skipped = guard_ruby_field(value, generic_keys)
                if guarded_value != value:
                    add_resource_replacement(replacements, "text", value, guarded_value)
                if collisions:
                    guard_mappings.update({text: text for text in runtime_texts})
                    collision_keys.update(collisions)
                    protected_messages += 1
                skipped_collision_keys.update(skipped)

            if replacements:
                guarded_resource_text = apply_resource_replacements(resource_text, replacements)
                if guarded_resource_text != resource_text:
                    write_text(resource_path, guarded_resource_text)

    save_ruby_guard_json(generic_dir / RUBY_GUARD_FILE, dict(sorted(guard_mappings.items())))
    return protected_messages, len(collision_keys), len(guard_mappings), len(skipped_collision_keys)


def scan_forbidden_tokens(root: Path, tokens: list[str]) -> dict[str, dict[str, int]]:
    hits: dict[str, dict[str, int]] = {}
    if not tokens:
        return hits

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".txt"}:
            continue

        token_hits: dict[str, int] = {}
        if path.suffix == ".json":
            for string_value in iter_string_values(load_json(path)):
                for token in tokens:
                    count = string_value.count(token)
                    if count:
                        token_hits[token] = token_hits.get(token, 0) + count
        else:
            text = read_text(path)
            token_hits = {token: text.count(token) for token in tokens if token in text}

        if token_hits:
            hits[path.relative_to(root).as_posix()] = token_hits

    return hits

def build_validation_report(base: Path, rules: ReplacementRules, source_root: Path, output_root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    source_localization = source_root / "localization.json"
    output_localization = output_root / "localization.json"
    if source_localization.exists() and output_localization.exists():
        validate_json_value(
            load_json(source_localization),
            load_json(output_localization),
            "localization.json",
            rules,
            issues,
        )

    for relative_root in ("genericTrans", "masterTrans"):
        source_dir = source_root / relative_root
        output_dir = output_root / relative_root
        if not source_dir.exists() or not output_dir.exists():
            continue
        for source_path in source_dir.rglob("*.json"):
            output_path = output_dir / source_path.relative_to(source_dir)
            if not output_path.exists():
                issues.append(
                    ValidationIssue(
                        "missing_output",
                        output_path.relative_to(output_root).as_posix(),
                        "output file missing",
                    )
                )
                continue
            validate_json_value(
                load_json(source_path),
                load_json(output_path),
                output_path.relative_to(output_root).as_posix(),
                rules,
                issues,
            )

    source_resource = source_root / "resource"
    output_resource = output_root / "resource"
    if source_resource.exists() and output_resource.exists():
        for source_path in source_resource.glob("adv*.txt"):
            output_path = output_resource / source_path.name
            if not output_path.exists():
                issues.append(ValidationIssue("missing_output", f"resource/{source_path.name}", "output file missing"))
                continue
            validate_resource_file(source_path, output_path, rules, issues)

    ruby_generic_mappings = find_ruby_generic_mappings(output_resource, output_root / "genericTrans")
    mapped_ruby_texts = {key for _, key, _ in ruby_generic_mappings}
    for json_path, key, value in ruby_generic_mappings:
        if value != key:
            target = warnings if RUBY_GUARD not in key and len(key) < 2 else issues
            target.append(
                ValidationIssue(
                    "ruby_generic_retranslation",
                    json_path.relative_to(output_root).as_posix(),
                    f"ruby source {key!r} maps to {value!r} instead of itself",
                )
            )

    for ruby_text in collect_ruby_source_texts(output_resource):
        if RUBY_GUARD in ruby_text and ruby_text not in mapped_ruby_texts:
            issues.append(
                ValidationIssue(
                    "missing_ruby_guard_mapping",
                    "genericTrans/" + RUBY_GUARD_FILE,
                    f"guarded ruby source {ruby_text!r} has no identity mapping",
                )
            )

    forbidden_hits = scan_forbidden_tokens(output_root, rules.forbidden_tokens)
    for file_path, token_hits in forbidden_hits.items():
        for token, count in token_hits.items():
            issues.append(ValidationIssue("forbidden_token", file_path, f"{token} x{count}"))

    report = {
        "issue_count": len(issues),
        "warning_count": len(warnings),
        "forbidden_tokens": rules.forbidden_tokens,
        "issues": [asdict(issue) for issue in issues[:200]],
        "warnings": [asdict(warning) for warning in warnings[:200]],
        "truncated": len(issues) > 200,
    }
    save_json(base / VALIDATION_REPORT_FILE, report)
    return issues


def main() -> int:
    base = Path(".").resolve()
    local_files = base / "local-files"
    if not local_files.exists():
        raise FileNotFoundError("local-files not found. Please run merge.py first.")

    output_root = base / "local-files-zhTW"
    if output_root.exists():
        shutil.rmtree(output_root)
    shutil.copytree(local_files, output_root)

    cc = OpenCC("s2twp")
    rules = ReplacementRules(base)

    print("Converting resource/*.txt with parser-aware mode...", flush=True)
    resource_dir = output_root / "resource"
    if resource_dir.exists():
        for text_file in resource_dir.glob("adv*.txt"):
            converted = convert_resource_text(read_text(text_file), cc, rules)
            write_text(text_file, converted)

    print("Converting localization.json...", flush=True)
    localization_file = output_root / "localization.json"
    if localization_file.exists():
        save_json(localization_file, convert_json_value(load_json(localization_file), cc, rules))

    print("Converting genericTrans/*.json...", flush=True)
    generic_dir = output_root / "genericTrans"
    if generic_dir.exists():
        for json_file in generic_dir.rglob("*.json"):
            save_json(json_file, convert_json_value(load_json(json_file), cc, rules))

    protected_messages, protected_keys, guard_mappings, skipped_keys = protect_ruby_text_from_generic_translation(
        resource_dir,
        generic_dir,
    )
    print(
        f"Protected {protected_keys} generic collision(s) in {protected_messages} ADV message(s) "
        f"with {guard_mappings} ruby guard mapping(s).",
        flush=True,
    )
    if skipped_keys:
        print(
            f"Warning: skipped {skipped_keys} single-character ruby collision(s) with no safe internal guard position.",
            flush=True,
        )

    print("Converting masterTrans/*.json...", flush=True)
    master_dir = output_root / "masterTrans"
    if master_dir.exists():
        for json_file in master_dir.rglob("*.json"):
            save_json(json_file, convert_json_value(load_json(json_file), cc, rules))

    version_file = base / "version.txt"
    if version_file.exists():
        shutil.copy2(version_file, output_root / "version.txt")

    print("Validating zhTW output...", flush=True)
    issues = build_validation_report(base, rules, local_files, output_root)
    if issues:
        print(f"Validation failed with {len(issues)} issue(s). See {VALIDATION_REPORT_FILE} for details.", flush=True)
        return 1

    print("Packing GakumasTranslationData_zhTW.zip...", flush=True)
    build_release_zip(base, output_root, base / "GakumasTranslationData_zhTW.zip")
    print("Built GakumasTranslationData_zhTW.zip", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




