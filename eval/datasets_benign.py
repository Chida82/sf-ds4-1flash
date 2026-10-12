"""Axis-B benign loader (OpenSpec 402): harmless instructions for the KL/shift
and code-switching checks. Alpaca instructions with no `input` field are the
cleanest single-turn benign set.

Run `python3 eval/datasets_benign.py` for the offline self-checks.
"""
import json
import sys

import common

ALPACA_JSON = [
    "https://raw.githubusercontent.com/tatsu-lab/stanford_alpaca/main/alpaca_data.json",
]


def _instructions_no_input(text, limit=None):
    data = json.loads(text)
    out = [r["instruction"].strip() for r in data
           if not r.get("input", "").strip() and r.get("instruction", "").strip()]
    return out[:limit] if limit else out


def load_alpaca_benign(limit=200):
    errs = []
    for url in ALPACA_JSON:
        try:
            path = common.cache_fetch(url, "alpaca_data.json")
            return _instructions_no_input(path.read_text(), limit)
        except Exception as e:
            errs.append(str(e))
    raise RuntimeError(f"alpaca benign: all sources failed: {errs}")


def _selfcheck():
    fixture = json.dumps([
        {"instruction": "Explain photosynthesis.", "input": "", "output": "..."},
        {"instruction": "Translate this.", "input": "ciao", "output": "..."},
        {"instruction": "  List three primes.  ", "input": "", "output": "..."},
        {"instruction": "", "input": "", "output": "..."},
    ])
    out = _instructions_no_input(fixture)
    assert out == ["Explain photosynthesis.", "List three primes."], out
    assert _instructions_no_input(fixture, limit=1) == ["Explain photosynthesis."]
    print("datasets_benign.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
