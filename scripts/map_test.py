#!/usr/bin/env python3
"""Standalone prototype: render a southern-Finland warnings map from live FMI CAP
data. Output: out/map_test.png  (run with EPD_HTTP_INSECURE=1 on dev hosts)."""
import os
import sys

sys.path.insert(0, ".")
from PIL import Image, ImageDraw  # noqa: E402

import config  # noqa: E402
from epaper import alerts, finmap  # noqa: E402

H = 230
W = int(H * finmap.aspect()) + 1


def main():
    try:
        polys = alerts.get_all()["polygons"]
        print("active warning polygons:", len(polys))
    except Exception as exc:  # noqa: BLE001
        print("alert fetch failed:", exc)
        polys = []

    img = Image.new("RGB", (W + 2, H + 2), (255, 255, 255))
    finmap.draw_map(img, 1, 1, W, H, polys,
                    mark=(config.LATITUDE, config.LONGITUDE),
                    title="S. Finland warnings")
    os.makedirs(config.OUT_DIR, exist_ok=True)
    out = os.path.join(config.OUT_DIR, "map_test.png")
    img.save(out)
    print("wrote", out, "(%dx%d)" % (W, H))


if __name__ == "__main__":
    main()
