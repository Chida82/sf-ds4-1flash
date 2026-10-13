#!/usr/bin/env python3
"""V4.1 steering admission at the CLI (OpenSpec 400). Model-backed: the gate is
checked after the GGUF is opened, so every case needs the real model.

Without the opt-in a direction file is refused with upstream's line, byte for
byte, exit 1. The CLI flag and a set DS4_ALLOW_V41_STEERING (empty, 0 or 1)
each lift that one term: with the file at an explicit zero scale the run
proceeds and prints the completion of a run without any file, while an
independently unsupported setting (--power 50) is still refused. Every run
starts from an environment with the variable removed, so a developer's shell
cannot pass the refusal cases for it."""
import argparse
import os
import struct
import subprocess
import tempfile
from pathlib import Path

REFUSAL = ("ds4: V4.1 requires Metal or single-GPU CUDA per rank (optional network "
           "tensor parallelism); DSpark, steering and legacy diagnostics are not "
           "supported (maximum context 1048576)")
LAYERS, EMBD = 40, 5120


def run(cli, model, extra, env_value=None, flag=False):
    env = {k: v for k, v in os.environ.items() if k != "DS4_ALLOW_V41_STEERING"}
    if env_value is not None:
        env["DS4_ALLOW_V41_STEERING"] = env_value
    argv = [cli, "-m", model, "--ssd-streaming", "--ctx", "512", "--nothink",
            "--temp", "0", "-n", "4"] + (["--allow-v41-steering"] if flag else []) \
        + extra + ["-p", "Say hi."]
    return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=600)


def completion(stdout):
    return [ln for ln in stdout.splitlines() if not ln.startswith("ds4:")]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model")
    ap.add_argument("--cli", default="./sf-ds4-1flash")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        dirs = Path(tmp) / "dirs.f32"
        dirs.write_bytes((struct.pack("<f", 1.0) + bytes(4 * (EMBD - 1))) * LAYERS)
        file_zero = ["--dir-steering-file", str(dirs), "--dir-steering-residual", "0"]

        base = run(a.cli, a.model, [])
        assert base.returncode == 0 and completion(base.stdout), base.stderr[-2000:]

        r = run(a.cli, a.model, file_zero)
        assert r.returncode == 1 and not r.stdout and REFUSAL in r.stderr.splitlines(), \
            ("default", r.returncode, r.stderr[-2000:])
        r = run(a.cli, a.model, file_zero + ["--power", "50"], flag=True)
        assert r.returncode == 1 and not r.stdout and REFUSAL in r.stderr.splitlines(), \
            ("opt-in --power 50", r.returncode, r.stderr[-2000:])

        for label, kw in (("--allow-v41-steering", {"flag": True}),
                          ("DS4_ALLOW_V41_STEERING=", {"env_value": ""}),
                          ("DS4_ALLOW_V41_STEERING=0", {"env_value": "0"}),
                          ("DS4_ALLOW_V41_STEERING=1", {"env_value": "1"})):
            r = run(a.cli, a.model, file_zero, **kw)
            assert r.returncode == 0 and REFUSAL not in r.stderr.splitlines(), \
                (label, r.returncode, r.stderr[-2000:])
            assert completion(r.stdout) == completion(base.stdout), \
                (label, completion(r.stdout), completion(base.stdout))
    print("V4.1 steering admission at the CLI: refused verbatim by default and with --power 50 "
          "under the opt-in; --allow-v41-steering and DS4_ALLOW_V41_STEERING empty/0/1 each admit "
          "a zero-scale file and print the unsteered completion: PASS")


if __name__ == "__main__":
    main()
