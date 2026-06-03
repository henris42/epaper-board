#!/usr/bin/env bash
# Push the app to the Odroid C2 and (optionally) run setup there.
# Run from your workstation:   ./deploy.sh
#
# Env overrides:
#   TARGET   ssh destination           (default root@10.1.1.58)
#   SSH      ssh binary                (default /usr/local/bin/ssh)
#   APP_DIR  install dir on device     (default /opt/epaper-display)
#   SETUP=1  also run setup_target.sh  (installs deps, sets tz)
#   SERVICE=1 install+enable the systemd timer during setup
set -euo pipefail

TARGET="${TARGET:-root@10.1.1.97}"
SSH="${SSH:-/usr/local/bin/ssh}"
SCP="${SCP:-/usr/local/bin/scp}"
APP_DIR="${APP_DIR:-/opt/epaper-display}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> packaging"
TARBALL="$(mktemp /tmp/epaper.XXXXXX.tar.gz)"
tar -C "$HERE" -czf "$TARBALL" \
    --exclude='out' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    config.py main.py requirements.txt README.md \
    epaper fonts scripts systemd native

echo "==> copying to $TARGET:$APP_DIR"
$SSH "$TARGET" "mkdir -p '$APP_DIR'"
$SCP "$TARBALL" "$TARGET:/tmp/epaper_deploy.tar.gz"
$SSH "$TARGET" "tar -C '$APP_DIR' -xzf /tmp/epaper_deploy.tar.gz && rm -f /tmp/epaper_deploy.tar.gz && mkdir -p '$APP_DIR/out'"
rm -f "$TARBALL"

if [ "${SETUP:-0}" = "1" ]; then
    echo "==> running setup_target.sh on device"
    $SSH "$TARGET" "APP_DIR='$APP_DIR' INSTALL_SERVICE='${SERVICE:-0}' bash '$APP_DIR/scripts/setup_target.sh'"
fi

echo "==> deployed to $TARGET:$APP_DIR"
echo "    test data only (no deps):  $SSH $TARGET 'cd $APP_DIR && python3 -m epaper.electricity'"
echo "    full run (needs Pillow):   $SSH $TARGET 'cd $APP_DIR && TZ=Europe/Helsinki EPD_BACKEND=mock python3 main.py'"
echo "    panel wiring test:         $SSH $TARGET 'cd $APP_DIR && sudo python3 scripts/epdtest.py'"
