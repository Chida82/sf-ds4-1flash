# The Model and Vision

[README](../README.md) | [Getting started](../README.md#start-here)

This fork is not a general GGUF runner: it loads DeepSeek V4.1 Flash and
refuses any GGUF whose `general.architecture` is not `deepseek41`. Run
`./download.sh` for the components it offers.

`./download.sh q2` updates the `deepseek-v4.1-flash.gguf` link; the vision
encoder does not. Pass `-m FILE` to avoid depending on the last download.

Downloads go through the Hugging Face CLI, which owns the shared cache; this
repository keeps only symlinks into it. Authentication is optional for public
weights; your cached token or `HF_TOKEN` is used when present.

## DeepSeek V4.1 Flash

| Component | File size | Main weights |
| --- | ---: | ---: |
| `q2` | 341 GiB | 152 GiB |

It uses imatrix-calibrated routed experts and includes 189 GiB of Engram
tables. Engram rows are read directly from the file as needed in every mode,
never loaded as a resident table. Keep the GGUF on a fast local SSD.

On one 128 GB Mac, use SSD streaming. Leave the expert cache budget automatic:

```sh
./download.sh q2
./sf-ds4-1flash --ssd-streaming --ctx 32768
```

Use `sf-ds4-1flash-server` with the same model and memory options.
`--think-level 25` sets reasoning effort explicitly; the range is 1 to 100,
with 0 disabling thinking. `/think 25` changes it in the CLI.
`--think` selects 75 and `--think-max` selects 100.

For two 128 GB Macs, follow the [TP/RDMA setup](DISTRIBUTED.md), passing this
GGUF with `-m` on both ranks and omitting `--ssd-streaming`. Each rank holds
about 81 GiB of main weights, plus context and runtime buffers. Both machines
need the complete GGUF on disk. A 256 GB or larger Mac can instead hold all
main weights; full residency has been tested on an M3 Ultra with 512 GB.

The Q4 release is not offered by `./download.sh`: upstream ships it as two
`.part` files that have to be joined into one 483 GiB real file, and this
repository holds no model data, only symlinks into the shared cache. Join the
parts yourself outside the repository and pass the result with `-m`.

Large SSD prefills process layers in wide batches. Metal overlaps computation
with the next layer's reads. Short appends keep using the expert cache.
Resident and TP inference also batch continued prefills automatically.

Scalar, batched and tensor-parallel execution are not numerically identical.
Q4 batched prefill shows a small probability-score loss on the short official
continuation test, with unchanged overall top-token agreement. See the
[QA results](../QA_BEFORE_RELEASES.md#17-deepseek-v41-flash) for details
and remaining differences.

For images, download the matching encoder and add it to the same command:

```sh
./download.sh vision
./sf-ds4-1flash -m gguf/DeepSeek-V4.1-Flash-Q2.gguf \
  --ssd-streaming --vision gguf/DeepSeek-V4.1-Flash-Vision.gguf
```

Vision works with SSD streaming, full residency and two-Mac TP. Pass the encoder
on both TP ranks. Use `/read image.png` in `sf-ds4-1flash` or the
[server image API](SERVER.md#images). V4 Flash vision encoders do not
work with V4.1. See [conversion](../gguf-tools/README.md#convert-deepseek-v41-flash)
to build the GGUFs from safetensors.

## Vision

PNG and JPEG input works in the CLI and HTTP server on Metal.
The encoder must match the model.
V4.1 Flash vision is currently Metal-only; its setup is [above](#deepseek-v41-flash).

