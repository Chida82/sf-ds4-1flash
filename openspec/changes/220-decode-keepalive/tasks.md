# Tasks

## 1. Gate

- [ ] 1.1 Prototype S1 on `perf/220-decode-keepalive` and measure all-hit expert-pass GPU spans (`DS4_METAL_CB_TIMES`) and the harness's GPU frequency with and without the switch. Close the change if neither moves.

## 2. GPU keep-alive

- [ ] 2.1 Share the keep-alive thread start between TP and the single streaming box; token-scoped pause on the V4.1 single-box decode, behind `DS4_METAL_DISABLE_V41_DECODE_KEEPALIVE`. Verify the decode-switch bitwise test and `make test`.
- [ ] 2.2 A/B `decode,append` with the long and cold guards, `--bitwise`, against the previous kept tree; keep rule; record the row and the power note.

## 3. CPU keep-alive

- [ ] 3.1 Add the user-interactive spinner with the same scope behind `DS4_METAL_DISABLE_V41_CPU_KEEPALIVE`; decode-switch bitwise test; A/B against S1; keep rule.

## 4. Integration

- [ ] 4.1 Review against `AGENT.md`; `AGENTS.md` switches and `docs/upstream-prs.md` lines; `make`, `make cpu`, `make test`, model-backed checks, segment-start A/B and the parity oracle; `openspec validate 220-decode-keepalive --strict`. No commit or push without a request.
