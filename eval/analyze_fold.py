"""Offline gates over a per-prompt fold capture (409 D2) and the arm-2 target calibration.

  python3 eval/analyze_fold.py --capture eval/out/capture/base --out eval/out/capture/base/report.json
  python3 eval/analyze_fold.py --capture eval/out/capture/base --native dir-steering/out/v41-native-refusal.f32
  python3 eval/analyze_fold.py --target-from eval/out/capture/base --direction F.f32 --scale 7 --class B \\
      [--layers 9-39] [--under eval/out/capture/fused7]
  python3 eval/analyze_fold.py --self-check

G1 Fisher separation of A (resist) vs B (opened) in the msuiche/abl_perp plane and the
span with dealignai; G2 detector quality of floor-resist (AUC, threshold at the floor,
benign FPR, leave-one-out AUC); G3 the native direction's cosine to msuiche. Pure
Python: the capture is ~100 prompts x 40 layers, a few thousand dot products per layer.
"""
import argparse
import array
import json
import math
import operator
import random
import statistics
import sys
from pathlib import Path

D = 5120
N_LAYERS = 40
BAND = range(9, 40)           # L9-39, where the refusal is decided
DEALIGN_BAND = range(10, 37)  # L10-36, dealignai's edited band
FLOOR = (6, 372, 426)
TARGETS = (23, 27)

# design.md D2, pre-registered
G1_J_PLANE_MIN = 1.0
G2_MAX_EARLY_LAYER = 20
G2_AUC_AB_MIN = 0.90
G2_AUC_ABENIGN_MIN = 0.95
G2_FPR_MAX = 0.10
G2_MIN_LAYERS = 30
G3_COS_MAX = 0.90
C_OUTSIDE_MIN = 14            # of L10-36, for choosing C as tau2's class
SPREAD_FRACTION = 0.5         # D6: IQR over the band above half the median = one scalar is wrong

REFS = {
    "msuiche": "dir-steering/vectors/v41-msuiche.f32",
    "audreyt": "dir-steering/vectors/v41-abliteration-attn.f32",
    "fused": "dir-steering/vectors/v41-fused-msuiche-audreyt-denoise.f32",
    "dealignai": "dir-steering/vectors/v41-dealignai-wo.f32",
    "abl_perp": "dir-steering/out/v41-fusedmsuiche-abl-ortho.f32",
    "floor_resist": "dir-steering/out/v41-floor-resist.f32",
}


def dot(a, b):
    return sum(map(operator.mul, a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def load_rows(path):
    a = array.array("f")
    a.frombytes(Path(path).read_bytes())
    if len(a) != N_LAYERS * D:
        raise SystemExit(f"{path}: {len(a)} floats, expected {N_LAYERS * D}")
    return [a[L * D:(L + 1) * D] for L in range(N_LAYERS)]


def gram_schmidt(vs):
    """Orthonormalize in order; a zero (or dependent) vector stays zero."""
    out = []
    for v in vs:
        w = list(v)
        for e in out:
            if e is not None:
                c = dot(e, w)
                w = [x - c * y for x, y in zip(w, e)]
        n = norm(w)
        out.append([x / n for x in w] if n > 1e-6 else None)
    return out


def solve(S, d):
    """Gauss-Jordan for a k x k system (k <= 3)."""
    k = len(d)
    M = [list(S[i]) + [d[i]] for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(k):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][k] / M[i][i] for i in range(k)]


def fisher(XA, XB):
    """(muA-muB)^T Sw^-1 (muA-muB), pooled within-class covariance, 1e-9 on the diagonal."""
    k = len(XA[0])
    mA = [statistics.fmean(x[i] for x in XA) for i in range(k)]
    mB = [statistics.fmean(x[i] for x in XB) for i in range(k)]
    S = [[1e-9 if i == j else 0.0 for j in range(k)] for i in range(k)]
    dof = max(1, len(XA) + len(XB) - 2)
    for X, m in ((XA, mA), (XB, mB)):
        for x in X:
            for i in range(k):
                for j in range(k):
                    S[i][j] += (x[i] - m[i]) * (x[j] - m[j]) / dof
    d = [a - b for a, b in zip(mA, mB)]
    return dot(d, solve(S, d))


def auc(pos, neg):
    """P(pos > neg) + 0.5 P(tie): the rank statistic, no library."""
    if not pos or not neg:
        return None
    s = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return s / (len(pos) * len(neg))


def quartiles(xs):
    xs = sorted(xs)
    if len(xs) < 2:
        return (xs[0], xs[0], xs[0]) if xs else (None, None, None)
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[0], q[1], q[2]


def load_capture(cdir):
    cdir = Path(cdir)
    m = json.loads((cdir / "manifest.json").read_text())
    prompts = []
    for p in m["prompts"]:
        if p.get("error") or not p.get("file"):
            continue
        p = dict(p)
        p["rows"] = load_rows(cdir / p["file"])
        prompts.append(p)
    return m, prompts


def in_class(p, cls):
    """'B', 'C', 'B+C' ...: class or tag membership."""
    want = set(cls.split("+"))
    return p["class"] in want or bool(want & set(p.get("tags", [])))


def analyze(cdir, native=None):
    m, prompts = load_capture(cdir)
    refs = {k: load_rows(v) for k, v in REFS.items()}
    if native:
        refs["native"] = load_rows(native)
    A = [p for p in prompts if p["class"] == "A"]
    B = [p for p in prompts if p["class"] == "B"]
    benign = [p for p in prompts if p["class"] == "benign"]
    floor = [p for p in prompts if p["idx"] in FLOOR]
    per_layer, coords = [], {str(p["idx"]): {} for p in prompts}
    for L in range(1, N_LAYERS):
        e1, e2, e3 = gram_schmidt([refs["msuiche"][L], refs["abl_perp"][L], refs["dealignai"][L]])
        w = refs["floor_resist"][L]
        has_w = norm(w) > 0.5
        x, cosv = {}, {}
        for p in prompts:
            h = p["rows"][L]
            nh = norm(h) or 1.0
            x[id(p)] = (dot(e1, h) if e1 else 0.0, dot(e2, h) if e2 else 0.0, dot(e3, h) if e3 else 0.0)
            cosv[id(p)] = {k: dot(refs[k][L], h) / nh for k in ("msuiche", "audreyt", "fused", "dealignai")}
            cosv[id(p)]["resist"] = dot(w, h) / nh if has_w else None
            coords[str(p["idx"])][L] = {"e": [round(v, 4) for v in x[id(p)]],
                                        "cos": {k: (round(v, 4) if v is not None else None)
                                                for k, v in cosv[id(p)].items()}}
        row = {"L": L}
        if e1 and e2 and len(A) > 1 and len(B) > 1:
            row["J_plane"] = fisher([x[id(p)][:2] for p in A], [x[id(p)][:2] for p in B])
            row["J_span"] = (fisher([x[id(p)] for p in A], [x[id(p)] for p in B]) if e3 else None)
        if has_w and len(A) > 1 and len(B) > 1:
            cA = [cosv[id(p)]["resist"] for p in A]
            cB = [cosv[id(p)]["resist"] for p in B]
            cN = [cosv[id(p)]["resist"] for p in benign]
            row["J_resist"] = fisher([(c,) for c in cA], [(c,) for c in cB])
            row["auc_ab"] = auc(cA, cB)
            row["auc_abenign"] = auc(cA, cN)
            if floor:
                tau = min(cosv[id(p)]["resist"] for p in floor)
                row["tau"] = tau
                row["fpr"] = sum(c >= tau for c in cN) / len(cN) if cN else None
                row["recall"] = sum(c >= tau for c in cA) / len(cA)
            row["loo_auc"] = loo_auc(A, B, L)
        if native:
            row["cos_native_msuiche"] = cos_rows(refs["native"][L], refs["msuiche"][L])
            row["cos_native_refs"] = {k: cos_rows(refs["native"][L], refs[k][L])
                                      for k in ("audreyt", "fused", "dealignai", "floor_resist")}
        per_layer.append(row)
    return m, prompts, per_layer, coords, summarize(per_layer, prompts, coords, native)


def cos_rows(a, b):
    na, nb = norm(a), norm(b)
    return None if na < 1e-6 or nb < 1e-6 else round(dot(a, b) / (na * nb), 4)


def loo_auc(A, B, L):
    """Held-out AUC: for each a in A, w_-a = unit(mean(A\\a) - mean(B)) from the capture,
    then P(c_a > c_b) over B. The floor-resist file was extracted from these classes, so
    the in-sample AUC is optimistic; this is the honest number."""
    sumA = [0.0] * D
    for p in A:
        sumA = list(map(operator.add, sumA, p["rows"][L]))
    mB = [0.0] * D
    for p in B:
        mB = list(map(operator.add, mB, p["rows"][L]))
    mB = [v / len(B) for v in mB]
    nb_rows = [(p["rows"][L], norm(p["rows"][L]) or 1.0) for p in B]
    total = 0.0
    for a in A:
        ha = a["rows"][L]
        w = [(s - x) / (len(A) - 1) - b for s, x, b in zip(sumA, ha, mB)]
        ca = dot(w, ha) / (norm(ha) or 1.0)
        total += auc([ca], [dot(w, h) / n for h, n in nb_rows])
    return total / len(A)


def med(rows, key, band=BAND):
    v = [r[key] for r in rows if r["L"] in band and r.get(key) is not None]
    return statistics.median(v) if v else None


def summarize(per_layer, prompts, coords, native):
    s = {k: med(per_layer, k) for k in ("J_plane", "J_span", "J_resist", "auc_ab", "auc_abenign",
                                        "fpr", "recall", "loo_auc")}
    jp = s["J_plane"]
    s["G1"] = ("proceed" if jp is not None and jp >= G1_J_PLANE_MIN else "stop") + \
        f" (median J_plane over L9-39 {jp if jp is None else round(jp, 3)} vs >= {G1_J_PLANE_MIN})"
    passing = [r["L"] for r in per_layer
               if r.get("auc_ab") is not None and r["auc_ab"] >= G2_AUC_AB_MIN
               and r.get("auc_abenign") is not None and r["auc_abenign"] >= G2_AUC_ABENIGN_MIN
               and r.get("fpr") is not None and r["fpr"] <= G2_FPR_MAX]
    early = [L for L in passing if L <= G2_MAX_EARLY_LAYER]
    if early:
        tau = next(r["tau"] for r in per_layer if r["L"] == early[0])
        s["G2"] = f"proceed, first branch: L* = {early[0]}, tau = {tau:.4f} ({len(passing)} layers pass)"
        s["arm1"] = {"branch": "early", "L": early[0], "tau": tau, "passing_layers": passing}
    elif len(passing) >= G2_MIN_LAYERS:
        s["G2"] = f"proceed, second branch: {len(passing)} layers pass (per-layer gating)"
        s["arm1"] = {"branch": "per-layer", "passing_layers": passing,
                     "tau": {r["L"]: r["tau"] for r in per_layer if r["L"] in passing}}
    else:
        s["G2"] = f"stop: {len(passing)} layers pass, none at L <= {G2_MAX_EARLY_LAYER}"
    if native:
        c = med(per_layer, "cos_native_msuiche")
        s["G3"] = ("proceed" if c is not None and abs(c) < G3_COS_MAX else "stop (probe only)") + \
            f" (median cos(native, msuiche) over L9-39 {c} vs < {G3_COS_MAX})"
    # where do 23/27 sit along e3 against B's IQR over L10-36
    B = [p for p in prompts if p["class"] == "B"]
    pos = {}
    for t in TARGETS:
        key = str(t)
        if key not in coords:
            continue
        out = 0
        for L in DEALIGN_BAND:
            q1, _, q3 = quartiles([coords[str(p["idx"])][L]["e"][2] for p in B if p["idx"] != t])
            v = coords[key][L]["e"][2]
            out += q1 is not None and (v < q1 or v > q3)
        pos[t] = out
    s["targets_outside_B_iqr_e3"] = pos
    s["tau2_class"] = ("C" if pos and len(pos) == len(TARGETS)
                       and all(v >= C_OUTSIDE_MIN for v in pos.values()) else "B+C")
    return s


def markdown(per_layer, s):
    def f(v, nd=3):
        return "—" if v is None else f"{v:.{nd}f}"
    lines = ["| L | J_plane | J_span | J_resist | AUC A/B | AUC A/benign | FPR | recall | LOO AUC |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in per_layer:
        lines.append(f"| {r['L']} | {f(r.get('J_plane'), 2)} | {f(r.get('J_span'), 2)} | "
                     f"{f(r.get('J_resist'), 2)} | {f(r.get('auc_ab'))} | {f(r.get('auc_abenign'))} | "
                     f"{f(r.get('fpr'), 2)} | {f(r.get('recall'), 2)} | {f(r.get('loo_auc'))} |")
    lines.append("")
    lines.append("Medians over L9-39: " + ", ".join(
        f"{k} {f(s[k])}" for k in ("J_plane", "J_span", "J_resist", "auc_ab", "auc_abenign", "fpr",
                                   "recall", "loo_auc")))
    for g in ("G1", "G2", "G3"):
        if g in s:
            lines.append(f"- **{g}**: {s[g]}")
    lines.append(f"- 23/27 outside B's IQR along e3 (of L10-36): {s['targets_outside_B_iqr_e3']}; "
                 f"tau2 class: {s['tau2_class']}")
    return "\n".join(lines)


def parse_layers(spec):
    a, _, b = spec.partition("-")
    return range(int(a), int(b or a) + 1)


def calibrate(cdir, direction, scale, cls, layers, under=None):
    """D6: tau = (1 - F) * median(cos_pre) per layer over the class; spread over the band."""
    d = load_rows(direction)

    def cos_pre(cap):
        _, prompts = load_capture(cap)
        members = [p for p in prompts if in_class(p, cls)]
        per = {}
        for L in layers:
            if norm(d[L]) < 0.5:
                continue
            per[L] = [dot(d[L], p["rows"][L]) / (norm(p["rows"][L]) or 1.0) for p in members]
        return per, len(members)

    base, n = cos_pre(cdir)
    per_layer = {L: {"median_cos_pre": statistics.median(v), "iqr": quartiles(v)[2] - quartiles(v)[0],
                     "tau": (1.0 - scale) * statistics.median(v)} for L, v in base.items() if v}
    taus = [r["tau"] for r in per_layer.values()]
    pooled = [c for v in base.values() for c in v]
    q1, qm, q3 = quartiles(taus)
    res = {"direction": direction, "scale": scale, "class": cls, "n": n,
           "layers": f"{layers.start}-{layers.stop - 1}", "per_layer": per_layer,
           "tau": (1.0 - scale) * statistics.median(pooled) if pooled else None,
           "tau_layer_median": qm, "tau_layer_iqr": None if q1 is None else q3 - q1,
           "pooled_cos_iqr": quartiles(pooled)[2] - quartiles(pooled)[0] if len(pooled) > 1 else None}
    res["one_scalar_ok"] = (res["tau_layer_iqr"] is not None and qm is not None
                            and res["tau_layer_iqr"] < SPREAD_FRACTION * abs(qm))
    if under:
        st, _ = cos_pre(under)
        pooled_u = [c for v in st.values() for c in v]
        mb, mu = statistics.median(pooled), statistics.median(pooled_u)
        res["under"] = {"capture": str(under), "median_base": mb, "median_under": mu,
                        "base_iqr": res["pooled_cos_iqr"],
                        "base_holds": abs(mu - mb) < (res["pooled_cos_iqr"] or 0.0),
                        "tau_under": (1.0 - scale) * mu}
    return res


def _self_check():
    rng = random.Random(409)
    n = 60
    planted = [rng.gauss(0, 1) for _ in range(D)]
    pn = norm(planted)
    planted = [v / pn for v in planted]
    randdir = [rng.gauss(0, 1) for _ in range(D)]
    rn = norm(randdir)
    randdir = [v / rn for v in randdir]
    A = [[rng.gauss(0, 1) + 3.0 * u for u in planted] for _ in range(n)]
    B = [[rng.gauss(0, 1) for _ in range(D)] for _ in range(n)]
    a_pl = auc([dot(planted, h) for h in A], [dot(planted, h) for h in B])
    a_rd = auc([dot(randdir, h) for h in A], [dot(randdir, h) for h in B])
    assert a_pl >= 0.97, a_pl
    assert abs(a_rd - 0.5) <= 0.1 + 0.6 * abs(dot(planted, randdir)), a_rd
    # J_plane recovers a planted 2D offset, J_span a planted 3D one (unit noise: J = |offset|^2)
    for off in ((1.5, 2.0), (1.0, 1.0, 1.5)):
        XA = [tuple(rng.gauss(0, 1) + o for o in off) for _ in range(2000)]
        XB = [tuple(rng.gauss(0, 1) for _ in off) for _ in range(2000)]
        want = sum(o * o for o in off)
        got = fisher(XA, XB)
        assert abs(got - want) < 0.12 * want, (off, got, want)
    assert abs(solve([[2, 1], [1, 3]], [3, 5])[0] - 0.8) < 1e-12
    assert auc([1, 2], [0, 2]) == 0.625  # 1>0, 2>0, 2=2 half: 2.5 of 4
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture")
    ap.add_argument("--native", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--target-from", default=None)
    ap.add_argument("--direction")
    ap.add_argument("--scale", type=float)
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--layers", default="9-39")
    ap.add_argument("--under", default=None)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if a.target_from:
        if not (a.direction and a.scale is not None and a.cls):
            ap.error("--target-from needs --direction, --scale and --class")
        res = calibrate(a.target_from, a.direction, a.scale, a.cls, parse_layers(a.layers), a.under)
        print(json.dumps({k: v for k, v in res.items() if k != "per_layer"}, indent=2))
        if a.out:
            Path(a.out).write_text(json.dumps(res, indent=2))
        return 0
    if not a.capture:
        ap.error("--capture is required")
    m, prompts, per_layer, coords, s = analyze(a.capture, a.native)
    print(markdown(per_layer, s))
    out = Path(a.out or Path(a.capture) / "report.json")
    out.write_text(json.dumps({"capture": m.get("run_id"), "steering": m.get("steering"),
                               "n": {c: sum(p["class"] == c for p in prompts)
                                     for c in ("A", "B", "C", "benign", "floor")},
                               "summary": s, "per_layer": per_layer, "coords": coords}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
