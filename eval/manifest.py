"""Run manifest and KPI-only summary (OpenSpec 402, design D3).

Two separate objects with two different audiences:

- the **manifest** is local evidence: experiment identities plus every attempted
  prompt, its status and raw text. It may contain content and never leaves the
  run directory.
- the **summary** is the agent-facing, KPI-only view: it is *constructed* from an
  allowlist of numeric/id/status fields, so prompt, response and token text cannot
  leak into it by accident (design D10). `summary.json` and its Markdown render
  use this object only.

Reuse is gated on experiment identity: a changed vector, model, binary, decoding
or data selection is a different experiment and cannot reuse prior acceptance
(spec: Run and evidence identity). The 341 GiB GGUF is never hashed; it is
identified by path/size/mtime with that limitation recorded.

Run `python3 eval/manifest.py` for the offline self-checks.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import common

SCHEMA_VERSION = "402.1"

# Only these keys may appear at the top level of a summary; build_summary
# constructs them explicitly and scan_for_content guards against leaks.
SUMMARY_ALLOWED = {
    "schema", "run_id", "profile", "mode", "report", "created",
    "intervention", "counts", "metrics", "controls", "coverage",
    "axes", "verdict", "evidence_ref", "milestone",
}


def _git(args, repo):
    try:
        out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                             text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def file_identity(path, *, do_hash=True, reason=None):
    """Path/size/mtime, and sha256 only when do_hash (small files). A large file
    records why it was not hashed, so identity is honest about its limitation."""
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False}
    st = p.stat()
    ident = {"path": str(p), "exists": True, "size": st.st_size,
             "mtime": int(st.st_mtime)}
    if do_hash:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        ident["sha256"] = h.hexdigest()
    else:
        ident["sha256"] = None
        ident["hash_skipped"] = reason or "not hashed"
    return ident


def model_identity(path):
    """Identify the GGUF without hashing it (341 GiB). Quant comes from the name."""
    ident = file_identity(path, do_hash=False, reason="large GGUF; identity is path/size/mtime")
    name = Path(path).name
    for q in ("Q2", "Q3", "Q4", "Q5", "Q6", "Q8", "F16", "BF16"):
        if q in name:
            ident["quant"] = q
            break
    return ident


def vector_identity(steer_path):
    """sha256 of the small .f32 plus its sidecar source/application block, or None
    when no vector is steered. The hash is the experiment identity for the arm:
    the same path with different bytes is a different experiment."""
    if steer_path is None:
        return None
    ident = file_identity(steer_path, do_hash=True)
    sidecar = Path(steer_path).with_suffix(".json")
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text())
            ident["source"] = meta.get("source")
            ident["application"] = meta.get("application")
        except Exception:
            ident["sidecar_error"] = True
    return ident


def intervention_identity(*, steer, residual, disable_env=False):
    """The effective edit: site, revision, scale, vector hash, disabled state.
    Site/revision mirror ds4.c (DS41_STEERING_SITE / _REVISION); a scale of 0 or a
    set DS4_METAL_DISABLE_V41_RESIDUAL_STEERING means no edit is applied."""
    active = bool(steer) and float(residual or 0) != 0.0 and not disable_env
    return {
        "site": "v41_attn_input_weighted_fold_post_engram",
        "revision": 2,
        "flag": "--dir-steering-residual",
        "scale": float(residual or 0),
        "disabled_env": bool(disable_env),
        "active": active,
        "vector": vector_identity(steer),
    }


def source_identity(repo=common.REPO):
    """Git commit + dirty flag and the two binaries' identity."""
    return {
        "commit": _git(["rev-parse", "HEAD"], repo) or "unknown",
        "dirty": bool(_git(["status", "--porcelain"], repo)),
        "cli": file_identity(common.CLI, do_hash=True),
        "eval_bin": file_identity(common.EVAL_BIN, do_hash=True),
    }


def experiment_identity(*, model, intervention, decoding, data, scorer):
    """The subset that defines 'the same experiment' for reuse (design D3). Raw
    prompts are not part of it; the data *selection* (ids/selector/hash) is."""
    return {
        "model": {k: model.get(k) for k in ("path", "size", "mtime", "quant")},
        "intervention": {"scale": intervention["scale"], "active": intervention["active"],
                         "vector_sha256": (intervention["vector"] or {}).get("sha256")},
        "decoding": decoding,
        "data": data,
        "scorer": scorer,
    }


def reuse_matches(a, b):
    """True iff two experiment_identity dicts describe the same experiment."""
    return a == b


# --- summary (KPI-only, constructed from allowlisted fields) -----------------

def build_summary(*, run_id, profile, mode, report, milestone,
                  intervention, counts, metrics, controls, coverage,
                  axes, verdict, evidence_ref):
    """Assemble the agent-facing summary from allowlisted fields only. Every value
    here is a number, an identity, a status or an opaque reference; no prompt or
    response text is accepted. `intervention` carries only scale/active/vector
    hash, not the vector itself."""
    iv = {"site": intervention["site"], "revision": intervention["revision"],
          "scale": intervention["scale"], "active": intervention["active"],
          "vector_sha256": (intervention["vector"] or {}).get("sha256")}
    summary = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "profile": profile,
        "mode": mode,
        "report": report,
        "milestone": milestone,
        "created": int(time.time()),
        "intervention": iv,
        "counts": counts,          # {requested, attempted, completed, valid, ...}
        "metrics": metrics,        # {name: {value|status, denominator, ...}}
        "controls": controls,      # {noop: ok/failed, null: ..., zero_dir: ...}
        "coverage": coverage,      # {axis: measured|not_measured}
        "axes": axes,              # per-axis KPI blocks (numeric only)
        "verdict": verdict,        # {eligible: bool, decision: ..., reason: ...}
        "evidence_ref": evidence_ref,
    }
    bad = set(summary) - SUMMARY_ALLOWED
    assert not bad, f"summary carries non-allowlisted keys: {bad}"
    return summary


def summary_markdown(s):
    """KPI-only Markdown. Names denominators and coverage; no prompt/response text."""
    L = [f"# Refusal-removal validation — {s['profile']} ({s['mode']}/{s['report']})",
         "",
         f"schema {s['schema']} · run `{s['run_id']}` · milestone {s['milestone']}",
         f"intervention: {s['intervention']['site']} rev {s['intervention']['revision']}, "
         f"scale {s['intervention']['scale']}, active={s['intervention']['active']}, "
         f"vector {s['intervention'].get('vector_sha256') or '-'}",
         "",
         "## Counts", ""]
    for k, v in s["counts"].items():
        L.append(f"- {k}: {v}")
    L += ["", "## Controls", ""]
    for k, v in s["controls"].items():
        L.append(f"- {k}: {v}")
    L += ["", "## Metrics (name: value [denominator])", ""]
    for name, m in s["metrics"].items():
        if "value" in m:
            L.append(f"- {name}: {m['value']} [n={m.get('denominator', '?')}]"
                     + (f" ±{m['ci']}" if "ci" in m else ""))
        else:
            L.append(f"- {name}: {m.get('status', 'not_measured')} "
                     f"({m.get('reason', '')})")
    L += ["", "## Coverage", ""]
    for axis, state in s["coverage"].items():
        L.append(f"- {axis}: {state}")
    v = s["verdict"]
    L += ["", "## Verdict", "",
          f"eligible: {v.get('eligible')} — {v.get('decision', 'n/a')}"
          f" ({v.get('reason', '')})", ""]
    return "\n".join(L) + "\n"


def scan_for_content(obj, needles):
    """Return [(jsonpath, needle)] for every canary needle found anywhere in obj.
    Used by the presentation-boundary tests (task 4.7): a summary must contain no
    prompt/response/token text."""
    hits = []

    def walk(o, path):
        if isinstance(o, str):
            for nd in needles:
                if nd and nd in o:
                    hits.append((path, nd))
        elif isinstance(o, dict):
            for k, v in o.items():
                for nd in needles:
                    if nd and nd in str(k):
                        hits.append((f"{path}.<key>", nd))
                walk(v, f"{path}.{k}")
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(obj, "$")
    return hits


def _selfcheck():
    # file identity hashes small files, skips a (fake) large one with a reason
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "v.f32"
        p.write_bytes(b"\x00\x01\x02\x03")
        fi = file_identity(p, do_hash=True)
        assert fi["sha256"] == hashlib.sha256(b"\x00\x01\x02\x03").hexdigest()
        fi2 = file_identity(p, do_hash=False, reason="big")
        assert fi2["sha256"] is None and fi2["hash_skipped"] == "big"
        # vector identity reads the sidecar provenance
        p.with_suffix(".json").write_text(json.dumps(
            {"source": {"hook": "residual_stream_post_layer"},
             "application": {"site": "v41_attn_input_weighted_fold_post_engram"}}))
        vi = vector_identity(p)
        assert vi["source"]["hook"] == "residual_stream_post_layer"
        assert vi["application"]["site"].startswith("v41_")

    # intervention: scale 0 or disabled env -> not active; a real scale -> active
    iv0 = intervention_identity(steer="/tmp/v.f32", residual=0)
    assert iv0["active"] is False
    ivd = intervention_identity(steer="/tmp/v.f32", residual=4, disable_env=True)
    assert ivd["active"] is False
    iv = intervention_identity(steer=None, residual=4)
    assert iv["active"] is False and iv["vector"] is None

    # reuse: a changed vector hash is a different experiment
    def expid(sha):
        return experiment_identity(
            model={"path": "m", "size": 1, "mtime": 2, "quant": "Q2"},
            intervention={"scale": 4.0, "active": True, "vector": {"sha256": sha}},
            decoding={"temp": 0, "max_tokens": 256}, data={"suite": "benign-smoke"},
            scorer={"keyword": "v1"})
    assert reuse_matches(expid("aa"), expid("aa"))
    assert not reuse_matches(expid("aa"), expid("bb"))

    # summary is allowlisted and renders without content
    s = build_summary(
        run_id="r1", profile="benign-smoke", mode="full", report="kpi",
        milestone="M0",
        intervention=intervention_identity(steer="/tmp/v.f32", residual=4),
        counts={"requested": 4, "attempted": 4, "completed": 4, "valid": 4},
        metrics={"benign_task_pass": {"value": 1.0, "denominator": 4},
                 "kl_fidelity": {"status": "not_measured", "reason": "M1"}},
        controls={"noop": "ok", "zero_dir": "ok"},
        coverage={"A": "not_measured", "B": "measured"},
        axes={"B": {"task_pass": 1.0}},
        verdict={"eligible": False, "decision": "report-only",
                 "reason": "benign-smoke is not full A-E"},
        evidence_ref="runs/r1")
    assert s["schema"] == SCHEMA_VERSION
    md = summary_markdown(s)
    assert "benign-smoke" in md and "not_measured" in md and "n=4" in md
    # a canary planted in prompts must not appear in the summary we built
    assert scan_for_content(s, ["CANARY_PROMPT_TEXT"]) == []
    assert scan_for_content({"completion": "has CANARY_PROMPT_TEXT in it"},
                            ["CANARY_PROMPT_TEXT"])
    print("manifest.py self-check: OK")


if __name__ == "__main__":
    _selfcheck()
    sys.exit(0)
