#!/usr/bin/env python3
"""V4.1 steering admission and site diagnostics at the CLI and server (OpenSpec
400, 401). Model-backed: the gate runs after the GGUF is opened, so every case
needs the real model.

Without the opt-in a direction file is refused with upstream's line, byte for
byte, exit 1, whatever else is passed. The CLI flag and a set
DS4_ALLOW_V41_STEERING (empty, 0 or 1) each lift that one term: with the file
at an explicit zero residual scale the run proceeds and prints the completion
of a run without any file, while an independently unsupported setting
(--power 50) is still refused. Under the opt-in a nonzero FFN or attention
scale is refused with its own line, including the file-alone case the CLI
turns into --dir-steering-ffn 1; a nonzero residual scale starts, prints the
site and revision, and an invalid file fails before any session. A steered
server does not open --kv-disk-dir and leaves the directory alone. Every run
starts from an environment with the variable removed, so a developer's shell
cannot pass the refusal cases for it."""
import argparse
import os
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

REFUSAL = ("ds4: V4.1 requires Metal or single-GPU CUDA per rank (optional network "
           "tensor parallelism); DSpark, steering and legacy diagnostics are not "
           "supported (maximum context 1048576)")
SITE_REFUSAL = ("ds4: V4.1 steering applies only at --dir-steering-residual F; "
                "--dir-steering-ffn and --dir-steering-attn are V4 hooks with no effect on "
                "this model (a file alone implies --dir-steering-ffn 1)")
STEERING_LINE = "ds4: V4.1 residual steering: "
SITE = "v41_attn_input_weighted_fold_post_engram rev 2"
KV_REFUSAL = "persistent KV cache is not supported while directional steering is active"
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


def serve(server, model, tmp, residual):
    """Start the server steered (or at scale 0) with a KV root; return the
    log lines up to the listening line and whether the KV root exists."""
    kv = Path(tmp) / f"kv-{residual}"
    env = {k: v for k, v in os.environ.items() if k != "DS4_ALLOW_V41_STEERING"}
    env["DS4_LOCK_FILE"] = str(Path(tmp) / "server.lock")
    argv = [server, "-m", model, "--ssd-streaming", "--ctx", "512", "--port", "18002",
            "--allow-v41-steering", "--dir-steering-file", str(Path(tmp) / "unit.f32"),
            "--dir-steering-residual", str(residual), "--kv-disk-dir", str(kv)]
    p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True)
    lines = []

    def reader():
        for ln in p.stdout:
            lines.append(ln.rstrip("\n"))

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    deadline = time.time() + 600
    try:
        while time.time() < deadline and p.poll() is None:
            if any("listening on" in ln for ln in lines):
                break
            time.sleep(0.5)
    finally:
        p.terminate()
        try:
            p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
    assert any("listening on" in ln for ln in lines), ("server did not listen", residual, lines[-20:])
    return lines, kv.exists()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model")
    ap.add_argument("--cli", default="./sf-ds4-1flash")
    ap.add_argument("--server", help="also check the steered server's KV root handling")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        # a valid matrix: row 0 zero, rows 1..39 the unit vector e_0
        unit = Path(tmp) / "unit.f32"
        row = struct.pack("<f", 1.0) + bytes(4 * (EMBD - 1))
        unit.write_bytes(bytes(4 * EMBD) + row * (LAYERS - 1))
        short = Path(tmp) / "short.f32"
        short.write_bytes(unit.read_bytes()[:-4])
        file_zero = ["--dir-steering-file", str(unit), "--dir-steering-residual", "0"]

        base = run(a.cli, a.model, [])
        assert base.returncode == 0 and completion(base.stdout), base.stderr[-2000:]

        # the no-opt-in refusal keeps precedence over every other diagnostic
        for label, extra in (("default", file_zero),
                             ("default --dir-steering-ffn 1", ["--dir-steering-file", str(unit),
                                                               "--dir-steering-ffn", "1"])):
            r = run(a.cli, a.model, extra)
            assert r.returncode == 1 and not r.stdout and REFUSAL in r.stderr.splitlines(), \
                (label, r.returncode, r.stderr[-2000:])
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

        # unsupported active sites under the opt-in: refused, not silently accepted
        for label, extra in (("file alone (implicit ffn 1)", ["--dir-steering-file", str(unit)]),
                             ("--dir-steering-attn 0.5", file_zero + ["--dir-steering-attn", "0.5"]),
                             ("--dir-steering-ffn 2", file_zero + ["--dir-steering-ffn", "2"])):
            r = run(a.cli, a.model, extra, flag=True)
            assert r.returncode == 1 and not r.stdout and SITE_REFUSAL in r.stderr.splitlines(), \
                (label, r.returncode, r.stderr[-2000:])

        # the residual site starts and names itself; an invalid file fails before any session
        r = run(a.cli, a.model, ["--dir-steering-file", str(unit), "--dir-steering-residual", "4"], flag=True)
        assert r.returncode == 0 and completion(r.stdout), ("residual 4", r.returncode, r.stderr[-2000:])
        assert any(ln.startswith(STEERING_LINE) and SITE in ln and ln.endswith("scale 4") for ln in
                   r.stderr.splitlines()), ("residual 4 startup line", r.stderr[-2000:])
        r = run(a.cli, a.model, ["--dir-steering-file", str(short), "--dir-steering-residual", "4"], flag=True)
        assert r.returncode == 1 and not r.stdout and \
            any("failed to load directional steering vectors" in ln for ln in r.stderr.splitlines()), \
            ("short file", r.returncode, r.stderr[-2000:])

        if a.server:
            lines, exists = serve(a.server, a.model, tmp, 4)
            assert any(KV_REFUSAL in ln for ln in lines) and not exists, ("steered server", lines[-20:])
            lines, _ = serve(a.server, a.model, tmp, 0)
            assert not any(KV_REFUSAL in ln for ln in lines), ("zero-scale server", lines[-20:])
    print("V4.1 steering admission at the CLI: refused verbatim by default (file alone or with "
          "--dir-steering-ffn 1) and with --power 50 under the opt-in; --allow-v41-steering and "
          "DS4_ALLOW_V41_STEERING empty/0/1 each admit a zero-scale file and print the unsteered "
          "completion; file alone, --dir-steering-ffn and --dir-steering-attn refused under the opt-in; "
          "--dir-steering-residual 4 starts and names the site; a truncated file fails"
          + ("; the steered server skips its KV root, the zero-scale one does not" if a.server else "")
          + ": PASS")


if __name__ == "__main__":
    main()
