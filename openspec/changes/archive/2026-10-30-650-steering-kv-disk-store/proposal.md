# Proposal

## Why

A server started with a steering profile runs with no disk KV cache at all (`ds4_server.c:14961`). The reason was sound: cache entries carry no steering identity. A prefix computed with steering differs from the same prefix computed without it from layer 1 onward, so a shared entry would silently change the model. After `640` most requests to such a server are unsteered and pay for the missing cache on every long agent prompt. Steered requests deserve a cache too, but one that can never be read by an unsteered request, nor by a steered request made under a different profile.

## What Changes

- **Two stores under one `--kv-disk-dir`:**
  ```
  <kv-disk-dir>/
    <40hex>.kv ...        unsteered requests (today's store, untouched)
    steering/
      PROFILE             identity of the profile whose entries live here
      <40hex>.kv ...      steered requests only
  ```
  - The root store already ignores `steering/`: `kv_cache_refresh` lists only `<40 hex>.kv` names at its own level (`ds4_kvstore.c:474`).
  - The steering store is a second `ds4_kvstore` opened on `<dir>/steering` with the same options as the root. It exists only when the server loaded a profile.
- **The budget is duplicated.** Each store gets `--kv-disk-space-mb` as its own budget, so the disk total can reach twice the value. Eviction inside each store is today's: hit count with half-life, anchor and continued-prefix factors, lowest score first.
- **Profile identity by marker.**
  - `steering/PROFILE` holds the SHA-1 of the loaded profile file's bytes, plus the profile's name for humans.
  - At server start:
    - **Marker matches:** the store opens as is.
    - **Marker differs, or is missing while `.kv` files exist:** the server deletes only the files in `steering/` whose names are `<40 hex>.kv`, logs how many, writes the new marker, then opens the store. The "missing" case covers a crash between the first store and the marker write.
  - Nothing outside `steering/`, and nothing in it that is not an entry file, is ever deleted. A profile rebuilt under the same name therefore never reuses entries computed with the old bytes.
- **Each request uses only its own store.** A request's steering flag (`640`) selects the store for lookup, load, store, continued-prefix stores, eviction context and tool-memory restore. An unsteered request never opens `steering/`, and a steered request never reads the root.
- **The engine lets the server persist steered sessions.**
  - The persistence refusal for steered sessions (`630`'s form of `ds41_steering_refuses_persistence`) gains a session-level permission that only the server sets, on sessions it routes to the steering store.
  - The payload format is unchanged and records no identity: segregation by store is the identity.
  - The CLI and eval have no disk cache and keep the refusal.
- **The server's guard goes.** `--kv-disk-dir` opens whether or not a profile is loaded. The log line that announced the skip is removed.
- **Tests:**
  - **Server unit tests** on a temporary directory, with entry files fabricated as the existing kvstore tests do (`ds4_server.c:19604`):
    - marker match keeps entries;
    - marker mismatch deletes only `steering/<40hex>.kv`;
    - a missing marker with entries deletes them;
    - root files and stray files survive;
    - store selection by request flag;
    - the root store does not list `steering/`.
  - **Model-backed acceptance:**
    - a steered request stores under `steering/`, and its repeat loads that entry and produces bitwise the same output as the cold run;
    - an unsteered request does the same in the root;
    - restarting with a changed profile empties `steering/` only.
- **Docs:**
  - `AGENTS.md`: the Steering row of Identity (the server skip of `--kv-disk-dir` becomes the store split).
  - `com-steering/README.md`.
  - `ds4_help.c`: `--kv-disk-dir` mentions the `steering/` subfolder and the duplicated budget.
  - `docs/upstream-prs.md` line `401`: "the server skips `--kv-disk-dir`" becomes the store split.

Non-goals:
- No change to the `.kv` file format or the eviction score.
- No cache for the CLI or eval.
- No per-profile subfolders: one profile, one `steering/`.
- No shared budget between the two stores.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `directional-steering`: "Steering and persistent state" is restated. Steered sessions refuse persistence unless the frontend has segregated them by profile identity, and the server does so. The scenario "Steered session with a KV root" changes from refused to stored under `steering/`.
- `request-steering` (introduced by `640`): adds the per-request store selection and the profile-identity marker.

## Impact

- **Code:**
  - `ds4_server.c`: store open, marker check and wipe, per-request store selection, guard removal, tests.
  - `ds4.c` / `ds4.h`: the session's persistence permission.
  - `ds4_kvstore.c` is unchanged unless the inventory of `640` shows a path that builds entry paths outside `kc->dir`.
- **Disk:** up to twice `--kv-disk-space-mb`. A profile change deletes the old steering entries at the next start, by design.
- **Speed:** unsteered requests on a profiled server get the disk cache back. No kernel or schedule change; output bitwise identical between a cold computation and a cache hit, as today.
- **Order:** fifth and last. It needs `640`'s request flag and live-state inventory, and `630`'s switch.
