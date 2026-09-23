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

## Memory

The Q2 GGUF is 340.6 GiB: about 152 GiB of main weights plus 189 GiB of Engram
tables, which are always read from the file (`Engram disk-only`). Keep it on a
fast local SSD.

On a 128 GB Mac, run with `--ssd-streaming`; nothing loads without it. A
resident run needs the ~152 GiB of main weights plus the context in memory; it
has not been measured on this tree.

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

