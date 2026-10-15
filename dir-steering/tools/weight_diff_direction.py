"""408 weight-diff refusal-direction recovery (offline, numpy, no model, no GPU).

ΔW = W_base - W_abliterated at a residual-writing site is rank-one along the removed
direction r: W' = (I - r r^T) W  =>  ΔW = r (r^T W). The top left singular vector of
ΔW (in the output/residual space) recovers r per layer. Primary sites are the two dense
Q8_0 projections attn_output_b [8192,5120] and ffn_down_shexp [2304,5120]; the residual
(output) dim is ne1=5120, directly comparable to the 402 vector.

Run with numpy from the disposable venv:
  /tmp/sfweightdiff/bin/python weight_diff_direction.py --selfcheck
  /tmp/sfweightdiff/bin/python weight_diff_direction.py <base.gguf> <abl.gguf> [--site attn_output_b]
"""
import struct
import sys

import numpy as np

GGML_TYPE = {0: "F32", 1: "F16", 8: "Q8_0", 10: "Q2_K", 16: "IQ2_XXS", 30: "BF16"}
N_LAYERS = 40
N_EMBD = 5120
SITES = {"attn_output_b": (8192, 5120), "ffn_down_shexp": (2304, 5120)}


def _rd(f, fmt):
    return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))[0]


def _rd_str(f):
    return f.read(_rd(f, "Q")).decode("utf-8", "replace")


def _skip_value(f, vt, alignment_box):
    sz = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    if vt in sz:
        f.read(sz[vt])
    elif vt == 8:
        _rd_str(f)
    elif vt == 9:
        et = _rd(f, "I")
        cnt = _rd(f, "Q")
        for _ in range(cnt):
            _skip_value(f, et, alignment_box)
    else:
        raise ValueError("bad value type %d" % vt)


def read_index(path):
    """Return (tensors, data_start). tensors[name] = (type_str, dims, abs_offset, nbytes)."""
    with open(path, "rb") as f:
        assert f.read(4) == b"GGUF"
        _rd(f, "I")  # version
        n_tensors = _rd(f, "Q")
        n_kv = _rd(f, "Q")
        alignment = 32
        for _ in range(n_kv):
            key = _rd_str(f)
            vt = _rd(f, "I")
            if key == "general.alignment" and vt == 4:
                alignment = _rd(f, "I")
            else:
                _skip_value(f, vt, None)
        tensors = {}
        for _ in range(n_tensors):
            name = _rd_str(f)
            nd = _rd(f, "I")
            dims = [_rd(f, "Q") for _ in range(nd)]
            t = _rd(f, "I")
            off = _rd(f, "Q")
            tensors[name] = [GGML_TYPE.get(t, "T%d" % t), dims, off, None]
        pos = f.tell()
        data_start = (pos + alignment - 1) // alignment * alignment
    return tensors, data_start, alignment


def q8_0_nbytes(nelem):
    return (nelem // 32) * 34


def read_raw(path, abs_off, nbytes):
    with open(path, "rb") as f:
        f.seek(abs_off)
        return f.read(nbytes)


def dequant_q8_0(raw, nelem):
    nb = nelem // 32
    flat = np.frombuffer(raw, dtype=np.uint8)[: nb * 34].reshape(nb, 34)
    d = flat[:, :2].copy().view(np.float16).reshape(nb).astype(np.float32)
    qs = flat[:, 2:].view(np.int8).astype(np.float32)
    return (qs * d[:, None]).reshape(nelem)


def recover_direction(dW, iters=8):
    """Top left singular vector of dW [n_out, n_in] and its singular-value share.
    Power iteration on dW dW^T; exact for a rank-one dW."""
    n_out = dW.shape[0]
    x = np.ones(n_out, dtype=np.float32)
    x /= np.linalg.norm(x)
    for _ in range(iters):
        y = dW.T @ x
        x = dW @ y
        nx = np.linalg.norm(x)
        if nx < 1e-20:
            return np.zeros(n_out, dtype=np.float32), 0.0
        x /= nx
    v = dW.T @ x
    sigma1 = np.linalg.norm(v)
    fro2 = float(np.sum(dW * dW))
    share = (sigma1 * sigma1) / fro2 if fro2 > 0 else 0.0
    return x.astype(np.float32), float(share)


def _selfcheck():
    rng = np.random.default_rng(0)
    r0 = rng.standard_normal(5120).astype(np.float32)
    r0 /= np.linalg.norm(r0)
    u0 = rng.standard_normal(8192).astype(np.float32)
    dW = np.outer(r0, u0).astype(np.float32)  # exact rank-one
    r, share = recover_direction(dW)
    cos = abs(float(r @ r0))
    assert cos > 0.999, cos
    assert share > 0.999, share
    # add a small rank-2 perturbation -> share drops below 1
    dW2 = dW + 0.1 * np.outer(rng.standard_normal(5120), rng.standard_normal(8192)).astype(np.float32)
    _, share2 = recover_direction(dW2)
    assert share2 < 0.999, share2
    # Q8_0 dequant round-trip: build blocks with known d and qs
    nb = 4
    qs = rng.integers(-100, 100, size=(nb, 32)).astype(np.int8)
    d = np.array([0.5, 1.0, 2.0, 0.25], dtype=np.float16)
    raw = b"".join(d[i].tobytes() + qs[i].tobytes() for i in range(nb))
    deq = dequant_q8_0(raw, nb * 32).reshape(nb, 32)
    ref = qs.astype(np.float32) * d.astype(np.float32)[:, None]
    assert np.allclose(deq, ref, atol=1e-3), np.abs(deq - ref).max()
    print("weight_diff_direction self-check: OK (rank-1 cos>0.999, share drop, Q8_0 round-trip)")


def sample_identical(base, ds_b, tb, abl, ds_a, ta, name, nbytes, probe=4 << 20):
    """Base-match sanity: compare the first and last `probe` bytes of an un-edited
    tensor. Returns True if both ends match (strong evidence it is untouched)."""
    if name not in tb or name not in ta:
        return None
    ob, oa = ds_b + tb[name][2], ds_a + ta[name][2]
    head = read_raw(base, ob, probe) == read_raw(abl, oa, probe)
    tail_off = max(0, nbytes - probe)
    tail = read_raw(base, ob + tail_off, min(probe, nbytes)) == \
        read_raw(abl, oa + tail_off, min(probe, nbytes))
    return bool(head and tail)


def run_diff(base, abl, site):
    ne0, ne1 = SITES[site]
    tb, ds_b, _ = read_index(base)
    ta, ds_a, _ = read_index(abl)
    nbytes = q8_0_nbytes(ne0 * ne1)
    out = []
    for il in range(N_LAYERS):
        name = "blk.%d.%s.weight" % (il, site)
        if name not in tb or name not in ta:
            out.append((il, "missing", None, 0.0))
            continue
        # comparability: same ggml type and shape, else the diff is not an edit
        if tb[name][0] != "Q8_0" or ta[name][0] != tb[name][0] or ta[name][1] != tb[name][1]:
            out.append((il, "incomparable:%s/%s" % (tb[name][0], ta[name][0]), None, 0.0))
            continue
        rb = read_raw(base, ds_b + tb[name][2], nbytes)
        ra = read_raw(abl, ds_a + ta[name][2], nbytes)
        if rb == ra:
            out.append((il, True, None, 0.0))
            continue
        Wb = dequant_q8_0(rb, ne0 * ne1).reshape(ne1, ne0)
        Wa = dequant_q8_0(ra, ne0 * ne1).reshape(ne1, ne0)
        r, share = recover_direction(Wb - Wa)
        out.append((il, False, r, share))
    return out


def main():
    import array
    import statistics
    if "--selfcheck" in sys.argv:
        _selfcheck()
        return
    base, abl = sys.argv[1], sys.argv[2]
    site = "attn_output_b"
    if "--site" in sys.argv:
        site = sys.argv[sys.argv.index("--site") + 1]
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None

    # base-match sanity: an un-edited tensor (token embeddings) must be identical
    tb, ds_b, _ = read_index(base)
    ta, ds_a, _ = read_index(abl)
    emb = "token_embd.weight"
    san = None
    if emb in tb and emb in ta:
        nelem = 1
        for d in tb[emb][1]:
            nelem *= d
        san = sample_identical(base, ds_b, tb, abl, ds_a, ta, emb, nelem * 2)
    print("base-match sanity (token_embd identical ends): %s" % san)

    res = run_diff(base, abl, site)
    n_ident = sum(1 for x in res if x[1] is True)
    edited = [x for x in res if x[1] is False]
    skipped = [x for x in res if isinstance(x[1], str)]
    print("site=%s layers=%d edited=%d identical=%d skipped=%d" %
          (site, len(res), len(edited), n_ident, len(skipped)))
    for il, st, _, _ in skipped:
        print("  layer %2d %s" % (il, st))

    a = array.array("f")
    a.frombytes(open("dir-steering/out/v41-msuiche.f32", "rb").read())
    v402 = np.array(a, dtype=np.float32).reshape(N_LAYERS, N_EMBD)
    emit = np.zeros((N_LAYERS, N_EMBD), dtype=np.float32)
    cosines, rows = [], []
    for il, st, r, share in res:
        if st is not False or r is None:
            continue
        ref = v402[il]
        nref = float(np.linalg.norm(ref))
        cos = float(r @ ref) / (np.linalg.norm(r) * nref) if nref > 1e-6 else float("nan")
        cosines.append(cos)
        rows.append((il, r))
        emit[il] = r if cos >= 0 else -r
        print("  layer %2d rank1_share=%.3f cos_to_402=%+.3f" % (il, share, cos))
    if cosines:
        ac = [abs(c) for c in cosines if c == c]
        print("  |cos| to 402: median=%.3f min=%.3f max=%.3f (n=%d)" %
              (statistics.median(ac), min(ac), max(ac), len(ac)))
        # single-global-r diagnostic: mutual cosine among recovered rows
        mut = []
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                ri, rj = rows[i][1], rows[j][1]
                mut.append(abs(float(ri @ rj) / (np.linalg.norm(ri) * np.linalg.norm(rj))))
        if mut:
            print("  recovered mutual |cos| (global-r?): median=%.3f min=%.3f max=%.3f" %
                  (statistics.median(mut), min(mut), max(mut)))
    if out_path:
        array.array("f", emit.reshape(-1).tolist()).tofile(open(out_path, "wb"))
        print("wrote candidate: %s" % out_path)


if __name__ == "__main__":
    main()
