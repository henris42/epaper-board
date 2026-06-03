"""Fetch Nord Pool FI spot prices from sahkotin.fi as CSV and shape them for the
price chart.

The CSV is `hour,price` with UTC timestamps and price in EUR/MWh. We convert to
c/kWh (divide by 10). sahkotin.fi presents a certificate that fails default
verification, so the request is made with TLS verification disabled.
"""
from datetime import datetime, timedelta, timezone

import config
from epaper.util import http_get, parse_utc, to_local


def _build_url():
    # show only the previous half hour, then as far ahead as data is published
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=config.PRICE_PAST_MINUTES)
    end = now + timedelta(hours=config.PRICE_FUTURE_HOURS)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    parts = ["start=" + start.strftime(fmt), "end=" + end.strftime(fmt)]
    if config.SAHKOTIN_INCLUDE_VAT:
        parts.append("vat")
    if config.PRICE_QUARTERS:
        parts.append("quarter")          # 15-minute resolution
    return config.SAHKOTIN_URL + "?" + "&".join(parts)


def _parse(csv_text):
    rows = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("hour"):
            continue
        try:
            ts, val = line.split(",", 1)
            price_c_kwh = float(val) / 10.0   # EUR/MWh -> c/kWh
        except ValueError:
            continue
        rows.append({
            "time": to_local(parse_utc(ts)),
            "price": price_c_kwh,
        })
    rows.sort(key=lambda r: r["time"])
    return rows


def get_prices():
    """Return {'hours': [...], 'now', 'min', 'max', 'avg', 'threshold'} or raise.

    Each hour row: {time, price, is_now, over}.
    """
    csv_text = http_get(_build_url(),
                        insecure=config.SAHKOTIN_INSECURE_TLS).decode("utf-8", "replace")
    rows = _parse(csv_text)
    if not rows:
        raise RuntimeError("sahkotin returned no price rows")

    now = datetime.now(timezone.utc).astimezone()
    threshold = config.PRICE_RED_THRESHOLD_C_KWH

    # infer slot length from the first gap (15 or 60 min)
    interval = 60
    if len(rows) >= 2:
        interval = max(1, int((rows[1]["time"] - rows[0]["time"]).total_seconds() // 60))
    slot = timedelta(minutes=interval)

    current = None
    for r in rows:
        r["over"] = r["price"] >= threshold
        r["is_now"] = r["time"] <= now < r["time"] + slot
        if r["is_now"]:
            current = r

    prices = [r["price"] for r in rows]
    return {
        "hours": rows,
        "now": current,
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
        "threshold": threshold,
        "interval": interval,
    }


if __name__ == "__main__":  # quick manual check
    p = get_prices()
    print("min %.2f  max %.2f  avg %.2f  threshold %.1f c/kWh" %
          (p["min"], p["max"], p["avg"], p["threshold"]))
    if p["now"]:
        print("now: %.2f c/kWh%s" %
              (p["now"]["price"], "  (RED)" if p["now"]["over"] else ""))
    for r in p["hours"][:6]:
        print("  %s  %6.2f c/kWh %s" %
              (r["time"].strftime("%a %H:%M"), r["price"], "RED" if r["over"] else ""))
