#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from ctds import (
    canonical_text,
    decode_msg_entries,
    extract_nitro_file,
    load_table,
    parse_msg_txt,
    source_rel_to_nitro,
    text_msg_entries,
)

HERE = Path(__file__).resolve().parent
CLEAR_TOKENS = ("{PRESS_CLEAR}", "{CLEAR}")
SEL_RE = re.compile(r"\{SEL\d+\}")


def selection_positions(text: str) -> list[tuple[str, int]]:
    s = canonical_text(text).replace(r"\n", "\n")
    out: list[tuple[str, int]] = []
    for match in SEL_RE.finditer(s):
        before = s[: match.start()]
        last = -1
        token = ""
        for clear in CLEAR_TOKENS:
            index = before.rfind(clear)
            if index > last:
                last = index
                token = clear
        segment = before
        if last != -1:
            segment = before[last + len(token) :]
            if segment.startswith("\n"):
                segment = segment[1:]
        out.append((match.group(), segment.count("\n")))
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check {SEL} line positions against the clean US ROM runtime layout.")
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--txt-dir", type=Path, required=True)
    p.add_argument("--tables-dir", type=Path, default=HERE / "tables")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rom = args.rom.read_bytes()
    nitro = {path.lower(): entry for path, entry in text_msg_entries(rom).items()}
    tables = {kind: load_table(kind, args.tables_dir) for kind in ("big", "small")}
    mismatches: list[tuple[str, int, list[tuple[str, int]], list[tuple[str, int]]]] = []
    checked = 0

    for source_path in sorted(args.txt_dir.rglob("*.msg.txt")):
        nitro_path, kind = source_rel_to_nitro(source_path, args.txt_dir)
        entry = nitro.get(nitro_path.lower())
        if entry is None:
            raise SystemExit(f"Source has no matching clean-ROM resource: {source_path}")
        _name, source = parse_msg_txt(source_path)
        clean = decode_msg_entries(extract_nitro_file(rom, entry), tables[kind], reversible=False)
        for (item, lang), source_text in source.items():
            if lang != "EN":
                continue
            clean_text = clean[(item, lang)]
            clean_pos = selection_positions(clean_text)
            source_pos = selection_positions(source_text)
            if clean_pos or source_pos:
                checked += 1
                if clean_pos != source_pos:
                    mismatches.append((str(source_path.relative_to(args.txt_dir)), item, clean_pos, source_pos))

    if mismatches:
        print(f"CHOICE_LAYOUT: FAIL ({len(mismatches)} mismatch(es), {checked} choice row(s) checked)")
        for file_name, item, clean_pos, source_pos in mismatches:
            print(f"- {file_name}#{item}: clean={clean_pos!r} source={source_pos!r}")
        raise SystemExit(1)
    print(f"CHOICE_LAYOUT: PASS (0 mismatches, {checked} choice row(s) checked)")


if __name__ == "__main__":
    main()
