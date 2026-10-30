# Design

## Context

- `ds4ctl` is the owner's private script (150 lines of sh). It keeps one hand-written plist per profile and a hard-coded profile list. It checks exclusion only through launchd pids, and uses one port for every profile. Its launchd conventions carry over: `bootstrap`, `kickstart -k`, `kill SIGTERM`, `print` for the pid, and `RunAtLoad`/`KeepAlive` false.
- The server reads three things relative to its working directory at every start:
  - `metal/*.metal`, compiled at runtime (`ds4_metal.m`);
  - steering profile names (`com-steering/profiles`);
  - the default model link `deepseek-v4.1-flash.gguf`.

  A copied binary alone therefore does not run, and a service whose cwd is the development checkout runs whatever that checkout holds.
- `gguf/` and the default model link are gitignored. A fresh worktree has no models until `./download.sh <component>` links them. That command reuses the Hugging Face cache and verifies it.
- The engine instance lock is `flock` on `/tmp/sf-ds4-1flash.lock`. Upstream's is `/tmp/ds4.lock`. A running engine keeps its file open.
- The repository's working rule is work in a worktree, merge into `main`. Serve follows `main` after the merge.

## Goals / Non-Goals

**Goals:**
- Model-agnostic script: the same file works in every child, and only the `.conf` differs.
- Everything machine-specific is computed at install time.

**Non-Goals:**
- No config generator, no template engine, no plist file in the repository.
- No readiness wait in `start`: like `ds4ctl`, it returns after launchd accepts the start, and `follow` shows the load.

## Decisions

### D1. Serve is a detached worktree in the model's home

- `git worktree add --detach ~/.sf/<model>/serve main`. It shares the repository's objects (no history copy). The tracked files (about 85 MB) and the build outputs (about 30 MB) are duplicated on disk.
- It lives in the model's own home: there it cannot collide with another child or with upstream, and it stays out of `.claude/worktrees/`, where work worktrees are removed when a change ends.
- `install` may run from the development checkout or from any worktree of the child: `git worktree add` works from either.

*Alternatives:*
- cwd in the development checkout: rejected, it runs unmerged code.
- An install target that copies the binary, `metal/` and `com-steering/profiles`: rejected, more code, and nothing records which commit was copied.

### D2. The `.conf` is a sourced sh fragment

```sh
SF_PORT=8910
SF_SERVER=sf-ds4-1flash-server
SF_COMPONENTS="main:deepseek-v4.1-flash.gguf vision:gguf/DeepSeek-V4.1-Flash-Vision.gguf"
SF_ARGS='--vision gguf/DeepSeek-V4.1-Flash-Vision.gguf --ctx 262144 --tokens 65536 --ssd-streaming --ssd-streaming-cache-experts 82GB --kv-disk-dir @HOME@/kv --kv-disk-space-mb 32768 --steering-profile-on-request com-steering/profiles/sf-ds4-1flash-candor.sfsteer --boost-on-max-effort'
```

- The model name and the child come from the file name: `sf-<model>.conf`.
- `@HOME@` is replaced by `~/.sf/<model>` when the plist is written. It is the only placeholder.
- Relative paths resolve against serve, which is the agent's `WorkingDirectory`.
- Options never contain spaces, so word splitting is safe.

*Alternative:* a plist template with placeholders. Rejected: the XML would be repeated in every child, and the plist would be harder to review than one line of options.

### D3. Installed models are discovered, not listed

- `status` and the exclusion check glob `~/Library/LaunchAgents/com.starforge.sf-*.plist`.
- A model's serve path and config are derived from its name: `~/.sf/<model>/serve/sfctl/sf-<model>.conf`.
- Each command reads only the config of the model it is about. The script is therefore identical in every child, and a symlink to any child's copy manages all of them.

### D4. Exclusion

`start` checks two things:
- the pid of every other `com.starforge.*` agent, through `launchctl print`;
- `lsof -t /tmp/ds4.lock /tmp/sf-*.lock`, minus the pid of the service itself when it is already running.

The lock check covers manual runs and `ds4ctl`, without either script knowing the other. No new lock file is added: the engine's own `flock` still makes the final decision, so if two starts race, the second engine exits on the lock.

### D5. Update

1. Refuse if `git -C serve status --porcelain` is not empty.
2. Record the pid and the old commit.
3. Stop the service if it is running, and wait for the pid to exit (`kill -0` loop, bounded).
4. `git -C serve checkout --detach main`.
5. `make -C serve $SF_SERVER`: only the server binary, the one thing the service runs.
6. Link any component in `SF_COMPONENTS` whose path is missing in serve: each entry is `component:path`, and `./download.sh <component>` runs only for a missing path.
7. Rewrite the plist, since the config may have changed.
8. Start again only if the service was running.
9. Print `old..new`.

If the build fails, sfctl stops there and does not start the service.

### D6. Install and the command link

1. Refuse if serve already exists (use `update`).
2. Refuse if `main` has no `sfctl/sf-<model>.conf` (the change is not merged yet). Create the worktree, build the server, and run `./download.sh` inside serve for each component whose path is missing.
3. Create `~/.sf/<model>/kv`.
4. Write the plist, with logs in `~/Library/Logs/sf/<model>.{out,err}.log`.
5. Bootstrap nothing: the agent is loaded by `start`.
6. Create `~/.local/bin/sfctl`, pointing to serve's script, only when the path is free or already a link into some `~/.sf/*/serve`. Anything else is left alone and reported.

### D7. Fanboost pre-check

When `SF_ARGS` contains `--boost`, which also matches `--boost-on-max-effort`, `start` runs `/usr/local/bin/fanboost check`. It prints the engine's advice (`fanboost/install.sh`) on failure. Same command and same meaning as the engine (boost-mode spec), checked one step earlier.

### D8. Test

`tests/test_sfctl.sh` runs inside `make test`. With `HOME` pointed at a temporary directory, it checks:
- `sfctl plist ds4-1flash` passes `plutil -lint`;
- the plist contains serve's server binary, port 8910 and `<HOME>/.sf/ds4-1flash/kv`;
- a command without a model fails with a usage error;
- `git grep -n /Users/ -- sfctl/` is empty.

It never calls `launchctl` and never builds anything.

## Risks / Trade-offs

- [The script copies in different children drift apart] → each command reads only its own model's config. A master copy in the StarForge orchestrator is a later step (non-goal here).
- [`update` while another engine is running] → `update` builds without a model, which is safe. The restart goes through `start`, so the exclusion still applies.
- [`download.sh` needs `hf` and network the first time] → it runs only at install, or when a link is missing. The README lists `hf` as a prerequisite.
- [A build in serve is CPU-heavy while a benchmark runs on the same machine] → the README says to run `install`/`update` only when the machine is not measuring.

## Migration Plan

`ds4ctl` keeps working and is untouched. Its profiles hold `/tmp/ds4.lock`, so sfctl refuses to start while one of them runs. Removing ds4ctl is the owner's call.

## Open Questions

None.
