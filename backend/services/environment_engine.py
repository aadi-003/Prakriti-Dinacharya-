"""Environment engine: season resolution, optional live weather (Open-Meteo, keyless), dosha influence rules."""
import json
import urllib.parse
import urllib.request
from datetime import datetime

from .rule_engine import apply_rules, load_rules

SEASONS = ("Winter", "Summer", "Monsoon", "Autumn", "Spring")
ALLOWED_WEATHER = ("clear", "partly cloudy", "cloudy", "fog", "drizzle", "rain", "thunderstorm", "snow")

# WMO weather-code -> internal condition (subset; anything unknown maps to 'cloudy')
WMO = {0: "clear", 1: "clear", 2: "partly cloudy", 3: "cloudy", 45: "fog", 48: "fog",
       51: "drizzle", 53: "drizzle", 55: "drizzle",
       61: "rain", 63: "rain", 65: "rain", 66: "rain", 67: "rain", 80: "rain", 81: "rain", 82: "rain",
       71: "snow", 73: "snow", 75: "snow", 77: "snow", 85: "snow", 86: "snow",
       95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm"}

# Indian-context month -> season (simplification of Ritucharya; documented in README; user can override)
MONTH_SEASON = {12: "Winter", 1: "Winter", 2: "Winter",
                3: "Summer", 4: "Summer", 5: "Summer",
                6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
                10: "Autumn", 11: "Autumn"}


def wmo_to_condition(code) -> str:
    try:
        return WMO.get(int(code), "cloudy")
    except (TypeError, ValueError):
        return "cloudy"


def month_to_season(month: int) -> str:
    return MONTH_SEASON[int(month)]


def fetch_weather(lat: float, lon: float, timeout: int = 6):
    """Live weather via Open-Meteo (no API key). Returns None on ANY failure — never raises."""
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        cur = data["current"]
        return {"temperature": float(cur["temperature_2m"]),
                "humidity": float(cur["relative_humidity_2m"]),
                "weather": wmo_to_condition(cur["weather_code"]),
                "provider": "open-meteo"}
    except Exception:
        return None


def geocode_city(city: str, timeout: int = 6):
    """City name -> approximate coordinates via Open-Meteo geocoding. Returns None on failure."""
    url = ("https://geocoding-api.open-meteo.com/v1/search"
           f"?name={urllib.parse.quote(city)}&count=1&language=en&format=json")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        if not results:
            return None
        r = results[0]
        return {"latitude": float(r["latitude"]), "longitude": float(r["longitude"]),
                "label": f"{r.get('name', '?')}, {r.get('country', '?')}"}
    except Exception:
        return None


def resolve_environment(p) -> dict:
    """
    p: validated EnvironmentRequest. Graceful degradation:
       - live weather fails -> status 'unavailable', month-based season still provided, no crash.
       - precise coordinates are never stored or echoed back; only a city-level label.
    """
    rules = load_rules("seasonal_rules.json")
    notes = []
    month = p.month if p.month else datetime.now().month
    season = p.season if p.season else month_to_season(month)

    status, label, provider = "ok", None, None
    temperature, humidity, weather = p.temperature, p.humidity, p.weather

    if p.mode in ("auto", "city"):
        loc = None
        if p.mode == "city":
            loc = geocode_city(p.city)
            if loc:
                label = loc["label"]
        else:
            loc = {"latitude": p.latitude, "longitude": p.longitude}
            label = "Approximate coordinates (city-level precision)"
        fetched = fetch_weather(loc["latitude"], loc["longitude"]) if loc else None
        if fetched:
            temperature, humidity = fetched["temperature"], fetched["humidity"]
            weather, provider = fetched["weather"], fetched["provider"]
        else:
            status = "unavailable"
            notes.append("Live weather could not be fetched (network or API unavailable). "
                         "Please enter temperature and humidity manually — the plan still works without them.")

    ctx = {"temperature": temperature, "humidity": humidity, "weather": weather, "season": season}
    influence, fired = apply_rules(rules["environmental_influences"], ctx, cap=6)

    explanations = [r["explanation"] for r in fired]
    if not fired:
        explanations.append("Current conditions fall in a moderate band; "
                            "no strong dosha-shifting environmental influence was detected.")

    return {"mode": p.mode, "status": status, "season": season, "month": month,
            "temperature": temperature, "humidity": humidity, "weather": weather,
            "weather_provider": provider, "location_label": label,
            "influence": influence,
            "influences_fired": [r["id"] for r in fired],
            "explanations": explanations, "notes": notes}