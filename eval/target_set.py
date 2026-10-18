import json, glob, re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate_judged_labels import CONFIGS, collect, _indices

# The 410 panel-30 (proposal) was built by an earlier version of this script from labels that
# mixed write runs in and skipped union[:N] runs; it stays fixed as recorded. Rerun with the
# corrected labels, the same rule gives 47 indices (2026-10-18): that is not the panel.
# labels: plain single-fold runs only, identity by sha256, conflicts are errors (410 6.1)
agg = collect()[0]
idx2prompt = {}
for f in sorted(glob.glob('eval/out/*/manifest.json')):
    try: m=json.load(open(f))
    except: continue
    idxs=_indices(m.get('selector',{}).get('selector',''))
    base=m.get('arms',{}).get('base',[])
    if not idxs or len(idxs)!=len(base): continue
    for idx,item in zip(idxs, base):
        if 'prompt' in item: idx2prompt.setdefault(idx, item['prompt'])

# discriminating: judged by >=2 configs, with >=1 COMPLY and >=1 non-COMPLY
disc=[]
allidx=set().union(*[set(agg[k]) for k in CONFIGS])
for idx in sorted(allidx):
    labs={k:agg[k][idx] for k in CONFIGS if idx in agg[k]}
    if len(labs)>=2 and any(v=='COMPLY' for v in labs.values()) and any(v!='COMPLY' for v in labs.values()):
        disc.append(idx)

cyber=[1,16,17,20,28,60,174,186,198,306,390,396,426,438]
hard=[6,468,1006,1123]   # mai aperti allo screen (426 gia in cyber)
def head(i):
    p=idx2prompt.get(i); 
    return ' '.join(p.split()[:9])+' ...' if p else '(testo non disponibile)'

print("=== DISCRIMINANTI (alcuni COMPLY, altri no) ===")
for i in disc:
    pat=''.join({'COMPLY':'C','DEFLECT':'D','REFUSE':'R'}.get(agg[k].get(i),'.') for k in CONFIGS)
    print(f"  {i:>4} [{pat}] {head(i)}")
print(f"  (pattern = msuiche/ablit/fused/dealignai; . = non giudicato)")

print("\n=== CYBER ===")
for i in cyber: print(f"  {i:>4} {head(i)}")
print("\n=== DURI (mai aperti allo screen) ===")
for i in hard: print(f"  {i:>4} {head(i)}")

final=sorted(set(disc)|set(cyber)|set(hard))
print(f"\n=== SET BERSAGLIO 410 (unione) = {len(final)} indici ===")
print(" ", final)
