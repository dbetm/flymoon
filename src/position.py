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


def predict_position(lat: float, lon: float, speed: float, direction: float, minutes: float) -> tuple:
    """Compute the future latitude and longitude of a plane given its current coordinates,
    speed, direction, and the time ahead to know the position.

    Parameters
    ----------
    lat : float
        Current latitude of the plane in decimal degrees.
    lon : float
        Current longitude of the plane in decimal degrees.
    speed : float
        Speed of the plane in meters per second (m/s).
    direction : float
        Direction of the plane in degrees from North (0° to 360°).
    minutes : float
        Time ahead in minutes to predict the future position.

    Returns
    -------
    new_lat : float
        Predicted future latitude of the plane in decimal degrees.
    new_lon : float
        Predicted future longitude of the plane in decimal degrees.

    Notes
    -----
    This function uses the Haversine formula to calculate the new position of the plane.
    The following mathematical steps are involved:

    1. Convert speed from meters per second (m/s) to kilometers per hour (km/h).
       Speed (km/h) = Speed (m/s) * 3.6

    2. Calculate the distance traveled in kilometers.
       Distance (km) = (Speed (km/h) / 60) * Minutes

    3. Convert the direction (bearing) from degrees to radians.
       Bearing (radians) = Direction (degrees) * π / 180

    4. Compute the new latitude using the formula:
       new_lat = asin(sin(lat) * cos(d/R) + cos(lat) * sin(d/R) * cos(bearing))

    5. Compute the new longitude using the formula:
       new_lon = lon + atan2(sin(bearing) * sin(d/R) * cos(lat), cos(d/R) - sin(lat) * sin(new_lat))

    where:
    - lat and lon are the initial latitude and longitude in radians.
    - d is the distance traveled.
    - R is the Earth's radius (mean radius = 6,371 km).
    """
    # Convert speed from m/s to km/h and calculate distance in km
    speed_kmh = speed * 3.6
    distance = (speed_kmh / NUM_MINUTES_PER_HOUR) * minutes

    # Convert direction to radians
    bearing = radians(direction)

    lat_rads = radians(lat)
    ratio_d_r = distance / EARTH_RADIOUS
    
    # Calculate new latitude
    new_lat = degrees(
        asin(
            sin(lat_rads)*cos(ratio_d_r) + cos(lat_rads)*sin(ratio_d_r)*cos(bearing)
        )
    )
    # Calculate new longitude
    new_lon = degrees(
        radians(lon) 
        + atan2(
            sin(bearing)*sin(ratio_d_r)*cos(lat_rads), 
            cos(ratio_d_r) - sin(lat_rads)*sin(radians(new_lat))
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