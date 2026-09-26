#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CLEAN_ROM="${CT_CLEAN_ROM:-$ROOT/.local/roms/clean/ChronoTrigger.nds}"
BUILD_DIR="$ROOT/.local/builds"
RELEASE_DIR="$ROOT/.local/releases/generated"
EXPECTED_CLEAN_SHA256="46df8e729e5f0d67ad382ff208d803efd88154a16b39e820d318bb1a1e7549d5"

variant="${1:-all}"

if [[ ! -f "$CLEAN_ROM" ]]; then
  echo "Clean US ROM not found: $CLEAN_ROM" >&2
  echo "Place it there or set CT_CLEAN_ROM=/path/to/ChronoTrigger.nds" >&2
  exit 1
fi

actual_sha256="$(python3 - "$CLEAN_ROM" <<'PY'
import hashlib, sys
p=sys.argv[1]
h=hashlib.sha256()
with open(p,'rb') as f:
    for chunk in iter(lambda:f.read(1024*1024), b''):
        h.update(chunk)
print(h.hexdigest())
PY
)"

if [[ "$actual_sha256" != "$EXPECTED_CLEAN_SHA256" ]]; then
  echo "Wrong clean ROM." >&2
  echo "Expected SHA-256: $EXPECTED_CLEAN_SHA256" >&2
  echo "Actual SHA-256:   $actual_sha256" >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$RELEASE_DIR"

python3 "$ROOT/tools/platform_ds/validate_roundtrip.py" --rom "$CLEAN_ROM"

build_variant() {
  local name="$1"
  local patch_name="$2"
  local txt_dir="$ROOT/projects/$name/text"
  local out_rom="$BUILD_DIR/${name}.nds"
  local patch_dir="$RELEASE_DIR/$name"
  local msg_dir="$BUILD_DIR/${name}_msg"

  rm -rf "$msg_dir" "$patch_dir"
  mkdir -p "$msg_dir" "$patch_dir"

  python3 "$ROOT/tools/platform_ds/validate_choice_layout.py" \
    --rom "$CLEAN_ROM" \
    --txt-dir "$txt_dir"

  python3 "$ROOT/tools/build_release_patches.py" \
    --rom "$CLEAN_ROM" \
    --txt-dir "$txt_dir" \
    --keep-msg-dir "$msg_dir" \
    --output "$out_rom" \
    --patch-dir "$patch_dir" \
    --patch-name "$patch_name"
}

case "$variant" in
  original|original_kajar_transfer)
    build_variant original_kajar_transfer "Chrono Trigger DS (KWhazit-Chrono Compedium Fan Translation Patch)"
    ;;
  polished|polished_faithful)
    build_variant polished_faithful "Chrono Trigger DS (KWhazit-Chrono Fan Translation Polished Patch)"
    ;;
  all)
    build_variant original_kajar_transfer "Chrono Trigger DS (KWhazit-Chrono Compedium Fan Translation Patch)"
    build_variant polished_faithful "Chrono Trigger DS (KWhazit-Chrono Fan Translation Polished Patch)"
    ;;
  *)
    echo "Usage: ./Build.sh [all|original|polished]" >&2
    exit 2
    ;;
esac
