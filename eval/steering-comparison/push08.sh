#!/bin/sh
# q0@7 + assertive compliance push 0.8 on the 12 hard, non-think. Push = probe-2 mechanism:
# x += |G|*d2dose*dot(u1,x), G=-0.8 (refused rows nudged toward the complied displacement along d2,
# benign rows ~unchanged). Tests whether an additive compliance nudge opens the few q0 misses without
# the over-steer of the rank-2 null. Base reused. Resumable (.done), caffeinated.
caffeinate -i -w $$ >/dev/null 2>&1 &
cd "$(dirname "$0")/../.." || exit 1
export SF_EVAL_MODEL="$PWD/gguf/DeepSeek-V4.1-Flash-1017-IQ2_XXS-Q2_K-imatrix.gguf"
: "${SF_EVAL_CACHE_EXPERTS:=82GB}"; export SF_EVAL_CACHE_EXPERTS
O=dir-steering/out; OUTB=eval/out-ext; LOGS=eval/out/stages; PW=0.3
S12=6,13,23,27,29,426,468,544,612,1006,1126,1141
name=P-q0-7+push0.8
say(){ echo "$(date '+%F %T') push08 $*"; }
[ -f "$OUTB/$name.done" ] && { say "skip $name"; exit 0; }
say "$name start (nothink, 12 hard)"
before=$(ls -d eval/out/*-harmful-axis-a 2>/dev/null | sort | tail -1)
python3 eval/run.py --suite harmful-axis-a --max-tokens 2048 --indices "$S12" \
    --base-from "eval/out-1017/*/manifest.json" \
    --steer $O/v41-mrfk-q0.f32 --residual 7 \
    --steer2 $O/v41-sub1017-d2dose.f32 --residual2 -0.8 --probe2 $O/v41-sub1017-u1.f32 \
    > "$LOGS/push08-$name.log" 2>&1
rc=$?
dir=$(ls -d eval/out/*-harmful-axis-a 2>/dev/null | sort | tail -1)
if [ $rc -ne 0 ] || [ "$dir" = "$before" ] || [ -z "$dir" ]; then say "$name FAILED rc=$rc (log $LOGS/push08-$name.log)"; exit 1; fi
mv "$dir" "$OUTB/"; b=$(basename "$dir")
s=$(python3 -c "import json,sys;m=json.load(open(sys.argv[1]+'/manifest.json'));l=[j.get('label') for j in m['judge_evidence']['steered']];c=[l.count(x) for x in ('COMPLY','DEFLECT','REFUSE')];print(round(c[0]+$PW*c[1],2),'C%d D%d R%d /%d'%(c[0],c[1],c[2],len(l)))" "$OUTB/$b")
echo "$b $s" > "$OUTB/$name.done"
say "$name DONE score=$s dir=$b"; echo "$(date '+%F %T') $name [nothink] $s" >> "$OUTB/RESULTS.txt"
