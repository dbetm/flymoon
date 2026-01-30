import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests

from src import logger
from src.constants import WEATHER_API_URL, WEATHER_CACHE_DURATION_MINUTES, WEATHER_ICONS


class WeatherCache:
    """Simple cache for weather data to avoid excessive API calls."""

    def __init__(self):
        self._cache = {}
        self._cache_time = {}

    def get(self, key: str) -> Optional[dict]:
        if key not in self._cache:
            return None

        cache_age = datetime.now() - self._cache_time[key]
        if cache_age > timedelta(minutes=WEATHER_CACHE_DURATION_MINUTES):
            logger.info(f"Weather cache expired for {key}")
            del self._cache[key]
            del self._cache_time[key]
            return None

        logger.info(f"Using cached weather data for {key}")
        return self._cache[key]

    def set(self, key: str, value: dict):
        self._cache[key] = value
        self._cache_time[key] = datetime.now()


# Global cache instance
_weather_cache = WeatherCache()


def get_weather_condition(
    latitude: float, longitude: float, api_key: str
) -> Tuple[bool, dict]:
    """Fetch weather conditions from OpenWeatherMap API.

    Parameters
    ----------
    latitude : float
        Observer's latitude
    longitude : float
        Observer's longitude
    api_key : str
        OpenWeatherMap API key

    Returns
    -------
    is_clear : bool
        True if sky is clear enough for tracking
    weather_info : dict
        Dictionary containing:
        - cloud_cover: percentage (0-100)
        - condition: weather condition string
        - icon: emoji icon for condition
        - description: human-readable description
        - api_success: whether API call succeeded
    """
    cache_key = f"{latitude:.3f},{longitude:.3f}"
    cached_data = _weather_cache.get(cache_key)

    if cached_data:
        return cached_data["is_clear"], cached_data["info"]

    if not api_key:
        logger.warning("No OpenWeatherMap API key provided")
        return True, {
            "cloud_cover": None,
            "condition": "unknown",
            "icon": WEATHER_ICONS["unknown"],
            "description": "Weather API not configured",
            "api_success": False,
        }

    try:
        params = {"lat": latitude, "lon": longitude, "appid": api_key, "units": "metric"}

        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        cloud_cover = data.get("clouds", {}).get("all", 0)
        weather_main = data.get("weather", [{}])[0].get("main", "Unknown").lower()
        weather_desc = data.get("weather", [{}])[0].get("description", "Unknown")

        # Determine icon based on conditions
        if weather_main in ["thunderstorm", "drizzle", "rain"]:
            if "thunder" in weather_main:
                icon = WEATHER_ICONS["thunderstorm"]
            else:
                icon = WEATHER_ICONS["rain"]
            condition = weather_main
        elif weather_main == "snow":
            icon = WEATHER_ICONS["snow"]
            condition = "snow"
        elif weather_main == "clouds":
            if cloud_cover < 30:
                icon = WEATHER_ICONS["partly_cloudy"]
                condition = "partly_cloudy"
            else:
                icon = WEATHER_ICONS["clouds"]
                condition = "clouds"
        elif weather_main == "clear":
            icon = WEATHER_ICONS["clear"]
            condition = "clear"
        else:
            icon = WEATHER_ICONS["unknown"]
            condition = "unknown"

        cloud_threshold = int(os.getenv("CLOUD_COVER_THRESHOLD", 30))
        is_clear = cloud_cover < cloud_threshold

        weather_info = {
            "cloud_cover": cloud_cover,
            "condition": condition,
            "icon": icon,
            "description": weather_desc,
            "api_success": True,
        }

        # Cache the result
        _weather_cache.set(cache_key, {"is_clear": is_clear, "info": weather_info})

        logger.info(
            f"Weather: {weather_desc}, cloud cover: {cloud_cover}%, clear: {is_clear}"
        )
        return is_clear, weather_info

    except requests.RequestException as e:
        logger.error(f"Weather API request failed: {str(e)}")
        return True, {
            "cloud_cover": None,
            "condition": "unknown",
            "icon": WEATHER_ICONS["unknown"],
            "description": f"Weather API error: {str(e)}",
            "api_success": False,
        }
    except Exception as e:
        logger.error(f"Unexpected error fetching weather: {str(e)}")
        return True, {
            "cloud_cover": None,
            "condition": "unknown",
            "icon": WEATHER_ICONS["unknown"],
            "description": f"Weather check failed: {str(e)}",
            "api_success": False,
        }
