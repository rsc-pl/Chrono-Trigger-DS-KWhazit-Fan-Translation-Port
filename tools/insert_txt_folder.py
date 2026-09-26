#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_DS = ROOT / "tools" / "platform_ds"
sys.path.insert(0, str(PLATFORM_DS))

from ctds import (  # noqa: E402
    extract_nitro_file,
    load_table,
    parse_msg_txt,
    patch_msg_with_source,
    patch_rom_bytes,
    sha256_file,
    source_rel_to_nitro,
    text_msg_entries,
    verify_rom_replacements,
)

EXPECTED_CLEAN_SHA256 = "46df8e729e5f0d67ad382ff208d803efd88154a16b39e820d318bb1a1e7549d5"
TABLES_DIR = PLATFORM_DS / "tables"


def default_output_path(rom: Path) -> Path:
    return rom.with_name(f"{rom.stem}_txt_patched{rom.suffix}")


def build_replacements(rom_data: bytes, txt_dir: Path, keep_msg_dir: Path | None) -> tuple[dict[str, bytes], int, int]:
    nitro = {path.lower(): entry for path, entry in text_msg_entries(rom_data).items()}
    tables = {kind: load_table(kind, TABLES_DIR) for kind in ("big", "small")}
    replacements: dict[str, bytes] = {}
    changed_slots = 0
    copied_source_slots = 0

    source_files = sorted(txt_dir.rglob("*.msg.txt"))
    if not source_files:
        raise SystemExit(f"No .msg.txt files found under {txt_dir}")

    for source_path in source_files:
        nitro_path, kind = source_rel_to_nitro(source_path, txt_dir)
        entry = nitro.get(nitro_path.lower())
        if entry is None:
            raise SystemExit(f"Source file has no matching TEXT resource in the clean ROM: {source_path} -> {nitro_path}")

        header_name, source_entries = parse_msg_txt(source_path)
        expected_header = Path(nitro_path).name
        if header_name.lower() != expected_header.lower():
            raise SystemExit(
                f"Header mismatch in {source_path}: [@{header_name}] does not match {expected_header}"
            )

        original = extract_nitro_file(rom_data, entry)
        generated, changed, copied = patch_msg_with_source(original, source_entries, tables[kind], language="EN")
        replacements[nitro_path] = generated
        changed_slots += changed
        copied_source_slots += copied

        if keep_msg_dir is not None:
            rel = source_path.relative_to(txt_dir).with_suffix("")
            out_path = keep_msg_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(generated)

    return replacements, changed_slots, copied_source_slots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Chrono Trigger DS ROM directly from public BIG/SMALL .msg.txt sources. "
            "Only Python's standard library and the clean US ROM are required."
        )
    )
    parser.add_argument("--rom", type=Path, required=True, help="Clean US Chrono Trigger DS .nds ROM.")
    parser.add_argument("--txt-dir", type=Path, required=True, help="Folder containing BIG/*.msg.txt and/or SMALL/*.msg.txt.")
    parser.add_argument("--output", type=Path, help="Patched output .nds. Defaults beside the input ROM.")
    parser.add_argument("--keep-msg-dir", type=Path, help="Optional output folder for generated binary .msg resources.")
    parser.add_argument("--dry-run", action="store_true", help="Build and verify in memory without writing the ROM.")
    parser.add_argument("--force-append", action="store_true", help="Append every replacement instead of using in-place writes where possible.")
    parser.add_argument(
        "--allow-unknown-rom",
        action="store_true",
        help="Development escape hatch: skip the known clean-ROM SHA-256 gate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.rom.is_file():
        raise SystemExit(f"Input ROM not found: {args.rom}")
    if not args.txt_dir.is_dir():
        raise SystemExit(f"TXT folder not found: {args.txt_dir}")

    clean_hash = sha256_file(args.rom)
    if clean_hash != EXPECTED_CLEAN_SHA256 and not args.allow_unknown_rom:
        raise SystemExit(
            "Wrong clean ROM.\n"
            f"Expected SHA-256: {EXPECTED_CLEAN_SHA256}\n"
            f"Actual SHA-256:   {clean_hash}"
        )

    output = args.output or default_output_path(args.rom)
    if args.keep_msg_dir is not None:
        args.keep_msg_dir.mkdir(parents=True, exist_ok=True)

    rom_data = args.rom.read_bytes()
    text_resources = text_msg_entries(rom_data)
    if len(text_resources) != 75:
        raise SystemExit(f"Expected 75 TEXT .msg resources in the supported ROM; found {len(text_resources)}")

    replacements, changed_slots, copied_source_slots = build_replacements(rom_data, args.txt_dir, args.keep_msg_dir)
    patched, log = patch_rom_bytes(rom_data, replacements, force_append=args.force_append)
    verify_rom_replacements(patched, replacements)

    print(f"Input ROM: {args.rom}")
    print(f"TXT source: {args.txt_dir}")
    print(f"TEXT resources in ROM: {len(text_resources)}")
    print(f"Source resource files: {len(replacements)}")
    print(f"Changed EN slots vs clean ROM: {changed_slots}")
    print(f"Unchanged source EN slots copied from clean ROM: {copied_source_slots}")
    print(f"Patched NitroFS resources verified: {len(replacements)}")
    for line in log:
        print(line)

    if args.dry_run:
        print("Dry run only; output ROM not written.")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    print(f"Wrote {output} ({len(patched)} bytes)")
    print(f"Output SHA-256: {sha256_file(output)}")


if __name__ == "__main__":
    main()
