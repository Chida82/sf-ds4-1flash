# Testing and Development

[README](../README.md)

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before proposing an inference change.
The [release QA guide](../QA_BEFORE_RELEASES.md) defines the hardware matrix,
checkpoint-matched quality tests, and speed checks. It also records which
checks were not completed. A smoke test is not full QA.

## Focused checks

Model-free checks include:

```sh
make ds4_test test-session-state
./ds4_test --server
```

On Metal, small GPU tensor tests are available without loading a full GGUF:

`make test` also includes model-backed tests. Select the right GGUF and ensure
that it fits before running it; do not accidentally load a large model on a
single device during multi-GPU QA.

## Investigating output

```sh
./sf-ds4-1flash --dump-tokens -p "..."
./sf-ds4-1flash --dump-logprobs /tmp/out.json --logprobs-top-k 20 --temp 0 -p "..."
./sf-ds4-1flash --dump-logits /tmp/logits.json --nothink --prompt-file prompt.txt
./sf-ds4-1flash-server --trace /tmp/ds4-trace.txt
```

Token dumps catch template differences without inference. Logits and
continuations help distinguish sampling changes from graph errors. Server
traces include cache and tool-parser decisions. Keep traces private when they
contain real conversations.

## Tools and source references

- [GGUF conversion and quantization](../gguf-tools/README.md)
- [Imatrix collection](../gguf-tools/imatrix/README.md) and
  [calibration corpus](../gguf-tools/imatrix/dataset/README.md)
- [Steering vectors](../dir-steering/README.md)
- [Benchmark scripts and charts](../speed-bench/README.md)
- [Evaluation data and licenses](../EVAL_DATA.md)
- [Session payload implementation](../sf-ds4-1flash.c) and
  [cache header definitions](../ds4_kvstore.h)
- [Pipeline protocol](../ds4_distributed.c) and [TP protocol](../ds4_tp.c)

For changes to state handling, cover rewind/replay, save/load, images, and
multiple sessions as well as a fresh prompt. For distributed changes, exercise
both ranks and failures; a local command-parser test is not physical TP QA.
