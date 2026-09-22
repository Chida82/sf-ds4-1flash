#!/bin/sh
# Download one DeepSeek V4.1 Flash component into the shared Hugging Face cache
# and link it here.  This child never keeps a second copy of a model: every file
# this script creates under gguf/ is a symlink into the cache (SPEC.md §C).
#
#   ./download.sh            list the components
#   ./download.sh q2         the main model, and the default -m target
#   ./download.sh vision     the vision encoder, for --vision FILE
set -eu

REPO="antirez/deepseek-v4.1-flash-gguf"
DEFAULT_LINK="deepseek-v4.1-flash.gguf"
ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    cat <<EOF
Components of $REPO:

  q2       DeepSeek-V4.1-Flash-Q2.gguf       main model (default for -m)
  vision   DeepSeek-V4.1-Flash-Vision.gguf   vision encoder, pass with --vision

  ./download.sh q2
  ./download.sh vision

Files live once in the Hugging Face cache (\$HUGGINGFACE_HUB_CACHE, else
\$HF_HOME/hub, else ~/.cache/huggingface/hub).  gguf/ holds symlinks to them and
./$DEFAULT_LINK points at the main model.

Not offered here: the Q4 release, which upstream ships as two .part files that
have to be joined into one multi-gigabyte file.  The join produces a real file
rather than a link, and this repository does not hold model data (SPEC.md §C).
Use Q2, or join the parts yourself outside the repository and pass the result
with -m.
EOF
}

if [ $# -eq 0 ]; then
    usage
    exit 0
fi

case "$1" in
    q2)     FILE="DeepSeek-V4.1-Flash-Q2.gguf";     LINK_DEFAULT=1 ;;
    vision) FILE="DeepSeek-V4.1-Flash-Vision.gguf"; LINK_DEFAULT=0 ;;
    -h|--help|help) usage; exit 0 ;;
    *)
        echo "download.sh: unknown component '$1'" >&2
        echo >&2
        usage >&2
        exit 2
        ;;
esac

if ! command -v hf >/dev/null 2>&1; then
    cat >&2 <<'EOF'
download.sh needs the Hugging Face CLI ("hf"), which owns the shared cache,
resume and content verification.  Install it with:

    pip install -U "huggingface_hub[cli]"
EOF
    exit 1
fi

echo "Fetching $FILE from $REPO ..."
# hf prints the absolute path of the cached file on stdout and its progress on
# stderr; some versions prefix the path with "path=".  Re-running is cheap: it
# verifies what is already cached instead of downloading again.
path="$(hf download "$REPO" "$FILE" | tail -1)"
path="${path#path=}"
if [ ! -f "$path" ]; then
    echo "download.sh: hf did not return a usable file path (got: $path)" >&2
    exit 1
fi

mkdir -p "$ROOT/gguf"
ln -sfn "$path" "$ROOT/gguf/$FILE"
echo "Linked gguf/$FILE -> $path"

if [ "$LINK_DEFAULT" -eq 1 ]; then
    ln -sfn "gguf/$FILE" "$ROOT/$DEFAULT_LINK"
    echo "Linked ./$DEFAULT_LINK -> gguf/$FILE"
fi
