# Metal on Apple Silicon

[README](../README.md) | [Getting started](../README.md#start-here)

## Build and run

Install Apple's command-line developer tools if needed:

```sh
xcode-select --install
```

From the repository root:

The same build supports M3 and M5 Macs. Hardware-specific fast paths are
selected automatically; no environment variable is needed to enable them.
Leave other GPU and memory-heavy applications idle when comparing performance.

## Choose a model

| Memory | Starting point |
| --- | --- |
| 64 GB | Flash Q2 with `--ssd-streaming` |
| 96 GB | Flash Q2; leave room for the context and other applications |
| 512 GB | Larger models, including PRO Q2 |

For a model larger than RAM, start with automatic cache sizing:

```sh
./sf-ds4-1flash --ssd-streaming
```

See [SSD streaming](SSD_STREAMING.md) before increasing the expert cache.
Do not bypass the memory guard just to make an oversized resident model start.

## Two Macs

Two 128 GB Macs can run a larger model fully resident with a 50/50 routed-expert
split. Thunderbolt RDMA is the low-latency option; TCP is also supported.
Follow [tensor parallel setup](DISTRIBUTED.md#tensor-parallelism-between-two-macs).
For more than two machines, use [pipeline parallelism](DISTRIBUTED.md#pipeline-parallelism).

## Next steps

