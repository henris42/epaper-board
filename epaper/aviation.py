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

    taf_raw = _get("taf", icao).strip()
    taf_lines = []
    for ln in taf_raw.splitlines():
        ln = ln.strip()
        if ln:
            taf_lines.append(ln)
    # the first line may start with "TAF "; drop that token for compactness
    if taf_lines and taf_lines[0].upper().startswith("TAF "):
        taf_lines[0] = taf_lines[0][4:]

    if not metar and not taf_lines:
        raise RuntimeError("no METAR/TAF for %s" % icao)
    return {"icao": icao, "metar": metar, "taf": taf_lines}


if __name__ == "__main__":
    a = get_aviation()
    print("ICAO:", a["icao"])
    print("METAR:", a["metar"])
    print("TAF:")
    for ln in a["taf"]:
        print("   ", ln)
