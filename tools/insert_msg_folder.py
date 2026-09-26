#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_DS = ROOT / "tools" / "platform_ds"
sys.path.insert(0, str(PLATFORM_DS))

from ctds import patch_rom_bytes, verify_rom_replacements  # noqa: E402


def default_output_path(rom: Path) -> Path:
    return rom.with_name(f"{rom.stem}_msg_patched{rom.suffix}")


def collect_replacements(msg_dir: Path) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    for path in sorted(msg_dir.rglob("*.msg")):
        rel = path.relative_to(msg_dir)
        parts = rel.parts
        kind = None
        name = path.name
        if len(parts) == 2 and parts[0].lower() in {"big", "small"}:
            kind = parts[0].lower()
        elif len(parts) == 3 and parts[0].lower() == "msg" and parts[1].lower() in {"big", "small"}:
            kind = parts[1].lower()
        if kind is None:
            continue
        nitro = f"msg/{kind}/{name}"
        if nitro in replacements:
            raise SystemExit(f"Duplicate replacement for {nitro}")
        replacements[nitro] = path.read_bytes()
    return replacements


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insert BIG/SMALL binary .msg resources into a Nintendo DS ROM.")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--msg-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-append", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.rom.is_file():
        raise SystemExit(f"Input ROM not found: {args.rom}")
    if not args.msg_dir.is_dir():
        raise SystemExit(f"MSG folder not found: {args.msg_dir}")
    replacements = collect_replacements(args.msg_dir)
    if not replacements:
        raise SystemExit(f"No BIG/SMALL .msg files found under {args.msg_dir}")

    output = args.output or default_output_path(args.rom)
    patched, log = patch_rom_bytes(args.rom.read_bytes(), replacements, force_append=args.force_append)
    verify_rom_replacements(patched, replacements)
    for line in log:
        print(line)
    if args.dry_run:
        print("Dry run only; output ROM not written.")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    print(f"Wrote {output} ({len(patched)} bytes)")
    print(f"Verified {len(replacements)} replacement files in output ROM.")


if __name__ == "__main__":
    main()
