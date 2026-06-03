"""Localisation: English / Finnish / Swedish. Pick via config.LANGUAGE.

Weekday and month names are defined here (not via the C locale, which may be
absent on the device). FMI's CAP warnings come translated from the matching
language feed, so warning text needs no local translation."""
import config

LANG = config.LANGUAGE if config.LANGUAGE in ("en", "fi", "sv") else "en"

# CAP warning feed + <info> language tag per UI language
ALERT_FEED = {"en": "atom_en-GB.xml", "fi": "atom_fi-FI.xml",
              "sv": "atom_sv-FI.xml"}[LANG]
ALERT_LANG = {"en": "en-GB", "fi": "fi-FI", "sv": "sv-FI"}[LANG]

WEEKDAYS = {  # Mon..Sun
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "fi": ["ma", "ti", "ke", "to", "pe", "la", "su"],
    "sv": ["mån", "tis", "ons", "tor", "fre", "lör", "sön"],
}
MONTHS = {  # Jan..Dec
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec"],
    "fi": ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä",
           "elo", "syys", "loka", "marras", "joulu"],
    "sv": ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep",
           "okt", "nov", "dec"],
}

STRINGS = {
    "en": {
        "updated": "updated", "stale": "STALE",
        "wind": "Wind", "humidity": "Humidity",
        "next24": "Next 24 hours", "maxprecip": "max %.1f mm/h",
        "electricity": "Electricity  c/kWh", "incl_vat": "incl. VAT",
        "avg": "avg", "now": "now", "warnings": "Warnings",
        "weather_na": "weather unavailable",
        "prices_na": "electricity prices unavailable",
        "metar_na": "METAR/TAF unavailable",
        "w_thunder": "Thunderstorms %s",
        "w_vwind": "Very strong wind, gusts %.0f m/s %s",
        "w_swind": "Strong wind, gusts %.0f m/s %s",
        "w_precip": "Heavy precipitation %s",
        "w_snow": "Snowfall %s",
        "w_fire": "Forest fire warning",
        "w_traffic": "Traffic weather warning",
    },
    "fi": {
        "updated": "päivitetty", "stale": "VANHA",
        "wind": "Tuuli", "humidity": "Kosteus",
        "next24": "Seuraavat 24 h", "maxprecip": "maks %.1f mm/h",
        "electricity": "Sähkö  c/kWh", "incl_vat": "sis. ALV",
        "avg": "ka", "now": "nyt", "warnings": "Varoitukset",
        "weather_na": "sää ei saatavilla",
        "prices_na": "sähkön hinta ei saatavilla",
        "metar_na": "METAR/TAF ei saatavilla",
        "w_thunder": "Ukkosta %s",
        "w_vwind": "Kova tuuli, puuskissa %.0f m/s %s",
        "w_swind": "Voimakas tuuli, puuskissa %.0f m/s %s",
        "w_precip": "Runsasta sadetta %s",
        "w_snow": "Lumisadetta %s",
        "w_fire": "Metsäpalovaroitus",
        "w_traffic": "Liikennesäävaroitus",
    },
    "sv": {
        "updated": "uppdaterad", "stale": "GAMMAL",
        "wind": "Vind", "humidity": "Fukt",
        "next24": "Nästa 24 h", "maxprecip": "max %.1f mm/h",
        "electricity": "El  c/kWh", "incl_vat": "inkl. moms",
        "avg": "snitt", "now": "nu", "warnings": "Varningar",
        "weather_na": "väder ej tillgängligt",
        "prices_na": "elpris ej tillgängligt",
        "metar_na": "METAR/TAF ej tillgängligt",
        "w_thunder": "Åska %s",
        "w_vwind": "Mycket hård vind, byar %.0f m/s %s",
        "w_swind": "Hård vind, byar %.0f m/s %s",
        "w_precip": "Kraftig nederbörd %s",
        "w_snow": "Snöfall %s",
        "w_fire": "Varning för terrängbrand",
        "w_traffic": "Trafikvädervarning",
    },
}

# FMI WeatherSymbol3 code -> condition text per language
CONDITIONS = {
    "en": {1: "Clear", 2: "Partly cloudy", 3: "Cloudy",
           21: "Light showers", 22: "Showers", 23: "Heavy showers",
           31: "Light rain", 32: "Rain", 33: "Heavy rain",
           41: "Light snow showers", 42: "Snow showers", 43: "Heavy snow showers",
           51: "Light snowfall", 52: "Snowfall", 53: "Heavy snowfall",
           61: "Thundershowers", 62: "Heavy thundershowers", 63: "Thunder",
           64: "Heavy thunder", 71: "Light sleet showers", 72: "Sleet showers",
           73: "Heavy sleet showers", 81: "Light sleet", 82: "Sleet",
           83: "Heavy sleet", 91: "Haze", 92: "Fog"},
    "fi": {1: "Selkeää", 2: "Puolipilvistä", 3: "Pilvistä",
           21: "Heikkoja kuuroja", 22: "Sadekuuroja", 23: "Voimakkaita kuuroja",
           31: "Heikkoa sadetta", 32: "Sadetta", 33: "Voimakasta sadetta",
           41: "Heikkoja lumikuuroja", 42: "Lumikuuroja", 43: "Sakeita lumikuuroja",
           51: "Heikkoa lumisadetta", 52: "Lumisadetta", 53: "Runsasta lumisadetta",
           61: "Ukkoskuuroja", 62: "Voimakkaita ukkoskuuroja", 63: "Ukkosta",
           64: "Voimakasta ukkosta", 71: "Heikkoja räntäkuuroja",
           72: "Räntäkuuroja", 73: "Voimakkaita räntäkuuroja",
           81: "Heikkoa räntää", 82: "Räntää", 83: "Voimakasta räntää",
           91: "Utua", 92: "Sumua"},
    "sv": {1: "Klart", 2: "Halvklart", 3: "Mulet",
           21: "Lätta skurar", 22: "Regnskurar", 23: "Kraftiga skurar",
           31: "Lätt regn", 32: "Regn", 33: "Kraftigt regn",
           41: "Lätta snöbyar", 42: "Snöbyar", 43: "Kraftiga snöbyar",
           51: "Lätt snöfall", 52: "Snöfall", 53: "Ymnigt snöfall",
           61: "Åskskurar", 62: "Kraftiga åskskurar", 63: "Åska",
           64: "Kraftig åska", 71: "Lätta snöblandade skurar",
           72: "Snöblandade skurar", 73: "Kraftiga snöblandade skurar",
           81: "Lätt snöblandat regn", 82: "Snöblandat regn",
           83: "Kraftigt snöblandat regn", 91: "Dis", 92: "Dimma"},
}


def t(key):
    return STRINGS[LANG].get(key, STRINGS["en"][key])


def condition(symbol):
    return CONDITIONS[LANG].get(symbol, CONDITIONS["en"].get(symbol, "—"))


def weekday(dt):
    return WEEKDAYS[LANG][dt.weekday()]


def fmt_date(dt):
    return "%s %d %s %d" % (weekday(dt), dt.day, MONTHS[LANG][dt.month - 1],
                            dt.year)
