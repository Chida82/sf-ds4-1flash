"""Geometry of two folds at one site: what the pair does to the plane of d1, d2.

  python3 dir-steering/tools/compose_geometry.py --cos 0.72 --f 5 --g 6
  python3 dir-steering/tools/compose_geometry.py --self-check

Sequential (the engine's rank-2): (I - G d2 d2^T)(I - F d1 d1^T). Additive:
I - F d1 d1^T - G d2 d2^T. `over-dose` = operator norm more than 20% above the
larger single fold max(|1-F|, |1-G|, 1) (design.md D0, D9).
"""
import argparse
import cmath
import math
import sys

OVER = 1.2


def sequential(c, f, g):
    s = math.sqrt(max(0.0, 1.0 - c * c))
    return [[(1 - g * c * c) * (1 - f), -g * c * s],
            [-g * c * s * (1 - f), 1 - g * s * s]]


def additive(c, f, g):
    s = math.sqrt(max(0.0, 1.0 - c * c))
    return [[1 - f - g * c * c, -g * c * s],
            [-g * c * s, 1 - g * s * s]]


def norm(m):
    """Largest singular value of a 2x2, closed form from M^T M."""
    a = m[0][0] ** 2 + m[1][0] ** 2
    b = m[0][0] * m[0][1] + m[1][0] * m[1][1]
    d = m[0][1] ** 2 + m[1][1] ** 2
    tr, det = a + d, a * d - b * b
    return math.sqrt(max(0.0, (tr + math.sqrt(max(0.0, tr * tr - 4 * det))) / 2))


def eigen(m):
    tr = m[0][0] + m[1][1]
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    disc = cmath.sqrt(tr * tr - 4 * det)
    return (tr + disc) / 2, (tr - disc) / 2, det


def single_fold(f, g):
    return max(abs(1 - f), abs(1 - g), 1.0)


def report(c, f, g):
    """One dict per form; `ratio` is norm / larger single fold."""
    out = {}
    for name, fn in (("sequential", sequential), ("additive", additive)):
        m = fn(c, f, g)
        l1, l2, det = eigen(m)
        n, sf = norm(m), single_fold(f, g)
        out[name] = {"m00": m[0][0], "eig": (l1, l2), "det": det, "norm": n,
                     "single": sf, "ratio": n / sf, "over_dose": n / sf > OVER}
    return out


def _show(c, f, g):
    print(f"cos {c} fold scales F={f} G={g}")
    for name, r in report(c, f, g).items():
        l1, l2 = r["eig"]
        if abs(l1.imag) > 1e-9:
            eig = (f"complex: rotation {math.degrees(2 * math.acos(min(1.0, abs(c)))):.1f} deg, "
                   f"amplification {math.sqrt(abs(r['det'])):.2f}")
        else:
            eig = f"eigenvalues {l1.real:.2f} {l2.real:.2f}"
        print(f"  {name:10s} M[0][0] {r['m00']:.2f}  {eig}  norm {r['norm']:.2f}  "
              f"single {r['single']:.2f}  ratio {r['ratio']:.2f}"
              f"{'  over-dose' if r['over_dose'] else ''}")


def _self_check():
    r = report(0.72, 5, 6)
    seq, add = r["sequential"], r["additive"]
    assert abs(seq["m00"] - 8.44) < 0.01, seq
    assert abs(seq["eig"][0].imag) > 1e-9 and abs(math.sqrt(seq["det"]) - 4.47) < 0.01, seq
    assert abs(math.degrees(2 * math.acos(0.72)) - 87.9) < 0.1
    assert abs(seq["norm"] - 15.03) < 0.01, seq
    e = sorted(x.real for x in add["eig"])
    assert abs(e[0] + 8.48) < 0.01 and abs(e[1] + 0.52) < 0.01, e
    for c, f, g, n in ((0.22, 7, 6, 9.58), (0.22, 7, 2, 6.00), (0.22, 7, 3, 6.45),
                       (0.22, 5, 4, 5.01), (0.0, 5, 6, 5.00), (0.5, 1, 1, 0.50)):
        got = report(c, f, g)["sequential"]["norm"]
        assert abs(got - n) < 0.01, (c, f, g, got, n)
    over = {(c, f, g) for c, f, g in ((0.72, 5, 6), (0.22, 7, 6), (0.22, 7, 2), (0.22, 5, 4),
                                       (0.22, 7, 3), (0.0, 5, 6), (0.5, 1, 1))
            if report(c, f, g)["sequential"]["over_dose"]}
    assert over == {(0.72, 5, 6), (0.22, 7, 6), (0.22, 5, 4)}, over
    print("ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cos", type=float)
    ap.add_argument("--f", type=float)
    ap.add_argument("--g", type=float)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)
    if a.self_check:
        return _self_check()
    if a.cos is None or a.f is None or a.g is None:
        ap.error("--cos, --f and --g are required")
    _show(a.cos, a.f, a.g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
