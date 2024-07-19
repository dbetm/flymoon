from skyfield.api import load

# General
NUM_MINUTES_PER_HOUR = 60
NUM_SECONDS_PER_MIN = 60
EARTH_RADIOUS = 6371

# Flight data
API_URL = "https://aeroapi.flightaware.com/aeroapi/flights/search"
CHANGE_ELEVATION = {
    "C": "climbing",
    "D": "descending",
    "-": "no change",
}

# Test data
TEST_DATA_PATH = "data/raw_flight_data_example.json"

"""
The load function is used to load astronomical data, such as planetary ephemerides, 
which are needed to calculate positions of celestial bodies.

This code loads the DE421 planetary ephemeris data from the Jet Propulsion Laboratory.
"""
ASTRO_EPHEMERIS = load("de421.bsp")
EARTH_TIMESCALE = load.timescale()


# Window time
# 60 * top_min = 900 datapoints for each flight
TOP_MINUTE = 15
INTERVAL_IN_SECS = 1

# Intersection
ALTITUDE_THRESHOLD = 15
AZIMUTHAL_THRESHOLD = 20