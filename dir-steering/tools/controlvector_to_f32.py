#!/usr/bin/env python3
"""Convert a GGUF `controlvector` (e.g. msuiche's DeepSeek-V4.1-Flash GLP) into
the flat `.f32` that ds4's `--dir-steering-file` loads, plus a `.json` sidecar
(OpenSpec 401).

The runtime reads `directional_steering_layer_count()` (40) x n_embd (5120)
float32, one normalized direction per normal layer. msuiche ships `direction.1 ..
direction.39`; `direction.N` maps to layer N and layer 0 is zeros, so the output
is 40 x 5120 x 4 = 819200 B. ds4 applies `y -= scale*d*dot(d,y)` (projective), so
`--dir-steering-residual +alpha` reproduces msuiche's `h -= alpha*(h.d)d`.

This vector's hook is `residual_stream_post_layer`; it is WRONG at the ffn/attn
hooks. Apply it only with `--dir-steering-residual` (401's site).

Usage:
    controlvector_to_f32.py IN.gguf [--out OUT.f32] [--n-layers 40] [--n-embd 5120]
    controlvector_to_f32.py --self-check     # offline, no file needed
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

GGML_F32 = 0
N_EMBD = 5120
N_LAYERS = 40  # directional_steering_layer_count() for DS4_SHAPE_FLASH41

# --- minimal GGUF reader -----------------------------------------------------

_FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
        7: "<B", 10: "<Q", 11: "<q", 12: "<d"}


class Gguf:
    def __init__(self, path):
        self.meta = {}
        self.tensors = {}  # name -> (dims, ggml_type, offset)
        with open(path, "rb") as f:
            blob = f.read()
        self.blob = blob
        self.pos = 0
        if self._bytes(4) != b"GGUF":
            raise ValueError("not a GGUF file (bad magic)")
        self.version = self._u("<I")
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
            self.tensors[name] = (dims, typ, data_start + off)

    def _bytes(self, n):
        b = self.blob[self.pos:self.pos + n]
        self.pos += n
        return b

    def _u(self, fmt):
        v = struct.unpack(fmt, self._bytes(struct.calcsize(fmt)))[0]
        return v

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
            raise ValueError(f"{name}: ggml type {typ}, expected F32")
        n = 1
        for d in dims:
            n *= d
        return list(struct.unpack(f"<{n}f", self.blob[off:off + n * 4])), dims


# --- conversion --------------------------------------------------------------

def convert(gguf_path, out_path=None, n_layers=N_LAYERS, n_embd=N_EMBD,
            norm_tol=1e-2):
    g = Gguf(gguf_path)
    arch = g.meta.get("general.architecture")
    if arch != "controlvector":
        raise SystemExit(f"refuse: general.architecture={arch!r}, need 'controlvector'")
    hint = g.meta.get("controlvector.model_hint")
    if hint != "deepseek_v41":
        raise SystemExit(f"refuse: controlvector.model_hint={hint!r}, need 'deepseek_v41'")
    hook = g.meta.get("glp.hook_point")
    if hook != "residual_stream_post_layer":
        raise SystemExit(f"refuse: glp.hook_point={hook!r}, need 'residual_stream_post_layer'")
    dirs = {n: t for n, t in g.tensors.items() if n.startswith("direction.")}
    if "direction.1" not in dirs:
        raise SystemExit("refuse: direction.1 missing")

    rows = [[0.0] * n_embd for _ in range(n_layers)]  # layer 0 stays zeros
    norms = []
    for name in dirs:
        idx = int(name.split(".")[1])
        if not (1 <= idx <= n_layers - 1):
            raise SystemExit(f"refuse: {name} out of range 1..{n_layers - 1}")
        vec, dims = g.tensor_f32(name)
        if dims != [n_embd]:
            raise SystemExit(f"refuse: {name} width {dims}, need [{n_embd}]")
        nrm = math.sqrt(sum(x * x for x in vec))
        norms.append(nrm)
        if abs(nrm - 1.0) > norm_tol:
            raise SystemExit(f"refuse: {name} L2 norm {nrm:.4f} not unit (tol {norm_tol})")
        rows[idx] = vec

    out_path = Path(out_path) if out_path else Path(gguf_path).with_suffix(".f32")
    flat = [x for row in rows for x in row]
    data = struct.pack(f"<{len(flat)}f", *flat)
    assert len(data) == n_layers * n_embd * 4, len(data)
    out_path.write_bytes(data)

    sidecar = {
        "hook": hook,
        "apply_with": "--dir-steering-residual",
        "wrong_at": ["--dir-steering-ffn", "--dir-steering-attn"],
        "alpha_default": g.meta.get("glp.alpha_default"),
        "model_hint": hint,
        "layer_count": g.meta.get("controlvector.layer_count"),
        "layer_ids_zero_based": g.meta.get("glp.layer_ids_zero_based"),
        "content_sha256": g.meta.get("glp.content_sha256"),
        "base_model": g.meta.get("glp.base_model"),
        "base_revision": g.meta.get("glp.base_revision"),
        "method": g.meta.get("glp.method"),
        "author": g.meta.get("general.author"),
        "validation": g.meta.get("glp.validation"),
        "f32_shape": [n_layers, n_embd],
        "f32_sha256": hashlib.sha256(data).hexdigest(),
        "sign_convention": "ds4 +scale removes the direction (h -= scale*(h.d)d)",
        "caveats": [
            "alpha is NON-monotone: 0.5 is the knee; 1.0 code-switches (zh); 2.0 regresses.",
            "layers 1-6 sit below the null gate; do not raise alpha blindly (see 403/405).",
        ],
    }
    sc_path = out_path.with_suffix(".json")
    sc_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2))
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


def _write_fixture(path, n_dirs, n_embd, *, arch="controlvector",
                   hint="deepseek_v41", hook="residual_stream_post_layer",
                   bad_width=None, drop_first=False, unit=True):
    kv = [("general.architecture", 8, arch),
          ("controlvector.model_hint", 8, hint),
          ("controlvector.layer_count", 4, n_dirs),
          ("glp.hook_point", 8, hook),
          ("glp.alpha_default", 6, 0.5),
          ("glp.content_sha256", 8, "deadbeef")]
    names = []
    for i in range(1, n_dirs + 1):
        if drop_first and i == 1:
            continue
        names.append(f"direction.{i}")
    tensors = []
    for i, name in enumerate(names):
        w = bad_width if bad_width else n_embd
        # a known pattern: direction.N row = [N, 0, 0, ...] then normalized
        vec = [0.0] * w
        vec[0] = float(int(name.split(".")[1]))
        if unit:
            nrm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vec = [x / nrm for x in vec]
        else:
            vec = [x * 3.0 for x in vec]  # non-unit
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
    align = 32
    pad = (-len(pre)) % align
    data = b"".join(struct.pack(f"<{len(vec)}f", *vec) for _, vec, _ in tensors)
    Path(path).write_bytes(pre + b"\x00" * pad + data)


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
        # layer 0 zeros; layer N row[0] == 1.0 (normalized [N,0,0,0] -> [1,0,0,0])
        assert vals[0:4] == [0, 0, 0, 0], vals[0:4]
        assert abs(vals[4] - 1.0) < 1e-6 and vals[5:8] == [0, 0, 0]  # direction.1
        assert abs(vals[8] - 1.0) < 1e-6  # direction.2 -> layer 2
        assert abs(vals[12] - 1.0) < 1e-6  # direction.3 -> layer 3
        meta = json.loads(sc.read_text())
        assert meta["hook"] == "residual_stream_post_layer"
        assert meta["apply_with"] == "--dir-steering-residual"
        assert meta["f32_shape"] == [4, 4]
        # refusals (task 1.2)
        for kwargs, needle in [
            (dict(arch="llama"), "architecture"),
            (dict(hint="glm"), "model_hint"),
            (dict(hook="ffn_out_pre_residual"), "hook_point"),
            (dict(drop_first=True), "direction.1 missing"),
            (dict(bad_width=8), "width"),
            (dict(unit=False), "not unit"),
        ]:
            bad = d / "bad.gguf"
            _write_fixture(bad, n_dirs=3, n_embd=4, **kwargs)
            try:
                convert(bad, d / "bad.f32", n_layers=4, n_embd=4)
                assert False, f"should have refused {kwargs}"
            except SystemExit as e:
                assert needle in str(e), (needle, str(e))
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
    print(f"{n} directions, row L2 norm in [{lo:.4f}, {hi:.4f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
