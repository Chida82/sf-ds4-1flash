import json, glob, re, os

CONFIGS = {
 "msuiche@5": ("v41-msuiche.f32",5.0), "abliteration@6":("v41-abliteration-attn.f32",6.0),
 "fused@7":("v41-fused-msuiche-audreyt-denoise.f32",7.0), "dealignai-wo@6":("v41-dealignai-wo.f32",6.0),
}
agg = {k:{} for k in CONFIGS}
idx2prompt = {}
for f in sorted(glob.glob('eval/out/*/manifest.json')):
    try: m=json.load(open(f))
    except: continue
    sel=m.get('selector',{}).get('selector',''); mm=re.search(r'\[([\d,]+)\]',sel)
    if not mm: continue
    idxs=[int(x) for x in mm.group(1).split(',')]
    for idx,item in zip(idxs, m.get('arms',{}).get('base',[])):
        if 'prompt' in item: idx2prompt.setdefault(idx, item['prompt'])
    iv=m.get('intervention',{})
    if not iv.get('active') or iv.get('flag')!='--dir-steering-residual': continue
    r2=iv.get('rank2'); 
    if isinstance(r2,dict) and r2.get('active'): continue
    vn=os.path.basename((iv.get('vector') or {}).get('path','')); sc=iv.get('scale')
    match=next((k for k,(n,s) in CONFIGS.items() if vn==n and abs((sc or -1)-s)<1e-6),None)
    if not match: continue
    for idx,j in zip(idxs, m.get('judge_evidence',{}).get('steered',[])):
        if j.get('label') in ('COMPLY','DEFLECT','REFUSE'): agg[match][idx]=j['label']

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
