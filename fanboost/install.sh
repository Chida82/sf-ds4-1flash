#!/bin/sh
# Builds fanboost, runs its self-test, and installs the root daemon after an explicit "yes".
#
#   ./fanboost/install.sh              install, or update an installed copy
#   ./fanboost/install.sh uninstall    stop the daemon (fans back to Apple's curve) and remove it
#
# Read fanboost/README.md first: the daemon writes the fan controller as root.
set -eu
cd "$(dirname "$0")"

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "fanboost runs only on Apple Silicon Macs." >&2
  exit 1
fi

if [ "${1:-}" = uninstall ]; then
  sudo make uninstall
  echo "fanboost removed; the fans are on Apple's curve."
  exit 0
fi

make
make test

cat <<'EOF'

fanboost installs a daemon that runs as root and writes the Mac's fan
controller (the SMC) through an interface Apple does not document.
- It only ever sets the fans to their maximum or hands them back to Apple's
  curve, so it cannot cool less than macOS would. A crash while boosting
  leaves the fans at full speed: noise, not heat.
- A macOS update can change the SMC and break it. Full fans all the time
  mean more noise and more wear on the fans.
- Any local process can ask for full fans without sudo (that is how
  sf-ds4-1flash --boost uses it).
- You use it at your own risk; nobody else is responsible for what it does
  on your machine.

It installs /usr/local/bin/fanboost and
/Library/LaunchDaemons/com.chida82.fanboost.plist (sudo will ask for your
password). Remove it with: ./fanboost/install.sh uninstall

EOF
printf 'Install fanboost? Type yes to continue: '
read -r answer
if [ "$answer" != yes ]; then
  echo "Not installed."
  exit 1
fi

sudo make install
echo
/usr/local/bin/fanboost status
