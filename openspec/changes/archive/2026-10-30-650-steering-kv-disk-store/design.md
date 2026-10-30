# Design

## Context

**The store.** `ds4_kvstore` (`ds4_kvstore.c`) holds one directory of `<sha1(prefix text)>.kv` entries:
- `ds4_kvstore_open` creates the directory (`kv_mkdir_p`) and runs one eviction pass.
- `kv_cache_refresh` lists only names that are exactly 40 hex characters plus `.kv`, at the store's own level, so a subdirectory is invisible to it.
- The lookup matches entries on the text prefix's SHA-1, model id, quant bits and context.
- Eviction removes the lowest `ds4_kvstore_entry_eviction_score` until the store fits `budget_bytes`.

**The server.**
- One store, `server.kv` (`ds4_server.c:9388`), used at 21 places: tool-memory restore (`10332-10351`), live-prefix store (`10515`), continued stores and suppression (`10593`, `10643`), load (`10681`), the request path's load/store/evict (`12680-12808`), shutdown stores (`14551`, `15102`) and open (`14971`).
- After `640` a request carries `steering`, and each slot's session carries its switch (`630`).
- The server skips opening the store while a profile is loaded (`14961`).

**The engine.** After `630`, `ds41_steering_refuses_persistence` refuses every payload stage, load and snapshot of a session whose steering is on.

## Goals / Non-Goals

**Goals:**
- Two stores, chosen by one rule.
- A profile identity check that can only ever delete steering entries.
- No change to the store's format or to its eviction.

**Non-Goals:**
- A combined budget.
- Per-profile folders.
- A cache for the CLI or eval.
- Identity inside payloads.

## Decisions

### D1. A second store, chosen by the slot's switch

`server` gains `kv_disk_cache kv_steering`. It is opened on `<dir>/steering` with the same budget and options as `kv`, only when a profile is loaded.

One accessor, `server_kv(server *s, bool steering)`, returns `&s->kv` or `&s->kv_steering`. Each of the 21 sites takes its store from the steering of what it serves:
- `ds4_session_steering(slot->session)` where a slot is at hand (stores, loads, shutdown);
- `req->steering` where only the request exists (tool-memory restore at parse time, which therefore gains the flag as a parameter).

The slot's switch was set from the request (`640` D4) before any store or load, so the two sources agree. A store opened while no profile is loaded is never selected, because no session or request can be steered then.

Alternative considered: one store with the profile identity salted into the entry names. It would make the rejected "strategy 2" one directory with a shared budget. The owner chose a separate folder with a marker and a duplicated budget.

### D2. Identity marker

At startup, after the engine has loaded the profile and before `kv_cache_open` on the steering store:
1. Hash the profile file. The engine exposes the resolved path (`ds4_engine_steering_profile_path`); the server reads the file whole, about 2.4 MB, and hashes it with `ds4_kvstore_sha1_bytes_hex`.
2. Read `<dir>/steering/PROFILE`, if present: a line `sha1 <40 hex>` and a line `name <basename>`, for humans.
3. Decide:
   - **Equal:** do nothing.
   - **Different, or missing while entries exist:** delete every entry in `<dir>/steering` whose name passes `ds4_kvstore_sha_hex_name`, and log `ds4-server: steering KV store: profile changed, removed N entries`.
4. Write the marker through a temporary file and `rename`, so a crash leaves either the old marker or the new one.
5. Open the store.

Nothing else is ever unlinked: not the root, not non-entry files, and not subdirectories.

Hash by path rather than inside the engine's loader: the loader reads the header and matrices in pieces, while the server needs one digest of the whole file. A profile replaced on disk between the engine's load and the hash would be recorded with the new bytes. The window is a few milliseconds at startup and the result is a cache that the next restart empties. That is documented, not guarded.

### D3. Engine permission for steered persistence

`ds4_session_set_persist_steered(ds4_session *s, bool on)` sets a session flag. `ds41_steering_refuses_persistence` refuses when `steering_on && !persist_steered`. When both stores are open, the server sets it on every slot's session at startup. The CLI and eval never set it, so their behaviour is `630`'s.

The payload format does not change. A steered payload carries no identity of its own; its folder and the marker are the identity. That is why only the server, which guarantees the folder, may set the flag.

### D4. The guard goes

The block at `ds4_server.c:14961` that skipped `--kv-disk-dir` under a profile is removed, together with its log line. The `sf:` comment explaining it moves, rewritten, to the steering store's open.

### D5. Tests

**Model-less**, server unit tests on a temporary directory, with entries fabricated by `ds4_kvstore_fill_header` as the existing kvstore tests do (`ds4_server.c:19604`):
- the marker decisions: equal, different, missing with entries, missing and empty;
- after a wipe, the root's entries, a stray `notes.txt` and a subdirectory in `steering/` all survive;
- `server_kv` selection for the four combinations of profile loaded and steering;
- the root store's entry list excludes `steering/`;
- eviction of an over-budget steering store removes no root file;
- `ds4_session_set_persist_steered`: a steered test session refuses persistence without the flag and passes the check with it.

**Model-backed**, by hand on the branch, with a temporary `--kv-disk-dir`:
1. An unsteered long request, twice: the second loads from the root, with identical tokens.
2. The same for a steered request under `steering/`.
3. The spec's "No cross reads".
4. A restart with a modified copy of the profile (a scale changed by `make_profile.py`): `steering/` is emptied, the root is not, and the log shows the count.

## Risks / Trade-offs

- [The wipe deletes something it should not] → It unlinks only names that the store itself would list as entries, only inside `<dir>/steering`, and the tests above put foreign files next to them.
- [Disk use doubles] → Accepted. Documented next to `--kv-disk-space-mb` in `ds4_help.c` and `docs/SERVER.md`.
- [A profile edited in place keeps its name] → The hash covers the bytes, so the store empties. That is the purpose of the marker.
- [A future upstream kvstore change builds paths outside `kc->dir`] → `640`'s inventory checks it today. The test of "No cross reads" would catch a regression.

## Migration Plan

None. Existing root entries stay valid. The first start with a profile creates `steering/` and its marker.
