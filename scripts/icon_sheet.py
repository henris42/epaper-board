#!/usr/bin/env python3
"""Render every weather icon (day + night, intensities, moon phases) to a sheet
for visual review. Output: out/icon_sheet.png"""
import os
import sys

sys.path.insert(0, ".")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import config  # noqa: E402
from epaper import icons  # noqa: E402

CELL = 110
PAD = 26
COLS = 6


def main():
    cats_day = ["clear", "pcloudy", "cloudy", "fog", "drizzle", "rain",
                "showers", "snow", "sleet", "thunder", "wind"]
    # build a flat list of (label, kwargs)
    items = []
    for c in cats_day:
        bad = c in ("rain", "drizzle", "showers", "snow", "sleet", "thunder")
        col = icons.RED if bad else icons.BLACK
        items.append((c, dict(category=c, color=col, intensity=2)))
    # night variants
    for c in ["clear", "pcloudy", "showers"]:
        items.append(("%s night" % c,
                      dict(category=c, color=icons.BLACK, night=True,
                           moon=(0.5, True))))
    # intensities
    for inten in (1, 3):
        items.append(("rain i%d" % inten,
                      dict(category="rain", color=icons.RED, intensity=inten)))
        items.append(("snow i%d" % inten,
                      dict(category="snow", color=icons.RED, intensity=inten)))
    # moon phases
    for frac, wax, name in [(0.02, True, "new"), (0.25, True, "wax-cres"),
                            (0.5, True, "1st-qtr"), (0.75, True, "wax-gib"),
                            (1.0, True, "full"), (0.75, False, "wan-gib"),
                            (0.5, False, "last-qtr"), (0.25, False, "wan-cres")]:
        items.append(("moon %s" % name,
                      dict(category="clear", color=icons.BLACK, night=True,
                           moon=(frac, wax))))

    # warning icons (drawn red, via draw_warning_icon)
    warn_cats = ["fire", "flood", "traffic", "wind", "thunder", "rain",
                 "snow", "heat", "cold", "generic"]
    for c in warn_cats:
        items.append(("warn:%s" % c, dict(_warn=c)))

    rows = (len(items) + COLS - 1) // COLS
    W = COLS * (CELL + PAD) + PAD
    H = rows * (CELL + PAD + 16) + PAD
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(config.FONT_REGULAR, 14)

    for i, (label, kw) in enumerate(items):
        r, c = divmod(i, COLS)
        x = PAD + c * (CELL + PAD)
        y = PAD + r * (CELL + PAD + 16)
        d.rectangle([x - 2, y - 2, x + CELL + 2, y + CELL + 2],
                    outline=(200, 200, 200))
        if "_warn" in kw:
            icons.draw_warning_icon(d, kw["_warn"], x, y, CELL, color=icons.RED)
        else:
            icons.draw_icon(d, x=x, y=y, size=CELL, **kw)
        d.text((x, y + CELL + 2), label, font=f, fill=(0, 0, 0))

    os.makedirs(config.OUT_DIR, exist_ok=True)
    out = os.path.join(config.OUT_DIR, "icon_sheet.png")
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
