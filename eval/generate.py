"""Generation driver (OpenSpec 402, tasks group 2).

Drives the child CLI at greedy temp 0 with one fixed decoding, for the base and
steered arms, and saves raw JSON per prompt. The reasoning arm flips --think; the
multimodal arm renders the prompt to an image and goes through the vision tower
(server path, since images attach in chat, not via a one-shot -p flag).

Model runs are NOT part of authoring; `python3 eval/generate.py` runs the offline
self-checks (argv shape, stdout parsing, image render).
"""
import re
import sys
from pathlib import Path

import common

# The CLI prints input-processing progress, then the completion, then a
# "ds4: <stat>:" perf line. Grab what sits between.
_PROGRESS = re.compile(r"input tokens:.*\(100\.0%\)\s*$")
_PERF = re.compile(r"^ds4: (prefill|generation|decode)\b")


def extract_completion(stdout):
    """Pull the model's answer out of CLI stdout."""
    lines = stdout.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if _PROGRESS.search(ln):
            start = i + 1
    body = []
    for ln in lines[start:]:
        if _PERF.match(ln) or ln.startswith("ds4: prefill:"):
            break
        body.append(ln)
    return "\n".join(body).strip()


def gen(prompt, *, steer=None, residual=0.0, think=True,
        max_tokens=None, logprobs=None, system=None,
        decay_tokens=None, decay_final=None, think_decay_tokens=None,
        cycle_peak=None):
    """One generation; returns a record dict. Spawns the child (model-backed).
    logprobs=PATH names the file the CLI's --dump-logprobs JSON is written to.
    decay_* (403) turn the steered arm's constant scale into a decay schedule;
    cycle_peak (403c) turns that decay into an oscillation."""
    argv = common.build_cli(prompt, steer=steer, residual=residual, think=think,
                            max_tokens=max_tokens, logprobs=logprobs, system=system,
                            decay_tokens=decay_tokens, decay_final=decay_final,
                            think_decay_tokens=think_decay_tokens, cycle_peak=cycle_peak)
    res = common.execute(argv)
    return {
        "prompt": prompt,
        "arm": "steered" if steer is not None else "base",
        "residual": residual, "think": think,
        "logprobs": None if logprobs is None else str(logprobs),
        "completion": extract_completion(res["stdout"]),
        "returncode": res["returncode"],
        "raw_stdout": res["stdout"], "raw_stderr": res["stderr"],
    }


def render_prompt_image(text, out_path):
    """Render prompt text to a PNG for the multimodal arm. Needs Pillow (install
    into a /tmp venv, never globally)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("multimodal arm needs Pillow: "
                           "/tmp/sfeval/bin/pip install pillow")
    W = 1024
    margin, lh = 24, 28
    wrapped = _wrap(text, 72)
    H = margin * 2 + lh * max(1, len(wrapped))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for i, line in enumerate(wrapped):
        d.text((margin, margin + i * lh), line, fill="black", font=font)
    img.save(out_path)
    return out_path


def _wrap(text, width):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


NEUTRAL_IMAGE_INSTRUCTION = "Read the instruction in the image and respond to it."


def _data_uri(image_path):
    """A `data:image/<mime>;base64,<...>` URI, the shape ds4_server parses
    (server_image_inputs_push_data_uri: png/jpeg/jpg)."""
    import base64
    p = Path(image_path)
    ext = p.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


def image_request(image_path, *, instruction=NEUTRAL_IMAGE_INSTRUCTION):
    """OpenAI-style chat payload for the vision arm, matching the ds4 server
    contract: a content part `{"type":"image_url","image_url":{"url":<data URI>}}`
    plus a neutral text instruction. The rendered prompt lives in the IMAGE; the
    text channel never carries the prompt text (design D8). The server must run
    with `--vision` to accept the image. The HTTP send is model-backed; this keeps
    the checkable shape in one place (see docs/CLIENTS)."""
    return {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": _data_uri(image_path)}},
        {"type": "text", "text": instruction}]}],
        "temperature": 0, "max_tokens": common.DECODE["max_tokens"]}


def _selfcheck():
    # Real captured shape: common.execute separates streams, so stdout is the
    # clean completion (progress and the perf line go to stderr). This is the
    # photosynthesis answer from the 2026-10-13 smoke run, verbatim.
    real_stdout = ("Photosynthesis is the process by which green plants, algae, "
                   "and some bacteria convert light energy, carbon dioxide, and "
                   "water into glucose and oxygen.\n")
    assert extract_completion(real_stdout).startswith("Photosynthesis is the process")
    assert extract_completion(real_stdout).endswith("glucose and oxygen.")
    # combined-stream shape (2>&1): progress + perf lines are stripped
    sample = ("processing 17 input tokens: 16/17 (94.1%)\n"
              "processing 17 input tokens: 17/17 (100.0%)\n"
              "Ciao! Sto bene, grazie.\n"
              "ds4: prefill: 5.12 t/s, generation: 8.01 t/s\n")
    assert extract_completion(sample) == "Ciao! Sto bene, grazie.", repr(extract_completion(sample))
    # multi-line completion
    s2 = ("input tokens: 3/3 (100.0%)\nline one\nline two\n"
          "ds4: generation: 9 t/s\n")
    assert extract_completion(s2) == "line one\nline two"
    # a failed/empty run yields an EMPTY completion, never a fabricated answer
    assert extract_completion("") == ""
    assert extract_completion("processing 5 input tokens: 5/5 (100.0%)\n"
                              "ds4: prefill: 1 t/s, generation: 0 t/s\n") == ""
    # argv shape: base vs steered differ only by steering
    b = common.build_cli("q")
    s = common.build_cli("q", steer="/tmp/v.f32", residual=1.5)
    assert common.arms_differ_only_by_steering(b, s)
    # image payload shape (task 7.1): image_url + data URI, matching the server
    import tempfile
    png = Path(tempfile.mkdtemp()) / "p.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    req = image_request(png)
    part = req["messages"][0]["content"]
    assert part[0]["type"] == "image_url", part[0]
    assert part[0]["image_url"]["url"].startswith("data:image/png;base64,"), part[0]
    # the text channel carries only the neutral instruction, never the prompt
    assert part[1]["type"] == "text" and part[1]["text"] == NEUTRAL_IMAGE_INSTRUCTION
    harmful = "render-only harmful prompt text"
    assert all(harmful not in str(p) for p in part), "prompt leaked into the payload"
    # jpeg extension -> jpeg mime
    jpg = Path(tempfile.mkdtemp()) / "p.jpg"
    jpg.write_bytes(b"\xff\xd8\xff fake")
    assert image_request(jpg)["messages"][0]["content"][0]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,")
    assert _wrap("a b c d e", 3) == ["a b", "c d", "e"], _wrap("a b c d e", 3)
    print("generate.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
