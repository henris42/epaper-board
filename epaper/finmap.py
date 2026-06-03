"""Tiny schematic map of southern Finland (up to Tampere) for the warnings view.

Draws a coarse national coastline, fills active warning areas in red, and marks a
few cities plus our location. Equirectangular projection with a cos(lat) factor
on longitude so shapes aren't stretched. Coordinates are (lon, lat)."""
import math

from epaper.icons import BLACK, RED, WHITE

# Coarse Finland outline (lon, lat) -- enough to read the southern coast at
# small size; the northern parts simply clip outside the map box.
FIN_OUTLINE = [
    (28.592, 69.065), (28.446, 68.365), (29.977, 67.698), (29.055, 66.944),
    (30.218, 65.806), (29.544, 64.949), (30.445, 64.204), (30.036, 63.553),
    (31.516, 62.868), (31.140, 62.358), (30.211, 61.780), (28.070, 60.504),
    (26.255, 60.424), (24.497, 60.057), (22.870, 59.846), (22.291, 60.392),
    (21.322, 60.720), (21.545, 61.705), (21.059, 62.607), (21.536, 63.190),
    (22.443, 63.818), (24.730, 64.902), (25.399, 65.111), (25.295, 65.534),
    (23.903, 66.006), (23.566, 66.396), (23.539, 67.936), (21.978, 68.617),
    (20.646, 69.106), (21.245, 69.370), (22.182, 68.844), (23.024, 68.690),
    (23.984, 68.689), (24.736, 68.650), (25.689, 69.092), (26.180, 69.825),
    (27.732, 70.164), (28.592, 69.065),
]

# (name, lat, lon, is_major)
CITIES = [
    ("Helsinki", 60.17, 24.94, True),
    ("Tampere", 61.50, 23.79, True),
    ("Turku", 60.45, 22.27, True),
    ("Lahti", 60.98, 25.66, False),
    ("Kotka", 60.47, 26.94, False),
    ("Hämeenlinna", 60.99, 24.46, False),
    ("Pori", 61.49, 21.80, False),
]

# bbox: lat0, lat1, lon0, lon1  (southern Finland, north edge ~ Tampere/Pori)
BBOX = (59.55, 61.85, 20.4, 28.9)


def aspect(bbox=BBOX):
    """Width/height ratio for an undistorted map of the bbox."""
    lat0, lat1, lon0, lon1 = bbox
    latm = (lat0 + lat1) / 2
    return ((lon1 - lon0) * math.cos(math.radians(latm))) / (lat1 - lat0)


def _projector(x, y, w, h, bbox=BBOX):
    lat0, lat1, lon0, lon1 = bbox
    latm = (lat0 + lat1) / 2
    kx = math.cos(math.radians(latm))
    xs = (lon1 - lon0) * kx
    ys = (lat1 - lat0)

    def proj(lon, lat):
        return (x + (lon - lon0) * kx / xs * w,
                y + (lat1 - lat) / ys * h)
    return proj


def draw_map(img, x, y, w, h, warning_polys, mark=None, title="Warnings"):
    """warning_polys: list of rings, each a list of (lon, lat). mark: (lat, lon)
    for our location. Warned areas are red-hatched so the map stays readable.

    Rendered into its own w x h tile and pasted, so geometry reaching outside the
    map box clips cleanly instead of spilling across the screen."""
    from PIL import Image, ImageDraw, ImageFont
    import config
    w, h = int(w), int(h)
    m = Image.new("RGB", (w, h), WHITE)
    md = ImageDraw.Draw(m)
    proj = _projector(0, 0, w, h, BBOX)

    # warned areas as a red diagonal hatch (polygon mask -> paste)
    mask = Image.new("1", (w, h), 0)
    kd = ImageDraw.Draw(mask)
    for ring in warning_polys:
        pts = [proj(lon, lat) for lon, lat in ring]
        if len(pts) >= 3:
            kd.polygon(pts, fill=1)
    hatch = Image.new("RGB", (w, h), WHITE)
    hd = ImageDraw.Draw(hatch)
    for i in range(-h, w, 7):
        hd.line([(i, 0), (i + h, h)], fill=RED, width=1)
    m.paste(hatch, (0, 0), mask)

    # coastline
    md.line([proj(lon, lat) for lon, lat in FIN_OUTLINE], fill=BLACK, width=2)

    # cities
    f = ImageFont.truetype(config.FONT_REGULAR, 10)
    for name, lat, lon, major in CITIES:
        px, py = proj(lon, lat)
        if not (0 <= px <= w and 0 <= py <= h):
            continue
        r = 2 if major else 1
        md.ellipse([px - r, py - r, px + r, py + r], fill=BLACK)
        if major:
            md.text((px + 4, py - 5), name, font=f, fill=BLACK)

    # our location marker (crosshair) on top
    if mark:
        px, py = proj(mark[1], mark[0])
        md.ellipse([px - 4, py - 4, px + 4, py + 4], outline=BLACK, width=2)
        md.line([px - 6, py, px + 6, py], fill=BLACK, width=1)
        md.line([px, py - 6, px, py + 6], fill=BLACK, width=1)

    md.text((4, 2), title, font=ImageFont.truetype(config.FONT_BOLD, 12),
            fill=BLACK)
    md.rectangle([0, 0, w - 1, h - 1], outline=BLACK, width=1)
    img.paste(m, (x, y))
