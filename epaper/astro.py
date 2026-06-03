"""Sun altitude (day/night) and moon phase. Pure stdlib, good to a fraction of a
degree — plenty for deciding night vs day and which moon glyph to draw."""
import math
from datetime import timezone


def _julian(dt):
    """Julian Date from an aware datetime (converted to UTC)."""
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    day = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def solar_altitude(dt_utc, lat, lon):
    """Sun altitude in degrees above the horizon."""
    n = _julian(dt_utc) - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    decl = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    lst = math.radians((gmst + lon) % 360)
    H = lst - ra
    alt = math.asin(math.sin(math.radians(lat)) * math.sin(decl)
                    + math.cos(math.radians(lat)) * math.cos(decl) * math.cos(H))
    return math.degrees(alt)


def is_night(dt_utc, lat, lon):
    """True when the sun is below the horizon (standard -0.833 deg refraction)."""
    return solar_altitude(dt_utc, lat, lon) < -0.833


def moon_phase(dt_utc):
    """Return (phase, illum, waxing):
      phase  0..1 (0/1 = new, 0.5 = full)
      illum  illuminated fraction 0..1
      waxing True while growing (lit limb on the right in the N hemisphere)
    """
    jd = _julian(dt_utc)
    syn = 29.530588853
    days = (jd - 2451550.1) % syn      # 2451550.1 = a known new moon
    phase = days / syn
    illum = (1 - math.cos(2 * math.pi * phase)) / 2
    return phase, illum, phase < 0.5


def _sun_event(date, lat, lon, rising, zenith=90.833):
    """Sunrise/sunset (UTC) for a date using the standard sunrise equation.
    Returns an aware UTC datetime, or None if the sun doesn't cross the horizon
    that day (polar day/night). zenith 90.833 = official sunrise/sunset."""
    from datetime import datetime, timedelta, timezone

    def sin(d): return math.sin(math.radians(d))
    def cos(d): return math.cos(math.radians(d))

    N = date.timetuple().tm_yday
    lng_hour = lon / 15.0
    t = N + ((6 if rising else 18) - lng_hour) / 24.0
    M = 0.9856 * t - 3.289
    L = (M + 1.916 * sin(M) + 0.020 * sin(2 * M) + 282.634) % 360
    RA = math.degrees(math.atan(0.91764 * math.tan(math.radians(L)))) % 360
    # put RA in the same quadrant as L
    RA = (RA + (math.floor(L / 90) * 90 - math.floor(RA / 90) * 90)) % 360
    RA /= 15.0
    sin_dec = 0.39782 * sin(L)
    cos_dec = cos(math.degrees(math.asin(sin_dec)))
    cos_H = (cos(zenith) - sin_dec * sin(lat)) / (cos_dec * cos(lat))
    if cos_H > 1 or cos_H < -1:
        return None                         # never rises / never sets
    H = (360 - math.degrees(math.acos(cos_H))) if rising \
        else math.degrees(math.acos(cos_H))
    H /= 15.0
    T = H + RA - 0.06571 * t - 6.622
    UT = (T - lng_hour) % 24
    base = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    return base + timedelta(hours=UT)


def sun_rise_set(date, lat, lon):
    """Return (sunrise_utc, sunset_utc); either may be None at high latitude."""
    return (_sun_event(date, lat, lon, True),
            _sun_event(date, lat, lon, False))


_PHASE_NAMES = [
    "New moon", "Waxing crescent", "First quarter", "Waxing gibbous",
    "Full moon", "Waning gibbous", "Last quarter", "Waning crescent",
]


def moon_phase_name(phase):
    return _PHASE_NAMES[int((phase * 8 + 0.5)) % 8]
