# Proposal

## Why

The owner runs models as on-demand local services through a private launchd script, `ds4ctl`. It manages upstream ds4 only. It runs whatever is checked out in the upstream development tree, and its paths (KV directory, logs, port 8904) belong to upstream. This child needs the same convenience for `sf-ds4-1flash-server`, with three differences:
- the service must never run a development branch, or Metal kernels that do not match its binary;
- the same tool must later serve the other StarForge children, which have different binaries and options;
- an agent must be able to install it on a Mac, and keep it in sync with main, from instructions in the repository alone.

## What Changes

- **New directory `sfctl/` in the child**, holding:
  - `sfctl`: a POSIX sh script;
  - `sf-ds4-1flash.conf`: this model's service config;
  - `README.md`: written for an agent.

  None of these files contains anything specific to one user or machine: paths come from `$HOME`, `id -u` and the script's location. The script is model-agnostic, so each child carries the same copy, and only the `.conf` differs.
- **A serving worktree.** `~/.sf/ds4-1flash/serve` is a git worktree of this repository, detached at local `main`, and built there. The service runs from it, so binary, `metal/` sources and steering profiles always come from one commit. It is never edited by hand.
- **Commands.** Every command except `install` and `status` takes the model name, `ds4-1flash`:

  | Command | What it does |
  |---|---|
  | `install` | Run from a checkout of the child. Creates the serve worktree at `main`, builds it, links the GGUF components with `./download.sh`, writes the launchd agent `com.starforge.sf-ds4-1flash` and the `~/.local/bin/sfctl` symlink into serve |
  | `update <model>` | Syncs serve to local `main` and rebuilds it. A running service is stopped first and restarted after; a stopped one stays stopped |
  | `start <model>`, `stop <model>`, `restart <model>` | Service control |
  | `status [<model>]` | State, pid, port and serve commit, and whether serve equals `main`. Without a model, every installed model |
  | `logs <model> [N]`, `follow <model>` | Show or follow the service log |
  | `plist <model>` | Prints the agent definition it would install |
  | `uninstall <model>` | Removes the agent and the serve worktree, and keeps KV, logs and the model cache |
- **Nothing starts on its own.** The agent has `RunAtLoad` and `KeepAlive` false, so a model runs only after `sfctl start <model>`.
- **One engine at a time.** `start` refuses while another sfctl service runs, or while any engine instance lock (`/tmp/ds4.lock`, `/tmp/sf-*.lock`) is held by a process. This covers manual CLI runs, upstream ds4 and `ds4ctl`. The child's instance lock is unchanged, and no new lock file is added.
- **This model's service** (`sf-ds4-1flash.conf`):
  - port 8910 on 127.0.0.1;
  - the 1017 main model and the vision encoder;
  - `--ctx 262144 --tokens 65536`;
  - `--ssd-streaming --ssd-streaming-cache-experts 82GB`;
  - disk KV in `~/.sf/ds4-1flash/kv` (internal SSD, 32 GiB);
  - `--steering-profile-on-request` with `sf-ds4-1flash-candor`;
  - `--boost-on-max-effort` (`670`).

  `start` runs `fanboost check` first when the options ask for boost, so a missing daemon is reported at the prompt rather than only in the log.
- **Syncing serve is documented for agents.**
  - `sfctl/README.md` gets the install procedure and a "Syncing serve" procedure: preconditions, `sfctl update`, verification and report.
  - `AGENTS.md` gets a short "Serving (sfctl)" section: a request to sync sfctl or serve means running that procedure after the change is merged into main.
- **Docs:** `README.md` gets a short "Running as a service" section, and the Identity table of `AGENTS.md` records the sfctl port and the serve path.

Non-goals:
- No start at login, and no restart on crash.
- No profile variants (light, max) in this change.
- No support for the other children yet: their `.conf` files come with their own changes.
- No master copy of the script in the StarForge orchestrator yet.
- `ds4ctl` is not touched.

## Capabilities

### New Capabilities
- `service-control`: how a model is installed, run, stopped, inspected, synced to main and removed as an on-demand local service. Covers the serve worktree, the per-model config, the exclusion between engines, and the no-autostart rule.

### Modified Capabilities
(none)

## Impact

- **New files:** `sfctl/sfctl`, `sfctl/sf-ds4-1flash.conf`, `sfctl/README.md`, and one model-less test wired into `make test`.
- **Edited:** `Makefile` (the test target), `README.md`, `AGENTS.md`.
- **No engine or server code changes.** The service config uses `670`'s `--boost-on-max-effort`, so this change lands after `670`.
- **On the machine, only when `install` runs:**
  - a worktree at `~/.sf/ds4-1flash/serve`;
  - a LaunchAgent plist;
  - logs under `~/Library/Logs/sf/`;
  - the `~/.local/bin/sfctl` symlink.

  An agent asks the owner before running `install` or `uninstall`.
- **StarForge orchestrator:** a follow-up outside this repository adds an sfctl-port column to the children registry (8909 ds4flash, 8910 ds4-1flash, 8911 glm5-3flash, 8912 q3-8flash).
- **Speed and output:** unchanged. No A/B run, no parity oracle.
