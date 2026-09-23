# Inference Across Machines

[README](../README.md)

There are two modes:

| Mode | Split | Main use |
| --- | --- | --- |
| Tensor parallelism | Routed experts and per-layer work across two Macs | Resident inference with lower per-token work on each GPU |
| Pipeline parallelism | Complete layer ranges across several machines | Fit larger models and overlap long prefills |

Network protocols have no authentication or encryption. Use trusted machines
and a trusted network; run the same commit on every peer. Model paths and
artifacts must agree. Update all TP peers together when changing versions.

## Tensor parallelism between two Macs

This is a 50/50 split with exactly one worker. Do not pass `--layers`.
Routed experts are sharded; attention partitioning depends on the model. Both
GPUs work on the same token and exchange partial results. This can reduce generation
latency, but the gain depends on the model, link, and comparison setup.

### Link setup

Use a Thunderbolt cable. RDMA requires an active verbs device with an
IPv4-mapped GID; a working ping alone does not establish that.

```sh
rdma_ctl status
ibv_devinfo -v
```

Addresses must be on the cabled member interfaces, not only the Thunderbolt
bridge. For example, after checking which interfaces are active:

```sh
# Machine A, example member interface en1.
sudo ifconfig en1 inet 10.99.0.2/30 alias
# Machine B, example member interface en6.
sudo ifconfig en6 inet 10.99.0.1/30 alias
```

For the large tested shards on otherwise idle 128 GB Macs, the setup raised
the per-boot GPU wired-memory limit on both machines:

```sh
sudo sysctl iogpu.wired_limit_mb=120000
```

This is specific to that memory configuration. It grants a larger GPU budget;
it does not create more RAM. Check model, context, and system headroom before
raising a limit on your machine.

### Start the pair

Start the worker first; it retries while the coordinator loads:

```sh
# Machine B.
./sf-ds4-1flash --tensor-parallel --role worker \
  --coordinator 10.99.0.2 9911 --transport rdma --ctx 8192

# Machine A.
./sf-ds4-1flash --tensor-parallel --role coordinator \
  --listen 10.99.0.2 9911 --transport rdma --ctx 8192
```

The verbs device and GID are selected automatically. If ambiguous, specify
`--rdma-device` and `--rdma-gid-index` from `ibv_devinfo`. Use `--transport tcp`
on both peers when RDMA is unavailable. Do not probe the waiting coordinator
with `curl` or `nc`: it may treat the connection as a worker handshake.

Keep workers running in a terminal or managed session and retain both logs.
Do not treat repeated handshake or RDMA timeouts as successful QA merely
because a retry works.

TP disk-cache restore currently rebuilds the exact saved token prefix on both
ranks rather than restoring the coordinator alone. Expect prefill on restore.
See [serving](SERVER.md).

## Pipeline parallelism

Each process maps only its assigned layers, retaining that slice of the KV
state. Layer ranges are inclusive. `N:output` includes the final layer and
output head. Activations travel from one stage to the next over TCP.

**Not working for DeepSeek V4.1 yet.** The layer-slice entry points still run
the generic graph that V4.1 does not allocate; the mode is kept and scheduled to
be fixed. Use tensor parallelism above for two Macs today. The commands below
show the intended usage. Replace the example address with your coordinator's
reachable address:

```sh
# Machine A.
./sf-ds4-1flash --role coordinator --layers 0:19 --listen 10.99.0.2 9911

# Machine B.
./sf-ds4-1flash --role worker --layers 20:output --coordinator 10.99.0.2 9911
```

Normally give the output head to the final worker. With several workers,
choose non-overlapping ranges covering the entire model. Workers register
their ranges with the coordinator; intermediate workers forward activations
directly to the next stage.

Long prefill chunks can occupy different stages simultaneously. A single
generation stream cannot use that overlap: each token must finish the route
before the next one is sampled. Use pipeline mode primarily for capacity and
long-prefill throughput, not as a guaranteed decode speedup.

### Tuning and recovery

Keep default chunk sizes first. `--dist-prefill-window N` controls the number
of chunks in flight; `--dist-prefill-chunk N` overrides the session-derived
chunk size. `--debug` shows route and per-hop timings.

Activations use 32-bit transport by default. `--dist-activation-bits 16` halves
the payload; `8` is more aggressive. These change numerical precision on the
wire, not weights or KV storage. Validate output when changing them.

A disconnected worker invalidates the route. In-flight work can fail; later
requests need a complete route before proceeding, and the coordinator can
replay the saved token prefix to rebuild worker state. Pipeline snapshots
serialize all layer slices into one payload and redistribute them when loaded.

For protocol details, see [ds4_distributed.c](../ds4_distributed.c)
and [ds4_tp.c](../ds4_tp.c).
