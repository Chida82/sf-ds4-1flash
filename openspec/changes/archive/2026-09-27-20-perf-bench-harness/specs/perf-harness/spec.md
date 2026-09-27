# Spec Delta

## Purpose

Gives every performance change in this child a before/after verdict: an A/B
comparison of two builds of the child on the same GGUF under SSD streaming with
a fixed expert cache, over the prefill and decode shapes of the owner's typical
workload, gated on token-identical (and, on request, bit-exact) output.

## ADDED Requirements

### Requirement: Two build trees on one model
The harness SHALL take two build trees, A (baseline) and B (candidate), and
compare them on one GGUF. Each tree's benchmark binary SHALL run with that
tree's own Metal kernel sources, and SHALL be brought up to date with `make`
before any measurement. Both builds SHALL receive the same absolute model path
and the same prompt file. The same tree MAY be passed as A and B (an A/A run
measures the noise floor).

#### Scenario: Kernel change is seen by B only
- **WHEN** B differs from A only in a file under `metal/`
- **THEN** A's runs use A's `metal/` sources and B's runs use B's

#### Scenario: Stale binary
- **WHEN** a tree's sources are newer than its benchmark binary
- **THEN** the harness rebuilds that binary before preflight

#### Scenario: Not a build tree
- **WHEN** a path given as A or B has no `metal/` directory or no Makefile
- **THEN** the harness exits with status 2 and names the path

#### Scenario: Worktree without the model link
- **WHEN** A is a worktree that has no default model symlink
- **THEN** both builds still open the file the harness's own checkout links to, by absolute path

### Requirement: Inherited toggles do not leak
The harness SHALL remove every inherited `DS4_*` environment variable from the
benchmark processes. Variables passed explicitly to the harness SHALL be given
to both builds and listed in the summary.

#### Scenario: Exported ablation switch
- **WHEN** the shell exports `DS4_METAL_DISABLE_V41_WIDE_PREFILL`
- **THEN** neither build sees it

#### Scenario: Explicit probe
- **WHEN** the user passes `DS4_METAL_STREAMING_EXPERT_TIMING_SUMMARY=1` to the harness
- **THEN** both builds run with it and the summary lists it

### Requirement: Streaming with a fixed expert cache
Every benchmark process SHALL run in SSD streaming mode with the same fixed
expert-cache target and the same allocated context of 32768 tokens, whatever
the kind. The harness SHALL read from each run's log the dynamic expert cache
the loader admitted, in GiB and in expert slots, and SHALL refuse the
invocation, with exit status 2 and the log line quoted, when the dynamic cache
of any run is outside 74.5-75.5 GiB or its slot count differs from the other
runs'. The summary SHALL print the cache size and slot count.

#### Scenario: Cache admitted
- **WHEN** the loader reports a 74.9 GiB dynamic cache with the same slot count in every run
- **THEN** the runs count and the summary prints that size and count

#### Scenario: Cache clamped
- **WHEN** another resident process leaves the loader admitting a 60 GiB dynamic cache
- **THEN** the harness exits 2 quoting the loader's cache line

#### Scenario: Same layout for every kind
- **WHEN** a decode kind and a cold-prompt kind run in one invocation
- **THEN** both bench processes report the same allocated context of 32768

### Requirement: Preflight refusal
Before any model process starts, the harness SHALL refuse to run, with exit
status 2 and the failed condition named, unless all of these hold:
- the machine is on AC power (a machine without a battery counts as on AC);
- the thermal state is Nominal;
- GPU temperature is below a configurable threshold;
- no process holds this child's instance lock and no other process has a
  resident set of 8 GiB or more;
- `mactop` is installed and returns a reading.

#### Scenario: On battery
- **WHEN** the charger is disconnected
- **THEN** the harness exits 2 with a message naming AC power, and no model process starts

#### Scenario: Another model is resident
- **WHEN** another child's server holds a 60 GiB resident set
- **THEN** the harness exits 2 and names that process's PID and command

#### Scenario: Missing monitor
- **WHEN** `mactop` is not on `PATH`
- **THEN** the harness exits 2 saying `mactop` is required; it does not run without the GPU log

### Requirement: One model process at a time
The harness SHALL run benchmark processes strictly one after another, never two
at once.

#### Scenario: Serial schedule
- **WHEN** a run finishes
- **THEN** the next run starts only after the previous process has exited

### Requirement: Scenario kinds
The harness SHALL measure these kinds, each selectable by name, and the groups
`cold` (the five cold kinds), `guards` (the two guard kinds) and `all` (every
kind but the guards). The prompt is the child's benchmark prose text. The
harness SHALL refuse an invocation that selects no kind.

| Kind | Context frontiers | Generated tokens per frontier | Metrics |
|---|---|---|---|
| `decode` | 2048, then 8192 on top of it | 256 | steady decode tokens/s at 2048 and at 8192; first-token ms as detail |
| `cold-2500` | 2500 from an empty context | 16 | time to first token (the prefill time), first-token ms as detail |
| `cold-3500` | 3500 | 16 | as above |
| `cold-5000` | 5000 | 16 | as above |
| `cold-7500` | 7500 | 16 | as above |
| `cold-10000` | 10000 | 16 | as above |
| `append` | 5000, then 5300, then 6800 | 16 | prefill seconds of +300 and of +1500 |
| `guard-16896` | 16896 from an empty context | 16 | time to first token |
| `guard-decode` | 8192 | 2500 | steady decode tokens/s over 2500 tokens |

A kind selected with `--guards` instead of `--kinds` SHALL run once as a single
A, B pair after the timed rounds, without a confidence interval, and its
metrics SHALL be marked as guards in the summary.

#### Scenario: Decode change
- **WHEN** the harness runs with `--kinds decode --guards guard-decode`
- **THEN** the timed rounds hold only `decode` runs, then one A and one B `guard-decode` run, and the summary marks the guard

#### Scenario: Prefill change
- **WHEN** the harness runs with `--kinds cold,append`
- **THEN** the five cold kinds and `append` are measured and no decode kind starts

#### Scenario: No kind
- **WHEN** neither `--kinds` nor `--guards` is given
- **THEN** the harness exits 2 listing the kinds and groups

### Requirement: Untimed warm-up
Before any timed run, the harness SHALL run every selected kind once for each
build without recording its throughput. The warm-up results SHALL feed the
correctness gate. If the warm-up already shows a correctness mismatch, the
harness SHALL stop before the timed rounds.

#### Scenario: Fail fast
- **WHEN** A's and B's warm-up token streams differ
- **THEN** the harness writes the mismatch, skips the timed rounds and exits with status 1

### Requirement: Interleaved timed rounds
For each kind the harness SHALL schedule timed runs in quads A B B A, so that
drift of any kind weighs on both builds equally, and SHALL form one pair from
each half of a quad: (A1, B1) and (B2, A2). For a metric the harness SHALL
report the A and B medians, the median over valid pairs of the pair ratio, and
a bootstrap 95% confidence interval of that median over the invocation's valid
pairs. Every ratio SHALL be printed as a gain, so that a positive percentage is
faster for every metric: B/A for tokens/s, A/B for seconds.

#### Scenario: One quad
- **WHEN** one quad of the `decode` kind completes
- **THEN** the decode metrics report the median of two gains and no interval

#### Scenario: Faster prefill reads positive
- **WHEN** B's time to first token at 5000 is 60 s against A's 66 s in every pair
- **THEN** the summary prints `ttft 5000` as +10.0%

### Requirement: Wall-clock budget
A harness invocation SHALL finish within its time budget, warm-up and guards
included. The budget SHALL default to 1800 seconds, and a budget above 3600
seconds SHALL be refused with status 2. The harness SHALL start another quad
only if its predicted duration, from the durations measured so far, fits in
the remaining budget, leaving room for the guards. If fewer than two valid
pairs exist for any headline metric, the verdict SHALL be inconclusive (exit
status 3), not a ratio.

#### Scenario: Budget reached
- **WHEN** the next quad would end after the budget
- **THEN** the harness stops scheduling quads, runs the guards and writes the summary from the pairs it has

#### Scenario: Too few pairs
- **WHEN** the budget fitted no quad of a selected kind, or disturbances left one pair
- **THEN** the summary marks that kind's metrics inconclusive and the harness exits 3

### Requirement: GPU log and disturbance rule
While the harness runs, it SHALL log GPU frequency, GPU temperature, GPU power,
GPU activity and thermal state at about 1 Hz. An optional preheat SHALL keep
the machine under load with untimed runs until a configurable time has passed
since the first run started (default 0, at most half the budget). The thermal
state SHALL NOT exclude a run or a pair. A pair SHALL be excluded only when one
of its runs has a median active GPU frequency below a configurable fraction
(default 0.90) of the median over the invocation's timed runs. The summary
SHALL report the GPU frequency range and the thermal states of the timed runs.
The monitor stopping before the last run SHALL abort the harness.

#### Scenario: External disturbance
- **WHEN** the timed runs' median frequency is 1300 MHz and one run ran at 900 MHz
- **THEN** that run's pair is excluded, both runs show the reason, and the quad's other pair is kept

#### Scenario: Monitor stops
- **WHEN** `mactop` exits before the last run
- **THEN** the harness aborts with status 2

### Requirement: Cache-state check
For every timed run and frontier the harness SHALL record the expert-cache
hits, misses, bytes read from the model file and read time of that frontier.
A pair whose hit or miss counts differ between A and B by more than a
configurable tolerance (default 1% of the frontier's lookups) or whose bytes
read differ by more than 5% SHALL be excluded, both runs carrying the reason,
unless the invocation declares a cache-policy change, in which case the
difference SHALL be reported as a note and the pair kept. The summary SHALL
print the hit rate of A and B per kind.

#### Scenario: Same policy, same state
- **WHEN** A and B differ only in a kernel and their counts match within the tolerance
- **THEN** every pair counts and the summary prints equal hit rates

#### Scenario: Cache state diverges
- **WHEN** B evicts differently and misses 4% more experts than A at the 8192 frontier
- **THEN** that pair is excluded with the reason, and the other pairs are judged on their own counts

#### Scenario: Declared policy change
- **WHEN** the invocation declares a cache-policy change and the counts differ
- **THEN** the pair is kept and the summary notes the hit rates of A and B

### Requirement: End-to-end estimate
The summary SHALL print an estimate of the request time of the typical mix for
A and for B, and its gain: the mean over prompts of 2500, 3500, 5000, 7500 and
10000 tokens and answers of 200, 1000 and 2000 tokens of the time to first
token of that prompt plus the answer divided by the steady decode rate at 2048
for prompts up to 5000 and at 8192 above. It SHALL be computed from the A and B
medians of the invocation. A phase whose kinds were not run SHALL count as
unchanged, and the summary SHALL name those kinds.

#### Scenario: Full run
- **WHEN** the `decode` kind and the five cold kinds ran
- **THEN** the summary prints the estimate for A and B in seconds and the gain

#### Scenario: Decode-only run
- **WHEN** only the `decode` kind ran
- **THEN** the estimate takes A's decode rates against B's, treats every time to first token as unchanged, and says so

### Requirement: Correctness gate
The harness SHALL compare the generated token ids of A and B for every kind and
frontier, and SHALL also compare A's runs with each other. Any difference SHALL
make the verdict FAIL (exit status 1) regardless of speed, naming the kind, the
frontier and the first differing position. In bitwise mode the harness SHALL
additionally compare, bit-exact, the logits A and B produce at every prefill
frontier and after the last decoded token of each frontier.

#### Scenario: Token drift
- **WHEN** B's decode after frontier 8192 differs from A's at token 57
- **THEN** the summary says FAIL: decode, frontier 8192, position 57, and the harness exits 1

#### Scenario: Nondeterministic baseline
- **WHEN** two A runs of the same kind produce different tokens
- **THEN** the summary says the baseline is nondeterministic and the harness exits 1

#### Scenario: Bitwise claim broken
- **WHEN** bitwise mode is on and one logit at the 2500 frontier differs in its last bit while tokens match
- **THEN** the verdict is FAIL and names the frontier and the vocabulary index

### Requirement: Output
Every invocation SHALL write, into one output directory: a raw CSV with one row
per timed run and frontier (build, kind, frontier, metrics, cache hits, misses,
bytes read and read time, GPU frequency median, flag and reason, token hash);
the raw GPU log; each run's standard error; and a summary that fits one screen
and is also printed. The summary SHALL name both trees with their commit and
whether they had uncommitted changes, the model file, the device, the cache
size and slot count, the budget used, the GPU frequency range and thermal
states of the timed runs, the number of valid and dropped pairs, the
correctness verdict, and per metric the A and B medians, the median gain, its
interval and the number of pairs.

#### Scenario: Citable verdict
- **WHEN** a run completes
- **THEN** the summary alone is enough to paste into a commit message as the change's evidence

### Requirement: Record row
The summary SHALL end with one Markdown table row, ready to paste into the
performance record, whose header the harness also defines. The row SHALL hold
the step (B's branch), the date, B's commit, the model file, the number of
valid pairs, the correctness verdict and, for every headline metric (decode at
2048 and 8192, time to first token at 2500, 3500, 5000, 7500 and 10000, append
+300 and +1500, the two guards and the end-to-end estimate), B's absolute
median together with the median gain. Metrics not measured in the invocation
SHALL appear as empty cells, so every row has the same columns.

#### Scenario: Subset of kinds
- **WHEN** only the `decode` kind was run
- **THEN** the cold, append and guard cells of the row are empty and the decode and estimate cells are filled

### Requirement: Pooled verdict across invocations
A pooling tool SHALL take a kind, a metric and the output directories of
several invocations, and print the pooled number of valid pairs, the median
gain and its bootstrap 95% confidence interval, leaving out the pairs the
harness excluded.

#### Scenario: Two invocations
- **WHEN** two invocations hold 4 and 6 valid `decode` pairs
- **THEN** the tool prints n=10 with the pooled median and interval

### Requirement: Benchmark frontier list
`sf-ds4-1flash-bench --frontiers N1,N2,...` SHALL measure prefill at exactly the
listed context frontiers, each timed interval being the tokens between one
frontier and the previous one (the first from an empty context). The list SHALL
be strictly increasing and positive, or the bench exits with status 2.

#### Scenario: Resumed suffixes
- **WHEN** the bench runs with `--frontiers 5000,5300,6800`
- **THEN** it reports prefill for 5000, 300 and 1500 new tokens, in that order

#### Scenario: Bad list
- **WHEN** the bench is given `--frontiers 8192,2048`
- **THEN** it exits with status 2 naming the option

### Requirement: Benchmark token, logit and cache evidence
With `--show-output`, the bench SHALL print the generated token ids of each
frontier. With `--dump-frontier-logits-dir`, it SHALL write, besides the
existing logits after each prefill frontier, the logits after the last decoded
token of that frontier, in the same format, with every float32 value written so
that it reads back to the same bits. With `--cache-stats`, it SHALL print after
each frontier the streaming expert-cache counters (hits, misses, bytes read,
read time) accumulated so far, so that a reader can take per-frontier deltas;
on a backend without an expert cache the option prints nothing.

#### Scenario: Decode logits file
- **WHEN** the bench runs with `--dump-frontier-logits-dir D --frontiers 2500`
- **THEN** `D` holds a prefill logits file and a decode logits file for frontier 2500

#### Scenario: Cache counters per frontier
- **WHEN** the bench runs with `--cache-stats --frontiers 2048,8192`
- **THEN** its standard error holds two counter reports, one after each frontier, in frontier order
