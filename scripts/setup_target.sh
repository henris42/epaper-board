#!/usr/bin/env bash
# Provision the Odroid C2 (Ubuntu 20.04) to run the e-paper display.
# Run ON THE DEVICE as root:   sudo bash scripts/setup_target.sh
#
# Installs Pillow + GPIO, sets the timezone, and (optionally) installs the
# systemd timer. Safe to re-run.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/epaper-display}"

echo "==> apt: Python imaging + tools"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
# python3-pil = Pillow without a compiler; swig/build for the wiringpi binding
apt-get install -y python3 python3-pil python3-dev python3-pip \
                   build-essential swig git

echo "==> timezone -> Europe/Helsinki"
timedatectl set-timezone Europe/Helsinki || ln -sf /usr/share/zoneinfo/Europe/Helsinki /etc/localtime

echo "==> GPIO library (odroid wiringpi, memory-mapped)"
if python3 -c "import wiringpi" 2>/dev/null || python3 -c "import odroid_wiringpi" 2>/dev/null; then
    echo "    wiringpi already present"
else
    # Try Hardkernel apt package first, then PyPI binding, then source build.
    if apt-get install -y odroid-wiringpi python3-odroid-wiringpi 2>/dev/null; then
        echo "    installed via apt"
    elif pip3 install --no-input odroid-wiringpi 2>/dev/null; then
        echo "    installed via pip (odroid-wiringpi)"
    else
        echo "    building Hardkernel wiringPi from source..."
        tmp="$(mktemp -d)"
        git clone --depth 1 https://github.com/hardkernel/wiringPi "$tmp/wiringPi"
        ( cd "$tmp/wiringPi" && ./build )
        # python binding
        git clone --depth 1 https://github.com/hardkernel/WiringPi2-Python "$tmp/py" || true
        if [ -d "$tmp/py" ]; then ( cd "$tmp/py" && python3 setup.py install ); fi
        rm -rf "$tmp"
    fi
fi

echo "==> native bit-bang helper (full refresh ~0.8 s of data vs ~2 min)"
# Compile the Hardkernel wiringPi GPIO sources (memory-mapped) straight into our
# helper .so -- no autotools/install needed. Just need the source tree + gcc.
WP_SRC="${WP_SRC:-/root/wiringPi}"
if [ ! -d "$WP_SRC/wiringPi" ]; then
    echo "    fetching wiringPi source..."
    git clone --depth 1 https://github.com/hardkernel/wiringPi "$WP_SRC" >/dev/null 2>&1
fi
if [ -d "$WP_SRC/wiringPi" ]; then
    ( cd "$WP_SRC/wiringPi"
      # all GPIO/board sources except the non-compilable template; epdbb.c
      # provides the pinToGpio/phyToGpio globals this tree leaves undefined.
      SRC=$(ls *.c | grep -v "^odroid_template.c$" | tr "\n" " ")
      gcc -O2 -fPIC -shared -I. "$APP_DIR/native/epdbb.c" $SRC \
          -o "$APP_DIR/native/libepdbb.so" -lpthread -lm -lrt -lcrypt ) \
      && echo "    built native/libepdbb.so  (EPD_GPIO=native)" \
      || echo "    WARNING: native helper compile failed; use EPD_GPIO=wiringpi"
else
    echo "    WARNING: wiringPi source unavailable; native backend off (use EPD_GPIO=wiringpi)"
fi

echo "==> verify python deps"
python3 - <<'PY'
import sys
import PIL
print("  Pillow", PIL.__version__)
ok = False
for m in ("wiringpi", "odroid_wiringpi"):
    try:
        __import__(m); print("  GPIO module:", m); ok = True; break
    except ImportError:
        pass
if not ok:
    print("  WARNING: no wiringpi binding; use EPD_GPIO=sysfs as fallback")
PY

if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
    echo "==> installing systemd timer"
    cp "$APP_DIR/systemd/epaper.service" /etc/systemd/system/
    cp "$APP_DIR/systemd/epaper.timer"   /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now epaper.timer
    echo "    timer enabled; first refresh shortly"
else
    echo "==> systemd timer NOT installed (set INSTALL_SERVICE=1 to enable)"
fi

echo "==> done. Next: verify wiring with"
echo "    sudo python3 $APP_DIR/scripts/epdtest.py"
