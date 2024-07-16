from dataclasses import dataclass
from datetime import datetime
from math import radians, degrees, sin, cos, asin, atan2

from skyfield.api import wgs84

from src.constants import EARTH_TIMESCALE, NUM_MINUTES_PER_HOUR, EARTH_RADIOUS

@dataclass
class AreaBoundingBox:
    lat_lower_left: float
    long_lower_left: float
    lat_upper_right: float
    long_upper_right: float


def predict_position(lat: float, lon: float, speed: float, direction: float, minutes: float):
    # Convert speed from m/s to km/h and calculate distance in km
    speed_kmh = speed * 3.6
    distance = (speed_kmh / NUM_MINUTES_PER_HOUR) * minutes
    
    # Calculate new latitude and longitude based on distance and bearing
    bearing = radians(direction)
    
    new_lat = degrees(
        asin(
            sin(radians(lat)) * cos(distance / EARTH_RADIOUS) 
            + cos(radians(lat)) * sin(distance / EARTH_RADIOUS) * cos(bearing)
        )
    )
    new_lon = degrees(
        radians(lon) 
        + atan2(
            sin(bearing) * sin(distance / EARTH_RADIOUS) * cos(radians(lat)), 
            cos(distance / EARTH_RADIOUS) - sin(radians(lat)) * sin(radians(new_lat))
        )
    )

    return new_lat, new_lon


def geographic_to_altaz(
    lat: float, lon: float, elevation, earth_ref, your_location, future_time: datetime
):
    time_ = EARTH_TIMESCALE.from_datetime(future_time)
    plane_location = earth_ref + wgs84.latlon(lat, lon, elevation_m=elevation)
    plane_alt, plane_az, _ = (plane_location - your_location).at(time_).altaz()

    return plane_alt.degrees, plane_az.degrees



def get_my_pos(lat, lon, elevation, base_ref):
    return base_ref + wgs84.latlon(lat, lon, elevation_m=elevation)