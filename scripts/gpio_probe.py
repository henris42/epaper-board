#!/usr/bin/env python3
"""Verify GPIO wiring before trusting the panel driver.

Toggles a single pin on and off so you can confirm it with an LED + resistor or a
multimeter, independent of the e-paper. Works with either GPIO backend.

Examples:
    # wiringpi physical pin 11 (default backend), blink 10x
    sudo python3 scripts/gpio_probe.py 11

    # sysfs kernel GPIO number 136, blink 5x
    EPD_GPIO=sysfs sudo python3 scripts/gpio_probe.py 136 --count 5
"""
import argparse
import sys
import time

sys.path.insert(0, ".")
from epaper.display.gpio import make_gpio  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pin", type=int, help="pin number (physical for wiringpi, "
                                          "kernel GPIO for sysfs)")
    ap.add_argument("--count", type=int, default=10, help="number of blinks")
    ap.add_argument("--period", type=float, default=0.5, help="seconds per state")
    args = ap.parse_args()

    g = make_gpio()
    g.setup_output(args.pin)
    print("toggling pin %d, %d times (Ctrl-C to stop)" % (args.pin, args.count))
    try:
        for i in range(args.count):
            g.write(args.pin, 1)
            print("  HIGH")
            time.sleep(args.period)
            g.write(args.pin, 0)
            print("  LOW")
            time.sleep(args.period)
    finally:
        g.cleanup()


if __name__ == "__main__":
    main()
