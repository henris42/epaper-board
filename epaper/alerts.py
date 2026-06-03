"""Official FMI weather warnings from the CAP alert feed (alerts.fmi.fi).

This is FMI's authoritative warning service (separate from the forecast WFS): a
"fat Atom" feed embedding CAP 1.2 messages, covering wind, thunderstorm, rain,
traffic weather, forest fire, flooding, sea level, heat/cold, etc. We keep only
the warnings whose area polygon contains our location and that are in effect now
(or start within a lookahead window).
"""
from datetime import datetime, timedelta, timezone

import xml.etree.ElementTree as ET

import config
from epaper.util import http_get

ATOM = "{http://www.w3.org/2005/Atom}"
CAP = "{urn:oasis:names:tc:emergency:cap:1.2}"

# CAP <event> text (English feed) -> our warning category (drives the icon).
# Matched by keyword, first hit wins.
_CATEGORY_KEYWORDS = [
    ("fire", ("wildfire", "forest fire", "grass fire")),
    ("thunder", ("thunder",)),
    ("flood", ("flood", "sea level", "high water", "water level")),
    ("traffic", ("traffic", "road", "pedestrian")),
    ("wind", ("wind", "gale", "storm")),
    ("rain", ("rain", "precipitation")),
    ("snow", ("snow", "blizzard")),
    ("heat", ("hot weather", "heat")),
    ("cold", ("cold weather", "frost", "cold")),
    ("uv", ("uv", "ultraviolet")),
]

# severity ranking for sorting (CAP: Minor/Moderate/Severe/Extreme)
_SEV_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}

LOOKAHEAD_HOURS = 18           # also show warnings starting within this window


def _category(event):
    e = (event or "").lower()
    for cat, words in _CATEGORY_KEYWORDS:
        if any(w in e for w in words):
            return cat
    return "generic"


def _parse_time(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip())   # CAP uses +HH:MM offsets
    except ValueError:
        return None


def _polygon_points(text):
    """CAP polygon: 'lat,lon lat,lon ...' -> list of (x=lon, y=lat)."""
    pts = []
    for tok in (text or "").split():
        if "," in tok:
            lat, lon = tok.split(",", 1)
            try:
                pts.append((float(lon), float(lat)))
            except ValueError:
                pass
    return pts


def _point_in_polygon(px, py, verts):
    """Ray-casting test. px=lon, py=lat; verts are (lon, lat)."""
    inside = False
    n = len(verts)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def get_alerts(lat=None, lon=None):
    """Return active/imminent FMI warnings covering (lat, lon), most severe
    first. Each: {category, event, severity, onset, expires}."""
    lat = config.LATITUDE if lat is None else lat
    lon = config.LONGITUDE if lon is None else lon

    xml = http_get(config.ALERTS_FEED_URL, timeout=config.HTTP_TIMEOUT)
    root = ET.fromstring(xml)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=LOOKAHEAD_HOURS)

    out = []
    seen = set()
    for entry in root.findall(ATOM + "entry"):
        # "fat Atom": the CAP alert is embedded inside <content>
        content = entry.find(ATOM + "content")
        alert = content.find(CAP + "alert") if content is not None else None
        if alert is None:
            continue
        info = None
        for cand in alert.findall(CAP + "info"):
            if cand.findtext(CAP + "language") == "en-GB":
                info = cand
                break
        if info is None:
            continue

        event = info.findtext(CAP + "event")
        severity = info.findtext(CAP + "severity") or "Unknown"
        onset = _parse_time(info.findtext(CAP + "onset"))
        expires = _parse_time(info.findtext(CAP + "expires"))

        # in effect now, or starting within the lookahead window
        if expires and expires < now:
            continue
        if onset and onset > horizon:
            continue

        # does any area polygon contain our point?
        hit = False
        for area in info.findall(CAP + "area"):
            for poly in area.findall(CAP + "polygon"):
                if _point_in_polygon(lon, lat, _polygon_points(poly.text)):
                    hit = True
                    break
            if hit:
                break
        if not hit:
            continue

        key = (event, severity)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "category": _category(event),
            "event": event,
            "severity": severity,
            "onset": onset,
            "expires": expires,
        })

    out.sort(key=lambda w: -_SEV_RANK.get(w["severity"], 0))
    return out


if __name__ == "__main__":
    for w in get_alerts():
        print("%-9s %-9s %s" % (w["category"], w["severity"], w["event"]))
    print("(none)" if not get_alerts() else "")
