# Spec Delta

## ADDED Requirements

### Requirement: Residual-stream steering hook
V4.1 SHALL support a steering point at `residual_stream_post_layer` — the post-layer
HC fold reduced to the single 5120 stream by the mean over the four hc copies, before
the engram read. `--dir-steering-residual F` SHALL apply `y -= F * d[L] * dot(d[L], y)`
there on layers 1-39. The `ffn_out` and `attn_out` points SHALL be unchanged.

#### Scenario: Edit lands at the fold, not at ffn_out
- **WHEN** a steering file is loaded with `--dir-steering-residual 0.5` and the
  opt-in
- **THEN** a graph dump shows the projection applied to the post-HC-fold stream and
  not to `ffn_out`

#### Scenario: No-op gate
- **WHEN** `--dir-steering-residual 0` with a file loaded
- **THEN** the 65-token decode logits, KV and Engram are bitwise identical to a run
  with no steering

### Requirement: Control-vector converter
`dir-steering/tools/controlvector_to_f32.py` SHALL read a GGUF `controlvector`
(39 `direction.<N>` tensors, fp32, 5120, unit norm) and write a ds4 `.f32` of
40 x 5120 with layer 0 zeroed and `direction.N` placed at layer N, plus a `.json`
sidecar recording the hook, default alpha, content hash, base revision and
provenance. A vector whose architecture, width, layer set or norm does not match
SHALL be refused with the cause named.

#### Scenario: Exact layer mapping
- **WHEN** a valid `controlvector` GGUF is converted
- **THEN** the `.f32` is 819200 bytes, layer 0 is all zeros, and layer N holds
  `direction.N` with unit norm preserved

#### Scenario: Mismatch refused
- **WHEN** the GGUF has the wrong hidden width or is missing `direction.1`
- **THEN** the converter exits naming the cause and writes no output
