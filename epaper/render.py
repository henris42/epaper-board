"""Render weather + electricity onto an 800x480 RGB image using only black, red
and white, then split it into the two 1-bit planes the panel needs.

Red is reserved for meaning: electricity hours at/above the threshold, the
threshold line, and freezing temperatures / thunder warnings.
"""
import math
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageChops

import config
from epaper import icons
from epaper import finmap
from epaper.icons import BLACK, RED, WHITE

W, H = config.EPD_WIDTH, config.EPD_HEIGHT

# vertical layout anchors for the lower half
MID_Y = 252                  # horizontal split: weather zone / bottom zone
AVIATION_TOP = 404           # divider above the METAR/TAF text strip
COL_X = 254                  # vertical split: left column / right column

# Layout: left column = current weather (top) + warnings map (bottom);
#         right column = 24h forecast (top) + electricity (bottom).
# warnings map (left column, below today's weather)
MAP_X, MAP_Y, MAP_W, MAP_H = 8, 262, 240, 132
# electricity (right column, beside the map)
ELEC_TOP = MID_Y
ELEC_X0, ELEC_X1 = 260, 792
ELEC_BOTTOM = 388            # price-chart baseline (room for hour labels)

_FONT_CACHE = {}


def font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _f(size, bold=False, cond=False):
    if cond:
        return font(config.FONT_COND_BOLD if bold else config.FONT_COND, size)
    return font(config.FONT_BOLD if bold else config.FONT_REGULAR, size)


def _bbox(d, s, fnt):
    """Text bounding box (l, t, r, b) across Pillow versions.
    textbbox: Pillow >= 8; getbbox: >= 8; getsize: <= 9 (e.g. 7.0 on the C2)."""
    if hasattr(d, "textbbox"):
        return d.textbbox((0, 0), s, font=fnt)
    if hasattr(fnt, "getbbox"):
        return fnt.getbbox(s)
    w, h = fnt.getsize(s)
    return 0, 0, w, h


def text(d, xy, s, fnt, fill=BLACK, anchor="la"):
    """Draw text with manual anchor handling (works across Pillow versions).
    anchor: two chars, horizontal[l/m/r] + vertical[a/m/d(=baseline->use a)]."""
    x, y = xy
    l, t, r, b = _bbox(d, s, fnt)
    w, h = r - l, b - t
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    if anchor[1] == "m":
        y -= h / 2
    elif anchor[1] == "d":
        y -= h
    d.text((x - l, y - t), s, font=fnt, fill=fill)
    return w, h


def _fmt_temp(t):
    if t is None:
        return "--"
    return "%.0f°" % round(t)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def _header(d, generated_at, stale):
    text(d, (8, 8), config.LOCATION_NAME, _f(26, bold=True))
    now = generated_at
    datestr = now.strftime("%a %-d %b %Y")
    upd = "updated %s" % now.strftime("%H:%M")
    if stale:
        upd = "STALE  " + upd
    text(d, (W - 8, 6), datestr, _f(20, bold=True), anchor="ra")
    text(d, (W - 8, 30), upd, _f(15), fill=RED if stale else BLACK, anchor="ra")
    d.line([6, 44, W - 6, 44], fill=BLACK, width=2)


# ---------------------------------------------------------------------------
# Current conditions (left column)
# ---------------------------------------------------------------------------
def _icon_args(h, moon):
    """Shared icon kwargs for a forecast row: red if bad, moon at night."""
    return dict(
        color=RED if h.get("bad") else BLACK,
        accent=RED,
        night=h.get("night", False),
        moon=(moon["illum"], moon["waxing"]) if moon else None,
        intensity=h.get("intensity", 2),
    )


def _current(d, cur, sun, moon):
    x0, x1 = 6, 250
    cx = (x0 + x1) // 2
    icons.draw_icon(d, cur["category"], cx - 35, 46, 70, **_icon_args(cur, moon))
    temp = cur["temp"]
    freezing = temp is not None and temp <= 0
    text(d, (cx, 114), _fmt_temp(temp), _f(50, bold=True),
         fill=RED if freezing else BLACK, anchor="ma")
    text(d, (cx, 166), cur["text"], _f(17),
         fill=RED if cur.get("bad") else BLACK, anchor="ma")

    # wind: speed with a direction arrow (points the way the wind blows)
    wind = cur.get("wind") or 0
    gust = cur.get("gust")
    wind_dir = cur.get("wind_dir")
    prefix, suffix = "Wind ", "%.0f m/s" % wind
    if gust and gust == gust and gust >= wind + 1:   # finite & meaningfully higher
        suffix += " (%.0f)" % gust
    fnt = _f(15)
    pw = _bbox(d, prefix, fnt)[2]
    sw = _bbox(d, suffix, fnt)[2]
    aw = 20 if (wind_dir is not None and wind >= 0.5) else 0
    sx = cx - (pw + aw + sw) / 2
    text(d, (sx, 188), prefix, fnt, anchor="la")
    if aw:
        _wind_arrow(d, sx + pw + aw / 2, 196, wind_dir, 8, BLACK)
    text(d, (sx + pw + aw, 188), suffix, fnt, anchor="la")

    # humidity
    hum = cur.get("humidity")
    if hum is not None:
        text(d, (cx, 207), "Humidity %.0f%%" % hum, _f(15), anchor="ma")

    # sunrise / sunset for today's big view
    if sun and (sun.get("sunrise") or sun.get("sunset")):
        sr = sun["sunrise"].strftime("%H:%M") if sun.get("sunrise") else "--"
        ss = sun["sunset"].strftime("%H:%M") if sun.get("sunset") else "--"
        _suntimes(d, cx, 227, sr, ss)


def _suntimes(d, cx, y, sr, ss):
    """Draw '↑ 04:07   ↓ 22:31' with simple up/down arrows."""
    fnt = _f(16, bold=True)
    srw = _bbox(d, sr, fnt)[2]
    ssw = _bbox(d, ss, fnt)[2]
    gap, aw = 30, 16
    total = aw + srw + gap + aw + ssw
    x = cx - total / 2
    _arrow(d, x + 5, y + 9, up=True)
    text(d, (x + aw, y), sr, fnt, anchor="la")
    x += aw + srw + gap
    _arrow(d, x + 5, y + 9, up=False)
    text(d, (x + aw, y), ss, fnt, anchor="la")


def _wind_arrow(d, cx, cy, from_deg, r, color=BLACK):
    """Arrow centred at (cx, cy) pointing the way the wind blows (downwind =
    from_deg + 180). Compass bearing: 0=N (up), 90=E (right)."""
    th = math.radians((from_deg + 180) % 360)
    dx, dy = math.sin(th), -math.cos(th)          # unit vector toward the tip
    fx, fy = cx + dx * r, cy + dy * r             # tip
    bx, by = cx - dx * r, cy - dy * r             # tail
    d.line([bx, by, fx, fy], fill=color, width=2)
    head = r * 0.8
    for ang in (28, -28):                          # two arrowhead wings
        a = math.radians(ang)
        rx = (-dx) * math.cos(a) - (-dy) * math.sin(a)
        ry = (-dx) * math.sin(a) + (-dy) * math.cos(a)
        d.line([fx, fy, fx + rx * head, fy + ry * head], fill=color, width=2)


def _arrow(d, x, y, up, color=BLACK):
    if up:
        d.line([x, y - 8, x, y + 8], fill=color, width=2)
        d.line([x, y - 8, x - 4, y - 3], fill=color, width=2)
        d.line([x, y - 8, x + 4, y - 3], fill=color, width=2)
    else:
        d.line([x, y - 8, x, y + 8], fill=color, width=2)
        d.line([x, y + 8, x - 4, y + 3], fill=color, width=2)
        d.line([x, y + 8, x + 4, y + 3], fill=color, width=2)


def _feels_like(t, wind):
    """Simple wind-chill style adjustment (kept light; FMI feels-like not
    requested in the params)."""
    if t is None:
        return None
    if t <= 10 and wind > 1.3:
        return (13.12 + 0.6215 * t - 11.37 * (wind ** 0.16)
                + 0.3965 * t * (wind ** 0.16))
    return t


# ---------------------------------------------------------------------------
# Next 24 hours (right panel)
# ---------------------------------------------------------------------------
def _detail_24h(d, hourly, moon):
    x0, x1 = 270, 792
    text(d, (x0, 49), "Next 24 hours", _f(19, bold=True))

    hours = hourly[:config.DETAIL_HOURS]
    n = len(hours)
    if n < 2:
        return
    gx0, gx1 = x0 + 8, x1
    step = (gx1 - gx0) / (n - 1)
    xs = [gx0 + i * step for i in range(n)]

    temps = [h["temp"] for h in hours if h["temp"] is not None]
    tmin, tmax = min(temps), max(temps)
    if tmax - tmin < 4:
        tmid = (tmax + tmin) / 2
        tmin, tmax = tmid - 2, tmid + 2
    gy_top, gy_bot = 120, 182

    def ty(t):
        return gy_bot - (t - tmin) / (tmax - tmin) * (gy_bot - gy_top)

    # zero-degree reference line if it falls in range (red, meaningful)
    if tmin < 0 < tmax:
        zy = ty(0)
        for xx in range(int(gx0), int(gx1), 10):
            d.line([xx, zy, xx + 5, zy], fill=RED, width=1)

    # weather symbols every 3h along the top band (night-aware, red if bad)
    for i in range(0, n, 3):
        icons.draw_icon(d, hours[i]["category"], xs[i] - 13, 74, 26,
                        **_icon_args(hours[i], moon))

    # temperature polyline + dots + labels every 3h
    pts = [(xs[i], ty(hours[i]["temp"])) for i in range(n)
           if hours[i]["temp"] is not None]
    if len(pts) >= 2:
        d.line(pts, fill=BLACK, width=2)
    for i in range(0, n, 3):
        t = hours[i]["temp"]
        if t is None:
            continue
        yy = ty(t)
        d.ellipse([xs[i] - 3, yy - 3, xs[i] + 3, yy + 3], fill=BLACK)
        text(d, (xs[i], yy - 17), _fmt_temp(t), _f(14, bold=True),
             fill=RED if t <= 0 else BLACK, anchor="ma")

    # precipitation bars along the bottom
    pmax = max([h["precip"] for h in hours] + [1.0])
    pb_top, pb_bot = 192, 212
    bw = max(4, step * 0.5)
    for i in range(n):
        p = hours[i]["precip"]
        if p <= 0:
            continue
        bh = (p / pmax) * (pb_bot - pb_top)
        d.rectangle([xs[i] - bw / 2, pb_bot - bh, xs[i] + bw / 2, pb_bot],
                    fill=BLACK)
    # if any precip, label the wettest hour
    wettest = max(hours, key=lambda h: h["precip"])
    if wettest["precip"] > 0:
        text(d, (gx1, 190), "max %.1f mm/h" % wettest["precip"],
             _f(12), anchor="rd")

    # hour labels every 3h
    for i in range(0, n, 3):
        text(d, (xs[i], 216), hours[i]["time"].strftime("%H"),
             _f(14), anchor="ma")


# ---------------------------------------------------------------------------
# Electricity price chart (bottom, full width)
# ---------------------------------------------------------------------------
def _electricity(d, prices):
    top = ELEC_TOP
    interval = prices.get("interval", 60)
    res = "15 min" if interval <= 15 else "%d min" % interval
    text(d, (ELEC_X0 + 6, top + 5), "Electricity  c/kWh", _f(19, bold=True))
    tw = _bbox(d, "Electricity  c/kWh", _f(19, bold=True))[2]
    text(d, (ELEC_X0 + 6 + tw + 8, top + 10), "incl. VAT · %s" % res, _f(12))
    # min / avg / max under the title
    summary = "min %.1f   avg %.1f   max %.1f" % (
        prices["min"], prices["avg"], prices["max"])
    text(d, (ELEC_X0 + 6, top + 28), summary, _f(13))

    # current price: big, top-right of the electricity box
    now = prices["now"]
    if now:
        nowtxt = "now %.1f" % now["price"]
        text(d, (ELEC_X1 - 4, top + 6), nowtxt, _f(30, bold=True),
             fill=RED if now["over"] else BLACK, anchor="ra")

    hours = prices["hours"]
    n = len(hours)
    if n == 0:
        return

    # chart area
    cx0, cx1 = ELEC_X0 + 38, ELEC_X1 - 4
    cy_top, cy_bot = top + 54, ELEC_BOTTOM
    threshold = prices["threshold"]
    vmax = max(prices["max"], threshold) * 1.08
    vmin = min(0.0, prices["min"])

    def vy(v):
        return cy_bot - (v - vmin) / (vmax - vmin) * (cy_bot - cy_top)

    y_base = vy(0)
    # y baseline (solid) + a max gridline (dashed, so it shows on 1-bit), labels
    for val in sorted(set([0.0, round(prices["max"], 1)])):
        yy = vy(val)
        if val == 0:
            d.line([cx0, yy, cx1, yy], fill=BLACK, width=1)
        else:
            for xx in range(int(cx0), int(cx1), 14):
                d.line([xx, yy, xx + 4, yy], fill=BLACK, width=1)
        text(d, (cx0 - 4, yy), "%.0f" % val, _f(13), anchor="rm")

    # threshold line in red (dashed)
    tyv = vy(threshold)
    for xx in range(int(cx0), int(cx1), 12):
        d.line([xx, tyv, xx + 6, tyv], fill=RED, width=2)
    text(d, (cx1, tyv - 2), "%.0f" % threshold, _f(13), fill=RED, anchor="rd")

    # bars (15-min slots touch each other to read as a continuous profile)
    bw = (cx1 - cx0) / n
    now_slot = None
    prev_day = None
    for i, r in enumerate(hours):
        bx = cx0 + i * bw
        col = RED if r["over"] else BLACK
        y0v = vy(max(r["price"], vmin))
        d.rectangle([bx, min(y0v, y_base), bx + bw, max(y0v, y_base)], fill=col)
        if r["is_now"]:
            now_slot = (bx, i)
        # day boundary marker + label
        dlabel = r["time"].strftime("%a")
        if dlabel != prev_day:
            if prev_day is not None:
                d.line([bx, cy_top - 4, bx, cy_bot + 4], fill=BLACK, width=1)
            text(d, (bx + 3, cy_bot + 4), dlabel, _f(14, bold=True), anchor="la")
            prev_day = dlabel
        # hour labels every 3h, on the hour (skip midnight; the day name marks it)
        if (r["time"].minute == 0 and r["time"].hour % 3 == 0
                and r["time"].hour != 0):
            d.line([bx, cy_bot, bx, cy_bot + 3], fill=BLACK, width=1)
            text(d, (bx, cy_bot + 4), r["time"].strftime("%H"), _f(12), anchor="ma")

    # highlight the current slot last so it sits on top
    if now_slot:
        bx, i = now_slot
        d.rectangle([bx - 1, cy_top, bx + bw + 1, cy_bot], outline=BLACK, width=2)
        text(d, (bx + bw / 2, cy_top - 2), "now", _f(13, bold=True), anchor="md")


# ---------------------------------------------------------------------------
# Warnings (derived from forecast: wind / thunder / heavy precip)
# ---------------------------------------------------------------------------
def _warn_triangle(d, x, y, s, color=RED):
    # outline via lines (polygon width= needs Pillow >= 8; device has 7.0)
    pts = [(x, y + s), (x + s, y + s), (x + s / 2, y), (x, y + s)]
    d.line(pts, fill=color, width=2, joint="curve")
    d.line([x + s / 2, y + s * 0.35, x + s / 2, y + s * 0.68], fill=color, width=2)
    d.line([x + s / 2, y + s * 0.78, x + s / 2, y + s * 0.84], fill=color, width=2)


def _warnings_banner(d, warnings):
    """Lower-right of the weather zone: an icon + label per active warning
    (FMI CAP warning, or a forecast-derived fallback). warnings is a list of
    {category, text}."""
    if not warnings:
        return
    x, y, s = 270, 226, 18
    maxx = 793
    fnt = _f(14, bold=True)
    cx = x
    for w in warnings:
        if cx + s + 30 > maxx:
            break
        icons.draw_warning_icon(d, w.get("category", "generic"), cx, y, s, color=RED)
        cx += s + 3
        label = _fit(d, w.get("text", ""), fnt, maxx - cx)
        text(d, (cx, y + 1), label, fnt, fill=RED)
        cx += _bbox(d, label, fnt)[2] + 14


# ---------------------------------------------------------------------------
# METAR / TAF (raw aviation text, bottom strip)
# ---------------------------------------------------------------------------
def _aviation(d, av):
    top = AVIATION_TOP
    d.line([6, top, W - 6, top], fill=BLACK, width=2)
    lab = _f(13, bold=True)
    if not av:
        text(d, (8, top + 8), "METAR/TAF unavailable", _f(14), fill=RED)
        return
    mono = font(config.FONT_MONO, 12)
    tx = 62                                   # mono text column (label-free)
    y = top + 7
    lh = 14

    text(d, (8, y), "METAR", lab)
    text(d, (tx, y + 1), _fit(d, av.get("metar", ""), mono, W - 8 - tx), mono)
    y += lh + 2

    taf = av.get("taf", [])
    for i, ln in enumerate(taf[:config.AVIATION_TAF_LINES]):
        if i == 0:
            text(d, (8, y), "TAF", lab)
        text(d, (tx, y + 1), _fit(d, ln, mono, W - 8 - tx), mono)
        y += lh


def _fit(d, s, fnt, maxw):
    """Truncate s to fit maxw px with the given font."""
    if _bbox(d, s, fnt)[2] <= maxw:
        return s
    while s and _bbox(d, s + "…", fnt)[2] > maxw:
        s = s[:-1]
    return s + "…"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------
def render(weather, prices, aviation=None, alert_polys=None, generated_at=None,
           stale=False, errors=None):
    """Return an RGB Image of the full screen."""
    if generated_at is None:
        generated_at = datetime.now().astimezone()
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    _header(d, generated_at, stale)
    # zone dividers: horizontal weather/bottom split + vertical left/right split
    d.line([6, MID_Y, W - 6, MID_Y], fill=BLACK, width=2)
    d.line([COL_X, 46, COL_X, AVIATION_TOP], fill=BLACK, width=1)

    if weather:
        moon = weather.get("moon")
        _current(d, weather["current"], weather.get("sun"), moon)
        _detail_24h(d, weather["hourly"], moon)
        _warnings_banner(d, weather.get("warnings"))
    else:
        text(d, (130, 150), "weather unavailable", _f(20), fill=RED, anchor="mm")

    # bottom-left: warnings map (below today's weather)
    finmap.draw_map(img, MAP_X, MAP_Y, MAP_W, MAP_H, alert_polys or [],
                    mark=(config.LATITUDE, config.LONGITUDE), title="Warnings")

    # bottom-right: electricity (beside the map)
    if prices:
        _electricity(d, prices)
    else:
        text(d, ((ELEC_X0 + ELEC_X1) / 2, (ELEC_TOP + AVIATION_TOP) / 2),
             "electricity prices unavailable", _f(20), fill=RED, anchor="mm")

    _aviation(d, aviation)

    if errors:
        text(d, (W - 8, AVIATION_TOP - 2), "!", _f(13, bold=True),
             fill=RED, anchor="rd")
    return img


def split_planes(img):
    """Split an RGB(black/red/white) image into (black_img, red_img) as mode-'1'
    images where pixel 0 = ink, 255 = blank, matching the panel buffer builder.

    Vectorised with PIL channel ops (C-speed) instead of a per-pixel Python loop
    -- the per-pixel version took seconds on the Odroid C2.
    """
    r, g, b = img.convert("RGB").split()
    # per-channel 0/255 threshold masks (mode 'L'); multiply acts as logical AND
    hi = lambda ch, t: ch.point(lambda v, t=t: 255 if v > t else 0)
    lo = lambda ch, t: ch.point(lambda v, t=t: 255 if v < t else 0)
    AND = ImageChops.multiply

    # 255 where red (red-dominant); 255 where black (dark in all channels).
    # red is excluded from black automatically since red needs r > 160.
    red_mask = AND(AND(hi(r, 160), lo(g, 110)), lo(b, 110))
    black_mask = AND(AND(lo(r, 128), lo(g, 128)), lo(b, 128))

    # driver wants 0 = ink: invert (mask is 255 at ink), then pack to 1-bit
    black = ImageChops.invert(black_mask).convert("1", dither=Image.NONE)
    red = ImageChops.invert(red_mask).convert("1", dither=Image.NONE)
    return black, red
