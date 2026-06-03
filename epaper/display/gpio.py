"""GPIO abstraction for the bit-banged SPI e-paper driver on the Odroid C2.

Two backends, selected by config.GPIO_BACKEND:

  "wiringpi" - odroid-wiringpi, memory-mapped via /dev/gpiomem. Fast (a full
               panel refresh's data clocks out in a handful of seconds). Pins are
               PHYSICAL header numbers (wiringPiSetupPhys). Recommended.

  "sysfs"    - /sys/class/gpio. No dependencies, works on any kernel, but slow
               (each toggle is a syscall). Pins are kernel GPIO numbers. Use
               scripts/gpio_probe.py to discover them on this board.

Both expose the same tiny interface:
    g = make_gpio()
    g.setup_output(pin); g.setup_input(pin)
    g.write(pin, 0/1); g.read(pin)
    g.cleanup()
"""
import os
import time

import config

IN, OUT = "in", "out"


class WiringPiGPIO:
    """odroid-wiringpi backend using physical pin numbering."""

    def __init__(self):
        wiringpi = None
        for modname in ("wiringpi", "odroid_wiringpi"):
            try:
                wiringpi = __import__(modname)
                break
            except ImportError:
                continue
        if wiringpi is None:  # pragma: no cover - device only
            raise ImportError(
                "wiringpi not installed. Run scripts/setup_target.sh on the "
                "Odroid, or set EPD_GPIO=sysfs.")
        self.wp = wiringpi
        # physical (board) pin numbering matches the header pin numbers used in
        # config.py and README wiring table.
        self.wp.wiringPiSetupPhys()

    def setup_output(self, pin):
        self.wp.pinMode(pin, self.wp.OUTPUT)

    def setup_input(self, pin):
        self.wp.pinMode(pin, self.wp.INPUT)

    def write(self, pin, value):
        self.wp.digitalWrite(pin, 1 if value else 0)

    def read(self, pin):
        return self.wp.digitalRead(pin)

    def cleanup(self):
        pass


class SysfsGPIO:
    """Pure-stdlib /sys/class/gpio backend. Slow but dependency-free.

    Pins are kernel GPIO numbers. File descriptors are kept open for speed.
    """

    BASE = "/sys/class/gpio"

    def __init__(self):
        self._value_fds = {}
        self._exported = []

    def _export(self, pin):
        path = "%s/gpio%d" % (self.BASE, pin)
        if not os.path.exists(path):
            with open("%s/export" % self.BASE, "w") as f:
                f.write(str(pin))
            # give udev a moment to create the node + fix permissions
            for _ in range(50):
                if os.path.exists("%s/direction" % path):
                    break
                time.sleep(0.02)
            self._exported.append(pin)
        return path

    def setup_output(self, pin):
        path = self._export(pin)
        with open("%s/direction" % path, "w") as f:
            f.write("out")
        self._value_fds[pin] = os.open("%s/value" % path, os.O_WRONLY)

    def setup_input(self, pin):
        path = self._export(pin)
        with open("%s/direction" % path, "w") as f:
            f.write("in")
        self._value_fds[pin] = os.open("%s/value" % path, os.O_RDONLY)

    def write(self, pin, value):
        fd = self._value_fds[pin]
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, b"1" if value else b"0")

    def read(self, pin):
        fd = self._value_fds[pin]
        os.lseek(fd, 0, os.SEEK_SET)
        return 1 if os.read(fd, 1) == b"1" else 0

    def cleanup(self):
        for fd in self._value_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        for pin in self._exported:
            try:
                with open("%s/unexport" % self.BASE, "w") as f:
                    f.write(str(pin))
            except OSError:
                pass


class NativeGPIO:
    """Fast backend: a small C library (native/libepdbb.so, built on wiringPi)
    runs the bit-bang inner loop in C. Pins are PHYSICAL header numbers.

    Exposes the same setup/write/read interface as the other backends, plus a
    `block(data, invert)` fast path the driver uses for the two big planes.
    """

    def __init__(self):
        import ctypes
        so = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), "native", "libepdbb.so")
        if not os.path.exists(so):
            raise ImportError(
                "native/libepdbb.so not built. Run scripts/setup_target.sh "
                "(or compile native/epdbb.c), or set EPD_GPIO=wiringpi.")
        lib = ctypes.CDLL(so)
        lib.epd_read.restype = ctypes.c_int
        lib.epd_block.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        self.lib = lib
        if lib.epd_setup() < 0:
            raise RuntimeError("wiringPiSetupPhys failed (need root / gpiomem)")
        lib.epd_set_delay(int(config.EPD_CLK_DELAY))

    def setup_output(self, pin):
        self.lib.epd_mode_out(pin)

    def setup_input(self, pin):
        self.lib.epd_mode_in(pin)

    def write(self, pin, value):
        self.lib.epd_write(pin, 1 if value else 0)

    def read(self, pin):
        return self.lib.epd_read(pin)

    def set_spi_pins(self, din, clk, cs, dc):
        self.lib.epd_set_spi_pins(din, clk, cs, dc)

    def block(self, data, invert=0):
        self.lib.epd_block(bytes(data), len(data), 1 if invert else 0)

    def cleanup(self):
        pass


def make_gpio(backend=None):
    backend = backend or config.GPIO_BACKEND
    if backend == "native":
        return NativeGPIO()
    if backend == "wiringpi":
        return WiringPiGPIO()
    if backend == "sysfs":
        return SysfsGPIO()
    if backend == "auto":
        for cls in (NativeGPIO, WiringPiGPIO, SysfsGPIO):
            try:
                return cls()
            except Exception:  # noqa: BLE001
                continue
        raise RuntimeError("no usable GPIO backend")
    raise ValueError("unknown GPIO_BACKEND: %r" % backend)
