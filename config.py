"""Central configuration for the e-paper weather + electricity display.

All tunables live here. Edit and re-run; no code changes needed for normal use.
"""
import os

# ---------------------------------------------------------------------------
# Location (Finnish Meteorological Institute uses lat/lon or place name)
# ---------------------------------------------------------------------------
# Kauniainen, baseline Helsinki area. FMI resolves the nearest forecast point.
LOCATION_NAME = "Kauniainen"
LATITUDE = 60.2121
LONGITUDE = 24.7276

# System timezone used for all on-screen times. The host's /etc/localtime must
# match this (run: timedatectl set-timezone Europe/Helsinki). All API timestamps
# are UTC and converted to local via the system tz, so no Python tz lib is needed.
TIMEZONE = "Europe/Helsinki"

# On-screen language: "en", "fi", or "sv". (The bottom METAR/TAF strip stays as
# raw aviation text in all languages.)
LANGUAGE = "fi"

# ---------------------------------------------------------------------------
# Electricity prices (sahkotin.fi -> Nord Pool FI spot)
# ---------------------------------------------------------------------------
# sahkotin returns EUR/MWh. We display c/kWh (divide by 10).
# ?vat appends Finnish VAT (25.5% as of 2024-09). Threshold is in c/kWh incl VAT.
SAHKOTIN_URL = "https://sahkotin.fi/prices.csv"
SAHKOTIN_INCLUDE_VAT = True          # request VAT-included prices
PRICE_QUARTERS = True                # 15-minute resolution (Nord Pool MTU)
PRICE_RED_THRESHOLD_C_KWH = 10.0     # bars at/above this are drawn in red
# Past is uninteresting: show only the previous half hour, then everything ahead
# that has been published. Tomorrow's prices appear ~14:15 local; the chart's
# right edge simply ends wherever the data does (varies by time of day).
PRICE_PAST_MINUTES = 30              # how much history to show left of "now"
PRICE_FUTURE_HOURS = 48             # upper bound on the request; data may be less

# ---------------------------------------------------------------------------
# Weather (FMI open data WFS)
# ---------------------------------------------------------------------------
FMI_WFS_URL = "https://opendata.fmi.fi/wfs"
# Official human-edited Scandinavian forecast (not a raw model).
FMI_STORED_QUERY = "fmi::forecast::edited::weather::scandinavia::point::simple"
FORECAST_HOURS = 72                  # how many hours of forecast to fetch
DETAIL_HOURS = 24                    # hours shown in the detailed strip

# ---------------------------------------------------------------------------
# Aviation weather (METAR/TAF) shown as raw text at the bottom of the panel
# ---------------------------------------------------------------------------
AVIATION_ICAO = "EFHK"               # Helsinki-Vantaa
AVIATION_TAF_LINES = 4               # max TAF lines rendered

# FMI official warnings (CAP feed). Filtered to LATITUDE/LONGITUDE by polygon.
# The per-language feed file is chosen in epaper/i18n.py (ALERT_FEED).
ALERTS_FEED_BASE = "https://alerts.fmi.fi/cap/feed/"

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
HTTP_TIMEOUT = 25                    # seconds per request
HTTP_RETRIES = 3
# sahkotin.fi presents a certificate that fails default verification, so we
# fetch it with TLS verification disabled. FMI uses normal verification.
SAHKOTIN_INSECURE_TLS = True

# ---------------------------------------------------------------------------
# Display geometry / fonts
# ---------------------------------------------------------------------------
EPD_WIDTH = 800
EPD_HEIGHT = 480

_ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(_ROOT, "fonts")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_COND = os.path.join(FONT_DIR, "DejaVuSansCondensed.ttf")
FONT_COND_BOLD = os.path.join(FONT_DIR, "DejaVuSansCondensed-Bold.ttf")
FONT_MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")

# Where the mock backend and debug previews are written.
OUT_DIR = os.path.join(_ROOT, "out")

# ---------------------------------------------------------------------------
# Display backend
# ---------------------------------------------------------------------------
# "auto"  -> use the real panel if the GPIO backend imports, else mock (PNG)
# "epd"   -> force the real Waveshare 7.5" B V2 panel (bit-banged SPI)
# "mock"  -> force PNG output to OUT_DIR (development / headless)
DISPLAY_BACKEND = os.environ.get("EPD_BACKEND", "auto")

# GPIO backend for the bit-bang SPI driver on the Odroid C2:
#   "native"   -> C helper (native/libepdbb.so) runs the inner loop in C; the
#                 full refresh data clocks out in ~1-2 s (recommended)
#   "wiringpi" -> odroid wiringpi Python binding; correct but ~2 min/refresh
#   "sysfs"    -> /sys/class/gpio, no deps, slowest (set numeric pins below)
#   "auto"     -> native, else wiringpi, else sysfs
GPIO_BACKEND = os.environ.get("EPD_GPIO", "native")

# Clock half-period for the native bit-bang, as an empty-loop iteration count.
# 0 = as fast as the GPIO allows. Raise it if you see garbled output (data loss
# from clocking faster than the panel/wiring can follow). ~a few s either way.
EPD_CLK_DELAY = int(os.environ.get("EPD_CLK_DELAY", 4))

# Pin assignment. For GPIO_BACKEND="wiringpi" these are PHYSICAL header pin
# numbers (wiringPiSetupPhys). The defaults match the Waveshare RPi HAT layout,
# which the C2's 40-pin header mirrors, so the supplied ribbon cable maps 1:1:
#
#   EPD pin   ->  C2 header (physical)   role
#   VCC       ->  1  (3.3V)
#   GND       ->  6  (GND)
#   DIN/MOSI  ->  19
#   CLK/SCLK  ->  23
#   CS        ->  24
#   DC        ->  22
#   RST       ->  11
#   BUSY      ->  18
#   PWR       ->  12   (newer Driver HAT rev: gates panel power, held HIGH)
#
# This matches Waveshare's official "E-Paper Driver HAT" -> Raspberry Pi table
# exactly. The Odroid C2's 40-pin header carries power/GND/GPIO at the same
# physical positions, so the HAT seats directly on it. (On the Pi these land on
# the hardware-SPI pins; the C2 has no SPI controller, which is why we bit-bang
# them as plain GPIO -- the HAT is just passive routing + the PWR MOSFET.)
#
# For GPIO_BACKEND="sysfs" replace these with the kernel sysfs GPIO numbers
# (base + offset; this C2 has ao-bank base=122, banks base=136). Use
# scripts/gpio_probe.py to find/verify the right numbers on your board.
PIN_DIN = int(os.environ.get("EPD_PIN_DIN", 19))
PIN_CLK = int(os.environ.get("EPD_PIN_CLK", 23))
PIN_CS = int(os.environ.get("EPD_PIN_CS", 24))
PIN_DC = int(os.environ.get("EPD_PIN_DC", 22))
PIN_RST = int(os.environ.get("EPD_PIN_RST", 11))
PIN_BUSY = int(os.environ.get("EPD_PIN_BUSY", 18))
# PWR gates panel power on the newer HAT; held HIGH while running. Set to 0 to
# disable (bare 8-wire panels with no PWR line don't need it).
PIN_PWR = int(os.environ.get("EPD_PIN_PWR", 12))
