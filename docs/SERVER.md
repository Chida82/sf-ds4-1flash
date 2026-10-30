# Serving Models

[README](../README.md) | [Client setup](CLIENTS.md)

## Start locally

```sh
./sf-ds4-1flash-server --ctx 32768
```

The default address is `http://127.0.0.1:8002`. Use `--host 0.0.0.0` to listen
on other interfaces. Restrict access to trusted clients; for an Internet-facing
deployment, put authentication and TLS in front of the server.

`--cors` enables browser cross-origin headers. It does not change the listening
address or provide access control.

The selected build chooses the backend. Pass `-m FILE` for an explicit model.
Use `--chdir /path/to/ds4` when starting outside the project directory so
relative runtime files such as Metal kernels can be found.

## APIs

| Endpoint | Use |
| --- | --- |
| `GET /v1/models` | Loaded model information |
| `POST /v1/chat/completions` | OpenAI-style chat |
| `POST /v1/responses` | Responses-style requests and continuations |
| `POST /v1/completions` | Text completions |
| `POST /v1/messages` | Anthropic-style messages |

The model id is `deepseek-v4.1-flash`. `deepseek-chat` and `deepseek-reasoner`
are accepted as thinking switches (off and on) for the same loaded model. The GGUF passed at startup selects the model.

```sh
curl http://127.0.0.1:8002/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4.1-flash","messages":[{"role":"user","content":"Explain Redis streams."}],"stream":true}'
```

Chat, Responses, and Anthropic support tools and SSE streaming. Reasoning is
returned separately from visible text in each API's native form. Standard
sampling and output-budget fields are supported; explicit request parameters
take precedence over defaults.

Message content is literal text. System, user and tool text, the assistant's
reasoning and content, and tool-call names and arguments are encoded as
ordinary tokens even when they spell a chat marker such as `<｜User｜>`,
`</think>` or `｜DSML｜`. Only the markers the chat template writes are control
tokens. A tool that reads this repository's sources, which contain those
markers, therefore cannot forge a turn or end the model's reasoning. Prompts
whose content spells no marker tokenize exactly as before. The CLI is
different: a prompt it receives already rendered as a chat keeps every marker
as a control token.

The same holds for the model's output. Reasoning ends, and a tool call
starts, only where the model emitted the `</think>` or `｜DSML｜` token. When
it writes those characters as ordinary text, for example while quoting or
editing a file that contains them, they reach the client as text in whatever
field they fall in: reasoning, content or a tool argument.

The default sampling settings are temperature 1, top-p 1, and min-p 0.05.
Thinking is on by default, at effort 75. Every API's effort name
(`reasoning_effort`, `chat_template_kwargs.reasoning_effort`, Anthropic
`output_config.effort`, Responses `reasoning.effort`) maps to the level the
prompt's `Reasoning Effort: N` line carries:

| Name | Level |
|---|---|
| `none`, `minimal` | thinking off |
| `low` | 25 |
| `medium` | 50 |
| `high` | 75 |
| `xhigh` | 90 |
| `max` | 100 |

A numeric string `"0"` to `"100"` sets the level directly; `"0"` turns
thinking off. `minimal` used to mean a little thinking: it now means none.

Precedence: an explicit disable (`think:false`, `thinking:false`, a disabled
thinking object) always wins; then an effort that means no thinking; then the
model alias (`deepseek-chat` off, `deepseek-reasoner` on), only when no
explicit thinking control was sent; then the effort, `high` by default.

## Multiple sessions

```sh
./sf-ds4-1flash-server --ctx 4096 --batched-session 4
```

Without `--batched-session`, there is one resident session. With it, the server
preallocates independent KV states and queues requests when all slots are busy.
Choose context and slot count together: a context that fits once may not fit
four times. Idle slots can be cached before reuse; active requests are not evicted.

| Backend/model | Decode execution |
| --- | --- |
| Metal, resident Flash | Native shared-expert/QKV batching where supported |
| Metal, resident V4.1 Flash | Native decoding for 2-8 sessions |
| Metal RDMA TP, V4.1 Flash | Native decoding for 3-8 sessions; ordered fallback for two |
| Metal SSD streaming, V4.1 Flash | Ordered fallback |

Fallback executes the rows separately. It provides concurrency and scheduling
fairness, not the aggregate speedup of native batching. Native grouping may
change floating-point reduction order slightly. V4.1 sessions containing images
use the ordered fallback.

## Steering per request

```sh
./sf-ds4-1flash-server --ssd-streaming --steering-profile-on-request sf-ds4-1flash-candor
```

`--steering-profile-on-request NAME|FILE` loads a steering profile
(`com-steering/`) and leaves it off. A request turns it on by asking for a
model id with the `-steering` suffix:

| Model id | Thinking | Steering |
|---|---|---|
| `deepseek-v4.1-flash-steering` | on | on |
| `deepseek-chat-steering` | off | on |
| `deepseek-reasoner-steering` | on | on |

The suffix only adds steering: the base id keeps its thinking rule, and an
explicit thinking control or effort still wins over it as for the base id.
The response reports the id the request sent. `/v1/models` lists
`deepseek-v4.1-flash-steering` only while a profile is loaded. Requests
without the suffix run the unsteered model, bitwise the same as a server
started without a profile.

A `-steering` id on a server without a profile, or with an unknown base
(`foo-steering`), is answered with a 400: a client must never believe it is
steered when it is not. `--steering-profile` is the CLI and eval flag, which
means always on; the server refuses it at startup and names the new flag.
Tensor-parallel and distributed roles refuse the flag too: the per-request
switch is not carried to other ranks.

A slot's live state belongs to one setting. A request routes away from slots
computed under the other setting, and a slot that changes setting drops its
live KV first, so the request evaluates its whole prompt. With one slot,
clients that alternate steered and unsteered requests re-prefill every time;
`--batched-session N` keeps both kinds resident. A Responses or Anthropic
continuation that relies on live tool state of the other setting gets the
usual 409 and must replay its history. The disk cache keeps the two kinds
apart (Disk KV cache, below). The request log carries `STEER` and the trace
`steering: on`.

## Images

Start with the matching language GGUF and `--vision FILE`; see
[model-specific instructions](MODELS.md#vision).

OpenAI chat and Responses accept inline PNG/JPEG data URIs. Anthropic accepts
base64 image sources. Remote URLs and server-side file paths are rejected.
Image blocks preserve their order in the request. The limit is 16 images and
a 64 MiB HTTP body.

## Disk KV cache

Disk caching saves useful prefixes across slot reuse and server restarts:

```sh
./sf-ds4-1flash-server --ctx 100000 \
  --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
```

Clients can resend complete conversation histories. The server first tries
the live token prefix, then compatible rendered-text prefixes from disk, and
prefills the new suffix. With multiple slots, each slot has its own live state;
disk is the additional persistence layer, not the only way to retain sessions.

TP cache loading rebuilds the saved token prefix on both ranks. It is not an
instantaneous restoration of both GPUs. Pipeline loading redistributes the
saved layer state over its route.

Defaults are intended to avoid saving fragile token boundaries. For unusual
workloads, the controls are `--kv-cache-min-tokens`,
`--kv-cache-cold-max-tokens`, `--kv-cache-continued-interval-tokens`,
`--kv-cache-boundary-trim-tokens`, and `--kv-cache-boundary-align-tokens`.
Check `./sf-ds4-1flash-server --help` for their defaults.

Quantization variants may share compatible prefixes. Add
`--kv-cache-reject-different-quant` for same-quant reuse only.

The cache directory can live on an external drive, which takes the cache's
writes off the soldered internal SSD. The README gives the command and the
one-time move. On the TB5 drive formatted APFS, a 36 MiB checkpoint stores
6.5 ms faster than on the internal SSD and loads 4 ms slower; on ExFAT it
stored about 2 ms slower (`speed-bench/perf-record.md`, KV cache placement
after 150, External drive on APFS). If the
directory cannot be created, for example because the drive is not mounted, the
server logs it and runs without a disk cache.
Cache files contain prompt text and model state: treat the directory as
private. It is disposable; stop the server before clearing it.

With `--steering-profile-on-request`, steered requests look up, load, store
and evict only under `<dir>/steering/`, and unsteered requests only in `<dir>`
itself; the root store never lists the subfolder. Entries carry no steering
identity, so the folder is bound to the profile's bytes: `<dir>/steering/PROFILE`
records the profile file's SHA-1 (and its name, for humans). At startup, when
the recorded digest differs, or is missing while entries exist, the server
deletes the entry files in `<dir>/steering/` (`<40 hex>.kv` only, nothing else)
and logs `steering KV store: profile changed, removed N entries`. Each store
applies `--kv-disk-space-mb` on its own, so the cache can use up to twice the
budget. A profile replaced on disk in the instant between the engine loading it
and the server hashing it is recorded with the new bytes; the next restart then
empties the store.

Files written before content became literal text (payload ABI 2) may hold
control tokens taken from content, so this build does not read them: the
cache starts cold once. They stay on disk and can be deleted by hand.

## Tool history and debugging

For DeepSeek, the server preserves sampled DSML tool blocks and assigns
unguessable tool IDs. Replaying those IDs avoids retokenizing a differently
formatted JSON history. The bounded replay map can be stored in cache files.
When exact replay is unavailable, canonical rendering may require rebuilding
part of the prefix.

`--tool-memory-max-ids` bounds this map.
`--disable-exact-dsml-tool-replay` disables it for diagnostic comparisons.
Use `--trace /tmp/ds4-trace.txt` to record prompt rendering, cache decisions,
generated text, and tool-parser events. Traces can contain sensitive content.

Cache formats are implementation details. The current header and extension
definitions are in [ds4_kvstore.h](../ds4_kvstore.h) and
[ds4_kvstore.c](../ds4_kvstore.c); model-specific payload handling is in
[ds4.c](../sf-ds4-1flash.c).
