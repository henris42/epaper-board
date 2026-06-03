"""Waveshare 7.5" black/white/red (V2 "B") panel driver, 800x480, driven by
bit-banged SPI over the Odroid C2's GPIO (no hardware SPI controller exists on
this kernel). Command sequence follows Waveshare's epd7in5b_V2 reference.

The panel is write-only over SPI; only BUSY is read back as a plain GPIO. SPI is
mode 0: data is set while CLK is low and latched on the rising edge.
"""
import time

import config
from epaper.display.gpio import make_gpio

# command set
PANEL_W, PANEL_H = 800, 480
_BITS = (7, 6, 5, 4, 3, 2, 1, 0)


class EPD:
    def __init__(self, gpio=None):
        self.g = gpio or make_gpio()
        self.DIN = config.PIN_DIN
        self.CLK = config.PIN_CLK
        self.CS = config.PIN_CS
        self.DC = config.PIN_DC
        self.RST = config.PIN_RST
        self.BUSY = config.PIN_BUSY
        self.PWR = config.PIN_PWR        # 0 = no PWR line (bare panel)
        self.width = PANEL_W
        self.height = PANEL_H

    # -- low level -------------------------------------------------------
    def _spi_byte(self, b):
        w = self.g.write
        din, clk = self.DIN, self.CLK
        for i in _BITS:
            w(din, (b >> i) & 1)
            w(clk, 1)
            w(clk, 0)

    def _spi_block(self, data):
        w = self.g.write
        din, clk = self.DIN, self.CLK
        for b in data:
            for i in _BITS:
                w(din, (b >> i) & 1)
                w(clk, 1)
                w(clk, 0)

    def _command(self, c):
        self.g.write(self.DC, 0)
        self.g.write(self.CS, 0)
        self._spi_byte(c)
        self.g.write(self.CS, 1)

    def _data(self, d):
        self.g.write(self.DC, 1)
        self.g.write(self.CS, 0)
        self._spi_byte(d)
        self.g.write(self.CS, 1)

    def _data_block(self, data, invert=0):
        # fast path: C helper clocks the whole block out (native backend)
        if hasattr(self.g, "block"):
            self.g.block(data, invert)
            return
        # portable path: pure-Python bit-bang
        if invert:
            data = bytes((~b) & 0xFF for b in data)
        self.g.write(self.DC, 1)
        self.g.write(self.CS, 0)
        self._spi_block(data)
        self.g.write(self.CS, 1)

    def _reset(self):
        self.g.write(self.RST, 1)
        time.sleep(0.2)
        self.g.write(self.RST, 0)
        time.sleep(0.004)
        self.g.write(self.RST, 1)
        time.sleep(0.2)

    def _busy_wait(self, timeout=60.0):
        """BUSY is active-low (0 = busy). Poll until idle, then return elapsed
        seconds. Idle is debounced (two reads ~50 ms apart) so a glitch on the
        bit-banged BUSY line can't end a refresh early -- which on these 3-colour
        panels would leave the red (developed last) weak and muddy."""
        start = time.time()
        while True:
            self._command(0x71)
            if self.g.read(self.BUSY) != 0:        # looks idle
                time.sleep(0.05)
                self._command(0x71)
                if self.g.read(self.BUSY) != 0:    # still idle -> confirmed
                    break
            time.sleep(0.05)
            if time.time() - start > timeout:
                raise RuntimeError("e-paper BUSY timeout (check wiring/power)")
        time.sleep(0.05)
        return time.time() - start

    # -- lifecycle -------------------------------------------------------
    def init(self):
        outputs = [self.DIN, self.CLK, self.CS, self.DC, self.RST]
        if self.PWR:
            outputs.append(self.PWR)
        for p in outputs:
            self.g.setup_output(p)
        self.g.setup_input(self.BUSY)
        if hasattr(self.g, "set_spi_pins"):
            self.g.set_spi_pins(self.DIN, self.CLK, self.CS, self.DC)
        if self.PWR:
            self.g.write(self.PWR, 1)     # power the panel on
            time.sleep(0.01)
        self.g.write(self.CS, 1)
        self.g.write(self.CLK, 0)

        self._reset()
        self._command(0x01)                    # power setting
        self._data(0x07); self._data(0x07); self._data(0x3F); self._data(0x3F)
        self._command(0x06)                    # booster soft start (charge pump)
        self._data(0x17); self._data(0x17); self._data(0x28); self._data(0x17)
        self._command(0x04)                    # power on
        time.sleep(0.1)
        self._busy_wait()
        self._command(0x00)                    # panel setting
        self._data(0x0F)
        self._command(0x61)                    # resolution: 800 x 480
        self._data(0x03); self._data(0x20)
        self._data(0x01); self._data(0xE0)
        self._command(0x15)
        self._data(0x00)
        self._command(0x50)                    # VCOM / data interval
        self._data(0x11); self._data(0x07)
        self._command(0x60)                    # TCON
        self._data(0x22)

    def display(self, black_img, red_img):
        """black_img / red_img are PIL mode-'1' images (0 = ink, 255 = blank)
        as produced by render.split_planes(). 800x480."""
        self._command(0x10)
        self._data_block(black_img.tobytes(), invert=0)   # 0-bit = black
        self._command(0x13)
        self._data_block(red_img.tobytes(), invert=1)     # inverted: 1-bit = red
        self._command(0x12)                    # refresh
        time.sleep(0.1)
        return self._busy_wait()               # seconds the refresh took

    def _fill(self, kw_byte, red_byte):
        """Flood the whole panel: kw_byte -> 0x10 (0x00 black, 0xFF white),
        red_byte -> 0x13 (0xFF red, 0x00 none). Returns the refresh seconds."""
        size = self.width * self.height // 8
        self._command(0x10)
        self._data_block(bytes([kw_byte]) * size, invert=0)
        self._command(0x13)
        self._data_block(bytes([red_byte]) * size, invert=0)
        self._command(0x12)
        time.sleep(0.1)
        return self._busy_wait()

    def clear(self, cycles=1):
        """Flush the panel to white. Two cycles scrubs light residual ghosting."""
        total = 0.0
        for _ in range(max(1, cycles)):
            total += self._fill(0xFF, 0x00)    # white, no red
        return total

    def condition(self, rounds=2):
        """Scrub deep burn-in (e.g. the factory shipping image) by exercising
        every pigment: full black, full red, full white, repeated. Run once."""
        total = 0.0
        for _ in range(max(1, rounds)):
            total += self._fill(0x00, 0x00)    # all black
            total += self._fill(0xFF, 0xFF)    # all red
            total += self._fill(0xFF, 0x00)    # all white
        return total

    def sleep(self):
        self._command(0x02)                    # power off
        self._busy_wait()
        self._command(0x07)                    # deep sleep
        self._data(0xA5)

    def close(self):
        # drop control lines, then cut panel power (matches Waveshare exit)
        try:
            self.g.write(self.RST, 0)
            self.g.write(self.DC, 0)
            if self.PWR:
                self.g.write(self.PWR, 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.g.cleanup()
        except Exception:  # noqa: BLE001
            pass
