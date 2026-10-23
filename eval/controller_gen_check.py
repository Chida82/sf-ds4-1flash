"""Fase 0 of the closed-loop controller: is the residual refusal of the 7 hard ids
readable along q0 at the FIRST GENERATED token (gen_), when it was NOT at the
decision token (rows_)?

For each residual id, z-score (robust median/MAD vs the other refused prompts) of the
projection on q0 (and u1, d2 for context) at layers 15/20/25/30/35, at position gen and
rows side by side. Plus the median q0.y of refused/complied/benign per layer.

Gate: if at gen the q0 z of the residual ids is anomalous (|z|>2 on >=2 of the 5 layers)
while it was normal at rows -> the refusal forms in generation, the controller has a
signal: BUILD. If normal at gen too -> STOP, do not build the engine.

CPU only, no model. Run with the emb-venv312 python (numpy).
  PY eval/controller_gen_check.py            # writes controller-gen-check.md
  PY eval/controller_gen_check.py --self-check
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_floor_direction as efd  # noqa: E402
import subspace_analysis as sa  # noqa: E402

RESIDUAL = {"nonthink": ["0", "18", "468"], "think": ["7", "544", "1123", "1126"]}
VECS = {"q0": "dir-steering/out/v41-mrfk-q0.f32", "u1": "dir-steering/out/v41-sub1017-u1.f32",
        "d2": "dir-steering/out/v41-sub1017-d2.f32"}
LAYERS = [15, 20, 25, 30, 35]
Z_THRESH = 2.0
MIN_LAYERS = 2  # how many of the 5 layers must exceed |z|>2 to call the id "anomalous"


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def residual_z(X, ids, recs, vecs, layers):
    """{(grp,id): {(vec,layer): z}} -- projection z-score vs the other refused prompts."""
    refused = np.array([j for j, i in enumerate(ids) if recs[i].get("refusal") is True])
    pos = {i: j for j, i in enumerate(ids)}
    rows = {}
    for name, V in vecs.items():
        for l in layers:
            v = unit(V[l])
            if not v.any():
                continue
            s = X[refused, l] @ v
            med = np.median(s)
            mad = np.median(np.abs(s - med)) * 1.4826 + 1e-6
            for grp, rid in RESIDUAL.items():
                for i in rid:
                    if i in pos:
                        rows.setdefault((grp, i), {})[(name, l)] = float((X[pos[i], l] @ v - med) / mad)
    return rows


def group_medians(X, ids, recs, q0, layers):
    """median q0.y for refused / complied / benign per layer."""
    refused = [j for j, i in enumerate(ids) if recs[i].get("refusal") is True]
    comply = [j for j, i in enumerate(ids) if recs[i].get("refusal") is False]
    benign = [j for j, i in enumerate(ids) if recs[i]["class"] == "benign"]
    out = {}
    for l in layers:
        v = unit(q0[l])
        out[l] = (float(np.median(X[refused, l] @ v)) if refused else float("nan"),
                  float(np.median(X[comply, l] @ v)) if comply else float("nan"),
                  float(np.median(X[benign, l] @ v)) if benign else float("nan"))
    return out


def anomalous_layers(zmap, grp, i, vec="q0"):
    """how many of LAYERS have |z|>Z_THRESH for this id on this vec."""
    d = zmap.get((grp, i), {})
    return [l for l in LAYERS if abs(d.get((vec, l), 0.0)) > Z_THRESH]


def build_report(capture):
    vecs = {n: np.fromfile(p, dtype=np.float32).reshape(efd.N_LAYERS, efd.D) for n, p in VECS.items()}
    data = {}
    for position in ("rows", "gen"):
        ids, X, recs = sa.load_capture(capture, position)
        data[position] = {
            "z": residual_z(X, ids, recs, vecs, LAYERS),
            "med": group_medians(X, ids, recs, vecs["q0"], LAYERS),
            "n": (sum(recs[i].get("refusal") is True for i in ids),
                  sum(recs[i].get("refusal") is False for i in ids),
                  sum(recs[i]["class"] == "benign" for i in ids)),
        }
    return _format(data, vecs)


def _format(data, vecs):
    L = ["# Fase 0 — residual refusal along q0 at gen_ vs rows_", "",
         f"Residual ids: nonthink {RESIDUAL['nonthink']}, think {RESIDUAL['think']}. "
         f"Layers {LAYERS}. z = robust (median/MAD) vs other refused. "
         f"Gate: |z|>{Z_THRESH} on >={MIN_LAYERS} layers at gen (and normal at rows).", ""]
    # counts
    for p in ("rows", "gen"):
        r, c, b = data[p]["n"]
        L.append(f"- {p}_: refused {r}, complied {c}, benign {b}")
    # median q0.y per group
    L += ["", "## median q0.y per group (refused / complied / benign)", "",
          "| pos | " + " | ".join(f"L{l}" for l in LAYERS) + " |", "|---|" + "---:|" * len(LAYERS)]
    for p in ("rows", "gen"):
        for gi, gname in enumerate(("refused", "complied", "benign")):
            L.append(f"| {p} {gname} | " + " | ".join(f"{data[p]['med'][l][gi]:+.0f}" for l in LAYERS) + " |")
    # q0 z per residual id, rows vs gen
    L += ["", "## q0 z-score per residual id (rows then gen)", "",
          "| pos | group | id | " + " | ".join(f"L{l}" for l in LAYERS) + " | #|z|>2 |",
          "|---|---|---|" + "---:|" * len(LAYERS) + "---:|"]
    gate = {}
    for p in ("rows", "gen"):
        for grp, rid in RESIDUAL.items():
            for i in rid:
                d = data[p]["z"].get((grp, i), {})
                cells = " | ".join(f"{d.get(('q0', l), float('nan')):+.1f}" for l in LAYERS)
                na = len([l for l in LAYERS if abs(d.get(("q0", l), 0.0)) > Z_THRESH])
                L.append(f"| {p} | {grp} | {i} | {cells} | {na} |")
                gate[(p, grp, i)] = na
    # verdict
    anom = [(grp, i) for grp, rid in RESIDUAL.items() for i in rid
            if gate[("gen", grp, i)] >= MIN_LAYERS and gate[("rows", grp, i)] < MIN_LAYERS]
    anom_gen = [(grp, i) for grp, rid in RESIDUAL.items() for i in rid if gate[("gen", grp, i)] >= MIN_LAYERS]
    L += ["", "## Verdict", ""]
    L.append(f"- ids anomalous at gen (|z|>2 on >={MIN_LAYERS} layers): {anom_gen or 'none'}")
    L.append(f"- of those, normal at rows (signal appears in generation): {anom or 'none'}")
    if anom_gen:
        L.append("")
        L.append("**BUILD**: q0 reads the residual refusal at the generated token for "
                 f"{len(anom_gen)}/7 residual ids -> the controller has a per-token signal. Proceed to Fase 1.")
    else:
        L.append("")
        L.append("**STOP**: q0.y of the residual ids is normal at gen_ too -> the controller has "
                 "nothing to read along q0. Do not build the engine; record and report.")
    return "\n".join(L), bool(anom_gen)


def _self_check():
    # synthetic: 40 refused, 1 of them (id '0') pushed +6 MAD on q0 at gen layers -> anomalous
    rng = np.random.default_rng(0)
    nL, D = efd.N_LAYERS, efd.D
    q0 = np.zeros((nL, D), np.float32);
    for l in LAYERS:
        q0[l] = unit(rng.standard_normal(D)).astype(np.float32)
    ids = [str(k) for k in range(40)]
    recs = {i: {"idx": i, "class": "study", "refusal": True} for i in ids}
    recs["0"] = {"idx": "0", "class": "study", "refusal": True}
    X = rng.standard_normal((40, nL, D)).astype(np.float32) * 0.1
    # inject: id '0' gets +6*std along q0 at the LAYERS
    for l in LAYERS:
        X[0, l] += 6.0 * q0[l]
    z = residual_z(X, ids, recs, {"q0": q0}, LAYERS)
    na = len(anomalous_layers(z, "nonthink", "0"))
    assert na >= MIN_LAYERS, ("id0 should be anomalous", na, z.get(("nonthink", "0")))
    # id '18' untouched -> normal
    na18 = len(anomalous_layers(z, "nonthink", "18"))
    assert na18 == 0, ("id18 should be normal", na18)
    print("controller_gen_check self-check: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default="eval/out-subspace-1017/capture")
    ap.add_argument("--out", default="eval/steering-comparison/controller-gen-check.md")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    txt, build = build_report(a.capture)
    Path(a.out).write_text(txt + "\n")
    print(txt)
    print("\nGATE:", "BUILD" if build else "STOP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
