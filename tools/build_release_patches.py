#!/usr/bin/env python3
from __future__ import annotations

import argparse
import binascii
import hashlib
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IPS_MAX_OFFSET = 0xFFFFFF
IPS_MAX_SIZE = 0xFFFFFF
BPS_EQUAL_LOOKAHEAD = 16


@dataclass
class PatchResult:
    name: str
    path: Path | None
    status: str
    detail: str
    size: int | None = None
    sha256: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc32_hex(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def crc32_le(data: bytes) -> bytes:
    return (binascii.crc32(data) & 0xFFFFFFFF).to_bytes(4, "little")


def bps_number(value: int) -> bytes:
    if value < 0:
        raise ValueError("BPS numbers cannot be negative")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(byte | 0x80)
            return bytes(out)
        out.append(byte)
        value -= 1


def bps_action(mode: int, length: int) -> bytes:
    if length <= 0:
        raise ValueError("BPS action length must be positive")
    return bps_number(((length - 1) << 2) | mode)


def iter_diff_runs(source: bytes, target: bytes, block_size: int = 64 * 1024, zero_extend_source: bool = False):
    """Yield [start, end) target ranges whose bytes differ from source.

    Equal blocks are skipped with C-level bytes comparisons.  Only blocks that
    actually contain differences are scanned byte-by-byte, avoiding a Python
    loop over the entire 128+ MiB ROM.
    """
    common = min(len(source), len(target))
    open_start: int | None = None
    pos = 0
    while pos < common:
        end = min(pos + block_size, common)
        a = source[pos:end]
        b = target[pos:end]
        if a == b:
            if open_start is not None:
                yield open_start, pos
                open_start = None
            pos = end
            continue
        for offset, (left, right) in enumerate(zip(a, b)):
            index = pos + offset
            if left != right:
                if open_start is None:
                    open_start = index
            elif open_start is not None:
                yield open_start, index
                open_start = None
        pos = end

    if len(target) > common and zero_extend_source:
        # UPS treats source bytes beyond EOF as zero.  A zero byte in an
        # appended target tail therefore remains equal and must split a run.
        pos = common
        while pos < len(target):
            end = min(pos + block_size, len(target))
            block = target[pos:end]
            if not block.strip(b"\x00"):
                if open_start is not None:
                    yield open_start, pos
                    open_start = None
                pos = end
                continue
            for offset, right in enumerate(block):
                index = pos + offset
                if right != 0:
                    if open_start is None:
                        open_start = index
                elif open_start is not None:
                    yield open_start, index
                    open_start = None
            pos = end
    elif len(target) > common:
        # BPS SourceRead cannot read beyond the source EOF, so the complete
        # appended target tail must be emitted as TargetRead, including zeros.
        if open_start is None:
            open_start = common
    elif open_start is not None:
        yield open_start, common
        open_start = None

    if open_start is not None:
        yield open_start, len(target)


def create_bps(source: bytes, target: bytes, metadata: bytes) -> bytes:
    patch = bytearray()
    patch += b"BPS1"
    patch += bps_number(len(source))
    patch += bps_number(len(target))
    patch += bps_number(len(metadata))
    patch += metadata

    pos = 0
    for start, end in iter_diff_runs(source, target):
        if start > pos:
            patch += bps_action(0, start - pos)  # SourceRead
        patch += bps_action(1, end - start)  # TargetRead
        patch += target[start:end]
        pos = end
    if pos < len(target):
        patch += bps_action(0, len(target) - pos)

    patch += crc32_le(source)
    patch += crc32_le(target)
    patch += crc32_le(bytes(patch))
    return bytes(patch)


def ups_number(value: int) -> bytes:
    return bps_number(value)


def create_ups(source: bytes, target: bytes) -> bytes:
    patch = bytearray()
    patch += b"UPS1"
    patch += ups_number(len(source))
    patch += ups_number(len(target))

    stream_pos = 0
    for start, end in iter_diff_runs(source, target, zero_extend_source=True):
        patch += ups_number(start - stream_pos)
        if end <= len(source):
            patch += bytes(a ^ b for a, b in zip(source[start:end], target[start:end]))
        else:
            common_end = min(end, len(source))
            if start < common_end:
                patch += bytes(a ^ b for a, b in zip(source[start:common_end], target[start:common_end]))
            tail_start = max(start, len(source))
            if end > tail_start:
                patch += target[tail_start:end]
        patch.append(0)
        stream_pos = end + 1

    patch += crc32_le(source)
    patch += crc32_le(target)
    patch += crc32_le(bytes(patch))
    return bytes(patch)

def create_ips(source: bytes, target: bytes) -> tuple[bytes | None, str]:
    if len(target) > IPS_MAX_SIZE:
        return None, (
            f"skipped: target ROM is {len(target)} bytes, above classic IPS safe size limit "
            f"0x{IPS_MAX_SIZE:06X}"
        )

    patch = bytearray(b"PATCH")
    pos = 0
    target_len = len(target)
    source_len = len(source)
    record_count = 0

    while pos < target_len:
        same = pos < source_len and source[pos] == target[pos]
        if same:
            pos += 1
            continue

        start = pos
        while pos < target_len and not (pos < source_len and source[pos] == target[pos]):
            pos += 1

        data = target[start:pos]
        cursor = 0
        while cursor < len(data):
            offset = start + cursor
            if offset > IPS_MAX_OFFSET:
                return None, f"skipped: changed offset 0x{offset:X} is above classic IPS 24-bit range"
            chunk = data[cursor : cursor + 0xFFFF]
            patch += offset.to_bytes(3, "big")
            patch += len(chunk).to_bytes(2, "big")
            patch += chunk
            cursor += len(chunk)
            record_count += 1

    patch += b"EOF"
    return bytes(patch), f"written: {record_count} changed data record(s)"


def write_patch(path: Path, data: bytes) -> PatchResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return PatchResult(
        name=path.suffix.lstrip(".").upper(),
        path=path,
        status="written",
        detail="ok",
        size=len(data),
        sha256=sha256_bytes(data),
    )


def run_xdelta3(xdelta3: str, source: Path, target: Path, output: Path) -> PatchResult:
    executable = shutil.which(xdelta3)
    if not executable:
        return PatchResult("XDELTA", None, "skipped", f"{xdelta3!r} was not found in PATH")

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, "-f", "-e", "-s", str(source), str(target), str(output)]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "xdelta3 failed").strip()
        return PatchResult("XDELTA", output, "failed", detail)
    return PatchResult(
        "XDELTA",
        output,
        "written",
        "ok",
        output.stat().st_size,
        sha256_file(output),
    )


def resolve_txt_dir(path: Path) -> Path:
    candidates = [path]
    if not path.is_absolute():
        candidates.append(ROOT / path)
        candidates.append(ROOT / "outputs" / "ds" / path)
    if path.name == "txt":
        parent = path.parent
        candidates.append(parent)
        if not parent.is_absolute():
            candidates.append(ROOT / parent)
            candidates.append(ROOT / "outputs" / "ds" / parent)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.is_dir() and list(candidate.rglob("*.msg.txt")):
            if candidate != path:
                print(f"Resolved TXT folder {path} -> {candidate}")
            return candidate

    checked = "\n".join(f"- {candidate}" for candidate in candidates)
    raise SystemExit(f"TXT folder not found or contains no .msg.txt files: {path}\nChecked:\n{checked}")


def build_rom(args: argparse.Namespace, txt_dir: Path, output: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "tools" / "insert_txt_folder.py"),
        "--rom",
        str(args.rom),
        "--txt-dir",
        str(txt_dir),
        "--output",
        str(output),
    ]
    if args.keep_msg_dir:
        command.extend(["--keep-msg-dir", str(args.keep_msg_dir)])
    if args.force_append:
        command.append("--force-append")

    print("Building patched ROM:")
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def public_path(path: Path) -> str:
    """Return a portable path for release-facing metadata.

    Paths inside the repository are written relative to the repository root.
    Paths outside the repository are reduced to the basename so a release
    artifact never leaks the builder's home directory or other local paths.
    """
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def write_checksums(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{digest}  {name}\n" for digest, name in rows)
    path.write_text(body, encoding="utf-8", newline="\n")


def write_release_readme(
    path: Path,
    patch_name: str,
    clean_crc32: str,
    patched_crc32: str,
    results: list[PatchResult],
) -> None:
    available = {result.name: result for result in results if result.status == "written" and result.path}
    bps_name = available["BPS"].path.name if "BPS" in available else f"{patch_name}.bps"
    ups_name = available["UPS"].path.name if "UPS" in available else f"{patch_name}.ups"
    xdelta_name = available["XDELTA"].path.name if "XDELTA" in available else None

    lines = [
        f"# {patch_name}",
        "",
        "## Recommended patch",
        "",
        f"Use **`{bps_name}`**. BPS is the canonical and recommended release format for this project.",
        "",
        f"`{ups_name}` is provided as a compatibility alternative. It should produce the same patched ROM when applied to the correct clean ROM.",
    ]
    if xdelta_name:
        lines.extend(
            [
                "",
                f"`{xdelta_name}` is an optional alternative generated when `xdelta3` is available. It is not the canonical release patch.",
            ]
        )

    lines.extend(
        [
            "",
            "## Required base ROM",
            "",
            "Use a clean **Chrono Trigger DS (US), revision 0** ROM.",
            "",
            f"**CRC32: `{clean_crc32}`**",
            "",
            "If the CRC32 does not match, do not force the patch. Use the correct clean ROM and try again.",
            "",
            "No ROM is included with this release.",
            "",
            "## Apply the patch online",
            "",
            "The easiest method is **Romhacking.net Online ROM Patcher (Rom Patcher JS)**:",
            "",
            "https://www.romhacking.net/patch/",
            "",
            "If that mirror is unavailable, use the upstream Rom Patcher JS page:",
            "",
            "https://www.marcrobledo.com/RomPatcher.js/",
            "",
            "1. Select your clean Chrono Trigger DS ROM as the ROM file.",
            f"2. Select **`{bps_name}`** as the patch file.",
            "3. Apply the patch.",
            "4. Save/download the patched `.nds` file.",
            "",
            "Both pages perform patching in the browser. BPS and UPS are supported by Rom Patcher JS.",
            "",
            "## TWiLight Menu++ / nds-bootstrap",
            "",
            "Chrono Trigger uses anti-piracy checks. For ROM hacks, use **TWiLight Menu++ v27.17.3 / nds-bootstrap v2.8.3 or newer**; nds-bootstrap v2.8.3 specifically fixed white-screen boot failures for Chrono Trigger ROM hacks.",
            "",
            "If the patched game still boots to white screens on DSi/3DS:",
            "",
            "1. Update both TWiLight Menu++ and nds-bootstrap.",
            "2. Reset this game's per-game settings to Default and disable cheats.",
            "3. Delete `sd:/_nds/nds-bootstrap/fatTable/` and `sd:/_nds/nds-bootstrap/patchOffsetCache/`, then launch the game again so the caches are rebuilt.",
            "",
            "Forwarders also use nds-bootstrap, so the same cache/settings troubleshooting can apply to a HOME Menu forwarder.",
            "",
            "## Verify the result",
            "",
            "The correctly patched ROM should have:",
            "",
            f"**CRC32: `{patched_crc32}`**",
            "",
            "You can also compare the patch-file hashes against `checksums_sha256.txt`.",
            "",
            "## Included release files",
            "",
            f"- **`{bps_name}`** — canonical/recommended patch.",
            f"- **`{ups_name}`** — compatibility alternative.",
        ]
    )
    if xdelta_name:
        lines.append(f"- **`{xdelta_name}`** — optional alternative; generated only when xdelta3 was available.")
    lines.extend(
        [
            "- **`checksums_sha256.txt`** — hashes for verification.",
            f"- **`{patch_name}_patch_report.md`** — technical build report.",
            "",
            "Do not distribute the clean or patched ROM. Distribute the patch files instead.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_report(
    path: Path,
    args: argparse.Namespace,
    txt_dir: Path,
    output: Path,
    clean_hash: str,
    patched_hash: str,
    results: list[PatchResult],
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Chrono Trigger DS Release Patch Build Report",
        "",
        f"- Built: {now}",
        f"- Clean ROM: `{public_path(args.rom)}`",
        f"- TXT folder: `{public_path(txt_dir)}`",
        f"- Patched ROM: `{public_path(output)}`",
        f"- Clean ROM SHA256: `{clean_hash}`",
        f"- Patched ROM SHA256: `{patched_hash}`",
        "",
        "## Patch Outputs",
        "",
        "| Format | Status | File | Size | SHA256 / detail |",
        "|---|---|---:|---:|---|",
    ]
    for result in results:
        file_text = f"`{result.path.name}`" if result.path else "-"
        size_text = str(result.size) if result.size is not None else "-"
        detail = result.sha256 or result.detail
        lines.append(f"| {result.name} | {result.status} | {file_text} | {size_text} | `{detail}` |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- BPS is the canonical and recommended release patch format for this project.",
            "- UPS is generated as an additional large-ROM-safe patch format.",
            "- Classic IPS is skipped automatically when the target ROM is too large or changed offsets exceed the 24-bit IPS range.",
            "- XDELTA is generated only when the external `xdelta3` executable is available.",
            "- Do not distribute the clean or patched ROM; distribute patch files plus the clean-ROM checksum.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Chrono Trigger DS patched ROM from a .msg.txt folder and create release patch files."
        )
    )
    parser.add_argument("--rom", type=Path, required=True, help="Clean input .nds ROM.")
    parser.add_argument(
        "--txt-dir",
        type=Path,
        required=True,
        help="Folder containing BIG/*.msg.txt and/or SMALL/*.msg.txt.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Patched output .nds ROM.")
    parser.add_argument(
        "--patch-dir",
        type=Path,
        default=Path("release_patches"),
        help="Folder for generated patch files and reports. Default: release_patches/",
    )
    parser.add_argument(
        "--patch-name",
        help="Base filename for patch files. Default: patched ROM stem.",
    )
    parser.add_argument(
        "--keep-msg-dir",
        type=Path,
        help="Optional folder where converted binary .msg files should be kept.",
    )
    parser.add_argument("--force-append", action="store_true", help="Append every replacement during ROM insertion.")
    parser.add_argument(
        "--skip-rom-build",
        action="store_true",
        help="Do not run insert_txt_folder.py; create patches from an already existing --output ROM.",
    )
    parser.add_argument("--xdelta3", default="xdelta3", help="xdelta3 executable name/path. Default: xdelta3.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.rom.is_file():
        raise SystemExit(f"Clean input ROM not found: {args.rom}")

    txt_dir = resolve_txt_dir(args.txt_dir)
    output = args.output
    if not args.skip_rom_build:
        build_rom(args, txt_dir, output)
    elif not output.is_file():
        raise SystemExit(f"--skip-rom-build was used, but patched ROM does not exist: {output}")

    if not output.is_file():
        raise SystemExit(f"Patched ROM was not created: {output}")

    patch_dir = args.patch_dir
    patch_name = args.patch_name or output.stem
    source = args.rom.read_bytes()
    target = output.read_bytes()

    clean_hash = sha256_bytes(source)
    patched_hash = sha256_bytes(target)
    clean_crc32 = crc32_hex(source)
    patched_crc32 = crc32_hex(target)

    metadata = (
        "Chrono Trigger DS Kajar/Chrono Compendium port\n"
        f"clean_sha256={clean_hash}\n"
        f"patched_sha256={patched_hash}\n"
    ).encode("utf-8")

    results: list[PatchResult] = []

    bps_path = patch_dir / f"{patch_name}.bps"
    bps = create_bps(source, target, metadata)
    results.append(write_patch(bps_path, bps))

    ups_path = patch_dir / f"{patch_name}.ups"
    ups = create_ups(source, target)
    results.append(write_patch(ups_path, ups))

    ips_path = patch_dir / f"{patch_name}.ips"
    ips, ips_detail = create_ips(source, target)
    if ips is None:
        results.append(PatchResult("IPS", None, "skipped", ips_detail))
    else:
        result = write_patch(ips_path, ips)
        result.detail = ips_detail
        results.append(result)

    xdelta_path = patch_dir / f"{patch_name}.xdelta"
    results.append(run_xdelta3(args.xdelta3, args.rom, output, xdelta_path))

    checksums: list[tuple[str, str]] = [
        (clean_hash, "CLEAN_ROM_REFERENCE_DO_NOT_DISTRIBUTE"),
        (patched_hash, "PATCHED_ROM_REFERENCE_DO_NOT_DISTRIBUTE"),
    ]
    for result in results:
        if result.path and result.sha256:
            checksums.append((result.sha256, result.path.name))
    write_checksums(patch_dir / "checksums_sha256.txt", checksums)
    write_report(patch_dir / f"{patch_name}_patch_report.md", args, txt_dir, output, clean_hash, patched_hash, results)
    write_release_readme(patch_dir / "README.md", patch_name, clean_crc32, patched_crc32, results)

    print("Patch build summary:")
    for result in results:
        file_text = f" -> {result.path}" if result.path else ""
        print(f"- {result.name}: {result.status}{file_text} ({result.detail})")
    print(f"- checksums: {patch_dir / 'checksums_sha256.txt'}")
    print(f"- report: {patch_dir / f'{patch_name}_patch_report.md'}")
    print(f"- release README: {patch_dir / 'README.md'}")


if __name__ == "__main__":
    main()
