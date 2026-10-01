#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_DS = ROOT / "tools" / "platform_ds"
import sys
sys.path.insert(0, str(PLATFORM_DS))

from ctds import (  # noqa: E402
    build_msg_from_entries,
    decode_msg_entries,
    extract_nitro_file,
    load_table,
    parse_msg,
    parse_msg_txt,
    parse_msg_txt_text,
    parse_filenames,
    patch_msg_with_source,
    patch_rom_bytes,
    serialize_msg_txt,
    sha256_bytes,
    sha256_file,
    source_rel_to_nitro,
    text_msg_entries,
    verify_rom_replacements,
)
from validate_choice_layout import selection_positions  # noqa: E402

CLEAN_SHA256 = "46df8e729e5f0d67ad382ff208d803efd88154a16b39e820d318bb1a1e7549d5"
VARIANTS = {
    "original_kajar_transfer": "7f6ec32910671aae52b979ecd04e99ca1c75c1653658c7bed38ea1873d10ee91",
    "polished_faithful": "c2aeb669e5240761602054bf2c76c3a0afadbf2d7b368f20e7e06dae01515dda",
}
TABLES_DIR = PLATFORM_DS / "tables"


def legacy_key(name: str) -> str | None:
    parts = Path(name).parts
    for i, part in enumerate(parts):
        if part.upper() in {"BIG", "SMALL"} and name.lower().endswith(".msg.txt"):
            return "/".join(parts[i:])
    return None


def compare_legacy_dump(rom: bytes, resources, tables, archive: Path) -> tuple[int, int]:
    with zipfile.ZipFile(archive) as zf:
        legacy = {}
        for name in zf.namelist():
            key = legacy_key(name)
            if key is not None:
                legacy[key] = zf.read(name)
    generated = {}
    for nitro_path, entry in resources.items():
        kind = "big" if nitro_path.lower().startswith("msg/big/") else "small"
        data = extract_nitro_file(rom, entry)
        layout = parse_msg(data)
        entries = decode_msg_entries(data, tables[kind], reversible=False)
        rel = ("BIG" if kind == "big" else "SMALL") + "/" + Path(nitro_path).name + ".txt"
        generated[rel] = serialize_msg_txt(Path(nitro_path).name, entries, layout.item_count)
    missing = set(legacy) ^ set(generated)
    mismatches = [key for key in sorted(set(legacy) & set(generated)) if legacy[key] != generated[key]]
    if missing or mismatches:
        raise RuntimeError(
            f"legacy dump mismatch: key_delta={len(missing)} byte_mismatches={len(mismatches)}"
        )
    return len(generated), 0


def validate_roundtrip(rom: bytes, resources, tables) -> None:
    failures = []
    for path, entry in sorted(resources.items()):
        original = extract_nitro_file(rom, entry)
        kind = "big" if path.lower().startswith("msg/big/") else "small"
        layout = parse_msg(original)
        decoded = decode_msg_entries(original, tables[kind], reversible=True)
        dump_bytes = serialize_msg_txt(Path(path).name, decoded, layout.item_count)
        _name, parsed = parse_msg_txt_text(dump_bytes.decode("utf-8-sig"), path)
        rebuilt = build_msg_from_entries(parsed, layout.item_count, tables[kind])
        if rebuilt != original:
            failures.append(path)
    if failures:
        raise RuntimeError(f"round-trip mismatches: {len(failures)}: {', '.join(failures[:8])}")


def validate_choice_layout(rom: bytes, resources, tables, source_root: Path) -> int:
    by_lower = {p.lower(): e for p, e in resources.items()}
    checked = 0
    mismatches = []
    for source_path in sorted(source_root.rglob("*.msg.txt")):
        nitro_path, kind = source_rel_to_nitro(source_path, source_root)
        entry = by_lower[nitro_path.lower()]
        clean = decode_msg_entries(extract_nitro_file(rom, entry), tables[kind], reversible=False)
        _name, source = parse_msg_txt(source_path)
        for key, text in source.items():
            item, lang = key
            if lang != "EN":
                continue
            clean_pos = selection_positions(clean[key])
            source_pos = selection_positions(text)
            if clean_pos or source_pos:
                checked += 1
                if clean_pos != source_pos:
                    mismatches.append((source_path, item, clean_pos, source_pos))
    if mismatches:
        first = mismatches[0]
        raise RuntimeError(
            f"choice layout mismatches: {len(mismatches)}; first={first[0]}#{first[1]} clean={first[2]} source={first[3]}"
        )
    return checked


def build_variant(rom: bytes, resources, tables, source_root: Path) -> tuple[bytes, int, int, int]:
    by_lower = {p.lower(): e for p, e in resources.items()}
    replacements = {}
    changed = 0
    copied = 0
    for source_path in sorted(source_root.rglob("*.msg.txt")):
        nitro_path, kind = source_rel_to_nitro(source_path, source_root)
        entry = by_lower.get(nitro_path.lower())
        if entry is None:
            raise RuntimeError(f"source has no ROM resource: {source_path} -> {nitro_path}")
        header, source = parse_msg_txt(source_path)
        if header.lower() != Path(nitro_path).name.lower():
            raise RuntimeError(f"header mismatch: {source_path}: {header} != {Path(nitro_path).name}")
        generated, n_changed, n_copied = patch_msg_with_source(
            extract_nitro_file(rom, entry), source, tables[kind], language="EN"
        )
        replacements[nitro_path] = generated
        changed += n_changed
        copied += n_copied
    patched, _log = patch_rom_bytes(rom, replacements)
    verify_rom_replacements(patched, replacements)
    return patched, len(replacements), changed, copied


def validate_rom_structure(clean_rom: bytes, patched_rom: bytes) -> tuple[int, int]:
    if len(patched_rom) != len(clean_rom):
        raise RuntimeError(
            f"patched ROM size drift: clean={len(clean_rom)} patched={len(patched_rom)}"
        )
    if patched_rom[:0x200] != clean_rom[:0x200]:
        raise RuntimeError("patched ROM header changed; game/AP-fix identification must remain stable")
    declared_capacity = (128 * 1024) << patched_rom[0x14]
    if len(patched_rom) > declared_capacity:
        raise RuntimeError(
            f"patched ROM exceeds declared cartridge capacity: {len(patched_rom)} > {declared_capacity}"
        )
    files = parse_filenames(patched_rom)
    outside = [entry for entry in files.values() if entry.start >= declared_capacity or entry.end > declared_capacity]
    if outside:
        first = outside[0]
        raise RuntimeError(
            f"NitroFS file(s) outside declared cartridge capacity: {len(outside)}; "
            f"first={first.path} {first.start:#x}-{first.end:#x}"
        )
    max_end = max(entry.end for entry in files.values())
    return declared_capacity, max_end


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run public Chrono Trigger DS source/build validation gates.")
    p.add_argument("--rom", type=Path, required=True, help="Clean US Chrono Trigger DS ROM.")
    p.add_argument(
        "--legacy-dump-zip",
        type=Path,
        help="Optional migration-only gate: compare the native dumper byte-for-byte with retained ds_us_dump.zip.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if sha256_file(args.rom) != CLEAN_SHA256:
        raise SystemExit(f"CLEAN_ROM: FAIL (expected {CLEAN_SHA256}, got {sha256_file(args.rom)})")
    print(f"CLEAN_ROM: PASS ({CLEAN_SHA256})")

    rom = args.rom.read_bytes()
    resources = text_msg_entries(rom)
    if len(resources) != 75:
        raise SystemExit(f"TEXT_RESOURCE_COUNT: FAIL ({len(resources)} != 75)")
    print("TEXT_RESOURCE_COUNT: PASS (75)")

    tables = {kind: load_table(kind, TABLES_DIR) for kind in ("big", "small")}
    validate_roundtrip(rom, resources, tables)
    print("ROUNDTRIP: PASS (75/75 byte-identical)")

    if args.legacy_dump_zip is not None:
        count, mismatches = compare_legacy_dump(rom, resources, tables, args.legacy_dump_zip)
        print(f"LEGACY_DUMP_COMPARE: PASS ({count}/75 byte-identical, mismatches={mismatches})")

    for variant, expected_hash in VARIANTS.items():
        source_root = ROOT / "projects" / variant / "text"
        choice_rows = validate_choice_layout(rom, resources, tables, source_root)
        print(f"CHOICE_LAYOUT[{variant}]: PASS (0 mismatches, {choice_rows} choice row(s))")
        patched, file_count, changed, copied = build_variant(rom, resources, tables, source_root)
        capacity, max_end = validate_rom_structure(rom, patched)
        print(
            f"ROM_STRUCTURE[{variant}]: PASS (size={len(patched)} capacity={capacity}; "
            f"NitroFS_max_end={max_end:#x}; header_preserved=yes)"
        )
        digest = sha256_bytes(patched)
        if digest != expected_hash:
            raise SystemExit(
                f"ROM_HASH[{variant}]: FAIL\nExpected: {expected_hash}\nActual:   {digest}"
            )
        print(
            f"ROM_HASH[{variant}]: PASS ({digest}; source_files={file_count}; "
            f"changed_EN_slots={changed}; copied_EN_slots={copied})"
        )

    print("VALIDATE_PROJECT: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
