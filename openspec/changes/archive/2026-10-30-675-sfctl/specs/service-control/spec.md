# Spec Delta

## Purpose

Defines how a StarForge child's model is installed, run, stopped, inspected, synced to main and removed as an on-demand local launchd service through `sfctl`, from a build that always matches one commit of main.

## ADDED Requirements

### Requirement: No service starts on its own
An installed service SHALL start only through `sfctl start <model>`. It SHALL NOT start at login, at install, or after it exits.

#### Scenario: Login
- **WHEN** the owner logs in with `ds4-1flash` installed
- **THEN** no `sf-ds4-1flash-server` process is running

#### Scenario: Service exits
- **WHEN** a running service exits or crashes
- **THEN** it stays stopped until the next `sfctl start ds4-1flash`

### Requirement: Commands name their model
Every command that acts on one model (`start`, `stop`, `restart`, `update`, `uninstall`, `logs`, `follow`, `plist`) SHALL require the model name and SHALL fail with a usage error without it. A model that is not installed SHALL be reported by name.

#### Scenario: Stop without a model
- **WHEN** the owner runs `sfctl stop` while `ds4-1flash` is running
- **THEN** sfctl exits with an error that names the running model and stops nothing

#### Scenario: Unknown model
- **WHEN** the owner runs `sfctl start q3-8flash` and that model is not installed
- **THEN** sfctl exits with an error saying `q3-8flash` is not installed

### Requirement: Status covers every installed model
`sfctl status` without a model SHALL list every installed model, each with its state (running with pid, or stopped), its port, the serve commit, and whether that commit differs from local `main`.

#### Scenario: Serve behind main
- **WHEN** a change was merged into `main` and serve was not updated
- **THEN** `sfctl status` marks `ds4-1flash` as behind main and shows both commits

### Requirement: One engine at a time
`sfctl start` SHALL refuse while another sfctl service is running, or while any ds4 engine instance lock (`/tmp/ds4.lock` or `/tmp/sf-*.lock`) is held by a process. The message SHALL name the holder's pid and, for an sfctl service, the command that stops it.

#### Scenario: Another model is running
- **WHEN** `q3-8flash` runs as an sfctl service and the owner runs `sfctl start ds4-1flash`
- **THEN** sfctl refuses, naming `q3-8flash`, its pid and `sfctl stop q3-8flash`

#### Scenario: A manual engine run holds a lock
- **WHEN** a manually started `sf-ds4-1flash` CLI, or an upstream ds4 server, holds its instance lock
- **THEN** `sfctl start ds4-1flash` refuses and names that pid

### Requirement: The service runs from a serve worktree at main
`sfctl install` SHALL create a git worktree of the child at `~/.sf/<model>/serve`, detached at local `main`, build it, and run the service from it. The service SHALL NOT run binaries or read Metal sources or steering profiles from any other checkout.

#### Scenario: Development branch checked out
- **WHEN** the development checkout is on a work branch with edited kernels and the owner restarts the service
- **THEN** the service runs the binary and kernels of serve's commit

### Requirement: Update syncs serve to local main
`sfctl update <model>` SHALL bring serve to local `main` and rebuild it. A running service SHALL be stopped first and started again after a successful build; a stopped service SHALL stay stopped. It SHALL refuse when serve has local modifications, and SHALL report the old and new commit.

#### Scenario: Update while running
- **WHEN** `ds4-1flash` is running and the owner runs `sfctl update ds4-1flash` after a merge
- **THEN** the service stops, serve moves to `main`, the build completes, the service starts again, and sfctl prints the old and new commit

#### Scenario: Dirty serve
- **WHEN** a file in serve was modified
- **THEN** `sfctl update` refuses without stopping the service and names the modified path

#### Scenario: Failed build
- **WHEN** the build fails after serve moved to the new commit
- **THEN** sfctl exits with an error and the service is not started

### Requirement: Model config is per model and generic
Each model SHALL have one config file in its child's repository that sets the service port, the server binary, the GGUF components to link, and the server options. Neither that file, nor the script, nor its README SHALL contain a user name, a home path or a machine-specific path. Those come from the environment at install time.

#### Scenario: Repository files
- **WHEN** the files under `sfctl/` are searched for `/Users/`
- **THEN** there is no match

#### Scenario: Different binaries
- **WHEN** two children are installed
- **THEN** each agent runs its own child's server binary with its own options, from its own serve worktree

### Requirement: Boost needs are checked before start
When a model's server options ask for boost, `sfctl start` SHALL run `fanboost check` first and SHALL refuse to start with a message pointing to `fanboost/install.sh` when the check fails.

#### Scenario: fanboost daemon down
- **WHEN** the owner runs `sfctl start ds4-1flash` and the fanboost daemon is not running
- **THEN** sfctl refuses before asking launchd to start anything

### Requirement: Uninstall keeps data
`sfctl uninstall <model>` SHALL stop the service, remove its launchd agent and its serve worktree, and SHALL keep the disk KV cache, the logs, the CLI history and the Hugging Face model cache. It SHALL remove the `sfctl` command link only when that link points into the removed worktree.

#### Scenario: Uninstall
- **WHEN** the owner runs `sfctl uninstall ds4-1flash`
- **THEN** `~/.sf/ds4-1flash/serve` and the agent are gone, and `~/.sf/ds4-1flash/kv` and the GGUF files in the Hugging Face cache are still there

### Requirement: The agent definition can be inspected
`sfctl plist <model>` SHALL print the launchd agent definition that `install` and `update` write, without changing anything.

#### Scenario: Inspect
- **WHEN** the owner runs `sfctl plist ds4-1flash`
- **THEN** a valid property list is printed, its program is `sf-ds4-1flash-server` inside serve, and no file is written
