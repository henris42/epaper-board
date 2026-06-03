"""Vector weather icons drawn with PIL so they stay crisp on the 1-bit panel and
need no assets. Each icon fits a size x size box at top-left (x, y).

draw_icon(d, category, x, y, size, color, accent, night, moon, intensity)
  category  one of: clear pcloudy cloudy fog rain showers drizzle snow sleet
                    thunder wind
  color     ink colour for the icon body (renderer passes RED for bad weather)
  accent    always-red detail (lightning bolt, warning)
  night     if True, clear/pcloudy/showers use a moon instead of the sun
  moon      (illum, waxing) when night; controls the moon glyph's phase
  intensity 1 light, 2 moderate, 3 heavy -> number of drops/flakes
"""
import math

BLACK = (0, 0, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)


# --- primitives ------------------------------------------------------------
def _sun(d, cx, cy, r, color):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=3)
    for k in range(8):
        a = k * math.pi / 4
        x1, y1 = cx + math.cos(a) * (r + 4), cy + math.sin(a) * (r + 4)
        x2 = cx + math.cos(a) * (r + 4 + r * 0.6)
        y2 = cy + math.sin(a) * (r + 4 + r * 0.6)
        d.line([x1, y1, x2, y2], fill=color, width=3)


def _moon(d, cx, cy, r, illum=0.5, waxing=True, color=BLACK):
    """A phased moon glyph drawn the natural way: the lit part is left white
    (paper) and the shadow is filled with ink. So a full moon is an open white
    circle, a new moon a solid ink disc, and a crescent a white sliver."""
    illum = max(0.0, min(1.0, illum))
    c = 2 * illum - 1                       # -1 new ... +1 full
    # outline so a white full moon still reads as a disc
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
    r2 = r * r
    for dy in range(-int(r), int(r) + 1):
        hw = math.sqrt(max(0.0, r2 - dy * dy))
        if hw < 0.5:
            continue
        if waxing:                          # lit on the right -> shadow on left
            x_lo, x_hi = cx - hw, cx - c * hw
        else:                               # lit on the left -> shadow on right
            x_lo, x_hi = cx + c * hw, cx + hw
        if x_hi - x_lo > 0.5:
            d.line([x_lo, cy + dy, x_hi, cy + dy], fill=color, width=1)


def _cloud(d, x, y, w, h, color, fill=WHITE, t=3):
    """A smooth cumulus silhouette: draw the union of lobes + base in the outline
    colour, then the same union inset by t in the fill colour. This leaves a
    clean, uniform outline with no internal seams."""
    by = y + h                              # flat base line
    # (cx, cy, r) lobes overlapping enough to merge into one silhouette
    lobes = [
        (x + 0.30 * w, by - 0.30 * h, 0.30 * h),
        (x + 0.50 * w, by - 0.52 * h, 0.40 * h),
        (x + 0.72 * w, by - 0.34 * h, 0.32 * h),
    ]
    rect = (x + 0.14 * w, by - 0.34 * h, x + 0.88 * w, by)

    def blob(col, inset):
        for cx, cy, r in lobes:
            d.ellipse([cx - r + inset, cy - r + inset,
                       cx + r - inset, cy + r - inset], fill=col)
        d.rectangle([rect[0] + inset, rect[1], rect[2] - inset, rect[3] - inset],
                    fill=col)

    blob(color, 0)                          # outline silhouette
    blob(fill, t)                           # inset interior -> uniform ring


def _drops(d, x, y, w, color, n, length=13):
    """Rain: long slanted streaks."""
    step = w / (n + 1)
    for i in range(1, n + 1):
        rx = x + step * i
        d.line([rx + 3, y, rx - 4, y + length], fill=color, width=3)


def _dots(d, x, y, w, color, n=5):
    """Drizzle: fine short dots in two staggered rows."""
    step = w / (n + 1)
    for i in range(1, n + 1):
        rx = x + step * i
        d.ellipse([rx - 1.5, y - 1.5, rx + 1.5, y + 1.5], fill=color)
        d.ellipse([rx - 1.5 + step / 2, y + 6 - 1.5,
                   rx + 1.5 + step / 2, y + 6 + 1.5], fill=color)


def _flakes(d, x, y, w, color, n):
    step = w / (n + 1)
    for i in range(1, n + 1):
        cx, cy = x + step * i, y + 7
        for a in (0, 60, 120):
            rad = math.radians(a)
            dx, dy = math.cos(rad) * 5, math.sin(rad) * 5
            d.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=color, width=2)


def _bolt(d, cx, y, color):
    pts = [(cx, y), (cx - 9, y + 15), (cx - 1, y + 15),
           (cx - 7, y + 28), (cx + 10, y + 11), (cx + 1, y + 11)]
    d.polygon(pts, fill=color)


def _wind(d, x, y, w, h, color):
    cy = y + h / 2
    for i, (ly, ln) in enumerate(((cy - h * 0.18, 0.8), (cy, 1.0),
                                  (cy + h * 0.18, 0.7))):
        x2 = x + w * ln
        d.line([x, ly, x2 - 8, ly], fill=color, width=3)
        d.arc([x2 - 16, ly - 10, x2, ly + 4], -90, 120, fill=color, width=3)


def _luminary(d, x, y, size, color, night, moon, r_scale=0.28, off=0.5):
    """Draw the sun, or a phased moon at night, centred in the box."""
    cx, cy = x + size * off, y + size * off
    if night:
        illum, waxing = (moon or (0.5, True))
        _moon(d, cx, cy, size * r_scale, illum, waxing, color)
    else:
        _sun(d, cx, cy, size * r_scale, color)


# --- public ----------------------------------------------------------------
def draw_icon(d, category, x, y, size, color=BLACK, accent=RED,
              night=False, moon=None, intensity=2):
    if category == "clear":
        _luminary(d, x, y, size, color, night, moon)
        return
    if category == "pcloudy":
        _luminary(d, x, y, size, color, night, moon, r_scale=0.18, off=0.34)
        _cloud(d, x + size * 0.18, y + size * 0.34, size * 0.72, size * 0.42, color)
        return
    if category == "cloudy":
        _cloud(d, x + size * 0.08, y + size * 0.2, size * 0.84, size * 0.5, color)
        return
    if category == "fog":
        _cloud(d, x + size * 0.08, y + size * 0.1, size * 0.84, size * 0.42, color)
        for i in range(3):
            yy = y + size * 0.64 + i * (size * 0.12)
            d.line([x + size * 0.16, yy, x + size * 0.84, yy], fill=color, width=3)
        return
    if category in ("rain", "drizzle", "showers"):
        if category == "showers":
            _luminary(d, x, y, size, color, night, moon, r_scale=0.15, off=0.3)
        _cloud(d, x + size * 0.08, y + size * 0.18, size * 0.84, size * 0.4, color)
        if category == "drizzle":
            _dots(d, x + size * 0.12, y + size * 0.66, size * 0.76, color, n=5)
        else:
            n = max(2, intensity + 1)
            _drops(d, x + size * 0.12, y + size * 0.62, size * 0.76, color, n,
                   length=size * 0.18)
        return
    if category == "snow":
        _cloud(d, x + size * 0.08, y + size * 0.18, size * 0.84, size * 0.4, color)
        _flakes(d, x + size * 0.12, y + size * 0.6, size * 0.76, color, max(2, intensity) + 1)
        return
    if category == "sleet":
        _cloud(d, x + size * 0.08, y + size * 0.18, size * 0.84, size * 0.4, color)
        _drops(d, x + size * 0.1, y + size * 0.62, size * 0.38, color, 1)
        _flakes(d, x + size * 0.48, y + size * 0.58, size * 0.42, color, 1)
        return
    if category == "thunder":
        _cloud(d, x + size * 0.08, y + size * 0.12, size * 0.84, size * 0.42, color)
        _bolt(d, x + size * 0.5, y + size * 0.56, accent)
        return
    if category == "wind":
        _wind(d, x + size * 0.12, y + size * 0.22, size * 0.76, size * 0.56, color)
        return
    _cloud(d, x + size * 0.08, y + size * 0.2, size * 0.84, size * 0.5, color)


# --- warning icons (for the alert banner) ----------------------------------
def draw_warning_icon(d, category, x, y, s, color=RED):
    """Compact alert glyph in an s x s box. Categories map from FMI CAP events:
    fire flood traffic wind thunder rain snow heat cold (+ generic triangle)."""
    cx, cy = x + s / 2, y + s / 2
    if category == "fire":
        d.polygon([(cx, y + 0.03 * s), (x + 0.80 * s, y + 0.45 * s),
                   (x + 0.70 * s, y + 0.82 * s), (cx, y + 0.97 * s),
                   (x + 0.30 * s, y + 0.82 * s), (x + 0.20 * s, y + 0.45 * s)],
                  fill=color)
        d.polygon([(cx, y + 0.46 * s), (x + 0.62 * s, y + 0.70 * s),
                   (cx, y + 0.88 * s), (x + 0.38 * s, y + 0.70 * s)], fill=WHITE)
    elif category == "flood":
        for yy in (y + 0.5 * s, y + 0.72 * s, y + 0.94 * s):
            pts = [(x + 0.05 * s + i, yy + math.sin(i / s * 4 * math.pi) * 0.05 * s)
                   for i in range(0, int(0.9 * s) + 1, 2)]
            d.line(pts, fill=color, width=2)
    elif category == "traffic":
        d.rectangle([x + 0.08 * s, y + 0.46 * s, x + 0.92 * s, y + 0.72 * s],
                    outline=color, width=2)
        d.rectangle([x + 0.30 * s, y + 0.30 * s, x + 0.70 * s, y + 0.48 * s],
                    outline=color, width=2)
        r = 0.1 * s
        for wx in (x + 0.30 * s, x + 0.70 * s):
            d.ellipse([wx - r, y + 0.66 * s, wx + r, y + 0.66 * s + 2 * r], fill=color)
    elif category == "wind":
        _wind(d, x + 0.08 * s, y + 0.25 * s, 0.84 * s, 0.5 * s, color)
    elif category == "thunder":
        d.polygon([(cx + 0.08 * s, y + 0.04 * s), (x + 0.25 * s, y + 0.56 * s),
                   (cx, y + 0.56 * s), (x + 0.40 * s, y + 0.96 * s),
                   (x + 0.78 * s, y + 0.42 * s), (cx + 0.04 * s, y + 0.42 * s)],
                  fill=color)
    elif category == "rain":
        for i in range(3):
            dx = x + (0.28 + 0.22 * i) * s
            d.line([dx + 0.06 * s, y + 0.2 * s, dx - 0.06 * s, y + 0.72 * s],
                   fill=color, width=2)
    elif category == "snow":
        _flakes(d, x + 0.1 * s, y + 0.25 * s, 0.8 * s, color, 3)
    elif category in ("heat", "cold"):
        sx, r = x + 0.5 * s, 0.14 * s
        d.rectangle([sx - 0.06 * s, y + 0.1 * s, sx + 0.06 * s, y + 0.64 * s],
                    outline=color, width=2)
        d.ellipse([sx - r, y + 0.6 * s, sx + r, y + 0.6 * s + 2 * r],
                  outline=color, width=2)
        if category == "heat":
            d.rectangle([sx - 0.03 * s, y + 0.24 * s, sx + 0.03 * s, y + 0.64 * s],
                        fill=color)
        d.ellipse([sx - r * 0.55, y + 0.64 * s, sx + r * 0.55, y + 0.64 * s + 1.4 * r],
                  fill=color)
    else:                                   # generic warning triangle with "!"
        d.line([(cx, y + 0.08 * s), (x + 0.95 * s, y + 0.9 * s),
                (x + 0.05 * s, y + 0.9 * s), (cx, y + 0.08 * s)],
               fill=color, width=2, joint="curve")
        d.line([cx, y + 0.4 * s, cx, y + 0.66 * s], fill=color, width=2)
        d.line([cx, y + 0.74 * s, cx, y + 0.80 * s], fill=color, width=2)
