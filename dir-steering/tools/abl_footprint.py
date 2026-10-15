"""Map the full abliteration footprint: which GGUF tensors differ between base and
abliterated, by head+tail raw-byte probe (no dequant). Groups by tensor basename."""
import sys, re
sys.path.insert(0, sys.argv[0].rsplit('/', 1)[0])
from weight_diff_direction import read_index, read_raw

base, abl = sys.argv[1], sys.argv[2]
PROBE = 4 << 20
tb, ds_b, _ = read_index(base)
ta, ds_a, _ = read_index(abl)

def edited(name):
    if name not in ta: return "missing_in_abl"
    # nbytes unknown without type math; probe head + a mid region
    ob, oa = ds_b + tb[name][2], ds_a + ta[name][2]
    if read_raw(base, ob, PROBE) != read_raw(abl, oa, PROBE):
        return True
    return False  # head identical; good enough for an edit-scope map

groups = {}  # basename (blk.N stripped) -> [n_edited, n_total]
per_layer_edit = {}
for name in tb:
    e = edited(name)
    key = re.sub(r'blk\.\d+\.', 'blk.N.', name)
    g = groups.setdefault(key, [0, 0, 0])
    g[1] += 1
    if e is True: g[0] += 1
    elif e == "missing_in_abl": g[2] += 1

print("tensor family                         edited/total  missing")
for key in sorted(groups):
    e, t, m = groups[key]
    mark = "  <-- EDITED" if e else ""
    print("  %-38s %3d/%-3d       %d%s" % (key, e, t, m, mark))
