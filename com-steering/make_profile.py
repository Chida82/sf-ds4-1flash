#!/usr/bin/env python3
"""Build or show a steering profile (.sfsteer): one file the engine loads with
--steering-profile, holding every slot's direction matrix, scale and
think/answer gate.

Layout: b"SFSTEER1", the JSON header length (uint32 little-endian), the JSON
header, then one 40x5120 float32 matrix per slot in slot order. The engine
reads "site", "layers", "width" and each slot's "scale" and "phase"; the other
keys are provenance.

  com-steering/make_profile.py OUT.sfsteer --name NAME [--description TEXT] \\
      --slot VECTOR.f32 SCALE PHASE [--slot VECTOR.f32 SCALE PHASE]
  com-steering/make_profile.py --show FILE.sfsteer

PHASE is both, think or answer. Stdlib only.
"""
import argparse
import hashlib
import json
import math
import os
import struct
import sys

MAGIC = b"SFSTEER1"
SITE = "v41_attn_input_weighted_fold_post_engram"
LAYERS, WIDTH = 40, 5120
MAT_BYTES = LAYERS * WIDTH * 4


def check_matrix(path, data, unit=True):
    """The engine's own checks: exact size, finite, row 0 zero, other rows unit (1e-2) or zero
    (unit=False, 419 closure rows: any finite norm)."""
    if len(data) != MAT_BYTES:
        sys.exit(f"{path}: {len(data)} bytes, need {MAT_BYTES}")
    vals = struct.unpack(f"<{LAYERS * WIDTH}f", data)
    for il in range(LAYERS):
        row = vals[il * WIDTH:(il + 1) * WIDTH]
        if not all(math.isfinite(v) for v in row):
            sys.exit(f"{path}: row {il} has a non-finite value")
        n = math.sqrt(sum(v * v for v in row))
        if il == 0 and n != 0.0:
            sys.exit(f"{path}: row 0 must be zero")
        if unit and n != 0.0 and abs(n - 1.0) > 1e-2:
            sys.exit(f"{path}: row {il} has norm {n:.4f}, need 1 or 0")


def build(args):
    if not 1 <= len(args.slot) <= 2:
        sys.exit("need one or two --slot")
    if len(args.decay) > len(args.slot):
        sys.exit("more --decay than --slot")
    slots, mats = [], []
    for i, (path, scale, phase) in enumerate(args.slot):
        if phase not in ("both", "think", "answer"):
            sys.exit(f"phase {phase!r}: need both, think or answer")
        if float(scale) == 0.0:
            sys.exit("a slot scale of 0 does nothing; drop the slot")
        data = open(path, "rb").read()
        check_matrix(path, data)
        mats.append(data)
        slot = {"vector": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
                "scale": float(scale), "phase": phase}
        if i < len(args.decay):  # 418: optional per-slot decay, in slot order
            tokens, final = int(args.decay[i][0]), float(args.decay[i][1])
            if tokens < 0 or not 0.0 <= final <= float(scale):
                sys.exit(f"slot {i}: decay_tokens >= 0 and 0 <= decay_final <= scale")
            slot["decay_tokens"], slot["decay_final"] = tokens, final
            if i < len(args.decay_hold):  # 418-C: plateau before the decay
                hold = int(args.decay_hold[i][0])
                if hold < 0:
                    sys.exit(f"slot {i}: decay_hold >= 0")
                slot["decay_hold"] = hold
            if i < len(args.decay_final_answer):  # 418-C: answer-phase final override
                fa = float(args.decay_final_answer[i][0])
                if not 0.0 <= fa <= float(scale):
                    sys.exit(f"slot {i}: 0 <= decay_final_answer <= scale")
                slot["decay_final_answer"] = fa
        slots.append(slot)
    header = {"name": args.name, "site": SITE, "layers": LAYERS, "width": WIDTH, "slots": slots}
    if args.closure:  # 419: additive closure channel, matrix after the slot matrices
        path, scale, omin, omax, ramp = args.closure
        scale, omin, omax, ramp = float(scale), int(omin), int(omax), int(ramp)
        if not scale > 0 or not 0 <= omin <= omax or ramp < 0:
            sys.exit("--closure: scale > 0, 0 <= onset_min <= onset_max, ramp >= 0")
        data = open(path, "rb").read()
        check_matrix(path, data, unit=False)  # 419: raw displacement rows, any finite norm
        mats.append(data)
        header["closure"] = {"vector": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
                             "scale": scale, "onset_min": omin, "onset_max": omax, "ramp_tokens": ramp,
                             "phase": "think"}
        if args.closure2:  # 419: second stage, a rises again from scale to scale2 after_tokens past the onset
            scale2, after, ramp2 = float(args.closure2[0]), int(args.closure2[1]), int(args.closure2[2])
            if scale2 < scale or after < 0 or ramp2 < 0:
                sys.exit("--closure2: scale2 >= scale, after >= 0, ramp2 >= 0")
            header["closure"].update({"scale2": scale2, "after_tokens": after, "ramp2_tokens": ramp2})
    elif args.closure2:
        sys.exit("--closure2 needs --closure")
    if args.description:
        header["description"] = args.description
    js = json.dumps(header, indent=1).encode()
    with open(args.out, "wb") as f:
        f.write(MAGIC + struct.pack("<I", len(js)) + js + b"".join(mats))
    print(f"{args.out}: {len(slots)} slot(s), {os.path.getsize(args.out)} bytes")


def show(path):
    with open(path, "rb") as f:
        if f.read(8) != MAGIC:
            sys.exit(f"{path}: not a steering profile")
        (n,) = struct.unpack("<I", f.read(4))
        header = json.loads(f.read(n))
        n_mat = len(header["slots"]) + (1 if "closure" in header else 0)
        mats = [f.read(MAT_BYTES) for _ in range(n_mat)]
        if f.read(1) or any(len(m) != MAT_BYTES for m in mats):
            sys.exit(f"{path}: size does not match {n_mat} matrices")
    for slot, m in zip(header["slots"] + ([header["closure"]] if "closure" in header else []), mats):
        if "sha256" in slot and hashlib.sha256(m).hexdigest() != slot["sha256"]:
            sys.exit(f"{path}: slot {slot.get('vector')} sha256 mismatch")
    print(json.dumps(header, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?")
    ap.add_argument("--name")
    ap.add_argument("--description")
    ap.add_argument("--slot", nargs=3, action="append", default=[], metavar=("VECTOR", "SCALE", "PHASE"))
    ap.add_argument("--decay", nargs=2, action="append", default=[], metavar=("TOKENS", "FINAL"),
                    help="418: per-slot decay, in slot order; scale eases to FINAL over TOKENS in-phase tokens")
    ap.add_argument("--decay-hold", dest="decay_hold", nargs=1, action="append", default=[], metavar="TOKENS",
                    help="418-C: per-slot (slot order) plateau; hold scale for TOKENS before the decay smoothstep starts")
    ap.add_argument("--closure", nargs=5, metavar=("VECTOR", "SCALE", "ONSET_MIN", "ONSET_MAX", "RAMP"),
                    help="419: additive closure channel (think only): x += a(t)*VECTOR[layer], a rises by "
                         "smoothstep to SCALE over RAMP tokens after onset ONSET_MIN (think-level <= 10) .. "
                         "ONSET_MAX (think-level 100)")
    ap.add_argument("--closure2", nargs=3, metavar=("SCALE2", "AFTER", "RAMP2"),
                    help="419: closure second stage: AFTER tokens past the onset a rises by smoothstep from SCALE "
                         "to SCALE2 over RAMP2 tokens (the door offered gently first, firmly later)")
    ap.add_argument("--decay-final-answer", dest="decay_final_answer", nargs=1, action="append", default=[], metavar="FINAL",
                    help="418-C: per-slot (slot order) answer-phase decay final override (0..scale); think keeps decay_final")
    ap.add_argument("--show", metavar="FILE")
    args = ap.parse_args()
    if args.show:
        show(args.show)
    elif args.out and args.name:
        build(args)
    else:
        ap.error("give OUT --name NAME --slot ..., or --show FILE")


if __name__ == "__main__":
    main()
