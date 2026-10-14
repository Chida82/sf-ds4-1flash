"""Shared glue for the refusal-removal validation harness (OpenSpec 402).

Model-agnostic. Nothing here runs the model at import. The build_* helpers
return argv lists so they can be checked offline; execute() is the only thing
that spawns the child. Datasets and large intermediates live under /tmp, never
in the repo (design D5).

Run `python3 eval/common.py` for the offline self-checks.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVAL = REPO / "eval"
OUT = EVAL / "out"
# /tmp is ephemeral by design; override with SF_EVAL_CACHE for a persistent dir.
CACHE = Path(os.environ.get("SF_EVAL_CACHE", "/tmp/sf-ds4-1flash-eval"))

MODEL = os.environ.get("SF_EVAL_MODEL", str(REPO / "deepseek-v4.1-flash.gguf"))
CLI = REPO / "sf-ds4-1flash"
EVAL_BIN = REPO / "sf-ds4-1flash-eval"
SERVER = REPO / "sf-ds4-1flash-server"

# Fixed across both arms. A difference here between base and steered is a
# harness fault, not a model finding (spec: A/B refusal-removal measurement).
DECODE = {"ctx": 32768, "max_tokens": 256, "temp": 0.0}


def ensure_dirs():
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)


def cache_fetch(url, name):
    """Download url to CACHE/name once and return the path. Raises naming the
    url on failure; loaders catch this and name the missing dataset id.

    Writes to a .part sibling and os.replace()s it into place, so an interrupted
    or empty download never leaves a truncated file that a later run reuses as
    valid (task 1.4). The cache dir is task-local (/tmp or SF_EVAL_CACHE)."""
    ensure_dirs()
    dst = CACHE / name
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sf-ds4-1flash-eval"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except Exception as e:  # network, 404, timeout
        raise RuntimeError(f"fetch failed: {url}: {e}")
    if not data:
        raise RuntimeError(f"fetch empty: {url}")
    part = dst.with_name(dst.name + ".part")
    part.write_bytes(data)
    os.replace(part, dst)  # atomic publish: readers see all-or-nothing
    return dst


def load_hf_dataset(repo_id, *, config=None, split="train"):
    """Lazy HF `datasets` load for sources with no stable raw URL. Raises a
    clear, install-naming error when the lib is absent so the caller can name
    the dataset and tell the user to pip-install into a /tmp venv (never a
    global install, per the host integrity rule)."""
    try:
        import datasets  # noqa: lazy on purpose
    except ImportError:
        raise RuntimeError(
            f"dataset {repo_id} needs the `datasets` lib; install it into a "
            f"disposable venv: python3 -m venv /tmp/sfeval && "
            f"/tmp/sfeval/bin/pip install datasets")
    return datasets.load_dataset(repo_id, config, split=split)


# --- generation argv (two arms differ ONLY by the steering block) ------------

def build_cli(prompt, *, steer=None, residual=0.0, think=True,
              max_tokens=None, logprobs=None, top_k=None, system=None, extra=None,
              logits=None, decay_tokens=None, decay_final=None,
              think_decay_tokens=None, cycle_peak=None):
    """argv for one greedy generation.

    base arm:    steer=None  -> no steering block at all.
    steered arm: steer=PATH  -> --allow-v41-steering + the steering block.
    scale-0 control: steer=PATH, residual=0 -> file named, no edit applied.
    logprobs=PATH: the CLI writes its --dump-logprobs JSON there (score_kl.load_dump).

    The residual site is the only one live on V4.1 (400/401). Naming it also
    stops the CLI from defaulting --dir-steering-ffn to 1 when a file is given;
    the FFN and attention flags, hooks of the old V4 graph, are never emitted.
    """
    mt = DECODE["max_tokens"] if max_tokens is None else max_tokens
    argv = [str(CLI), "-m", MODEL, "--ssd-streaming",
            "--ctx", str(DECODE["ctx"]), "--temp", "0", "-n", str(mt)]
    argv += [] if think else ["--nothink"]
    if system:
        argv += ["--system", system]
    if logits is not None:
        # full first-position logits over the whole vocabulary (first-token screen)
        argv += ["--dump-logits", str(logits)]
    if logprobs is not None:
        argv += ["--dump-logprobs", str(logprobs)]
        if top_k is not None:
            argv += ["--logprobs-top-k", str(int(top_k))]
    if steer is not None:
        argv += ["--allow-v41-steering", "--dir-steering-file", str(steer),
                 "--dir-steering-residual", _num(residual)]
        # sf: 403 decay schedule (experimental). Omitted -> constant scale.
        if decay_tokens is not None:
            argv += ["--dir-steering-residual-decay-tokens", str(int(decay_tokens))]
        if think_decay_tokens is not None:
            argv += ["--dir-steering-think-residual-decay-tokens",
                     str(int(think_decay_tokens))]
        if decay_final is not None:
            argv += ["--dir-steering-residual-decay-final", _num(decay_final)]
        # sf: 403c cyclic schedule (experimental). >0 -> oscillate (down/hold-min/up)
        # with rises climbing to this peak. Omitted -> one-shot decay.
        if cycle_peak is not None:
            argv += ["--dir-steering-residual-cycle-peak", _num(cycle_peak)]
    if extra:
        argv += list(extra)
    argv += ["-p", prompt]
    return argv


def _num(x):
    s = f"{float(x):g}"
    return s


def steering_block(argv):
    """The steering-specific tail of an argv, for proving the two arms differ
    only by the edit. Returns the tokens from --allow-v41-steering onward, up to
    (but not including) the trailing -p/prompt pair."""
    try:
        i = argv.index("--allow-v41-steering")
    except ValueError:
        return []
    j = argv.index("-p", i) if "-p" in argv[i:] else len(argv)
    return argv[i:j]


def arms_differ_only_by_steering(base_argv, steered_argv):
    """True iff steered_argv is base_argv with a contiguous steering block
    inserted (same decoding, same prompt). The spec's determinism contract,
    checkable without the model. Removes the block positionally, not by value, so
    a shared token like "0" in --temp is not mistaken for the steering scale."""
    sb = steering_block(steered_argv)
    if not sb:
        return steered_argv == base_argv
    i = steered_argv.index("--allow-v41-steering")
    stripped = steered_argv[:i] + steered_argv[i + len(sb):]
    return stripped == base_argv


# --- structured arm comparison (task 2.2) ------------------------------------
# The two arms must differ ONLY by the steering block. The positional strip above
# is kept for the invariant shape; this parses the argv into named knobs so a
# changed temperature, template, budget or a duplicated conflicting flag hidden
# in `extra` is rejected before the model runs, by value and not by position.

# flags that carry a value; the rest are booleans by presence.
_VALUE_FLAGS = {
    "-m", "--ctx", "--temp", "-n", "--system", "-sys", "-p", "--prompt-file",
    "--dir-steering-file", "--dir-steering-residual", "--dir-steering-ffn",
    "--dir-steering-attn", "--dump-logprobs", "--logprobs-top-k", "--dump-logits",
}
# knobs that MUST match between arms (everything the model sees except steering).
_INVARIANT = ("model", "ctx", "temp", "max_tokens", "think", "system", "prompt",
              "logprobs", "top_k", "ssd", "prompt_file")
# knobs the steering block is allowed to introduce.
_STEERING_KEYS = ("allow_v41", "steer", "residual", "ffn", "attn")


def parse_arm(argv):
    """Parse one generation argv into {knob: value}. Raises ValueError naming a
    flag supplied twice with different values (a duplicate conflicting option)."""
    seen = {}
    knob = {"model": None, "ctx": None, "temp": None, "max_tokens": None,
            "think": True, "system": None, "prompt": None, "prompt_file": None,
            "logprobs": None, "top_k": None, "ssd": False,
            "allow_v41": False, "steer": None, "residual": None,
            "ffn": None, "attn": None, "extra": []}
    i = 1  # argv[0] is the binary
    while i < len(argv):
        a = argv[i]
        if a in _VALUE_FLAGS:
            if i + 1 >= len(argv):
                raise ValueError(f"{a} has no value")
            v = argv[i + 1]
            if a in seen and seen[a] != v:
                raise ValueError(f"conflicting duplicate {a}: {seen[a]!r} vs {v!r}")
            seen[a] = v
            i += 2
            if a == "-m":
                knob["model"] = v
            elif a == "--ctx":
                knob["ctx"] = v
            elif a == "--temp":
                knob["temp"] = v
            elif a == "-n":
                knob["max_tokens"] = v
            elif a in ("--system", "-sys"):
                knob["system"] = v
            elif a == "-p":
                knob["prompt"] = v
            elif a == "--prompt-file":
                knob["prompt_file"] = v
            elif a == "--dir-steering-file":
                knob["steer"] = v
            elif a == "--dir-steering-residual":
                knob["residual"] = v
            elif a == "--dir-steering-ffn":
                knob["ffn"] = v
            elif a == "--dir-steering-attn":
                knob["attn"] = v
            elif a == "--dump-logprobs":
                knob["logprobs"] = v
            elif a == "--logprobs-top-k":
                knob["top_k"] = v
            elif a == "--dump-logits":
                knob["logprobs"] = v  # a dump target, invariant between arms
            continue
        if a == "--nothink":
            knob["think"] = False
        elif a == "--allow-v41-steering":
            knob["allow_v41"] = True
        elif a == "--ssd-streaming":
            knob["ssd"] = True
        else:
            knob["extra"].append(a)
        i += 1
    return knob


def compare_arms(base_argv, steered_argv):
    """Return (ok, reason). The arms are a valid pair iff they parse, share every
    invariant knob and any unknown `extra`, and differ only inside the steering
    block. A changed temperature/template/budget/model or a duplicate conflicting
    flag fails here (task 2.2), before any model call."""
    try:
        b, s = parse_arm(base_argv), parse_arm(steered_argv)
    except ValueError as e:
        return False, f"unparseable arm: {e}"
    for k in _INVARIANT:
        if b[k] != s[k]:
            return False, f"arms differ on invariant {k}: {b[k]!r} vs {s[k]!r}"
    if b["extra"] != s["extra"]:
        return False, f"arms differ on unrecognized options: {b['extra']} vs {s['extra']}"
    # the base arm must carry no steering; the steered arm's FFN/attn stay unset
    if any(b[k] for k in _STEERING_KEYS):
        return False, "base arm carries a steering block"
    if s["ffn"] is not None or s["attn"] is not None:
        return False, "steered arm names an FFN/attention site (V4 hook, inert on V4.1)"
    return True, "arms differ only by the residual steering block"


def execute(argv, *, timeout=1800, caffeinate=True):
    """Run one arm. caffeinate keeps the Mac awake for long sweeps; the child
    serializes on /tmp/sf-ds4-1flash.lock so arms never overlap."""
    cmd = (["caffeinate", "-i"] if caffeinate else []) + argv
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {"argv": argv, "returncode": p.returncode,
            "stdout": p.stdout, "stderr": p.stderr}


def save_json(path, obj):
    ensure_dirs()
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def load_json(path):
    return json.loads(Path(path).read_text())


def _selfcheck():
    base = build_cli("hi")
    steered = build_cli("hi", steer="/tmp/v.f32", residual=4.0)
    assert "--allow-v41-steering" not in base and "--dump-logprobs" not in base
    assert steering_block(steered) == [
        "--allow-v41-steering", "--dir-steering-file", "/tmp/v.f32",
        "--dir-steering-residual", "4"], steering_block(steered)
    # the V4-graph sites are never named: the CLI would default ffn to 1
    assert "--dir-steering-ffn" not in steered and "--dir-steering-attn" not in steered
    assert arms_differ_only_by_steering(base, steered), "arms diverge beyond steering"
    # scale-0 control: the file is named, the residual scale is 0, no FFN default
    z = build_cli("hi", steer="/tmp/v.f32", residual=0.0)
    assert steering_block(z)[-2:] == ["--dir-steering-residual", "0"]
    assert "--dir-steering-ffn" not in z and arms_differ_only_by_steering(base, z)
    # the diagnostic dump goes to a named file, the same in both arms
    lp = build_cli("hi", logprobs="/tmp/lp.json", top_k=32)
    assert lp[lp.index("--dump-logprobs") + 1] == "/tmp/lp.json"
    assert lp[lp.index("--logprobs-top-k") + 1] == "32"
    assert arms_differ_only_by_steering(
        lp, build_cli("hi", steer="/tmp/v.f32", residual=4.0, logprobs="/tmp/lp.json", top_k=32))
    # think on omits --nothink, off adds it; decoding otherwise identical
    assert "--nothink" not in build_cli("x", think=True)
    assert "--nothink" in build_cli("x", think=False)

    # --- structured arm comparison (task 2.2) --------------------------------
    b2 = build_cli("q")
    s2 = build_cli("q", steer="/tmp/v.f32", residual=4.0)
    ok, why = compare_arms(b2, s2)
    assert ok, why
    # a changed temperature hidden in extra -> duplicate --temp -> rejected
    bad_temp = build_cli("q", steer="/tmp/v.f32", residual=4.0, extra=["--temp", "0.7"])
    ok, why = compare_arms(b2, bad_temp)
    assert not ok and ("temp" in why or "duplicate" in why), why
    # changed thinking between arms -> rejected
    ok, why = compare_arms(build_cli("q", think=True),
                           build_cli("q", steer="/tmp/v.f32", residual=4.0, think=False))
    assert not ok and "think" in why, why
    # changed model -> rejected
    ok, why = compare_arms(b2, build_cli("q", steer="/tmp/v.f32", residual=4.0,
                                         extra=["-m", "other.gguf"]))
    assert not ok and "conflicting duplicate -m" in why, why
    # changed token budget -> rejected
    ok, why = compare_arms(build_cli("q", max_tokens=256),
                           build_cli("q", steer="/tmp/v.f32", residual=4.0, max_tokens=128))
    assert not ok and "max_tokens" in why, why
    # a different prompt -> rejected
    ok, why = compare_arms(build_cli("q"), build_cli("other", steer="/tmp/v.f32", residual=4.0))
    assert not ok and "prompt" in why, why
    # naming an FFN site on the steered arm -> rejected (V4 hook, inert on V4.1)
    ok, why = compare_arms(b2, build_cli("q", steer="/tmp/v.f32", residual=4.0,
                                         extra=["--dir-steering-ffn", "1"]))
    assert not ok and "FFN" in why, why
    # a clean scale-0 control is a valid pair (same decoding, file named)
    ok, why = compare_arms(b2, build_cli("q", steer="/tmp/v.f32", residual=0.0))
    assert ok, why
    # a dump target is a value, not swallowing the next flag: --dump-logprobs PATH
    # leaves --dir-steering-file parseable, and top_k is captured too.
    dp = parse_arm(build_cli("q", steer="/tmp/v.f32", residual=4.0,
                             logprobs="/tmp/lp.json", top_k=32))
    assert dp["logprobs"] == "/tmp/lp.json" and dp["steer"] == "/tmp/v.f32"
    assert dp["residual"] == "4"
    # --dump-logits is an invariant dump target between arms
    lg = parse_arm(build_cli("q", logits="/tmp/first.json"))
    assert lg["logprobs"] == "/tmp/first.json"
    print("common.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
