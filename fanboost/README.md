# fanboost

An extra cooling daemon for Apple Silicon Macs, developed and tested on a
MacBook Pro M5 Max (Mac17,6) with macOS 27. `sf-ds4-1flash --boost` uses it to
run the fans at full speed while the GPU works. It is bundled here so that the
flag can be tried without anything else; the engine runs the same with or
without it.

Fan control stays with Apple: fanboost puts the fans at 100% when asked, then
gives control back to Apple's curve. It only ever writes the maximum, so it
can never cool less than macOS would.

> **Use at your own risk.** fanboost runs as root and writes the fan
> controller (the SMC) through an interface Apple does not document. Read
> "Risks" below before installing. Whoever installs and runs it is
> responsible for what it does on their machine.

The daemon's own messages, log lines and `fanboost status` output are in
Italian; this page translates them where it matters.

## Install

```sh
./fanboost/install.sh              # build, self-test, confirm, sudo make install
./fanboost/install.sh uninstall    # stop the daemon (fans back to Apple) and remove it
```

The script builds `fanboost`, runs its self-test (`ok`), explains the risks,
and installs only after you type `yes`. It installs:

| What | Where |
|---|---|
| Binary | `/usr/local/bin/fanboost`, `root:wheel` 755 |
| launchd | `/Library/LaunchDaemons/com.chida82.fanboost.plist`, started at boot and restarted if it exits |
| Request | `/tmp/fanboost.lease` (created by `max`, removed by `release`) |
| Pause | the state of the Darwin notification `com.chida82.fanboost` (no file) |
| State for `status` | the state of the notification `com.chida82.fanboost.state`, published by the daemon every cycle; gone when the daemon dies |
| Log | the system log, subsystem `com.chida82.fanboost`, state changes only |

The manual equivalent is `make`, `make test`, `sudo make install`,
`sudo make uninstall` in this directory.

## Risks

- **Root and an undocumented interface.** The daemon writes SMC keys
  (`F*md`, `F*Tg`) that Apple does not document. A macOS update can change
  them and break it.
- **Only full speed or Apple's curve.** There is no intermediate setting, so
  fanboost cannot run the fans slower than Apple would. A crash while boosting
  leaves the fans at full speed until the next start: noise, not heat. At
  start the daemon always hands the fans back to Apple.
- **Noise and wear.** Full fans are loud, and running them at full speed for
  long periods wears them faster.
- **Anyone on the machine can ask for full fans.** `max` and `pause` need no
  sudo. The most `max` can do is full fans while it keeps renewing; the most
  `pause` can do is the stock Mac, Apple's curve and its throttling. Every
  pause is logged.
- **What the daemon reads.** It never opens the request file: it only reads
  its modification time with `lstat`, ignores symlinks and non-regular files,
  and ignores a modification time more than 2 s in the future, so `touch -t`
  cannot hold the fans up forever.

## How it works

The fans have two states and nothing in between:

| State | Fans |
|---|---|
| AUTO | Apple's curve |
| BOOST | 100% at once, no ramp |

Two independent logics can ask for BOOST, and one is enough.

**1. Thermal protection (turn it on with `resume`).** The daemon starts
paused; after `fanboost resume` it reads chip, SSD and battery every 2 seconds.

| Sensor | Enters BOOST (ON) | Back to AUTO (OFF) |
|---|---|---|
| Chip (max of every `Tp*`/`Tg*` sensor) | ≥ 85 °C | ≤ 75 °C |
| SSD (`TH0x`) | ≥ 68 °C | ≤ 64 °C |
| Battery (max of `TB0T`, `TB1T`, `TB2T`) | ≥ 38 °C | ≤ 35 °C |

- BOOST starts only when a sensor stays above ON for **15 consecutive
  seconds**: a short spike does not start the fans, and a drop resets the wait.
- Once on, it lasts at least 10 seconds, then ends when **every** sensor is
  below OFF.

**2. Direct request (`max`/`release`).** Any program can ask for 100%, without
`sudo`:

- `fanboost max` starts BOOST at once, without the 15-second wait, and the
  request lasts **10 seconds**. Another `max` before it expires renews it.
- `fanboost release` withdraws the request, but the fans stay at 100% for **at
  least 3 seconds** (about 4 in practice): heat has inertia, and the tail
  avoids pulses from a close `max` and `release`. A `max` during the tail
  cancels it.
- With no `max` for 10 seconds the request expires on its own, with no further
  tail. A program that hangs or crashes therefore cannot leave the fans at
  full speed.

**Who wins.** The fans are at 100% when thermal protection **or** a request
asks for it. `max` wins over everything, including a paused protection. Hot
protection wins over `release`. Protection keeps evaluating during a request,
so at expiry it takes over without a gap.

**Pause (`pause`/`resume`).** The starting state is pause: at boot, after an
install and after a daemon crash, thermal protection is off until
`fanboost resume`. `fanboost pause` turns it off again. Requests work in pause
too. The daemon itself always runs: only it, as root, can write the fans.

**How a request reaches the daemon.** The daemon runs as root, the commands as
a normal user, and they talk without privileges:
1. **`/tmp/fanboost.lease`.** `max` creates it or updates its modification
   time; `release` deletes it. The request is active while that time is less
   than 10 seconds old.
2. **The state of the notification `com.chida82.fanboost`.** `resume` sets it
   to 1, `pause` to 0; the daemon resets it to 0 at start.
3. **The notification itself.** The commands post it after doing their part,
   so the daemon wakes at once instead of at its next 2-second cycle. A `max`
   that only renews an active request touches the file and does not post, so
   even hundreds of `max` per second do not wake the daemon.

`sf-ds4-1flash --boost` runs `/usr/local/bin/fanboost max` at most once a
second while the GPU has work, and never sends `release`: after the last
request the fans stay at full speed for about 10 seconds, then go back to
Apple's curve. Before loading the model it runs `fanboost check` and refuses
to start when fanboost is missing or its daemon is down. How a request
reaches the daemon is fanboost's business; the engine only runs the commands
and reads their exit status.

## Commands

None needs `sudo`.

| Command | Effect |
|---|---|
| `fanboost` | monitor: every 2 s prints temperatures, thermal state (`si`/`no`/`pausa`), request (`si`/`coda`/`no`) and fans; never writes, even with sudo |
| `fanboost status` | the current state: daemon up or not, protection (paused, below threshold, waiting, BOOST), request (seconds to expiry), fans with rpm/target/mode, temperatures with thresholds |
| `fanboost check` | exits 0 when the daemon is running, otherwise 1 with one line on stderr; prints nothing else (for scripts, such as `sf-ds4-1flash --boost`) |
| `fanboost help` | the command list; an unknown command prints it too and exits with an error |
| `fanboost max` | fans at 100% at once for 10 s; repeated, it renews |
| `fanboost release` | withdraws the request: fans at 100% for at least 3 s (about 4), then protection or Apple's curve |
| `fanboost resume` | turns thermal protection on (it starts paused) |
| `fanboost pause` | turns it off again; `max`/`release` always work |
| `fanboost run` | the daemon (launchd starts it) |
| `fanboost -t` | self-test (`make test`) |

The log of the last day (in zsh `log` is a builtin, so use the full path):

```sh
/usr/bin/log show --last 1d --predicate 'subsystem == "com.chida82.fanboost"'
```

Typical lines: `richiesta: max` (request), `BOOST (richiesta)`,
`richiesta: release, ventole al 100% per almeno 3 s`, `richiesta: scaduta`
(expired), `termica: chip 86.2°C (soglia 85)` (thermal, threshold),
`AUTO: chip 71.0 ssd 45.3 batteria 33.9 °C`, `pause: termica spenta, richieste
attive`, `resume: termica attiva`.

## Times and thresholds

All at the top of `fanboost.c`:

| Constant | Value | Meaning |
|---|---|---|
| `PERIOD` | 2 s | interval between readings |
| `ENTER` | 15 s | time above ON before each thermal BOOST |
| `HOLD` | 10 s | minimum length of a thermal BOOST |
| `TTL` | 10 s | validity of a `max` |
| `TAIL` | 3 s | minimum time at 100% after a `release` (about 4 s with the readings) |
| `ON[]`, `OFF[]` | see the table above | thresholds for chip, SSD, battery |

## SMC notes (verified on the M5)

- Reading needs no root: IOKit `AppleSMC`, selector 2 (cmd 9 key info, 5 read,
  6 write, 8 key by index). Writing needs root.
- On the M5, `F*md = 1` is enough for manual mode (lower case; fallback
  `F*Md`); no `Ftst`, which only M1-M4 need. The SMC protocol follows
  `SMC/smc.swift` in [exelban/stats](https://github.com/exelban/stats).
- BOOST writes `F*Tg = F*Mx` first, then `F*md = 1`, so there is never a
  moment in manual mode with a zero target. AUTO writes `F*md = 0` and then
  `F*Tg = 0`, giving control back to Apple first.
- From stopped fans the SMC holds the motor at about 7% for about 5 s before
  it turns; from moving fans the maximum arrives in about 1.3 s.
- The SMC sometimes refuses the first write: it is retried up to 10 times,
  every 100 ms. In BOOST, mode and target are rewritten every cycle, which
  recovers a reset after sleep.
- `TH0x` is the SSD (NAND) and matches the NVMe SMART temperature; the `TS*`
  keys are not the SSD. `Tf06`/`Tf16` read about 95 °C and map to nothing on
  the M5, so they are excluded.
- Under full GPU load the fans at 100% instead of Apple's 53% lower the chip
  only a little. In sf-ds4-1flash's bench sweeps the chip still reached
  92-95 °C with full fans, against 100.9 °C on Apple's curve
  (`speed-bench/perf-record.md`).
