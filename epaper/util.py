"""Small shared helpers: HTTP fetching (with optional insecure TLS) and time
conversion. Standard library only so it runs on the target's Python 3.8."""
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone

import config

# Dev escape hatch: some hosts lack a usable CA bundle for Python. Set
# EPD_HTTP_INSECURE=1 to disable TLS verification for ALL requests (handy for
# generating local previews). Leave unset in production so FMI is verified.
_FORCE_INSECURE = os.environ.get("EPD_HTTP_INSECURE") == "1"


def http_get(url, insecure=False, timeout=None, retries=None):
    """GET a URL, returning the body as bytes. Retries with backoff.

    insecure=True disables TLS verification (needed for sahkotin.fi).
    """
    timeout = config.HTTP_TIMEOUT if timeout is None else timeout
    retries = config.HTTP_RETRIES if retries is None else retries

    ctx = ssl.create_default_context()
    if insecure or _FORCE_INSECURE:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={"User-Agent": "epaper-display/1.0"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - surface after retries
            last_err = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError("GET failed for %s: %s" % (url, last_err))


def parse_utc(ts):
    """Parse an ISO-8601 UTC timestamp (with optional .mmm and trailing Z)
    into an aware UTC datetime."""
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1]
    # drop fractional seconds if present
    if "." in ts:
        ts = ts.split(".", 1)[0]
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def to_local(dt_utc):
    """Convert an aware UTC datetime to the host's local timezone."""
    return dt_utc.astimezone()


def now_local():
    return datetime.now(timezone.utc).astimezone()
