"""Axis-B KL scorer (OpenSpec 402, design D2).

KL of the steered next-token distribution from base, on the same forced tokens,
read from `--dump-logprobs --logprobs-top-k` (top-k support, an approximation
noted as such). Reported next to an identity-requant noise floor: a KL below the
floor is model equivalence, not a real shift. The embedding-cosine proxy is the
flagged fallback when logprobs are unavailable.

Run `python3 eval/score_kl.py` for the offline self-checks.
"""
import array
import json
import math
import struct
import sys
import tempfile
from pathlib import Path

EPS = 1e-9


def load_dump(path):
    """Per-step {token_id: logprob} from the CLI's --dump-logprobs JSON:
    {"source","prompt_tokens","ctx","top_k","steps":[{"step","selected":
    {"id","text","bytes"},"top_logprobs":[{"token":{"id","text","bytes"},
    "logit","logprob"}]}]}. Keyed by id, so both arms compare the same
    vocabulary entry whatever its text."""
    dump = json.loads(Path(path).read_text())
    return [{e["token"]["id"]: e["logprob"] for e in s["top_logprobs"]}
            for s in dump["steps"]]


def _to_probs(logprob_dict):
    p = {t: math.exp(lp) for t, lp in logprob_dict.items()}
    z = sum(p.values()) or 1.0
    return {t: v / z for t, v in p.items()}


def kl_position(base_lp, steered_lp):
    """KL(base || steered) over the union of top-k support, steered floored by
    EPS where it has no mass (top-k truncation)."""
    p = _to_probs(base_lp)
    q = _to_probs(steered_lp)
    out = 0.0
    for t, pt in p.items():
        if pt <= 0:
            continue
        qt = q.get(t, EPS)
        out += pt * math.log(pt / max(qt, EPS))
    return out


def kl_sequence(base_seq, steered_seq):
    """Mean per-position KL over a forced-token sequence."""
    n = min(len(base_seq), len(steered_seq))
    if n == 0:
        return 0.0
    return sum(kl_position(base_seq[i], steered_seq[i]) for i in range(n)) / n


# --- full-vocabulary forced-prefix KL (OpenSpec 402, task 5.2, design D7) -----
# A reported full KL must use the complete shared vocabulary on identical forced
# prefixes. Empty, nonfinite, duplicate-id or mismatched-support input fails; a
# top-k-only list cannot be passed here and called a full KL.

class KLInputError(ValueError):
    pass


def validate_full_dist(logprob_dict):
    """A single-position full distribution: non-empty, finite, and (as logprobs)
    normalized to ~1. Raises KLInputError otherwise."""
    if not logprob_dict:
        raise KLInputError("empty distribution")
    total = 0.0
    for t, lp in logprob_dict.items():
        if not math.isfinite(lp):
            raise KLInputError(f"non-finite logprob for id {t}")
        total += math.exp(lp)
    if not (0.98 <= total <= 1.02):
        raise KLInputError(f"distribution not full/normalized (sum p = {total:.4f}); "
                           "a top-k slice cannot be a full KL")
    return True


def load_full_dump(path):
    """Full-vocabulary per-step distributions from a dump that carries every
    vocab entry. Rejects duplicate ids within a step. Returns [{id: logprob}]."""
    dump = json.loads(Path(path).read_text())
    out = []
    for s in dump["steps"]:
        d = {}
        for e in s["top_logprobs"]:
            tid = e["token"]["id"]
            if tid in d:
                raise KLInputError(f"duplicate id {tid} in a step")
            d[tid] = e["logprob"]
        out.append(d)
    return out


def kl_full_position(base_lp, steered_lp):
    """KL(base || steered) at one position over the FULL shared vocabulary. Both
    distributions must cover the same token ids (identical support). Accumulates
    in a numerically stable form from log-probabilities."""
    validate_full_dist(base_lp)
    validate_full_dist(steered_lp)
    if base_lp.keys() != steered_lp.keys():
        raise KLInputError("base and steered cover different vocab support")
    out = 0.0
    for t, blp in base_lp.items():
        p = math.exp(blp)
        if p <= 0:
            continue
        out += p * (blp - steered_lp[t])  # p * log(p/q), stable from logprobs
    return max(out, 0.0)


def kl_full_sequence(base_seq, steered_seq):
    """Mean full-vocabulary KL over a forced-token sequence. Lengths must match
    exactly (a shorter/empty sequence fails, never truncates to the shorter)."""
    if len(base_seq) != len(steered_seq):
        raise KLInputError(f"sequence length mismatch: {len(base_seq)} vs {len(steered_seq)}")
    if not base_seq:
        raise KLInputError("empty sequence")
    vals = [kl_full_position(b, s) for b, s in zip(base_seq, steered_seq)]
    return {"mean_kl": sum(vals) / len(vals), "per_position": vals, "n": len(vals)}


# --- dense full-vocab dump (CLI --perplexity-dump, task 5.1) ------------------
# The CLI writes a compact binary: b"DLP1", int32 vocab, int32 steps, then per
# step int32 forced_token_id and vocab float32 log-softmax values. Dense arrays
# (index == token id) avoid a 128k-entry dict per position.

DUMP_MAGIC = b"DLP1"


def load_full_binary(path):
    """Read a --perplexity-dump file into {vocab, forced:[ids], steps:[array('f')]}."""
    data = Path(path).read_bytes()
    if data[:4] != DUMP_MAGIC:
        raise KLInputError(f"bad magic {data[:4]!r}, expected {DUMP_MAGIC!r}")
    vocab, steps = struct.unpack_from("<ii", data, 4)
    if vocab <= 0 or steps < 0:
        raise KLInputError(f"bad header vocab={vocab} steps={steps}")
    off = 12
    row = 4 + vocab * 4
    if len(data) != off + steps * row:
        raise KLInputError(f"size {len(data)} != header {off + steps * row}")
    forced, out = [], []
    for _ in range(steps):
        (fid,) = struct.unpack_from("<i", data, off)
        off += 4
        a = array.array("f")
        a.frombytes(data[off:off + vocab * 4])
        off += vocab * 4
        forced.append(fid)
        out.append(a)
    return {"vocab": vocab, "forced": forced, "steps": out}


def kl_full_dense_position(base_lp, steer_lp):
    """KL(base || steered) over dense full-vocab logprob arrays (index == id)."""
    if len(base_lp) != len(steer_lp):
        raise KLInputError(f"vocab mismatch: {len(base_lp)} vs {len(steer_lp)}")
    if not base_lp:
        raise KLInputError("empty distribution")
    out = 0.0
    for blp, slp in zip(base_lp, steer_lp):
        if not (math.isfinite(blp) and math.isfinite(slp)):
            raise KLInputError("non-finite logprob")
        p = math.exp(blp)
        if p > 0:
            out += p * (blp - slp)
    return max(out, 0.0)


def kl_full_dense_sequence(base_dump, steer_dump):
    """Full-vocab KL over two dense dumps. The forced token ids and vocab must
    match exactly (identical teacher-forced prefix in both arms)."""
    if base_dump["vocab"] != steer_dump["vocab"]:
        raise KLInputError("vocab size differs between arms")
    if base_dump["forced"] != steer_dump["forced"]:
        raise KLInputError("forced token sequences differ between arms")
    b, s = base_dump["steps"], steer_dump["steps"]
    if len(b) != len(s):
        raise KLInputError(f"step count differs: {len(b)} vs {len(s)}")
    if not b:
        raise KLInputError("empty sequence")
    vals = [kl_full_dense_position(bp, sp) for bp, sp in zip(b, s)]
    return {"mean_kl": sum(vals) / len(vals), "per_position": vals, "n": len(vals)}


def report_kl(base_seq, steered_seq, noise_floor):
    kl = kl_sequence(base_seq, steered_seq)
    return {"kl": kl, "noise_floor": noise_floor,
            "above_floor": kl > noise_floor,
            "note": "top-k support approximation of forced-token KL"}


def embedding_cosine_fallback(vec_a, vec_b):
    """Flagged, less-rigorous fallback when logprobs are unavailable."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    na = math.sqrt(sum(a * a for a in vec_a)) or 1.0
    nb = math.sqrt(sum(b * b for b in vec_b)) or 1.0
    return {"cosine": dot / (na * nb), "note": "FALLBACK proxy, not KL"}


def _selfcheck():
    d = {"a": math.log(0.5), "b": math.log(0.3), "c": math.log(0.2)}
    assert abs(kl_position(d, d)) < 1e-9, "KL(p||p) must be ~0"
    assert abs(kl_sequence([d, d], [d, d])) < 1e-9
    shifted = {"a": math.log(0.2), "b": math.log(0.3), "c": math.log(0.5)}
    assert kl_position(d, shifted) > 0
    rep = report_kl([d], [shifted], noise_floor=0.131)
    assert "kl" in rep and rep["noise_floor"] == 0.131
    assert abs(embedding_cosine_fallback([1, 0], [1, 0])["cosine"] - 1.0) < 1e-9
    # the dump as ds4_cli.c writes it (run_logprobs_dump, json_write_token)
    sample = ('{\n  "source":"ds4",\n  "prompt_tokens":5,\n  "ctx":512,\n  "top_k":2,\n'
              '  "steps":[\n    {"step":0,"selected":{"id":7,"text":"a","bytes":[97]},'
              '"top_logprobs":[{"token":{"id":7,"text":"a","bytes":[97]},"logit":1.5,"logprob":-0.1},'
              '{"token":{"id":9,"text":"b","bytes":[98]},"logit":0.5,"logprob":-2.4}]},\n'
              '    {"step":1,"selected":{"id":9,"text":"b","bytes":[98]},'
              '"top_logprobs":[{"token":{"id":9,"text":"b","bytes":[98]},"logit":2,"logprob":-0.05}]}\n'
              '  ]\n}\n')
    tmp = Path(tempfile.mkdtemp()) / "lp.json"
    tmp.write_text(sample)
    seq = load_dump(tmp)
    assert seq == [{7: -0.1, 9: -2.4}, {9: -0.05}], seq
    assert abs(kl_sequence(seq, seq)) < 1e-9

    # --- full-vocab KL regressions (task 5.2, design D7) ---------------------
    # self-KL is ~0
    full = {1: math.log(0.5), 2: math.log(0.3), 3: math.log(0.2)}
    assert abs(kl_full_position(full, full)) < 1e-12
    # the near-tie swap: 0.500001 <-> 0.499999 over a 2-token full vocab is ~0,
    # NOT the ~0.69 (or ~20.7) a top-1 selection would fabricate.
    base = {1: math.log(0.500001), 2: math.log(0.499999)}
    steer = {1: math.log(0.499999), 2: math.log(0.500001)}
    assert kl_full_position(base, steer) < 1e-6, kl_full_position(base, steer)
    # taking each distribution's top-1 and calling it full KL is rejected: a
    # degenerate {1:1.0} vs {2:1.0} is different support (and would be a huge KL)
    try:
        kl_full_position({1: math.log(1.0)}, {2: math.log(1.0)})
        assert False, "different support must fail"
    except KLInputError as e:
        assert "support" in str(e)
    # a top-k slice (sum p < 1) cannot pass as a full distribution
    try:
        validate_full_dist({1: math.log(0.4), 2: math.log(0.3)})
        assert False
    except KLInputError as e:
        assert "top-k" in str(e) or "normalized" in str(e)
    # empty / unequal-length sequences fail, never truncate
    try:
        kl_full_sequence([full], [full, full])
        assert False
    except KLInputError as e:
        assert "length mismatch" in str(e)
    try:
        kl_full_sequence([], [])
        assert False
    except KLInputError:
        pass
    # duplicate ids within a step are rejected on load
    dupe = ('{"steps":[{"top_logprobs":['
            '{"token":{"id":5},"logprob":-0.1},'
            '{"token":{"id":5},"logprob":-0.2}]}]}')
    tmp2 = Path(tempfile.mkdtemp()) / "dup.json"
    tmp2.write_text(dupe)
    try:
        load_full_dump(tmp2)
        assert False
    except KLInputError as e:
        assert "duplicate" in str(e)
    # nonfinite logprob fails validation
    try:
        kl_full_position({1: 0.0, 2: float("-inf"), 3: float("nan")},
                         {1: 0.0, 2: 0.0, 3: 0.0})
        assert False
    except KLInputError:
        pass
    # a real near-equal full dist gives a small positive KL
    s2 = {1: math.log(0.45), 2: math.log(0.35), 3: math.log(0.20)}
    r = kl_full_sequence([full], [s2])
    assert r["n"] == 1 and r["mean_kl"] > 0 and r["mean_kl"] < 0.1, r

    # --- dense dump round-trip (task 5.1 format) -----------------------------
    def _mk_dump(path, vocab, steps):
        # steps: list of (forced_id, [logprobs])
        buf = bytearray(DUMP_MAGIC)
        buf += struct.pack("<ii", vocab, len(steps))
        for fid, lps in steps:
            buf += struct.pack("<i", fid)
            buf += array.array("f", lps).tobytes()
        Path(path).write_bytes(buf)

    lp = [math.log(0.5), math.log(0.3), math.log(0.2)]
    with tempfile.TemporaryDirectory() as d:
        bp, sp = Path(d) / "base.bin", Path(d) / "steer.bin"
        _mk_dump(bp, 3, [(1, lp), (2, lp)])
        _mk_dump(sp, 3, [(1, lp), (2, lp)])
        bd, sd = load_full_binary(bp), load_full_binary(sp)
        assert bd["vocab"] == 3 and bd["forced"] == [1, 2] and len(bd["steps"]) == 2
        # self-KL across identical dumps is ~0
        rr = kl_full_dense_sequence(bd, sd)
        assert rr["n"] == 2 and rr["mean_kl"] < 1e-6, rr
        # a shifted steered dump gives positive KL
        lp2 = [math.log(0.2), math.log(0.3), math.log(0.5)]
        _mk_dump(sp, 3, [(1, lp2), (2, lp2)])
        rr = kl_full_dense_sequence(bd, load_full_binary(sp))
        assert rr["mean_kl"] > 0, rr
        # forced-sequence mismatch between arms fails
        _mk_dump(sp, 3, [(9, lp), (2, lp)])
        try:
            kl_full_dense_sequence(bd, load_full_binary(sp))
            assert False
        except KLInputError as e:
            assert "forced" in str(e)
        # a truncated file is rejected
        (Path(d) / "trunc.bin").write_bytes(bp.read_bytes()[:-4])
        try:
            load_full_binary(Path(d) / "trunc.bin")
            assert False
        except KLInputError as e:
            assert "size" in str(e)
    print("score_kl.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
