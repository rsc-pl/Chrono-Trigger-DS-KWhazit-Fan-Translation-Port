#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import ctds

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE_DIR = Path(__file__).resolve().parent / "tables"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dump Chrono Trigger DS TEXT .msg resources directly from a clean ROM.")
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--reversible", action="store_true", help="Emit raw {HEX} for alternate binary encodings so decode->encode is byte-exact.")
    p.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLE_DIR)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    rom = args.rom.read_bytes()
    files = ctds.text_msg_entries(rom)
    if len(files) != 75:
        raise SystemExit(f"Expected 75 TEXT .msg resources, found {len(files)}")
    tables = {kind: ctds.load_table(kind, args.tables_dir) for kind in ("big", "small")}
    written = 0
    for nitro_path, entry in sorted(files.items()):
        parts = nitro_path.split("/")
        kind = parts[1].lower()
        name = parts[-1]
        data = ctds.extract_nitro_file(rom, entry)
        layout = ctds.parse_msg(data)
        entries = ctds.decode_msg_entries(data, tables[kind], reversible=args.reversible)
        rendered = ctds.serialize_msg_txt(name, entries, layout.item_count)
        out = args.output_dir / kind.upper() / f"{name}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(rendered)
        written += 1
    print(f"Dumped {written} TEXT .msg resources to {args.output_dir}")
    print(f"Mode: {'reversible' if args.reversible else 'Chrono Translator compatible'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
