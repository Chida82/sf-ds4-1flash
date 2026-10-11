# Tasks

Starts after `320` has landed. Each step is judged by the config's rule against the previous one, with `--dspark --mtp-model <file>` on both builds.

## 1. Budget (S1)

- [ ] 1.1 Subtract the drafter's resident bytes from the automatic budget under `--dspark`, and name it in the startup line. Verify the two spec scenarios by running them, and `310`'s memory timeline under the automatic budget: zero swapouts and at least 18 GiB available. Then the harness under `82GB`: `--kinds decode,append --bitwise`, nothing below zero.

## 2. Ordered steps (D1)

- [ ] 2.1 Rank S2, S3 and S5 from `320`'s section (miss share of a cycle, prose against the rule, memory), and write the order into this change's section in `perf-record.md`.
- [ ] 2.2 S2, only if `320`'s section shows the cycle's miss time growing with the union: issue the union's misses for a layer together on the reader pool and both drives. Verify that the miss read time per cycle falls (`--cache-stats`), and apply the keep rule on `decode-code`, with prose not below the rule.
- [ ] 2.3 S3, exponential back-off with a re-probe floor. Verify the `decode` (prose) CI against `310`'s rule and `decode-code` not below zero.
- [ ] 2.4 S4, sweep of cap {2, 3, 5} and confidence {0.4, 0.6, 0.8} on `decode-code` and `decode`, then the chosen pair once on `310`'s chat and tool kinds. Verify the default changes only when its CI is above zero on code and within the rule on prose.
- [ ] 2.5 S5, only if D3 holds. With the owner's approval for the shards and a `mktemp` virtual environment:
  - convert the `mtp.*` weights to Q2-class experts;
  - extend the loader check (spec);
  - re-measure acceptance on the four kinds;
  - measure the harness against MXFP4.

  Verify the rows test and the token gate. The `download.sh` component changes only after the owner publishes the file.

## 3. Integration

- [ ] 3.1 Update the README gains table and `AGENTS.md` memory notes; `make test`; parity without the flag; `openspec validate 330-dspark-streaming-tuning --strict`. No commit or push without a request.
