"""Time and weather skill: geocode place names, fetch weather (Open-Meteo, no API key), current time."""
from __future__ import annotations
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> short description
WEATHER_CODES = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def get_current_time_utc() -> str:
    """Return current UTC time as a short string for context (24h)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_current_time_utc_12h() -> str:
    """Return current UTC time in 12-hour AM/PM format for context and user-facing replies."""
    now = datetime.now(timezone.utc)
    h = now.hour
    if h == 0:
        hour12, am_pm = 12, "AM"
    elif h < 12:
        hour12, am_pm = h, "AM"
    elif h == 12:
        hour12, am_pm = 12, "PM"
    else:
        hour12, am_pm = h - 12, "PM"
    return now.strftime("%Y-%m-%d ") + f"{hour12}:{now.minute:02d} {am_pm} UTC"


async def geocode(query: str) -> tuple[float, float, str] | None:
    """Resolve a place name to (latitude, longitude, display_name). Returns None if not found."""
    query = (query or "").strip()
    if not query:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(GEOCODE_URL, params={"name": query, "count": 1})
            r.raise_for_status()
            data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        first = results[0]
        lat = float(first["latitude"])
        lon = float(first["longitude"])
        name = first.get("name", query)
        country = first.get("country_code", "")
        if country:
            name = f"{name}, {country}"
        return (lat, lon, name)
    except Exception as e:
        logger.warning("Geocode failed for %r: %s", query, e)
        return None


def _timezone_from_coords_sync(latitude: float, longitude: float) -> str | None:
    """Offline lookup: return IANA timezone (e.g. 'Asia/Jerusalem') for lat/lon, or None."""
    try:
        from timezonefinder import timezone_at
        tz = timezone_at(lat=latitude, lng=longitude)
        return tz
    except Exception as e:
        logger.warning("Timezonefinder failed for %.2f,%.2f: %s", latitude, longitude, e)
        return None


# Fallback when coords lookup fails: map location-name keywords to IANA timezone
_LOCATION_TZ_FALLBACKS: list[tuple[list[str], str]] = [
    (["israel", "holon", "jerusalem", "tel aviv", "haifa", "beer sheva", "eilat"], "Asia/Jerusalem"),
]


async def get_timezone_for_coords(latitude: float, longitude: float, location_name: str | None = None) -> str:
    """Return IANA timezone (e.g. 'Asia/Jerusalem') for lat/lon. Location-name override when it clearly indicates a region (e.g. Holon, Israel -> Asia/Jerusalem)."""
    # Location name override: if user said "Holon" or "Israel", trust it over coords (coords can be wrong)
    if location_name:
        name_lower = location_name.lower()
        for keywords, tz_id in _LOCATION_TZ_FALLBACKS:
            if any(kw in name_lower for kw in keywords):
                return tz_id
    tz = _timezone_from_coords_sync(latitude, longitude)
    if tz:
        return tz
    
    logger.info("Timezonefinder returned None for %.4f,%.4f; falling back to Open-Meteo", latitude, longitude)
    fallback = "UTC"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                WEATHER_URL,
                params={"latitude": latitude, "longitude": longitude, "current": "temperature_2m"},
            )
            r.raise_for_status()
            data = r.json()
        fallback = data.get("timezone") or "UTC"
        logger.info("Open-Meteo returned timezone: %s", fallback)
    except Exception as e:
        logger.warning("Open-Meteo timezone lookup failed for %.2f,%.2f: %s", latitude, longitude, e)
    
    # Sanity check: if we got UTC but the user said "Israel" or "Holon", warn loudly
    if fallback == "UTC" and location_name:
        name_lower = location_name.lower()
        if any(k in name_lower for k in ("israel", "holon", "jerusalem", "tel aviv")):
             logger.error("SUSPICIOUS TIMEZONE: Resolved to UTC for location '%s' (lat=%.4f, lon=%.4f). Check network or timezonefinder installation.", location_name, latitude, longitude)
    
    return fallback


async def fetch_weather(latitude: float, longitude: float) -> str:
    """Fetch current weather summary for lat/lon. Returns a short one-line description."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                WEATHER_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,relative_humidity_2m,weather_code",
                },
            )
            r.raise_for_status()
            data = r.json()
        cur = data.get("current") or {}
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code", 0)
        desc = WEATHER_CODES.get(int(code), "unknown")
        if temp is not None:
            return f"{desc}, {temp}°C"
        return desc
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        return "unavailable"


async def fetch_weather_with_forecast(
    latitude: float, longitude: float, timezone_str: str | None = None
) -> dict[str, str]:
    """Fetch current weather plus today and tomorrow forecast. Returns dict with current, today, tomorrow (each a short line).
    timezone_str: IANA timezone (e.g. 'Asia/Jerusalem') for correct today/tomorrow boundaries. Default UTC."""
    tz = timezone_str or "UTC"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                WEATHER_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,weather_code",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                    "timezone": tz,
                    "forecast_days": 3,
                },
            )
            r.raise_for_status()
            data = r.json()
        out: dict[str, str] = {}
        cur = data.get("current") or {}
        ctemp = cur.get("temperature_2m")
        ccode = cur.get("weather_code", 0)
        cdesc = WEATHER_CODES.get(int(ccode), "unknown")
        out["current"] = f"{cdesc}, {ctemp}°C" if ctemp is not None else cdesc
        daily = data.get("daily") or {}
        times = daily.get("time") or []
        codes = daily.get("weather_code") or []
        max_t = daily.get("temperature_2m_max") or []
        min_t = daily.get("temperature_2m_min") or []
        for i in range(min(3, len(times))):
            day_label = "today" if i == 0 else ("tomorrow" if i == 1 else "day after")
            code = int(codes[i]) if i < len(codes) else 0
            desc = WEATHER_CODES.get(code, "unknown")
            tmax = max_t[i] if i < len(max_t) else None
            tmin = min_t[i] if i < len(min_t) else None
            if tmax is not None and tmin is not None:
                out[day_label] = f"{desc}, {tmin:.0f}–{tmax:.0f}°C"
            elif tmax is not None:
                out[day_label] = f"{desc}, {tmax:.0f}°C"
            else:
                out[day_label] = desc
        return out
    except Exception as e:
        logger.warning("Weather forecast fetch failed: %s", e)
        return {"current": "unavailable", "today": "unavailable", "tomorrow": "unavailable"}


def parse_location_from_message(text: str) -> str | None:
    """If the user message looks like they're setting their location, return the place string; else None."""
    t = (text or "").strip()
    if not t or len(t) > 200:
        return None
    lower = t.lower()
    prefixes = (
        "set location to ",
        "set my location to ",
        "my location is ",
        "i'm in ",
        "i am in ",
        "location: ",
        "i live in ",
        "i'm from ",
        "i am from ",
    )
    for p in prefixes:
        if lower.startswith(p):
            return t[len(p) :].strip()
    if lower.startswith("location is "):
        return t[12:].strip()
    return None
