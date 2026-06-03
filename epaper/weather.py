"""Fetch the official FMI forecast for the configured location and shape it
into current / hourly / daily structures for rendering.

FMI open data WFS, "simple" feature format. Each <BsWfs:BsWfsElement> carries a
Time, a ParameterName and a ParameterValue. We pivot those into per-hour rows.
"""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import timedelta

import config
from epaper import astro
from epaper.util import http_get, parse_utc, to_local

# FMI WeatherSymbol3 code -> (category, text, intensity). Category drives the
# icon; intensity (1 light .. 3 heavy) drives drop/flake count.
SYMBOL3 = {
    1:  ("clear",   "Clear",              0),
    2:  ("pcloudy", "Partly cloudy",      0),
    3:  ("cloudy",  "Cloudy",             0),
    21: ("showers", "Light showers",      1),
    22: ("showers", "Showers",            2),
    23: ("showers", "Heavy showers",      3),
    31: ("drizzle", "Light rain",         1),
    32: ("rain",    "Rain",               2),
    33: ("rain",    "Heavy rain",         3),
    41: ("snow",    "Light snow showers", 1),
    42: ("snow",    "Snow showers",       2),
    43: ("snow",    "Heavy snow showers", 3),
    51: ("snow",    "Light snowfall",     1),
    52: ("snow",    "Snowfall",           2),
    53: ("snow",    "Heavy snowfall",     3),
    61: ("thunder", "Thundershowers",     2),
    62: ("thunder", "Heavy thundershowers", 3),
    63: ("thunder", "Thunder",            2),
    64: ("thunder", "Heavy thunder",      3),
    71: ("sleet",   "Light sleet showers", 1),
    72: ("sleet",   "Sleet showers",      2),
    73: ("sleet",   "Heavy sleet showers", 3),
    81: ("sleet",   "Light sleet",        1),
    82: ("sleet",   "Sleet",              2),
    83: ("sleet",   "Heavy sleet",        3),
    91: ("fog",     "Haze",               1),
    92: ("fog",     "Fog",                2),
}

# Categories drawn in red on the panel (precipitation / storms).
BAD_CATEGORIES = {"drizzle", "rain", "showers", "snow", "sleet", "thunder"}

_NS = {"wfs": "http://www.opengis.net/wfs/2.0",
       "BsWfs": "http://xml.fmi.fi/schema/wfs/2.0"}

# Parameters requested from FMI (order matters only for the URL).
_PARAMS = ["Temperature", "WindSpeedMS", "WindGust",
           "WeatherSymbol3", "Precipitation1h"]


def _build_url():
    # request from the current hour to now + FORECAST_HOURS, hourly
    from datetime import datetime, timezone
    start_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=config.FORECAST_HOURS)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    params = (
        "service=WFS&version=2.0.0&request=getFeature"
        "&storedquery_id=%s"
        "&latlon=%.4f,%.4f"
        "&parameters=%s"
        "&starttime=%s&endtime=%s&timestep=60"
    ) % (
        config.FMI_STORED_QUERY,
        config.LATITUDE, config.LONGITUDE,
        ",".join(_PARAMS),
        start_dt.strftime(fmt), end_dt.strftime(fmt),
    )
    return config.FMI_WFS_URL + "?" + params


def _parse(xml_bytes):
    """Return list of hourly dict rows sorted by time."""
    root = ET.fromstring(xml_bytes)
    # time(iso) -> {param: value}
    rows = defaultdict(dict)
    for el in root.iterfind(".//BsWfs:BsWfsElement", _NS):
        t = el.findtext("BsWfs:Time", namespaces=_NS)
        name = el.findtext("BsWfs:ParameterName", namespaces=_NS)
        val = el.findtext("BsWfs:ParameterValue", namespaces=_NS)
        if t is None or name is None:
            continue
        try:
            fval = float(val)
            if fval != fval:      # NaN
                fval = None
        except (TypeError, ValueError):
            fval = None
        rows[t][name] = fval

    hourly = []
    for t in sorted(rows):
        r = rows[t]
        sym = r.get("WeatherSymbol3")
        cat, text, inten = SYMBOL3.get(int(sym) if sym is not None else -1,
                                       ("cloudy", "—", 0))
        dt_utc = parse_utc(t)
        hourly.append({
            "time": to_local(dt_utc),
            "time_utc": dt_utc,
            "temp": r.get("Temperature"),
            "wind": r.get("WindSpeedMS"),
            "gust": r.get("WindGust"),
            "precip": r.get("Precipitation1h") or 0.0,
            "symbol": int(sym) if sym is not None else None,
            "category": cat,
            "text": text,
            "intensity": inten,
            "bad": cat in BAD_CATEGORIES,
            "night": astro.is_night(dt_utc, config.LATITUDE, config.LONGITUDE),
        })
    return hourly


def _daily(hourly):
    """Aggregate hourly rows into per-day min/max + a representative midday
    symbol, for a short multi-day outlook."""
    by_day = defaultdict(list)
    for h in hourly:
        by_day[h["time"].date()].append(h)
    days = []
    for d in sorted(by_day):
        rows = by_day[d]
        temps = [r["temp"] for r in rows if r["temp"] is not None]
        if not temps:
            continue
        # pick the symbol nearest 14:00 local as the day's headline
        midday = min(rows, key=lambda r: abs(r["time"].hour - 14))
        days.append({
            "date": d,
            "tmin": min(temps),
            "tmax": max(temps),
            "category": midday["category"],
            "symbol": midday["symbol"],
        })
    return days


# wind thresholds (m/s) for derived warnings, loosely matching FMI land warnings
WIND_WARN_GUST = 15.0
WIND_STRONG_GUST = 20.0


def _warnings(hourly):
    """Derive weather warnings from the next-24h forecast (FMI has no open
    warnings WFS). Returns a short list of strings, most severe first."""
    window = hourly[:config.DETAIL_HOURS]
    warns = []

    thunder = [h for h in window if h["category"] == "thunder"]
    if thunder:
        warns.append(("Thunderstorms %s" %
                      _span(thunder), 3))

    gust_peak = max(window, key=lambda h: (h["gust"] or 0))
    gp = gust_peak["gust"] or 0
    if gp >= WIND_STRONG_GUST:
        warns.append(("Very strong wind, gusts %.0f m/s %s" %
                      (gp, gust_peak["time"].strftime("%H:%M")), 3))
    elif gp >= WIND_WARN_GUST:
        warns.append(("Strong wind, gusts %.0f m/s %s" %
                      (gp, gust_peak["time"].strftime("%H:%M")), 2))

    heavy = [h for h in window if h["precip"] >= 4.0]
    if heavy:
        warns.append(("Heavy precipitation %s" % _span(heavy), 2))

    snow = [h for h in window if h["category"] == "snow"]
    if snow and not thunder:
        warns.append(("Snowfall %s" % _span(snow), 1))

    warns.sort(key=lambda w: -w[1])
    return [w[0] for w in warns[:3]]


def _span(rows):
    """Compact 'HH–HH' label for a set of hourly rows."""
    a = min(r["time"] for r in rows)
    b = max(r["time"] for r in rows)
    if a.hour == b.hour:
        return a.strftime("%H:%M")
    return "%s–%s" % (a.strftime("%H"), b.strftime("%H"))


def get_weather():
    """Return weather dict (current/hourly/daily/sun/moon/warnings) or raise."""
    xml_bytes = http_get(_build_url(), timeout=config.HTTP_TIMEOUT)
    hourly = _parse(xml_bytes)
    if not hourly:
        raise RuntimeError("FMI returned no forecast rows")

    current = dict(hourly[0])
    current["label"] = "Now"

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    phase, illum, waxing = astro.moon_phase(now)
    sr, ss = astro.sun_rise_set(now.astimezone().date(),
                                config.LATITUDE, config.LONGITUDE)

    return {
        "current": current,
        "hourly": hourly[:config.DETAIL_HOURS],
        "hourly_all": hourly,
        "daily": _daily(hourly)[:5],
        "sun": {
            "sunrise": to_local(sr) if sr else None,
            "sunset": to_local(ss) if ss else None,
        },
        "moon": {
            "phase": phase, "illum": illum, "waxing": waxing,
            "name": astro.moon_phase_name(phase),
        },
        "warnings": _warnings(hourly),
    }


if __name__ == "__main__":  # quick manual check
    w = get_weather()
    c = w["current"]
    print("Now: %.1fC %s, wind %.0f m/s" % (c["temp"], c["text"], c["wind"] or 0))
    for h in w["hourly"][:6]:
        print("  %s %5.1fC %-16s precip %.1f" %
              (h["time"].strftime("%H:%M"), h["temp"], h["text"], h["precip"]))
    for d in w["daily"]:
        print("Day %s  %.0f..%.0f  %s" %
              (d["date"], d["tmin"], d["tmax"], d["category"]))
