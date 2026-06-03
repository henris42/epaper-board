#!/usr/bin/env bash
# One e-paper refresh, with a CPU-governor bump for the short render window.
#
# The Odroid C2 idles on a low-power governor (powersave) to stay cool/quiet.
# This raises it (conservative) for the ~20 s render + panel refresh, then always
# drops it back -- even if the render fails or is interrupted.
#
# Scheduled every 15 min by systemd (systemd/epaper.timer) or cron. Must run as
# root: it needs /dev/gpiomem for the panel and write access to scaling_governor.
set -uo pipefail

APP_DIR="${APP_DIR:-/opt/epaper-display}"
GOV_ACTIVE="${GOV_ACTIVE:-conservative}"   # while rendering
GOV_IDLE="${GOV_IDLE:-powersave}"          # between refreshes

set_governor() {
    local g="$1"
    for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        [ -w "$f" ] && echo "$g" > "$f" 2>/dev/null || true
    done
}

# Always return to the idle governor on exit (success, failure, or signal).
trap 'set_governor "$GOV_IDLE"' EXIT

set_governor "$GOV_ACTIVE"

cd "$APP_DIR" || exit 1
TZ="${TZ:-Europe/Helsinki}" EPD_BACKEND="${EPD_BACKEND:-epd}" \
    EPD_GPIO="${EPD_GPIO:-native}" python3 main.py
rc=$?

exit $rc
