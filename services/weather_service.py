"""
weather_service.py — OpenWeatherMap integration.

Fetches current weather for any city.
No confirmation needed — read-only action, just like news.

Requires in .env:
    OPENWEATHER_API_KEY=your_key_here
"""

import logging
import requests
from typing import Dict, Optional

import config

log = logging.getLogger(__name__)

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def fetch_weather(city: str) -> Dict:
    """
    Fetch current weather for a city.

    Returns a dict with keys:
        status  : "success" or "error"
        message : human-readable result or error description
        data    : raw weather fields (only on success)
    """
    api_key = getattr(config, "OPENWEATHER_API_KEY", "")
    if not api_key:
        return {
            "status": "error",
            "message": (
                "OpenWeatherMap API key is not configured. "
                "Please add OPENWEATHER_API_KEY to your .env file."
            ),
        }

    city = city.strip()
    if not city:
        return {"status": "error", "message": "No city name provided."}

    try:
        response = requests.get(
            OPENWEATHER_URL,
            params={
                "q":     city,
                "appid": api_key,
                "units": "metric",   # Celsius
            },
            timeout=10,
        )

        # City not found
        if response.status_code == 404:
            return {
                "status": "error",
                "message": (
                    f"City '{city}' not found. "
                    "Please check the spelling or try a nearby major city."
                ),
            }

        # Invalid API key
        if response.status_code == 401:
            return {
                "status": "error",
                "message": (
                    "Invalid OpenWeatherMap API key. "
                    "Please check your OPENWEATHER_API_KEY in .env."
                ),
            }

        response.raise_for_status()
        data = response.json()

        # ── Extract fields ───────────────────────────────────
        temp        = round(data["main"]["temp"])
        feels_like  = round(data["main"]["feels_like"])
        humidity    = data["main"]["humidity"]
        description = data["weather"][0]["description"].capitalize()
        wind_speed  = round(data["wind"]["speed"] * 3.6)   # m/s → km/h
        city_name   = data["name"]
        country     = data["sys"]["country"]
        visibility  = round(data.get("visibility", 0) / 1000, 1)  # m → km

        return {
            "status": "success",
            "message": _format_weather(
                city_name, country, temp, feels_like,
                description, humidity, wind_speed, visibility
            ),
            "data": {
                "city":        city_name,
                "country":     country,
                "temp_c":      temp,
                "feels_like":  feels_like,
                "description": description,
                "humidity":    humidity,
                "wind_kmh":    wind_speed,
                "visibility":  visibility,
            },
        }

    except requests.Timeout:
        return {"status": "error", "message": "Weather request timed out. Please try again."}
    except requests.RequestException as exc:
        log.error("Weather API request failed: %s", exc)
        return {"status": "error", "message": f"Weather fetch failed: {exc}"}
    except (KeyError, ValueError) as exc:
        log.error("Weather response parsing error: %s", exc)
        return {"status": "error", "message": "Unexpected response from weather service."}


def _format_weather(
    city: str, country: str, temp: int, feels_like: int,
    description: str, humidity: int, wind_kmh: int, visibility: float
) -> str:
    """Format weather data into a clean readable string."""
    return (
        f"Weather in {city}, {country}\n"
        f"{'-' * 35}\n"
        f"Condition   : {description}\n"
        f"Temperature : {temp}°C  (feels like {feels_like}°C)\n"
        f"Humidity    : {humidity}%\n"
        f"Wind Speed  : {wind_kmh} km/h\n"
        f"Visibility  : {visibility} km\n"
        f"{'-' * 35}"
    )