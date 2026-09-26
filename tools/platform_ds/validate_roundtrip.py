#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ctds import (
    build_msg_from_entries,
    decode_msg_entries,
    extract_nitro_file,
    load_table,
    parse_msg,
    parse_msg_txt_text,
    serialize_msg_txt,
    text_msg_entries,
)

HERE = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify reversible decode->encode round-trip for every Chrono Trigger DS TEXT .msg resource.")
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--tables-dir", type=Path, default=HERE / "tables")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    rom = args.rom.read_bytes()
    resources = text_msg_entries(rom)
    if len(resources) != 75:
        raise SystemExit(f"FAIL: expected 75 TEXT .msg resources, found {len(resources)}")
    tables = {kind: load_table(kind, args.tables_dir) for kind in ("big", "small")}
    failures: list[str] = []
    for path, entry in sorted(resources.items()):
        original = extract_nitro_file(rom, entry)
        kind = "big" if path.lower().startswith("msg/big/") else "small"
        layout = parse_msg(original)
        entries = decode_msg_entries(original, tables[kind], reversible=True)
        dump_bytes = serialize_msg_txt(Path(path).name, entries, layout.item_count)
        _name, parsed_entries = parse_msg_txt_text(dump_bytes.decode("utf-8-sig"), path)
        rebuilt = build_msg_from_entries(parsed_entries, layout.item_count, tables[kind])
        if rebuilt != original:
            failures.append(path)
    if failures:
        print(f"ROUNDTRIP: FAIL ({len(failures)}/75 mismatches)")
        for path in failures:
            print(f"- {path}")
        raise SystemExit(1)
    print("ROUNDTRIP: PASS (75/75 TEXT .msg resources byte-identical)")


if __name__ == "__main__":
    main()
