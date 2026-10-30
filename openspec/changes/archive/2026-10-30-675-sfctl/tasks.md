# Tasks

Work happens on a branch in a worktree, never on main. No commit or push without a request. Starts from main with `670` landed (the config uses `--boost-on-max-effort`).

## 1. Script and config

- [x] 1.1 `sfctl/sf-ds4-1flash.conf` as in design D2. Verify `sh -n` on it, and `git grep -n /Users/ -- sfctl/` is empty.
- [x] 1.2 `sfctl/sfctl`: argument parsing, model lookup (D3), `plist`, `status`, `logs`, `follow`. Every one-model command requires a model. Verify `sh -n`, then `sfctl plist ds4-1flash | plutil -lint -` with `HOME` set to a scratch directory.
- [x] 1.3 `start`, `stop` and `restart`, with the exclusion check (D4) and the fanboost pre-check (D7). Verify `sfctl stop` without a model fails and names the running model. Leave the launchd paths for group 3.
- [x] 1.4 `install`, `update` and `uninstall` (D1, D5, D6). Verify `sh -n`, and read each refusal path: serve exists, serve dirty, command link occupied by a file.
- [x] 1.5 `tests/test_sfctl.sh` and its rule in `make test` (D8). Verify `make test` prints the sfctl test's checks by name, and `grep -c '^test:' Makefile` is 1.

## 2. Docs

- [x] 2.1 `sfctl/README.md`, written for an agent:
  - prerequisites: macOS, `hf`, fanboost for this config, `~/.local/bin` on `PATH`;
  - "Ask the owner before `install` or `uninstall`";
  - install;
  - commands, with the ds4-1flash examples;
  - "Syncing serve": preconditions (merged into main, serve clean), `sfctl update <model>`, verification (`sfctl status` shows serve equal to main; a new start in the log if the service was running), and reporting `git log --oneline old..new`;
  - "never edit serve, never update from a work branch";
  - how a new child adds its `.conf`.

  Verify every command in it matches the script's usage text.
- [x] 2.2 `AGENTS.md`:
  - a "Serving (sfctl)" section: a request to sync sfctl or serve means `sfctl/README.md` "Syncing serve", after the change is merged into main;
  - an Identity row "Service: sfctl, port 8910, serve `~/.sf/ds4-1flash/serve`".

  `README.md`: a short "Running as a service" section that points to `sfctl/README.md`. Verify `git grep -n sfctl -- AGENTS.md README.md` shows all three.

## 3. Acceptance on the machine

Ask the owner first: these steps install a LaunchAgent and a `~/.local/bin` link, and they load the model.

- [x] 3.1 After the merge into main, run `./sfctl/sfctl install` from the development checkout. Verify:
  - `~/.sf/ds4-1flash/serve` is at `main`;
  - `sfctl status` shows `ds4-1flash stopped port 8910` with serve equal to main;
  - `plutil -lint` passes on the installed plist;
  - `launchctl print gui/$(id -u)/com.starforge.sf-ds4-1flash` fails (nothing loaded).
- [x] 3.2 `sfctl start ds4-1flash`, then `follow` until the server listens. Verify:
  - `curl 127.0.0.1:8910/v1/models` lists `deepseek-v4.1-flash` and `deepseek-v4.1-flash-steering`;
  - one short `max` request logs boost on and off (`670`).
- [x] 3.3 Exclusion: with the service running, start the dev CLI. Verify it exits on the instance lock. Stop the service, start the dev CLI with a long prompt, run `sfctl start ds4-1flash`, and verify sfctl refuses with the CLI's pid.
- [x] 3.4 `sfctl update ds4-1flash` with the service running and serve already at main. Verify it stops, rebuilds, restarts and prints `old..new` with equal commits. Make a file in serve dirty and verify `update` refuses without stopping anything; then restore it.
- [x] 3.5 `sfctl stop ds4-1flash`, then log out and in, or reboot. Verify no `sf-ds4-1flash-server` process is running. (Verified by reloading the agent the way login does, `launchctl bootout` then `bootstrap` of the plist: state `not running`, `runs = 0`, no server process.)

## 4. Integration

- [x] 4.1 `make test` (read the test names) and `openspec validate 675-sfctl --strict`. Verify both pass.

No A/B run and no parity oracle: the change adds no engine or server code.

## Workflow follow-up

- StarForge orchestrator (outside this repository): add the sfctl port column to the children registry (8909, 8910, 8911, 8912).
- After every later merge into main: "sync sfctl" = `sfctl/README.md` "Syncing serve".
