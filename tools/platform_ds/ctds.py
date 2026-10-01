#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

LANGS = ("L1", "EN", "L2", "FR")
DIR_ID_BASE = 0xF000
DEFAULT_APPEND_ALIGN = 4
RAW_HEX_RE = re.compile(r"^[0-9A-Fa-f]{2,}$")
ENTRY_RE = re.compile(
    r"^\[@ITEM\s+(\d+)\s+\(([^)]+)\)\s*\]\r?\n(.*?)(?=^\[@ITEM\s+\d+\s+\([^)]+\)\s*\]\r?$|\Z)",
    re.M | re.S,
)
HEADER_RE = re.compile(r"^\[@([^\]]+)\]\s*", re.M)


@dataclass(frozen=True)
class FileEntry:
    path: str
    file_id: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class MsgLayout:
    lang_count: int
    item_count: int
    offsets: tuple[int, ...]
    segments: tuple[bytes, ...]


@dataclass
class TextTable:
    kind: str
    encode: dict[str, bytes]
    decode: dict[bytes, str]
    display: dict[bytes, str]
    alternatives: dict[str, tuple[bytes, ...]]
    terminator: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def write_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def align(value: int, alignment: int) -> int:
    if alignment <= 1:
        return value
    return (value + alignment - 1) // alignment * alignment


def header_ranges(rom: bytes | bytearray) -> tuple[int, int, int, int]:
    if len(rom) < 0x50:
        raise ValueError("Input is too small to be a Nintendo DS ROM")
    fnt_offset = read_u32(rom, 0x40)
    fnt_size = read_u32(rom, 0x44)
    fat_offset = read_u32(rom, 0x48)
    fat_size = read_u32(rom, 0x4C)
    if not fnt_offset or not fnt_size or not fat_offset or not fat_size:
        raise ValueError("ROM header has empty FNT/FAT offsets")
    if fnt_offset + fnt_size > len(rom):
        raise ValueError("FNT range is outside the ROM")
    if fat_offset + fat_size > len(rom):
        raise ValueError("FAT range is outside the ROM")
    if fat_size % 8:
        raise ValueError("FAT size is not divisible by 8")
    return fnt_offset, fnt_size, fat_offset, fat_size


def parse_filenames(rom: bytes | bytearray) -> dict[str, FileEntry]:
    fnt_offset, fnt_size, fat_offset, fat_size = header_ranges(rom)
    file_count = fat_size // 8
    dir_count = read_u16(rom, fnt_offset + 6)
    if dir_count <= 0 or dir_count * 8 > fnt_size:
        raise ValueError(f"Invalid FNT directory count: {dir_count}")

    paths: dict[str, FileEntry] = {}
    visited: set[int] = set()

    def parse_dir(dir_index: int, dir_path: str) -> None:
        if dir_index in visited:
            return
        visited.add(dir_index)
        entry_pos = fnt_offset + dir_index * 8
        subtable_rel = read_u32(rom, entry_pos)
        file_id = read_u16(rom, entry_pos + 4)
        pos = fnt_offset + subtable_rel
        if pos < fnt_offset or pos >= fnt_offset + fnt_size:
            raise ValueError(f"Directory {dir_index} subtable is outside FNT")

        while True:
            if pos >= fnt_offset + fnt_size:
                raise ValueError(f"Directory {dir_index} entry overruns FNT")
            control = rom[pos]
            pos += 1
            if control == 0:
                break
            is_dir = bool(control & 0x80)
            name_len = control & 0x7F
            if name_len == 0:
                raise ValueError(f"Directory {dir_index} contains empty name")
            raw_name = bytes(rom[pos : pos + name_len])
            pos += name_len
            try:
                name = raw_name.decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Non-ASCII NitroFS name in directory {dir_index}: {raw_name!r}") from exc
            child_path = f"{dir_path}/{name}" if dir_path else name
            if is_dir:
                child_id = read_u16(rom, pos)
                pos += 2
                child_index = child_id - DIR_ID_BASE
                if not 0 <= child_index < dir_count:
                    raise ValueError(f"Invalid child directory id 0x{child_id:04X}: {child_path}")
                parse_dir(child_index, child_path)
            else:
                if not 0 <= file_id < file_count:
                    raise ValueError(f"Invalid file id {file_id}: {child_path}")
                fat = fat_offset + file_id * 8
                start = read_u32(rom, fat)
                end = read_u32(rom, fat + 4)
                if start > end or end > len(rom):
                    raise ValueError(f"Invalid FAT range for {child_path}: {start:#x}-{end:#x}")
                paths[child_path] = FileEntry(child_path, file_id, start, end)
                file_id += 1

    parse_dir(0, "")
    return paths


def text_msg_entries(rom: bytes | bytearray) -> dict[str, FileEntry]:
    entries = parse_filenames(rom)
    out = {
        path: entry
        for path, entry in entries.items()
        if path.lower().endswith(".msg")
        and (path.lower().startswith("msg/big/") or path.lower().startswith("msg/small/"))
    }
    return out


def extract_nitro_file(rom: bytes, entry: FileEntry) -> bytes:
    return rom[entry.start : entry.end]


def _decode_table_file(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data[:32]:
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def _semantic_value(raw: str) -> str:
    raw = raw.replace(r"\{", "{").replace(r"\}", "}").replace(r"\\", "\\")
    raw = raw.replace(r"\t", "\t").replace(r"\n", "\n").replace(r"\0", "\0")
    return raw


def _display_value(raw: str) -> str:
    raw = raw.replace(r"\{", "{").replace(r"\}", "}").replace(r"\\", "\\")
    if raw == r"\n":
        return "\n"
    if raw == r"\t":
        return r"\t"
    if raw == r"\0":
        return r"\0"
    return raw


def load_table(kind: str, table_dir: Path) -> TextTable:
    if kind not in {"big", "small"}:
        raise ValueError(f"Unknown table kind: {kind}")
    root_name = "big_asci.tbl" if kind == "big" else "small_asci.tbl"
    encode: dict[str, bytes] = {}
    decode: dict[bytes, str] = {}
    display: dict[bytes, str] = {}
    alternatives_work: dict[str, list[bytes]] = {}
    seen: set[Path] = set()

    def load(path: Path) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen.add(path)
        for raw_line in _decode_table_file(path).splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.lower().startswith(".include"):
                include = stripped.split(None, 1)[1].strip()
                load(path.parent / include)
                continue
            if "=" not in raw_line:
                continue
            hex_code, raw_value = raw_line.split("=", 1)
            hex_code = "".join(hex_code.split())
            if not hex_code or len(hex_code) % 2:
                continue
            code = bytes.fromhex(hex_code)
            semantic = _semantic_value(raw_value)
            shown = _display_value(raw_value)
            decode.setdefault(code, semantic)
            display.setdefault(code, shown)
            encode.setdefault(semantic, code)
            alternatives_work.setdefault(semantic, []).append(code)

    load(table_dir / root_name)
    terminator = b"\x02" if kind == "big" else b"\x00"
    if kind == "small":
        encode.setdefault("\0", terminator)
        decode.setdefault(terminator, "\0")
        display.setdefault(terminator, r"\0")
        alternatives_work.setdefault("\0", []).append(terminator)
    if encode.get("\0") != terminator:
        raise ValueError(f"Unexpected {kind} terminator mapping: {encode.get(chr(0))!r}")
    alternatives = {k: tuple(dict.fromkeys(v)) for k, v in alternatives_work.items()}
    return TextTable(kind, encode, decode, display, alternatives, terminator)


def parse_msg(data: bytes) -> MsgLayout:
    if len(data) < 16 or data[4:8] != b"TEXT":
        raise ValueError("Input is not a TEXT .msg resource")
    lang_count = data[8]
    if lang_count != len(LANGS):
        raise ValueError(f"Unexpected language count: {lang_count}")
    item_count = struct.unpack_from("<H", data, 9)[0]
    declared_size = struct.unpack_from("<I", data, 12)[0]
    if declared_size != len(data):
        raise ValueError(f"MSG size field mismatch: header={declared_size}, actual={len(data)}")
    table_end = 16 + item_count * lang_count * 4
    if table_end > len(data):
        raise ValueError("MSG offset table overruns resource")
    offsets = tuple(struct.unpack_from("<I", data, 16 + i * 4)[0] for i in range(item_count * lang_count))
    if offsets and offsets[0] != table_end:
        raise ValueError(f"First MSG data offset is {offsets[0]}, expected {table_end}")
    if any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("MSG offsets are not monotonic")
    if any(off < table_end or off > len(data) for off in offsets):
        raise ValueError("MSG offset outside data area")
    segments = tuple(
        data[offsets[i] : (offsets[i + 1] if i + 1 < len(offsets) else len(data))]
        for i in range(len(offsets))
    )
    return MsgLayout(lang_count, item_count, offsets, segments)


def _match_code(data: bytes, pos: int, table: TextTable, lengths: tuple[int, ...]) -> tuple[bytes, str] | None:
    for length in lengths:
        code = data[pos : pos + length]
        if code in table.decode:
            return code, table.decode[code]
    return None


def decode_segment(segment: bytes, table: TextTable, reversible: bool = False) -> str:
    if not segment.endswith(table.terminator):
        raise ValueError(f"Segment does not end with {table.terminator.hex().upper()} terminator")
    payload = segment[: -len(table.terminator)]
    lengths = tuple(sorted({len(code) for code in table.decode if code != table.terminator}, reverse=True))
    out: list[str] = []
    pos = 0
    while pos < len(payload):
        matched = _match_code(payload, pos, table, lengths)
        if matched is None:
            out.append("{" + f"{payload[pos]:02X}" + "}")
            pos += 1
            continue
        code, semantic = matched
        if reversible and table.encode.get(semantic) != code:
            out.append("{" + code.hex().upper() + "}")
        elif reversible and semantic == "\n":
            out.append(r"\n")
        elif reversible and semantic == "\t":
            out.append(r"\t")
        elif reversible and semantic == "\\":
            out.append(r"\\")
        elif reversible and semantic == "{":
            out.append(r"\{")
        elif reversible and semantic == "}":
            out.append(r"\}")
        else:
            out.append(table.display[code])
        pos += len(code)
    out.append(r"\0")
    return "".join(out)


def decode_msg_entries(data: bytes, table: TextTable, reversible: bool = False) -> dict[tuple[int, str], str]:
    layout = parse_msg(data)
    entries: dict[tuple[int, str], str] = {}
    for item in range(layout.item_count):
        for slot, lang in enumerate(LANGS):
            segment = layout.segments[item * layout.lang_count + slot]
            entries[(item, lang)] = decode_segment(segment, table, reversible=reversible)
    return entries


def serialize_msg_txt(name: str, entries: dict[tuple[int, str], str], item_count: int) -> bytes:
    lines: list[str] = [f"[@{name}]", ""]
    for item in range(item_count):
        for lang in LANGS:
            if (item, lang) not in entries:
                raise ValueError(f"Missing entry {name} item={item} lang={lang}")
            lines.append(f"[@ITEM {item} ({lang}) ]")
            lines.append(entries[(item, lang)])
            lines.append("")
    text = "\n".join(lines) + "\n"
    return b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8")


def parse_msg_txt_text(text: str, source_name: str = "<text>") -> tuple[str, dict[tuple[int, str], str]]:
    header = HEADER_RE.search(text)
    if not header:
        raise ValueError(f"Missing [@file] header in {source_name}")
    name = header.group(1)
    entries: dict[tuple[int, str], str] = {}
    for item_s, lang, body in ENTRY_RE.findall(text):
        item = int(item_s)
        if lang not in LANGS:
            raise ValueError(f"Unexpected language {lang!r} in {source_name}, item {item}")
        key = (item, lang)
        if key in entries:
            raise ValueError(f"Duplicate entry {key} in {source_name}")
        entries[key] = body.strip("\r\n")
    return name, entries


def parse_msg_txt(path: Path) -> tuple[str, dict[tuple[int, str], str]]:
    return parse_msg_txt_text(path.read_text(encoding="utf-8-sig"), str(path))


def canonical_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _encode_raw_token(token: str) -> bytes | None:
    if not (token.startswith("{") and token.endswith("}")):
        return None
    inner = token[1:-1]
    if RAW_HEX_RE.fullmatch(inner) and len(inner) % 2 == 0:
        return bytes.fromhex(inner)
    return None


def token_overrides_for_segment(segment: bytes) -> dict[str, bytes]:
    # The historical DS builder preserved the ROM's alternate {Crono} token
    # encoding when re-encoding a changed BIG segment.  Other duplicate glyph
    # encodings use the table's canonical form.  Keeping this narrowly scoped
    # is required to reproduce the known-good ROMs.
    for code in (b"\xC5\xB7", b"\xC6\x88"):
        if code in segment:
            return {"{Crono}": code}
    return {}

def encode_text(text: str, table: TextTable, overrides: dict[str, bytes] | None = None) -> bytes:
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith(r"\0", i):
            out.extend(table.terminator)
            i += 2
            continue
        if text.startswith(r"\n", i):
            code = (overrides or {}).get("\n", table.encode.get("\n"))
            if code is None:
                raise ValueError("Table has no newline mapping")
            out.extend(code)
            i += 2
            continue
        if text.startswith(r"\t", i):
            code = (overrides or {}).get("\t", table.encode.get("\t"))
            if code is None:
                raise ValueError("Table has no tab mapping")
            out.extend(code)
            i += 2
            continue
        ch = text[i]
        if ch == "\r":
            i += 1
            continue
        if ch == "{":
            end = text.find("}", i + 1)
            if end == -1:
                raise ValueError(f"Unclosed token near {text[i:i+40]!r}")
            token = text[i : end + 1]
            raw = _encode_raw_token(token)
            if raw is not None:
                out.extend(raw)
            else:
                code = (overrides or {}).get(token, table.encode.get(token))
                if code is None:
                    raise ValueError(f"Unknown token {token}")
                out.extend(code)
            i = end + 1
            continue
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "{}\\":
            ch = text[i + 1]
            i += 2
        else:
            i += 1
        code = (overrides or {}).get(ch, table.encode.get(ch))
        if code is None:
            raise ValueError(f"Character {ch!r} is not in {table.kind} table")
        out.extend(code)
    if not out.endswith(table.terminator):
        out.extend(table.terminator)
    return bytes(out)


def build_msg_from_entries(entries: dict[tuple[int, str], str], item_count: int, table: TextTable) -> bytes:
    segments: list[bytes] = []
    for item in range(item_count):
        for lang in LANGS:
            key = (item, lang)
            if key not in entries:
                raise ValueError(f"Missing entry item={item} lang={lang}")
            segments.append(encode_text(entries[key], table))
    return build_msg_from_segments(item_count, segments)


def build_msg_from_segments(item_count: int, segments: list[bytes] | tuple[bytes, ...]) -> bytes:
    expected = item_count * len(LANGS)
    if len(segments) != expected:
        raise ValueError(f"Expected {expected} segments, got {len(segments)}")
    text_offset = 16 + expected * 4
    offsets: list[int] = []
    blob = bytearray()
    for segment in segments:
        offsets.append(text_offset + len(blob))
        blob.extend(segment)
    total_size = text_offset + len(blob)
    header = bytearray(b"\x00\x00\x00\x00TEXT")
    header.append(len(LANGS))
    header.extend(struct.pack("<H", item_count))
    header.append(0)
    header.extend(struct.pack("<I", total_size))
    for offset in offsets:
        header.extend(struct.pack("<I", offset))
    return bytes(header + blob)


def patch_msg_with_source(
    original: bytes,
    source_entries: dict[tuple[int, str], str],
    table: TextTable,
    language: str = "EN",
) -> tuple[bytes, int, int]:
    layout = parse_msg(original)
    clean_text = decode_msg_entries(original, table, reversible=False)
    segments = list(layout.segments)
    changed = 0
    copied = 0
    for key, source_text in source_entries.items():
        item, lang = key
        if item < 0 or item >= layout.item_count:
            raise ValueError(f"Source refers to invalid item {item}; resource has {layout.item_count} items")
        if lang not in LANGS:
            raise ValueError(f"Source refers to invalid language {lang}")
        clean = clean_text[key]
        if lang != language:
            # Translation projects in this repository target EN only.  Keep every
            # non-target language segment byte-for-byte from the clean ROM even if
            # a historical text snapshot serialized it differently.
            continue
        index = item * layout.lang_count + LANGS.index(lang)
        if canonical_text(source_text) == canonical_text(clean):
            copied += 1
            continue
        overrides = token_overrides_for_segment(layout.segments[index])
        segments[index] = encode_text(source_text, table, overrides=overrides)
        changed += 1
    # EN slots absent from a sparse source are intentionally untouched.
    return build_msg_from_segments(layout.item_count, segments), changed, copied


def patch_rom_bytes(
    rom: bytes,
    replacements: dict[str, bytes],
    append_align: int = DEFAULT_APPEND_ALIGN,
    force_append: bool = False,
) -> tuple[bytes, list[str]]:
    out = bytearray(rom)
    files = parse_filenames(out)
    by_lower = {path.lower(): entry for path, entry in files.items()}
    _fnt, _fnt_size, fat_offset, _fat_size = header_ranges(out)

    # Commercial DS ROMs are commonly padded to their declared cartridge
    # capacity.  Appending to len(rom) would therefore place enlarged files
    # *outside* that capacity.  Reuse the free 0xFF padding after the final
    # NitroFS file instead, preserving the original header/game code/CRC so
    # loader and AP-fix identification remain unchanged.
    declared_capacity = (128 * 1024) << out[0x14]
    allocation_limit = min(len(out), declared_capacity)
    append_cursor = align(max(entry.end for entry in files.values()), append_align)
    if append_cursor > allocation_limit:
        raise ValueError(
            f"NitroFS already exceeds declared ROM capacity: {append_cursor:#x} > {allocation_limit:#x}"
        )

    log: list[str] = []
    for nitro_path in sorted(replacements):
        entry = by_lower.get(nitro_path.lower())
        if entry is None:
            raise ValueError(f"ROM does not contain NitroFS path: {nitro_path}")
        replacement = replacements[nitro_path]
        if not force_append and len(replacement) <= entry.size:
            start = entry.start
            end = start + len(replacement)
            out[start:end] = replacement
            write_u32(out, fat_offset + entry.file_id * 8, start)
            write_u32(out, fat_offset + entry.file_id * 8 + 4, end)
            mode = "in-place"
        else:
            start = append_cursor
            end = start + len(replacement)
            if end > allocation_limit:
                raise ValueError(
                    f"Not enough free ROM padding for {nitro_path}: need through {end:#x}, "
                    f"capacity ends at {allocation_limit:#x}"
                )
            out[start:end] = replacement
            write_u32(out, fat_offset + entry.file_id * 8, start)
            write_u32(out, fat_offset + entry.file_id * 8 + 4, end)
            append_cursor = align(end, append_align)
            mode = "padding"
        log.append(
            f"{nitro_path}\tfile_id={entry.file_id}\told={entry.size}\tnew={len(replacement)}"
            f"\tdelta={len(replacement)-entry.size:+d}\tmode={mode}"
        )
    return bytes(out), log


def verify_rom_replacements(rom: bytes, replacements: dict[str, bytes]) -> None:
    files = parse_filenames(rom)
    by_lower = {path.lower(): entry for path, entry in files.items()}
    for path, expected in replacements.items():
        entry = by_lower.get(path.lower())
        if entry is None:
            raise ValueError(f"Output ROM lost replacement path: {path}")
        actual = rom[entry.start : entry.end]
        if actual != expected:
            raise ValueError(f"ROM replacement verification failed: {path}")


def source_rel_to_nitro(path: Path, source_root: Path) -> tuple[str, str]:
    rel = path.relative_to(source_root)
    if len(rel.parts) != 2 or not rel.name.endswith(".msg.txt"):
        raise ValueError(f"Expected BIG/SMALL/name.msg.txt path, got {rel}")
    kind = rel.parts[0].lower()
    if kind not in {"big", "small"}:
        raise ValueError(f"Expected BIG or SMALL folder, got {rel.parts[0]}")
    msg_name = rel.name.removesuffix(".txt")
    return f"msg/{kind}/{msg_name}", kind
