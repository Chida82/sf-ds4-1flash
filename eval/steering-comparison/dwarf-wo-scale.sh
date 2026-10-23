#!/bin/sh
# Adaptive scale search for dwarf-wo (DwarfStar weight-diff refusal dir, global 1017 answer dir),
# 12 hard, NON-think, mt 2048. Hill-climb from 7 (down first, then up). Logic in dwarf_scale_search.py.
caffeinate -i -w $$ >/dev/null 2>&1 &
cd "$(dirname "$0")/../.." || exit 1
export SF_EVAL_MODEL="$PWD/gguf/DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf"
: "${SF_EVAL_CACHE_EXPERTS:=82GB}"; export SF_EVAL_CACHE_EXPERTS
exec python3 eval/steering-comparison/dwarf_scale_search.py
