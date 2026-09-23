# Contributing

DwarfStar4 changes should be tested against the failure mode they can realistically
affect. The project has two regression tracks: correctness and speed. Please
include the commands you ran, the machine/backend, the model quant, and any
notable failures in the PR or commit notes.

Do not send PRs affecting one or more inference backends without checking if the
resulting code is still correct and fast. The only acceptable regression speed
is when an important correctness bug is fixed and it requires some speed penalty.

## Correctness Regression Tests

Build the default backend first:

```sh
make clean
make
```

The C test runner is `ds4_test`. `make test` builds everything and runs the
model-free suites (`./ds4_test --server`, session state, TP, sampling, prompt
prefix, layer pack, vision fixtures, eval case validation).

Model-backed checks load the real GGUF. On a machine that cannot hold the Q2
weights (340.6 GiB with Engram), set `DS4_TEST_SSD_STREAMING=1`; run one at a
time, since each load is expensive:

```sh
DS4_TEST_SSD_STREAMING=1 ./ds4_test --long-context
DS4_TEST_SSD_STREAMING=1 ./ds4_test --tool-call-quality
DS4_TEST_SSD_STREAMING=1 ./ds4_test --metal-kernels
```

The runner defaults to `deepseek-v4.1-flash.gguf`; override it with
`DS4_TEST_MODEL=/path/to/model.gguf` and see `./ds4_test --help` for the rest.

For CPU portability, at least verify that the CPU target still builds:

```sh
make cpu
```

The CPU backend is a reference/debug path, not the production performance
target. Remember that executing the CPU path on Metal can crash the system
because of a kernel bug in macOS.

## Quality Checks For Quantization Changes

Build the scorer:

```sh
make -C gguf-tools quality-score
```

Then score old and new GGUFs against the same manifest and compare:

```sh
gguf-tools/quality-testing/score_official OLD.gguf \
  gguf-tools/quality-testing/data/manifest.tsv /tmp/old.tsv 4096

gguf-tools/quality-testing/score_official NEW.gguf \
  gguf-tools/quality-testing/data/manifest.tsv /tmp/new.tsv 4096

python3 gguf-tools/quality-testing/compare_scores.py /tmp/old.tsv /tmp/new.tsv
```

Lower `avg_nll` is better. See
`gguf-tools/quality-testing/README.md` for collecting or refreshing official
continuations.

## Speed Regression Tests

Use `sf-ds4-1flash-bench` for throughput regressions. It reports instantaneous prefill and
generation speed at context frontiers, not one whole-run average. Prefill is
incremental: each row measures only the newly processed suffix since the
previous frontier.

Default linear sweep:

```sh
./sf-ds4-1flash-bench \
  -m deepseek-v4.1-flash.gguf \
  --prompt-file speed-bench/promessi_sposi.txt \
  --ctx-start 2048 \
  --ctx-max 65536 \
  --step-incr 2048 \
  --gen-tokens 128 \
  --csv /tmp/ds4-speed.csv
```

Use the same machine, backend, model file, context sweep, power/thermal state,
and background load when comparing two commits. For backend work, run at least
one before/after CSV and compare both `prefill_tps` and `gen_tps`. Generation is
greedy and skips EOS so each frontier gets the same number of generated tokens.

To generate a graph for a CSV:

```sh
python3 speed-bench/plot_speed.py /tmp/ds4-speed.csv --title "Machine t/s"
```

## Reporting sessions bugs

For debugging a failing generation, keep the trace:

```sh
./sf-ds4-1flash-server --trace /tmp/ds4-trace.txt ...
```
