#!/bin/sh
# Local runtime bootstrap shared by every language. Never consumes protocol stdin.
set -eu
umask 077

runtime_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
core="$runtime_dir/core"
[ -f "$core/pyproject.toml" ] || core=$(dirname -- "$runtime_dir")
[ -f "$core/gherila/bridge.py" ] || { echo 'Gherila: bundled Python core is missing.' >&2; exit 1; }

hash() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@" | awk '{print $1}';
  else shasum -a 256 "$@" | awk '{print $1}'; fi
}

case "$(uname -m)" in
  x86_64|amd64) arch=x86_64 ;;
  aarch64|arm64) arch=aarch64 ;;
  *) echo 'Gherila: automatic setup supports x86_64 and ARM64 hosts.' >&2; exit 1 ;;
esac
case "$(uname -s)" in
  Darwin) target="$arch-apple-darwin"; default_cache="$HOME/Library/Caches/gherila" ;;
  Linux)
    target="$arch-unknown-linux-gnu"
    case "$(ldd --version 2>&1 || true)" in *musl*) target="$arch-unknown-linux-musl" ;; esac
    default_cache="${XDG_CACHE_HOME:-$HOME/.cache}/gherila" ;;
  *) echo 'Gherila: use gherila.ps1 on Windows.' >&2; exit 1 ;;
esac
cache=${GHERILA_CACHE_DIR:-$default_cache}
mkdir -p "$cache"
cache=$(CDPATH='' cd -- "$cache" && pwd)
version=$(tr -d '\r\n' < "$runtime_dir/uv-version")
key=$({
  hash "$core/pyproject.toml" "$core/setup.py" "$core/requirements.txt" "$core"/gherila/*.py
  hash "$runtime_dir/gherila.sh" "$runtime_dir/uv-version" "$runtime_dir/uv-checksums.txt"
} | hash)
marker="$cache/environments/$target-$key.txt"
python=''
if [ -f "$marker" ]; then python=$(cat "$marker"); fi

if [ -z "$python" ] || [ ! -x "$python" ]; then
  uv_dir="$cache/uv/$version/$target"
  uv="$uv_dir/uv"
  temp=$(mktemp -d "$cache/setup.XXXXXXXX")
  unfinished_env=''
  trap 'rm -rf -- "$temp"; if [ -n "$unfinished_env" ]; then rm -rf -- "$unfinished_env"; fi' EXIT
  trap 'exit 1' HUP INT TERM
  if [ ! -x "$uv" ]; then
    [ "${GHERILA_OFFLINE:-0}" != 1 ] || { echo 'Gherila: runtime is not cached; first setup needs internet access.' >&2; exit 1; }
    archive="uv-$target.tar.gz"
    expected=$(awk -v name="$archive" '$2 == name {print $1}' "$runtime_dir/uv-checksums.txt")
    [ -n "$expected" ] || { echo 'Gherila: no verified runtime for this platform.' >&2; exit 1; }
    echo 'Gherila: preparing a private Python runtime (first use).' >&2
    curl --fail --location --silent --show-error --retry 2 --connect-timeout 20 --max-time 180 \
      --proto '=https' --proto-redir '=https' \
      "https://github.com/astral-sh/uv/releases/download/$version/$archive" -o "$temp/uv.tar.gz"
    [ "$(hash "$temp/uv.tar.gz")" = "$expected" ] || { echo 'Gherila: runtime checksum mismatch; download was not executed.' >&2; exit 1; }
    tar --no-same-owner -xzf "$temp/uv.tar.gz" -C "$temp"
    mkdir -p "$uv_dir"
    mv "$temp/uv-$target/uv" "$uv"
    chmod 700 "$uv"
  fi
  # Build in the private cache, so installed SDKs can be read-only.
  source="$cache/sources/$key"
  if [ ! -d "$source" ]; then
    mkdir -p "$temp/core/gherila" "$cache/sources"
    cp "$core/pyproject.toml" "$core/setup.py" "$core/requirements.txt" "$core/README.md" "$core/LICENSE" "$temp/core/"
    cp "$core"/gherila/*.py "$temp/core/gherila/"
    # A concurrent setup may have completed this identical source copy first.
    if ! mv "$temp/core" "$source" 2>/dev/null; then [ -d "$source" ] || exit 1; fi
  fi
  export UV_PYTHON_INSTALL_DIR="$cache/python" UV_PYTHON_BIN_DIR="$cache/bin" UV_CACHE_DIR="$cache/uv-cache"
  export UV_PYTHON_DOWNLOADS=automatic UV_NO_PROGRESS=1 UV_NO_CONFIG=1
  if [ "${GHERILA_OFFLINE:-0}" = 1 ]; then export UV_OFFLINE=1; fi
  mkdir -p "$cache/envs"
  unfinished_env=$(mktemp -d "$cache/envs/$key.XXXXXXXX")
  "$uv" venv --managed-python --python 3.13 "$unfinished_env" </dev/null >&2
  python="$unfinished_env/bin/python"
  "$uv" pip install --python "$python" "$source" </dev/null >&2
  "$python" -I -X utf8 -c 'import gherila.bridge' </dev/null
  [ -x "$python" ] || { echo 'Gherila: runtime setup did not produce a Python executable.' >&2; exit 1; }
  unfinished_env=''
  mkdir -p "$cache/environments"
  printf '%s\n' "$python" > "$temp/python.txt"
  mv "$temp/python.txt" "$marker"
  rm -rf -- "$temp"
  trap - EXIT HUP INT TERM
fi

if [ "${1:-}" = --print-python ]; then printf '%s\n' "$python"; exit 0; fi
exec "$python" -I -X utf8 -u -m gherila "$@"
