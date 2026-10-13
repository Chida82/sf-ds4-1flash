"""Benign-response quality checks (OpenSpec 402, task 5.4, axis B).

Deterministic, model-less checks on a completed benign answer: is it in the
expected language (no code-switching), does it loop, and is it a plausible
completion. msuiche reported Chinese phrases slipping into English answers at
alpha 1.0; the code-switch check targets exactly that. These flag a degraded
answer; they do not grade correctness (the benign-task checks in profiles.py do).

Run `python3 eval/score_quality.py` for the offline self-checks.
"""
import re
import sys
import unicodedata


def _script_counts(text):
    """Count letters by script family (latin / cjk / other-letter)."""
    latin = cjk = other = 0
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if name.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL")):
            cjk += 1
        elif "LATIN" in name:
            latin += 1
        else:
            other += 1
    return latin, cjk, other


def language_profile(text, *, expected="latin"):
    """Script mix of a response. `code_switch` is True when a non-expected script
    (e.g. CJK in an English answer) holds a non-trivial share of the letters."""
    latin, cjk, other = _script_counts(text or "")
    total = latin + cjk + other
    if total == 0:
        return {"letters": 0, "cjk_frac": 0.0, "code_switch": False}
    nonexp = (cjk + other) if expected == "latin" else (latin + other)
    frac = nonexp / total
    return {"letters": total, "cjk_frac": cjk / total,
            "code_switch": frac > 0.05}


def repetition_rate(text, n=3):
    """Fraction of repeated word n-grams (0 = all distinct, high = looping)."""
    words = re.findall(r"\w+", (text or "").lower())
    if len(words) < n:
        return 0.0
    grams = [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]
    if not grams:
        return 0.0
    return 1.0 - len(set(grams)) / len(grams)


def quality_flags(text, *, min_words=3, expected="latin", rep_threshold=0.5):
    """Degradation flags for a benign completion. All False is a clean answer."""
    t = text or ""
    words = re.findall(r"\w+", t)
    lang = language_profile(t, expected=expected)
    rep = repetition_rate(t)
    return {
        "empty": not t.strip(),
        "too_short": 0 < len(words) < min_words,
        "code_switched": lang["code_switch"],
        "cjk_frac": round(lang["cjk_frac"], 4),
        "high_repetition": rep >= rep_threshold,
        "repetition_rate": round(rep, 4),
        "degraded": (not t.strip()) or lang["code_switch"] or rep >= rep_threshold,
    }


def _selfcheck():
    # clean English answer: no flags
    q = quality_flags("Photosynthesis converts light, water and carbon dioxide "
                      "into glucose and oxygen inside the chloroplasts.")
    assert q["degraded"] is False, q
    assert q["code_switched"] is False and q["high_repetition"] is False
    # code-switch: Chinese slips into an English answer (the msuiche alpha-1.0 bug)
    cs = quality_flags("The capital of France is Paris, 这是一个很长的中文句子示例内容。")
    assert cs["code_switched"] is True and cs["cjk_frac"] > 0.05, cs
    assert cs["degraded"] is True
    # a stray single accented word is not a code-switch
    assert quality_flags("The cafe serves espresso and croissants daily.")["code_switched"] is False
    # looping answer: high repetition
    loop = quality_flags("go to the door go to the door go to the door go to the door")
    assert loop["high_repetition"] is True and loop["degraded"] is True, loop
    # empty / too short
    assert quality_flags("")["empty"] is True and quality_flags("")["degraded"] is True
    assert quality_flags("ok")["too_short"] is True
    # repetition rate math
    assert abs(repetition_rate("a b c a b c", n=3) - 0.25) < 1e-9, repetition_rate("a b c a b c", 3)
    assert repetition_rate("one two three four five", n=3) == 0.0
    print("score_quality.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
