"""Display backend factory and a common show() entry point.

A backend exposes a single function: show(rgb_image) -> None, which takes the
full-screen RGB image from render.render() and gets it onto the medium.
"""
import os

import config
from epaper import render


class MockBackend:
    """Writes the composed image (and the two 1-bit planes) to OUT_DIR as PNGs.
    Used for development and on any host without the panel."""

    def __init__(self):
        os.makedirs(config.OUT_DIR, exist_ok=True)

    def show(self, img):
        path = os.path.join(config.OUT_DIR, "display.png")
        img.save(path)
        black, red = render.split_planes(img)
        # Save a panel-accurate preview: white bg, black ink, red ink.
        preview = img.copy()
        preview.save(os.path.join(config.OUT_DIR, "preview.png"))
        black.save(os.path.join(config.OUT_DIR, "plane_black.png"))
        red.save(os.path.join(config.OUT_DIR, "plane_red.png"))
        print("mock display -> %s" % path)


class EpdBackend:
    """Drives the real Waveshare 7.5" B V2 panel via the bit-bang driver."""

    def __init__(self):
        from epaper.display.epd7in5b import EPD
        self.epd = EPD()

    def show(self, img):
        black, red = render.split_planes(img)
        self.epd.init()
        try:
            self.epd.display(black, red)
        finally:
            self.epd.sleep()
            self.epd.close()


def get_backend(name=None):
    name = name or config.DISPLAY_BACKEND
    if name == "mock":
        return MockBackend()
    if name == "epd":
        return EpdBackend()
    if name == "auto":
        # try the panel; fall back to mock if GPIO/driver isn't available
        try:
            return EpdBackend()
        except Exception as exc:  # noqa: BLE001
            print("EPD backend unavailable (%s); using mock." % exc)
            return MockBackend()
    raise ValueError("unknown DISPLAY_BACKEND: %r" % name)
