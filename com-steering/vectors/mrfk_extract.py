import sys,numpy as np
npz, outdir = sys.argv[1], sys.argv[2]
L,D=40,5120
z=np.load(npz,allow_pickle=True); Q=z['Q'].astype(np.float32); S=z['scales'].astype(np.float32)
def write(path, rowfn):
    M=np.zeros((L,D),np.float32)
    for l in range(L): M[l]=rowfn(l)
    M[0]=0.0  # layer-0 masked, repo convention
    M.tofile(path); return M
# unit replicated
q0u=write(f"{outdir}/v41-mrfk-q0.f32", lambda l: Q[:,0])
q1u=write(f"{outdir}/v41-mrfk-q1.f32", lambda l: Q[:,1])
# attn-profile weighted (sqrt of normalized attn scale → effective per-layer strength ∝ scale)
a=S[:,0]/S[:,0].max()
write(f"{outdir}/v41-mrfk-q0-attnprof.f32", lambda l: Q[:,0]*np.sqrt(a[l]))
print("wrote q0,q1,q0-attnprof to",outdir)

def load(p): return np.fromfile(p,np.float32).reshape(L,D)
refs={}
import os
for name,p in [("msuiche","dir-steering/vectors/v41-msuiche.f32"),
               ("dealignai-wo","dir-steering/vectors/v41-dealignai-wo.f32"),
               ("u1","dir-steering/out/v41-sub1017-u1.f32")]:
    if os.path.exists(p): refs[name]=load(p)
def cos(a,b):
    n=np.linalg.norm(a)*np.linalg.norm(b)
    return float(a@b/n) if n>0 else 0.0
print("\nPer-layer |cos| of mrfk q0 / q1 vs our per-layer directions:")
print("layer | q0·u1 q1·u1 | q0·msu q1·msu | q0·deal q1·deal | u1·msu")
for l in range(1,L):
    row=[l]
    def c(v): return abs(cos(Q[:,0],v)),abs(cos(Q[:,1],v))
    parts=[]
    for nm in ("u1","msuiche","dealignai-wo"):
        if nm in refs:
            a,b=c(refs[nm][l]); parts.append(f"{a:.2f} {b:.2f}")
        else: parts.append("  -   -  ")
    um = abs(cos(refs['u1'][l],refs['msuiche'][l])) if 'u1' in refs and 'msuiche' in refs else 0
    if l%4==1 or l in (15,16,24,25):
        print(f"{l:2d} | {parts[0]} | {parts[1]} | {parts[2]} | {um:.2f}")
# summary medians
import numpy as np
med=lambda vals:float(np.median(vals))
for nm in refs:
    c0=[abs(cos(Q[:,0],refs[nm][l])) for l in range(1,L)]
    c1=[abs(cos(Q[:,1],refs[nm][l])) for l in range(1,L)]
    print(f"median |cos| q0·{nm}={med(c0):.2f}  q1·{nm}={med(c1):.2f}")
