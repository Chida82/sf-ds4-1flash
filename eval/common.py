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
    url on failure; loaders catch this and name the missing dataset id."""
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
    dst.write_bytes(data)
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

def build_cli(prompt, *, steer=None, ffn=1.0, attn=0.0, think=True,
              max_tokens=None, logprobs=False, system=None, extra=None):
    """argv for one greedy generation.

    base arm:    steer=None  -> no steering block at all.
    steered arm: steer=PATH  -> --allow-v41-steering + the steering block.
    scale-0 control: steer=PATH, ffn=0, attn=0 -> file loaded, no edit applied.
    """
    mt = DECODE["max_tokens"] if max_tokens is None else max_tokens
    argv = [str(CLI), "-m", MODEL, "--ssd-streaming",
            "--ctx", str(DECODE["ctx"]), "--temp", "0", "-n", str(mt)]
    argv += [] if think else ["--nothink"]
    if system:
        argv += ["--system", system]
    if logprobs:
        argv += ["--dump-logprobs"]
    if steer is not None:
        argv += ["--allow-v41-steering", "--dir-steering-file", str(steer),
                 "--dir-steering-ffn", _num(ffn), "--dir-steering-attn", _num(attn)]
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
    steered = build_cli("hi", steer="/tmp/v.f32", ffn=2.0)
    assert "--allow-v41-steering" not in base
    assert "--allow-v41-steering" in steered
    assert steering_block(steered) == [
        "--allow-v41-steering", "--dir-steering-file", "/tmp/v.f32",
        "--dir-steering-ffn", "2", "--dir-steering-attn", "0"], steering_block(steered)
    assert arms_differ_only_by_steering(base, steered), "arms diverge beyond steering"
    # scale-0 control still carries the file but no edit
    z = build_cli("hi", steer="/tmp/v.f32", ffn=0.0, attn=0.0)
    assert "--dir-steering-ffn" in z and z[z.index("--dir-steering-ffn") + 1] == "0"
    # think on omits --nothink, off adds it; decoding otherwise identical
    assert "--nothink" not in build_cli("x", think=True)
    assert "--nothink" in build_cli("x", think=False)
    print("common.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
