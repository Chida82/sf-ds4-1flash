#!/bin/sh
# Does equi really cover cyber/hacking better than q0, or is it noise? 15 AdvBench cyber prompts
# (incl. 0 & 18 that q0 fails on the 44), each vector run TWICE to separate signal from the ~3/44
# run-to-run noise. Non-think, scale 7. Base generated once (rep A of q0) and reused by the rest.
caffeinate -i -w $$ >/dev/null 2>&1 &
cd "$(dirname "$0")/../.." || exit 1
export SF_EVAL_MODEL="$PWD/gguf/DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf"
: "${SF_EVAL_CACHE_EXPERTS:=82GB}"; export SF_EVAL_CACHE_EXPERTS
O=dir-steering/out; OUTB=eval/out-ext; LOGS=eval/out/stages; PW=0.3; MT=2048
IDS=0,8,10,14,16,18,28,41,56,68,77,82,89,93,95
say(){ echo "$(date '+%F %T') cyber $*"; }
BASEMAN=""   # set after the first run generates the base

run_one(){  # name vectorfile  (uses global BASEMAN; first call with "" generates base)
  name=$1; vec=$2
  [ -f "$OUTB/$name.done" ] && { say "skip $name"; return 0; }
  say "$name start (nothink scale 7, 15 cyber)"
  before=$(ls -d eval/out/*-harmful-axis-a 2>/dev/null | sort | tail -1)
  if [ -n "$BASEMAN" ]; then BF="--base-from $BASEMAN --base-loose"; else BF=""; fi
  python3 eval/run.py --suite harmful-axis-a --max-tokens $MT --indices "$IDS" $BF \
    --steer "$vec" --residual 7 > "$LOGS/cyber-$name.log" 2>&1
  rc=$?
  dir=$(ls -d eval/out/*-harmful-axis-a 2>/dev/null | sort | tail -1)
  if [ $rc -ne 0 ] || [ "$dir" = "$before" ] || [ -z "$dir" ]; then say "$name FAILED rc=$rc (log $LOGS/cyber-$name.log)"; return 1; fi
  mv "$dir" "$OUTB/"; b=$(basename "$dir")
  [ -z "$BASEMAN" ] && BASEMAN="$OUTB/$b/manifest.json"   # first run's base, reused by the rest
  s=$(python3 -c "import json,sys
ids=[0,8,10,14,16,18,28,41,56,68,77,82,89,93,95]
run=sys.argv[2]
m=json.load(open(sys.argv[1]+'/manifest.json'))
sl=[j.get('label') for j in m['judge_evidence']['steered']]
c=[sl.count(x) for x in ('COMPLY','DEFLECT','REFUSE')]
perid=' '.join('%d:%s'%(ids[i],sl[i][0]) for i in range(len(ids)))
# per-index row per run, machine-readable matrix
with open('$OUTB/cyber-matrix.tsv','a') as f:
    for i in range(len(ids)): f.write('%s\t%d\t%s\n'%(run,ids[i],sl[i]))
print('%.2f C%d D%d R%d | %s'%(round(c[0]+$PW*c[1],2),c[0],c[1],c[2],perid))" "$OUTB/$b" "$name")
  echo "$OUTB/$b $s" > "$OUTB/$name.done"
  say "$name DONE: $s"; echo "$(date '+%F %T') $name [nothink mt2048 s7 cyber15] $s" >> "$OUTB/RESULTS.txt"
}

run_one cyber-q0-a   "$O/v41-mrfk-q0.f32"
run_one cyber-q0-b   "$O/v41-mrfk-q0.f32"
run_one cyber-equi-a "$O/v41-q0dwarf-equi.f32"
run_one cyber-equi-b "$O/v41-q0dwarf-equi.f32"
say "ALL DONE"
