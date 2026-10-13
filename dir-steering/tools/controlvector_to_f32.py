#!/usr/bin/env python3
"""Convert a GGUF `controlvector` (msuiche's DeepSeek-V4.1-Flash GLP vector) into
the flat `.f32` matrix that `--dir-steering-file` loads, plus a `.json` sidecar
(OpenSpec 401).

The runtime reads `directional_steering_layer_count()` (40) x n_embd (5120)
float32, 819200 bytes. Source rows `direction.1 .. direction.39` land at rows
1..39; row 0 is zero. Every check below runs before either file is written.

Two different tensors are involved, and the sidecar names both:

- the **source hook**, where the vector was derived: `residual_stream_post_layer`,
  the post-layer residual, with alpha 0.5 measured there;
- the **application site**, where ds4 applies it: the weighted HC attention-input
  fold of each layer, after Engram and before the attention norm
  (`v41_attn_input_weighted_fold_post_engram`, `--dir-steering-residual`).

They are not equivalent. ds4 applies `h -= scale*d*dot(d,h)` (projective, same
sign convention as the source). Scales 4 and 8 at the application site were
first-token screening candidates (2026-10-13), not a validated default: the
runtime default is 0. The raw `.f32` carries no provenance; only the sidecar does.

Usage:
    controlvector_to_f32.py IN.gguf [--out OUT.f32] [--n-layers 40] [--n-embd 5120]
    controlvector_to_f32.py --self-check     # offline, no file needed
"""
import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

GGML_F32 = 0
N_EMBD = 5120
N_LAYERS = 40  # directional_steering_layer_count() for DS4_SHAPE_FLASH41
NORM_TOL = 1e-2  # the runtime's DS41_STEERING_NORM_TOL
SOURCE_HOOK = "residual_stream_post_layer"
APPLICATION_SITE = "v41_attn_input_weighted_fold_post_engram"  # ds4.c DS41_STEERING_SITE
INTERVENTION_REVISION = 2  # ds4.c DS41_STEERING_REVISION
DIRECTION_RE = re.compile(r"^direction\.([1-9][0-9]*)$")

# --- minimal GGUF reader -----------------------------------------------------

_FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
        7: "<B", 10: "<Q", 11: "<q", 12: "<d"}


class Refuse(SystemExit):
    def __init__(self, why):
        super().__init__(f"refuse: {why}")


class Gguf:
    def __init__(self, path):
        self.meta = {}
        self.tensors = {}  # name -> (dims, ggml_type, absolute offset)
        self.duplicates = []
        with open(path, "rb") as f:
            blob = f.read()
        self.blob = blob
        self.pos = 0
        if self._bytes(4) != b"GGUF":
            raise Refuse("not a GGUF file (bad magic)")
        self.version = self._u("<I")
        if self.version not in (2, 3):
            raise Refuse(f"GGUF version {self.version}, need 2 or 3")
        ntensors = self._u("<Q")
        nkv = self._u("<Q")
        for _ in range(nkv):
            k = self._str()
            self.meta[k] = self._value(self._u("<I"))
        infos = []
        for _ in range(ntensors):
            name = self._str()
            nd = self._u("<I")
            dims = [self._u("<Q") for _ in range(nd)]
            typ = self._u("<I")
            off = self._u("<Q")
            infos.append((name, dims, typ, off))
        align = self.meta.get("general.alignment", 32)
        data_start = (self.pos + align - 1) // align * align
        for name, dims, typ, off in infos:
            if name in self.tensors:
                self.duplicates.append(name)
            self.tensors[name] = (dims, typ, data_start + off)

    def _bytes(self, n):
        b = self.blob[self.pos:self.pos + n]
        if len(b) != n:
            raise Refuse("truncated header")
        self.pos += n
        return b

    def _u(self, fmt):
        return struct.unpack(fmt, self._bytes(struct.calcsize(fmt)))[0]

    def _str(self):
        return self._bytes(self._u("<Q")).decode("utf-8", "replace")

    def _value(self, t):
        if t == 8:
            return self._str()
        if t == 9:
            et = self._u("<I")
            cnt = self._u("<Q")
            if et == 8:
                return [self._str() for _ in range(cnt)]
            return [self._u(_FMT[et]) for _ in range(cnt)]
        if t == 7:
            return bool(self._u("<B"))
        return self._u(_FMT[t])

    def tensor_f32(self, name):
        dims, typ, off = self.tensors[name]
        if typ != GGML_F32:
            raise Refuse(f"{name}: ggml type {typ}, expected F32")
        n = 1
        for d in dims:
            n *= d
        if off + n * 4 > len(self.blob):
            raise Refuse(f"{name}: storage runs past the end of the file")
        return list(struct.unpack(f"<{n}f", self.blob[off:off + n * 4])), dims


# --- conversion --------------------------------------------------------------

def _expect(meta, key, want):
    got = meta.get(key)
    if got != want:
        raise Refuse(f"{key}={got!r}, need {want!r}")


def validate(g, n_layers, n_embd, norm_tol):
    """Return rows[n_layers][n_embd] or raise Refuse. Nothing is written here."""
    _expect(g.meta, "general.architecture", "controlvector")
    _expect(g.meta, "controlvector.model_hint", "deepseek_v41")
    _expect(g.meta, "glp.hook_point", SOURCE_HOOK)
    if g.duplicates:
        raise Refuse(f"duplicate tensor {g.duplicates[0]}")
    wanted = set(range(1, n_layers))
    seen = {}
    for name in g.tensors:
        m = DIRECTION_RE.match(name)
        if not m:
            raise Refuse(f"unexpected tensor {name!r} (only direction.1..{n_layers - 1})")
        idx = int(m.group(1))
        if idx not in wanted:
            raise Refuse(f"{name} out of range 1..{n_layers - 1}")
        seen[idx] = name
    missing = sorted(wanted - set(seen))
    if missing:
        raise Refuse(f"direction.{missing[0]} missing ({len(missing)} of {len(wanted)} rows absent)")
    count = g.meta.get("controlvector.layer_count")
    if count is not None and count != len(wanted):
        raise Refuse(f"controlvector.layer_count={count}, but {len(wanted)} directions are required")
    ids = g.meta.get("glp.layer_ids_zero_based")
    if ids is not None and sorted(ids) != sorted(wanted):
        raise Refuse("glp.layer_ids_zero_based does not list exactly layers "
                     f"1..{n_layers - 1}")
    rows = [[0.0] * n_embd for _ in range(n_layers)]  # row 0 stays zero
    for idx in sorted(seen):
        name = seen[idx]
        dims, _, _ = g.tensors[name]
        if dims != [n_embd]:
            raise Refuse(f"{name} width {dims}, need [{n_embd}]")
        vec, _ = g.tensor_f32(name)
        if not all(math.isfinite(x) for x in vec):
            raise Refuse(f"{name} has a non-finite value")
        nrm = math.sqrt(sum(x * x for x in vec))
        if abs(nrm - 1.0) > norm_tol:
            raise Refuse(f"{name} L2 norm {nrm:.4f} not unit (tol {norm_tol})")
        rows[idx] = vec
    return rows


def convert(gguf_path, out_path=None, n_layers=N_LAYERS, n_embd=N_EMBD,
            norm_tol=NORM_TOL):
    g = Gguf(gguf_path)
    rows = validate(g, n_layers, n_embd, norm_tol)
    flat = [x for row in rows for x in row]
    data = struct.pack(f"<{len(flat)}f", *flat)
    assert len(data) == n_layers * n_embd * 4, len(data)
    sidecar = {
        "source": {
            "hook": SOURCE_HOOK,
            "alpha_default": g.meta.get("glp.alpha_default"),
            "alpha_note": "measured by the source at its own hook; not a runtime scale",
            "model_hint": g.meta.get("controlvector.model_hint"),
            "layer_count": g.meta.get("controlvector.layer_count"),
            "layer_ids_zero_based": g.meta.get("glp.layer_ids_zero_based"),
            "content_sha256": g.meta.get("glp.content_sha256"),
            "base_model": g.meta.get("glp.base_model"),
            "base_revision": g.meta.get("glp.base_revision"),
            "method": g.meta.get("glp.method"),
            "author": g.meta.get("general.author"),
            "validation": g.meta.get("glp.validation"),
            "gguf_sha256": hashlib.sha256(g.blob).hexdigest(),
        },
        "application": {
            "flag": "--dir-steering-residual",
            "site": APPLICATION_SITE,
            "intervention_revision": INTERVENTION_REVISION,
            "equivalent_to_source_hook": False,
            "site_note": "the weighted HC attention-input fold, after Engram, before the "
                         "attention norm; the source hook is the post-layer residual",
            "sign_convention": "ds4 +scale removes the direction (h -= scale*d*dot(d,h))",
            "scale_default": 0.0,
            "scale_screening_candidates": [4.0, 8.0],
            "scale_note": "first-token screening on 2026-10-13, not a validated default; "
                          "0.5 at this site was a near no-op",
            "refused_at": ["--dir-steering-ffn", "--dir-steering-attn"],
        },
        "f32": {
            "shape": [n_layers, n_embd],
            "bytes": len(data),
            "row_0": "zero",
            "row_n": "source direction.N",
            "sha256": hashlib.sha256(data).hexdigest(),
            "provenance_note": "the raw file carries none of this; keep the sidecar with it",
        },
    }
    out_path = Path(out_path) if out_path else Path(gguf_path).with_suffix(".f32")
    sc_path = out_path.with_suffix(".json")
    out_path.write_bytes(data)
    sc_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2))
    norms = [math.sqrt(sum(x * x for x in r)) for r in rows[1:]]
    return out_path, sc_path, (min(norms), max(norms), len(norms))


# --- minimal GGUF writer (self-check fixture only) ---------------------------

def _w_str(s):
    b = s.encode()
    return struct.pack("<Q", len(b)) + b


def _w_kv(k, t, v):
    out = _w_str(k) + struct.pack("<I", t)
    if t == 8:
        out += _w_str(v)
    elif t == 4:
        out += struct.pack("<I", v)
    elif t == 6:
        out += struct.pack("<f", v)
    else:
        raise ValueError(t)
    return out


def _fixture_row(n, w):
    """direction.N = e_((7N) mod w): distinct per layer, so a permuted or
    duplicated row changes the output."""
    vec = [0.0] * w
    vec[(7 * n) % w] = 1.0
    return vec


def _write_fixture(path, n_dirs, n_embd, *, arch="controlvector",
                   hint="deepseek_v41", hook=SOURCE_HOOK, bad_width=None,
                   drop=(), extra=(), duplicate=None, unit=True, poison=None,
                   layer_count=None, truncate=0):
    kv = [("general.architecture", 8, arch),
          ("controlvector.model_hint", 8, hint),
          ("controlvector.layer_count", 4, n_dirs if layer_count is None else layer_count),
          ("glp.hook_point", 8, hook),
          ("glp.alpha_default", 6, 0.5),
          ("glp.content_sha256", 8, "deadbeef")]
    names = [f"direction.{i}" for i in range(1, n_dirs + 1) if i not in drop]
    names += list(extra)
    if duplicate:
        names.append(duplicate)
    tensors = []
    for name in names:
        w = bad_width if bad_width else n_embd
        m = re.match(r"direction\.0*(\d+)", name)
        n = int(m.group(1)) if m else 1
        vec = _fixture_row(n, w)
        if not unit:
            vec = [x * 3.0 for x in vec]
        if poison is not None and n == 2:
            vec[0] = poison
        tensors.append((name, vec, w))

    header = b"GGUF" + struct.pack("<I", 3) + struct.pack("<Q", len(tensors)) + \
        struct.pack("<Q", len(kv))
    meta = b"".join(_w_kv(*x) for x in kv)
    infos = b""
    off = 0
    for name, vec, w in tensors:
        infos += _w_str(name) + struct.pack("<I", 1) + struct.pack("<Q", w) + \
            struct.pack("<I", GGML_F32) + struct.pack("<Q", off)
        off += w * 4
    pre = header + meta + infos
    pad = (-len(pre)) % 32
    data = b"".join(struct.pack(f"<{len(vec)}f", *vec) for _, vec, _ in tensors)
    blob = pre + b"\x00" * pad + data
    Path(path).write_bytes(blob[:len(blob) - truncate] if truncate else blob)


def _selfcheck():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # 3 directions, n_embd=4 -> output 4 layers x 4
        fx = d / "cv.gguf"
        _write_fixture(fx, n_dirs=3, n_embd=4)
        out, sc, (lo, hi, n) = convert(fx, d / "cv.f32", n_layers=4, n_embd=4)
        data = out.read_bytes()
        assert len(data) == 4 * 4 * 4, len(data)
        vals = list(struct.unpack("<16f", data))
        assert vals[0:4] == [0, 0, 0, 0], vals[0:4]
        for layer in (1, 2, 3):  # direction.N -> row N, e_((7N) mod 4): 3, 2, 1
            row = vals[4 * layer:4 * layer + 4]
            assert row == _fixture_row(layer, 4), (layer, row)
        assert (lo, hi, n) == (1.0, 1.0, 3)
        meta = json.loads(sc.read_text())
        assert meta["source"]["hook"] == SOURCE_HOOK
        assert meta["source"]["alpha_default"] == 0.5
        assert meta["application"]["site"] == APPLICATION_SITE
        assert meta["application"]["intervention_revision"] == INTERVENTION_REVISION
        assert meta["application"]["equivalent_to_source_hook"] is False
        assert meta["application"]["scale_default"] == 0.0
        assert meta["application"]["flag"] == "--dir-steering-residual"
        assert meta["f32"]["shape"] == [4, 4]
        assert meta["f32"]["sha256"] == hashlib.sha256(data).hexdigest()
        assert meta["source"]["gguf_sha256"] == hashlib.sha256(fx.read_bytes()).hexdigest()
        # refusals: nothing written, cause named
        for kwargs, needle in [
            (dict(arch="llama"), "architecture"),
            (dict(hint="glm"), "model_hint"),
            (dict(hook="ffn_out_pre_residual"), "hook_point"),
            (dict(drop=(1,)), "direction.1 missing"),
            (dict(drop=(2,)), "direction.2 missing"),
            (dict(drop=(3,)), "direction.3 missing"),
            (dict(extra=("direction.4",)), "out of range"),
            (dict(extra=("direction.02",)), "unexpected tensor"),
            (dict(extra=("direction.2.weight",)), "unexpected tensor"),
            (dict(duplicate="direction.2"), "duplicate tensor"),
            (dict(layer_count=39), "layer_count"),
            (dict(bad_width=8), "width"),
            (dict(unit=False), "not unit"),
            (dict(poison=float("nan")), "non-finite"),
            (dict(poison=float("inf")), "non-finite"),
            (dict(truncate=8), "past the end"),
        ]:
            bad = d / "bad.gguf"
            _write_fixture(bad, n_dirs=3, n_embd=4, **kwargs)
            try:
                convert(bad, d / "bad.f32", n_layers=4, n_embd=4)
                assert False, f"should have refused {kwargs}"
            except SystemExit as e:
                assert needle in str(e), (needle, str(e))
            assert not (d / "bad.f32").exists() and not (d / "bad.json").exists(), kwargs
    print("controlvector_to_f32.py self-check: OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gguf", nargs="?", help="input controlvector GGUF")
    ap.add_argument("--out", help="output .f32 (default: alongside input)")
    ap.add_argument("--n-layers", type=int, default=N_LAYERS)
    ap.add_argument("--n-embd", type=int, default=N_EMBD)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check or not args.gguf:
        _selfcheck()
        return 0
    out, sc, (lo, hi, n) = convert(args.gguf, args.out, args.n_layers, args.n_embd)
    print(f"wrote {out} ({out.stat().st_size} B) and {sc.name}")
    print(f"{n} directions, row L2 norm in [{lo:.4f}, {hi:.4f}]; "
          f"apply with --dir-steering-residual (site {APPLICATION_SITE}, rev {INTERVENTION_REVISION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
