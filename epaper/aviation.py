"""METAR + TAF for an airport (default EFHK, Helsinki-Vantaa) from the NOAA
Aviation Weather Center API (free, no key, normal TLS).

Returned as raw aviation text, lightly cleaned: METAR as a single line, TAF as a
list of lines (the report line + its FM/BECMG/PROB change groups)."""
import config
from epaper.util import http_get

_BASE = "https://aviationweather.gov/api/data"


def _get(kind, icao):
    url = "%s/%s?ids=%s&format=raw" % (_BASE, kind, icao)
    return http_get(url, timeout=config.HTTP_TIMEOUT).decode("utf-8", "replace")


def get_aviation(icao=None):
    """Return {'icao', 'metar', 'taf'} where metar is a str and taf a list of
    lines. Raises on failure (caller treats aviation as optional)."""
    icao = icao or config.AVIATION_ICAO

    metar_raw = _get("metar", icao).strip()
    # the API may prefix "METAR "; keep just the body, single line
    metar = " ".join(metar_raw.split())
    if metar.upper().startswith("METAR "):
        metar = metar[6:]

    # collapse the source's line breaks into one normalised string; the renderer
    # word-wraps it to the panel width (the raw feed breaks mid change-group).
    taf = " ".join(_get("taf", icao).split())
    if taf.upper().startswith("TAF "):
        taf = taf[4:]

    if not metar and not taf:
        raise RuntimeError("no METAR/TAF for %s" % icao)
    return {"icao": icao, "metar": metar, "taf": taf}


if __name__ == "__main__":
    a = get_aviation()
    print("ICAO:", a["icao"])
    print("METAR:", a["metar"])
    print("TAF:", a["taf"])
