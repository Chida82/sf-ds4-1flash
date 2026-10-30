# sfctl

`sfctl` runs a StarForge model as an on-demand local service on macOS, through
a launchd agent in the user's session. It is written for agents: follow the
procedures below as written.

- One script, the same in every child (`sfctl/sfctl`), and one config per model
  (`sfctl/sf-<model>.conf`). `<model>` is the child's name without `sf-`:
  `ds4-1flash` runs `sf-ds4-1flash`.
- Each service runs from its own **serve worktree**, `~/.sf/<model>/serve`: a git
  worktree of the child detached at local `main`, built there. Binary, Metal
  sources and steering profiles therefore always come from one commit of `main`,
  never from a development branch.
- Nothing starts at login, and nothing restarts after an exit or a crash. A
  model runs only after `sfctl start <model>`.
- One engine at a time: `start` refuses while another sfctl service runs, or
  while any process holds an engine instance lock (`/tmp/ds4.lock`,
  `/tmp/sf-*.lock`), which covers manual runs and upstream ds4.

## Ask the owner before `install` or `uninstall`

Both change the machine: a worktree under `~/.sf/`, a LaunchAgent plist, logs
under `~/Library/Logs/sf/`, and the `~/.local/bin/sfctl` link. Run them only
after the owner has said yes for this machine. `start`, `stop` and `update` load
or unload a model of about 340 GiB from SSD: do not run them while the machine is
measuring something (a benchmark, an A/B run, an eval).

## Prerequisites

- macOS on Apple silicon, with the child's own build prerequisites (`make`, the
  Xcode command line tools).
- The Hugging Face CLI, `hf`, for `./download.sh`. Models live once in the shared
  Hugging Face cache; serve only holds links to them.
- `~/.local/bin` on `PATH`, for the `sfctl` command.
- fanboost, when the model's config asks for boost (the ds4-1flash config does,
  with `--boost-on-max-effort`): `./fanboost/install.sh` in the child, see
  `fanboost/README.md`. `start` runs `fanboost check` and refuses when it fails.

## Install

From a checkout of the child (any worktree), after the change that added the
model's `.conf` is merged into `main`:

```sh
./sfctl/sfctl install            # the checkout's only model; or: install ds4-1flash
```

It:
1. refuses if `~/.sf/<model>/serve` already exists (use `update`) or `main` has
   no `sfctl/sf-<model>.conf`;
2. creates the serve worktree at `main` and builds the server there;
3. runs `./download.sh <component>` in serve for each model link it lacks
   (the first time this verifies or downloads the GGUFs through `hf`);
4. writes the agent `~/Library/LaunchAgents/com.starforge.sf-<model>.plist`,
   without loading it;
5. creates `~/.local/bin/sfctl` pointing to serve's script, only when that
   path is free or already a link into some `~/.sf/*/serve`.

Verify:
- `sfctl status` shows `<model> stopped port <port>, serve <sha> = main`;
- `plutil -lint ~/Library/LaunchAgents/com.starforge.sf-<model>.plist` passes;
- `launchctl print gui/$(id -u)/com.starforge.sf-<model>` fails: nothing is
  loaded until `start`.

## Commands

```text
sfctl install [<model>]   from a child checkout (see Install)
sfctl update <model>      sync serve to local main and rebuild (see Syncing serve)
sfctl start <model>       start the service
sfctl stop <model>        stop the service
sfctl restart <model>     stop, then start
sfctl status [<model>]    state, pid, port and serve commit; all models without a name
sfctl logs <model> [N]    last N lines of the service log (default 80)
sfctl follow <model>      follow the service log
sfctl plist <model>       print the launchd agent definition, write nothing
sfctl uninstall <model>   remove the agent and serve; keep KV, logs and models
```

Every command except `install` and `status` needs the model name; without it
sfctl exits with a usage error that names the running model, if any.

With ds4-1flash:

```sh
sfctl start ds4-1flash          # returns at once; the model loads in the background
sfctl follow ds4-1flash         # until "listening on http://127.0.0.1:8910"
curl -s 127.0.0.1:8910/v1/models
sfctl status
sfctl logs ds4-1flash 200
sfctl stop ds4-1flash
```

The ds4-1flash service (`sf-ds4-1flash.conf`) listens on `127.0.0.1:8910` with
the 1017 model and the vision encoder, a 256K context, SSD streaming with an
`82GB` expert cache, a 32 GiB disk KV cache in `~/.sf/ds4-1flash/kv`, the candor
steering profile loaded off (a request selects it with a `-steering` model id,
such as `deepseek-v4.1-flash-steering`), and `--boost-on-max-effort` (boost only
while a request with reasoning effort `max` generates). Logs go to
`~/Library/Logs/sf/ds4-1flash.out.log` and `.err.log`.

## Syncing serve

A request to "sync sfctl" or "sync serve" means this procedure. Serve follows
the child's local `main`; it is never updated from a work branch.

Preconditions:
1. The change is merged into the child's local `main`. A change still on a work
   branch is not served.
2. Serve is clean: `git -C ~/.sf/<model>/serve status --porcelain` prints
   nothing. Serve is never edited by hand; if it is dirty, stop and report the
   paths to the owner instead of discarding them.
3. The machine is not measuring anything.

Run:

```sh
sfctl status                 # note the state and the serve commit
sfctl update <model>
```

`update` refuses on a dirty serve without stopping anything. Otherwise it stops
the service if it is running, moves serve to `main`, builds the server, links
any model the config needs and serve lacks, rewrites the agent, starts the
service again only if it was running, and prints `old..new` with the commits in
between. If the build fails it stops there and leaves the service stopped.

Verify:
- `sfctl status` shows `serve <sha> = main`;
- if the service was running: it is running again, and `sfctl logs <model>`
  shows a new start (`listening on ...`) after the update.

Report to the owner the `old..new` range and its commits
(`git -C ~/.sf/<model>/serve log --oneline old..new`), and whether the service
was restarted.

## Uninstall

```sh
sfctl uninstall <model>
```

It stops the service, removes the agent and the serve worktree, and removes
`~/.local/bin/sfctl` only when it points into that worktree (then it relinks it
to another installed model, if any). It keeps `~/.sf/<model>/kv`, the CLI
history, the logs and the Hugging Face cache. A serve with local modifications
is not removed: git refuses and sfctl reports it.

## Adding a model

A child adds its own service in its own change:
1. copy `sfctl/sfctl` and this README from a child that has them, unchanged;
2. write `sfctl/sf-<model>.conf` with `SF_PORT` (one per child: 8909 ds4flash,
   8910 ds4-1flash, 8911 glm5-3flash, 8912 q3-8flash), `SF_SERVER`,
   `SF_COMPONENTS` (`component:path` pairs for `./download.sh`) and `SF_ARGS`
   (server options after `--port`; relative paths resolve in serve; `@HOME@`
   becomes `~/.sf/<model>`; no option may contain a space);
3. add `tests/test_sfctl.sh` to `make test` and adapt its model name and port.

Nothing in `sfctl/` may name a user or a machine path: everything specific to a
machine is computed when sfctl runs.
