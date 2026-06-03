#!/usr/bin/env python3
"""Standalone panel test: clear the screen, then draw a black/red test pattern.

Run this once after wiring up the panel to confirm the driver, pins and SPI
bit-banging all work before relying on the full app.

    sudo EPD_GPIO=wiringpi python3 scripts/epdtest.py
    sudo EPD_GPIO=wiringpi python3 scripts/epdtest.py --clear-only
"""
import argparse
import sys
import time

sys.path.insert(0, ".")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import config  # noqa: E402
from epaper import render  # noqa: E402
from epaper.display.epd7in5b import EPD  # noqa: E402


def pattern():
    img = Image.new("RGB", (config.EPD_WIDTH, config.EPD_HEIGHT), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(config.FONT_BOLD, 40)
    d.rectangle([2, 2, config.EPD_WIDTH - 3, config.EPD_HEIGHT - 3],
                outline=(0, 0, 0), width=3)
    d.text((20, 20), "EPD 7.5\" B/W/R test", font=f, fill=(0, 0, 0))
    d.text((20, 80), "black text", font=f, fill=(0, 0, 0))
    d.text((20, 140), "red text", font=f, fill=(255, 0, 0))
    # color swatches
    d.rectangle([20, 220, 260, 340], fill=(0, 0, 0))
    d.rectangle([280, 220, 520, 340], fill=(255, 0, 0))
    # gradient of lines
    for i in range(0, config.EPD_WIDTH, 20):
        d.line([i, 360, i, 460], fill=(0, 0, 0) if (i // 20) % 2 else (255, 0, 0))
    return img


def solid(color):
    return Image.new("RGB", (config.EPD_WIDTH, config.EPD_HEIGHT), color)


def thirds():
    """Top third black, middle red, bottom white -- to judge red saturation
    against true black on the same screen."""
    img = solid((255, 255, 255))
    d = ImageDraw.Draw(img)
    h = config.EPD_HEIGHT
    d.rectangle([0, 0, config.EPD_WIDTH, h // 3], fill=(0, 0, 0))
    d.rectangle([0, h // 3, config.EPD_WIDTH, 2 * h // 3], fill=(255, 0, 0))
    f = ImageFont.truetype(config.FONT_BOLD, 36)
    d.text((20, 20), "BLACK", font=f, fill=(255, 255, 255))
    d.text((20, h // 3 + 20), "RED", font=f, fill=(255, 255, 255))
    d.text((20, 2 * h // 3 + 20), "WHITE", font=f, fill=(0, 0, 0))
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clear-only", action="store_true")
    ap.add_argument("--image", choices=["pattern", "thirds", "red", "black",
                    "white"], default="pattern",
                    help="what to draw after clearing")
    ap.add_argument("--clear-cycles", type=int, default=2)
    ap.add_argument("--condition", type=int, metavar="ROUNDS", default=0,
                    help="scrub deep burn-in (factory image): N rounds of "
                         "black/red/white before clearing. Try 3.")
    args = ap.parse_args()

    images = {"pattern": pattern, "thirds": thirds,
              "red": lambda: solid((255, 0, 0)),
              "black": lambda: solid((0, 0, 0)),
              "white": lambda: solid((255, 255, 255))}

    epd = EPD()
    print("init...")
    epd.init()
    if args.condition > 0:
        print("conditioning (%d rounds of black/red/white)..." % args.condition)
        t0 = time.time()
        epd.condition(rounds=args.condition)
        print("  conditioned in %.1fs" % (time.time() - t0))
    print("clear (%d cycles)..." % args.clear_cycles)
    t0 = time.time()
    refresh = epd.clear(cycles=args.clear_cycles)
    print("  cleared in %.1fs  (refresh %.1fs)" % (time.time() - t0, refresh))
    if not args.clear_only:
        print("drawing '%s'..." % args.image)
        black, red = render.split_planes(images[args.image]())
        t0 = time.time()
        refresh = epd.display(black, red)
        total = time.time() - t0
        print("  drawn in %.1fs  (data clock-out %.1fs, refresh %.1fs)"
              % (total, total - refresh, refresh))
        print("  NOTE: a full B/W/R refresh should be ~25-35s; much less means")
        print("        it ended early and red will look weak.")
    print("sleep...")
    epd.sleep()
    epd.close()
    print("done")


if __name__ == "__main__":
    main()
