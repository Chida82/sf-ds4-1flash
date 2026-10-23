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


def check_matrix(path, data):
    """The engine's own checks: exact size, finite, row 0 zero, other rows unit (1e-2) or zero."""
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
        if n != 0.0 and abs(n - 1.0) > 1e-2:
            sys.exit(f"{path}: row {il} has norm {n:.4f}, need 1 or 0")


def build(args):
    if not 1 <= len(args.slot) <= 2:
        sys.exit("need one or two --slot")
    slots, mats = [], []
    for path, scale, phase in args.slot:
        if phase not in ("both", "think", "answer"):
            sys.exit(f"phase {phase!r}: need both, think or answer")
        if float(scale) == 0.0:
            sys.exit("a slot scale of 0 does nothing; drop the slot")
        data = open(path, "rb").read()
        check_matrix(path, data)
        mats.append(data)
        slots.append({"vector": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
                      "scale": float(scale), "phase": phase})
    header = {"name": args.name, "site": SITE, "layers": LAYERS, "width": WIDTH, "slots": slots}
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
        mats = [f.read(MAT_BYTES) for _ in header["slots"]]
        if f.read(1) or any(len(m) != MAT_BYTES for m in mats):
            sys.exit(f"{path}: size does not match {len(header['slots'])} slot(s)")
    for slot, m in zip(header["slots"], mats):
        if "sha256" in slot and hashlib.sha256(m).hexdigest() != slot["sha256"]:
            sys.exit(f"{path}: slot {slot.get('vector')} sha256 mismatch")
    print(json.dumps(header, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?")
    ap.add_argument("--name")
    ap.add_argument("--description")
    ap.add_argument("--slot", nargs=3, action="append", default=[], metavar=("VECTOR", "SCALE", "PHASE"))
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
