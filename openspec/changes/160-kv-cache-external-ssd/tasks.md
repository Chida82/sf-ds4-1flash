# Tasks

## 1. Gate and setup

- [ ] 1.1 Read the `140` and `150` outcomes. If neither kept an external-SSD placement, add a one-line note to `speed-bench/perf-record.md` and close the change. Verify: the note names both decisions.
- [ ] 1.2 Warn the owner that the external SSD must be connected. Prepare the internal and `/Volumes/<external>/sf-ds4-1flash/kv` directories with the same `--kv-disk-space-mb`. Verify the server log shows `KV disk cache <dir>` for each arm, and a trial of the hit shape shows `kv cache hit` lines from disk; if the bench cannot produce disk hits, stop and ask before changing any tool.

## 2. Measurement and decision

- [ ] 2.1 Run D2's cold and hit shapes in ABBA order with the kept `140`/`150` environment in both arms, wrapped with `caffeinate -i` and `nohup`. Verify the logs of every run name the KV directory and the external placement, and record per-shape median E2EL/TTFT with pooled 95% CI, bytes written per request and load ms per MiB.
- [ ] 2.2 Apply D3. Verify `speed-bench/perf-record.md` has a diagnostic section with the figures and the verdict; if a shape is below -0.2%, report its percentage and CI to the owner and stop for their decision.

## 3. Documentation (only if accepted)

- [ ] 3.1 Update `README.md` (server command and one-time move), `docs/SERVER.md` and the suggested `--kv-disk-dir` in `AGENTS.md`, with the commands from the measured run and the measured budget. Verify the docs are in English, name the not-mounted behavior, and `openspec validate 160-kv-cache-external-ssd --strict` passes. No commit or push without an explicit request.
