from enum import Enum

from skyfield.api import load

# General
NUM_MINUTES_PER_HOUR = 60
NUM_SECONDS_PER_MIN = 60
EARTH_RADIOUS = 6371

# Notifications
TARGET_TO_EMOJI = {"moon": "🌙", "sun": "☀️"}
MAX_NUM_ITEMS_TO_NOTIFY = 5

# Flight data
API_URL = "https://aeroapi.flightaware.com/aeroapi/flights/search"
CHANGE_ELEVATION = {
    "C": "climbing",
    "D": "descending",
    "-": "no",
}

# Test data
TEST_DATA_PATH = "data/raw_flight_data_example.json"
POSSIBLE_TRANSITS_DIR = "data/possible-transits/log.txt"

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
class Altitude(Enum):
    LOW = lambda x: x <= 15  # less or equal
    MEDIUM = lambda x: x <= 30  # less or equal
    MEDIUM_HIGH = lambda x: x <= 60  # less or equal
    HIGH = lambda x: x > 60  # greater than
