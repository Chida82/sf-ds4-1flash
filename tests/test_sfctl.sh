#!/bin/sh
# Model-less checks of sfctl/sfctl (OpenSpec 675). HOME points at a scratch
# directory, so nothing is installed and launchctl is never asked to change
# anything; no build runs.
set -u

root=$(cd "$(dirname "$0")/.." && pwd -P)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail=0

check() {
    # $1 name, rest: command that must succeed
    name=$1
    shift
    if "$@"; then
        echo "sfctl: $name: ok"
    else
        echo "sfctl: $name: FAILED"
        fail=1
    fi
}

sfctl() { HOME="$tmp" "$root/sfctl/sfctl" "$@"; }

plist=$(sfctl plist ds4-1flash)
plist_lints() { printf '%s\n' "$plist" | plutil -lint -s - ; }
plist_has() { printf '%s\n' "$plist" | grep -qF "$1"; }

check "plist is a valid property list" plist_lints
check "plist runs serve's server" plist_has "<string>$tmp/.sf/ds4-1flash/serve/sf-ds4-1flash-server</string>"
check "plist port 8910" plist_has "<string>8910</string>"
check "plist KV in the model home" plist_has "<string>$tmp/.sf/ds4-1flash/kv</string>"
plist_false() { printf '%s\n' "$plist" | grep -A1 -F "<key>$1</key>" | grep -qF '<false/>'; }
check "plist never starts on its own" plist_false RunAtLoad
check "plist never restarts on exit" plist_false KeepAlive
check "no placeholder left" sh -c '! printf "%s\n" "$1" | grep -q "@HOME@"' sh "$plist"

usage_error() { sfctl "$@" >/dev/null 2>&1; [ $? -eq 2 ]; }
check "stop without a model is a usage error" usage_error stop
check "start without a model is a usage error" usage_error start
check "unknown command is a usage error" usage_error bogus
not_installed() { sfctl start q3-8flash 2>&1 | grep -q "q3-8flash is not installed"; }
check "unknown model is named" not_installed
nothing_installed() { [ "$(sfctl status)" = "no sfctl service installed" ]; }
check "status with nothing installed" nothing_installed
check "plist writes nothing" sh -c '[ ! -e "$1/Library" ] && [ ! -e "$1/.sf" ]' sh "$tmp"
generic() { ! grep -rn /Users/ "$root/sfctl" >/dev/null; }
check "no user path under sfctl/" generic

[ "$fail" -eq 0 ] && echo "sfctl tests passed"
exit "$fail"
