import os
from enum import Enum

from skyfield.api import load

# General
NUM_MINUTES_PER_HOUR = 60
NUM_SECONDS_PER_MIN = 60
EARTH_RADIOUS = 6371
KM_TO_NAUTICAL_MILES = 0.539957

# Notifications
TARGET_TO_EMOJI = {"moon": "🌙", "sun": "☀️", "both": "🌙☀️"}
MAX_NUM_ITEMS_TO_NOTIFY = 5
ALT_DIFF_THRESHOLD_TO_NOTIFY = 5.0
AZ_DIFF_THRESHOLD_TO_NOTIFY = 10.0

# Weather
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_CACHE_DURATION_MINUTES = 10  # 6 requests per hour
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_ICONS = {
    "clear": "☀️",
    "clouds": "☁️",
    "partly_cloudy": "⛅",
    "rain": "🌧️",
    "snow": "🌨️",
    "thunderstorm": "⛈️",
    "unknown": "❓",
}

# Flight data
# FlightAware AeroAPI
AEROAPI_BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
FLIGHTS_SEARCH_URL = f"{AEROAPI_BASE_URL}/flights/search"

CHANGE_ELEVATION = {
    "C": "climbing",
    "D": "descending",
    "-": "no",
}

# Test data
TEST_DATA_PATH = "data/raw_flight_data_example.json"
POSSIBLE_TRANSITS_LOGFILENAME = "data/possible-transits/log_{date_}.csv"

# Astro data
ASTRO_EPHEMERIS = load("de421.bsp")
"""
The load function is used to load astronomical data, such as planetary ephemerides, 
which are needed to calculate positions of celestial bodies.

This code loads the DE421 planetary ephemeris data from the Jet Propulsion Laboratory.
"""
EARTH_TIMESCALE = load.timescale()


# Window time
# 60 * top_min = 900 datapoints for each flight
TOP_MINUTE = 15
INTERVAL_IN_SECS = 1


# Transit
class PossibilityLevel(Enum):
    UNLIKELY = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


POSIBILITY_LEVEL_TO_COLOR = {
    PossibilityLevel.HIGH.value: "🟢",
    PossibilityLevel.MEDIUM.value: "🟠",
    PossibilityLevel.LOW.value: "🟡",
}
