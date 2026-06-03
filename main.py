#!/usr/bin/env python3
"""Entry point: fetch weather + electricity prices, render the screen, push it
to the panel (or PNG in mock mode).

Resilient by design: if a source fails we fall back to the last good data cached
on disk and flag the screen as STALE, so a flaky network never blanks the panel.

Usage:
    python3 main.py                 # use config.DISPLAY_BACKEND (auto)
    EPD_BACKEND=mock python3 main.py
    python3 main.py --once          # default; render once and exit
"""
import argparse
import os
import pickle
import sys
import time
import traceback
from datetime import datetime, timezone

import config
from epaper import weather as weather_mod
from epaper import electricity as elec_mod
from epaper import aviation as aviation_mod
from epaper import render
from epaper.display.base import get_backend

CACHE_PATH = os.path.join(config.OUT_DIR, "last_good.pkl")
MAX_STALE_SECONDS = 6 * 3600  # show STALE banner; still render older than this


def _load_cache():
    try:
        with open(CACHE_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _save_cache(cache):
    os.makedirs(config.OUT_DIR, exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(cache, f)
    os.replace(tmp, CACHE_PATH)


def gather():
    """Fetch both sources, using cache for whichever fails.

    Returns (weather, prices, generated_at, stale, errors).
    """
    from concurrent.futures import ThreadPoolExecutor

    cache = _load_cache()
    errors = []
    now = datetime.now(timezone.utc)

    # The three sources are independent network fetches -- run them concurrently
    # so the total wait is the slowest one, not the sum.
    sources = [
        ("weather", weather_mod.get_weather),
        ("prices", elec_mod.get_prices),
        ("aviation", aviation_mod.get_aviation),
    ]
    results = {}
    with ThreadPoolExecutor(max_workers=len(sources)) as ex:
        futures = {ex.submit(fn): key for key, fn in sources}
        for fut, key in futures.items():
            try:
                results[key] = fut.result()
                cache[key] = results[key]
                cache[key + "_ts"] = now
            except Exception as exc:  # noqa: BLE001
                label = "metar/taf" if key == "aviation" else key
                errors.append("%s: %s" % (label, exc))
                results[key] = cache.get(key)

    weather = results.get("weather")
    prices = results.get("prices")
    aviation = results.get("aviation")

    if weather is not None or prices is not None or aviation is not None:
        _save_cache(cache)

    # stale if either shown dataset came from cache
    stale = bool(errors) and (weather is not None or prices is not None)
    return weather, prices, aviation, datetime.now().astimezone(), stale, errors


def run_once(backend):
    weather, prices, aviation, generated_at, stale, errors = gather()
    if weather is None and prices is None:
        print("ERROR: no data and no cache; rendering error screen")
    img = render.render(weather, prices, aviation, generated_at=generated_at,
                        stale=stale, errors=errors)
    backend.show(img)
    if errors:
        print("completed with warnings: %s" % "; ".join(errors))
    else:
        print("completed OK at %s" % generated_at.strftime("%Y-%m-%d %H:%M:%S"))
    return 0 if (weather or prices) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", default=None,
                    help="override backend: auto|epd|mock")
    ap.add_argument("--loop", type=int, metavar="MINUTES", default=0,
                    help="refresh every N minutes instead of running once")
    args = ap.parse_args(argv)

    backend = get_backend(args.backend)

    if args.loop <= 0:
        return run_once(backend)

    print("looping every %d min (Ctrl-C to stop)" % args.loop)
    while True:
        try:
            run_once(backend)
        except Exception:  # noqa: BLE001 - never let the loop die
            traceback.print_exc()
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    sys.exit(main())
