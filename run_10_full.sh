#!/bin/bash
# Tasks 10.2 through 10.14 — sequential, one model at a time.
# PYTHONUNBUFFERED=1 so output appears immediately.
set -e
export PYTHONUNBUFFERED=1

FUSED=dir-steering/vectors/v41-fused-msuiche-audreyt-denoise.f32
DEALIGNAI_WO=dir-steering/vectors/v41-dealignai-wo.f32
DEALIGNAI_SW2=dir-steering/vectors/v41-dealignai-sharedw2.f32
MSUICHE=dir-steering/vectors/v41-msuiche.f32
ABLIT=dir-steering/vectors/v41-abliteration-attn.f32
MSU_L18=dir-steering/out/v41-msuiche-L1-8.f32
ABL_L939=dir-steering/out/v41-abl-L9-39.f32

ts() { date "+%Y-%m-%d %H:%M:%S"; }

echo "$(ts) === 10.2: fused@7 + dealignai-wo@2 on union[:30] ==="
python3 eval/run.py --suite harmful-axis-a \
  --steer "$FUSED" --residual 7 \
  --steer2 "$DEALIGNAI_WO" --residual2 2 \
  --max-tokens 2048 --judge base --limit 30
echo "$(ts) === 10.2 done ==="

echo "$(ts) === 10.3: fused@7 + dealignai-wo@1 on eight ==="
python3 eval/run.py --suite harmful-axis-a \
  --steer "$FUSED" --residual 7 \
  --steer2 "$DEALIGNAI_WO" --residual2 1 \
  --max-tokens 2048 --judge base --indices 1,6,13,16,23,27,372,426
echo "$(ts) === 10.3 done ==="

echo "$(ts) === 10.4: fused@7 + dealignai-sharedw2@2 on eight ==="
python3 eval/run.py --suite harmful-axis-a \
  --steer "$FUSED" --residual 7 \
  --steer2 "$DEALIGNAI_SW2" --residual2 2 \
  --max-tokens 2048 --judge base --indices 1,6,13,16,23,27,372,426
echo "$(ts) === 10.4 done ==="

echo "$(ts) === 10.5: msuiche@5 + dealignai-wo@2 on floor ==="
python3 eval/run.py --suite harmful-axis-a \
  --steer "$MSUICHE" --residual 5 \
  --steer2 "$DEALIGNAI_WO" --residual2 2 \
  --max-tokens 2048 --judge base --indices 6,372,426,42,60,66
echo "$(ts) === 10.5 done ==="

echo "$(ts) === 10.6: re-run 4b on idx 6 ==="
python3 eval/run.py --suite harmful-axis-a \
  --steer "$MSU_L18" --residual 5 \
  --steer2 "$ABL_L939" --residual2 6 \
  --max-tokens 2048 --judge base --indices 6
echo "$(ts) === 10.6 done ==="

echo "$(ts) === 10.8a: capture fold on pool205 ==="
python3 eval/capture_fold.py --indices @eval/pool205.txt --out eval/out/capture/pool
echo "$(ts) === 10.8a done ==="

echo "$(ts) === 10.8b: discover phase-A screen dealignai-wo@6,@2 + dealignai-sharedw2@6 ==="
# discover.py is crash-safe; new vector files won't overwrite existing ones
python3 eval/discover.py \
  --vectors "$DEALIGNAI_WO,$DEALIGNAI_SW2" \
  --scales "2,6"
echo "$(ts) === 10.8b done ==="

echo "$(ts) === 10.11: benign-smoke under msuiche@5 ==="
python3 eval/run.py --suite benign-smoke \
  --steer "$MSUICHE" --residual 5
echo "$(ts) === 10.11 done ==="

echo "$(ts) === 10.14: router labels — 15 prompts x 4 configs ==="
ROUTER_IDX="6,372,426,468,544,612,676,943,955,1006,1081,1123,1126,1141,1150"

echo "$(ts) --- 10.14 msuiche@5 ---"
python3 eval/run.py --suite harmful-axis-a \
  --steer "$MSUICHE" --residual 5 \
  --max-tokens 2048 --judge base --indices "$ROUTER_IDX"

echo "$(ts) --- 10.14 abliteration@6 ---"
python3 eval/run.py --suite harmful-axis-a \
  --steer "$ABLIT" --residual 6 \
  --max-tokens 2048 --judge base --indices "$ROUTER_IDX"

echo "$(ts) --- 10.14 fused@7 ---"
python3 eval/run.py --suite harmful-axis-a \
  --steer "$FUSED" --residual 7 \
  --max-tokens 2048 --judge base --indices "$ROUTER_IDX"

echo "$(ts) --- 10.14 dealignai-wo@6 ---"
python3 eval/run.py --suite harmful-axis-a \
  --steer "$DEALIGNAI_WO" --residual 6 \
  --max-tokens 2048 --judge base --indices "$ROUTER_IDX"

echo "$(ts) === 10.14 done ==="
echo "$(ts) === ALL TASKS COMPLETE ==="
