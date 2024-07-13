from skyfield.api import load

NUM_MINUTES_PER_HOUR = 60
EARTH_RADIOUS = 6371


# Test data

TEST_DATA_PATH = "data/raw_flight_data_example.json"

"""
The load function is used to load astronomical data, such as planetary ephemerides, 
which are needed to calculate positions of celestial bodies.

This code loads the DE421 planetary ephemeris data from the Jet Propulsion Laboratory.
"""
ASTRO_EPHEMERIS = load("de421.bsp")

EARTH_TIMESCALE = load.timescale()