from dataclasses import dataclass
from datetime import datetime
from math import asin, atan2, cos, degrees, radians, sin, sqrt

from skyfield.api import wgs84

from src.constants import (
    EARTH_RADIOUS,
    EARTH_TIMESCALE,
    KM_TO_NAUTICAL_MILES,
    NUM_MINUTES_PER_HOUR,
)


@dataclass
class AreaBoundingBox:
    lat_lower_left: float
    long_lower_left: float
    lat_upper_right: float
    long_upper_right: float


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth using the Haversine formula.

    Parameters
    ----------
    lat1 : float
        Latitude of the first point in decimal degrees.
    lon1 : float
        Longitude of the first point in decimal degrees.
    lat2 : float
        Latitude of the second point in decimal degrees.
    lon2 : float
        Longitude of the second point in decimal degrees.

    Returns
    -------
    float
        Distance between the two points in nautical miles.

    Notes
    -----
    The Haversine formula calculates the shortest distance over the earth's surface,
    giving an "as-the-crow-flies" distance between the points (ignoring any hills, etc.).

    Formula:
        a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
        c = 2 * atan2(√a, √(1-a))
        distance = R * c

    where R is the Earth's radius and Δlat, Δlon are the differences in latitude and longitude.
    """
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance_km = EARTH_RADIOUS * c
    distance_nm = distance_km * KM_TO_NAUTICAL_MILES

    return distance_nm


def predict_position(
    lat: float, lon: float, speed: float, direction: float, minutes: float
) -> tuple:
    """Compute the future latitude and longitude of a plane given its current coordinates,
    speed, direction, and the time ahead to know the position.

    Parameters
    ----------
    lat : float
        Current latitude of the plane in decimal degrees.
    lon : float
        Current longitude of the plane in decimal degrees.
    speed : float
        Ground speed of the plane in kilometers per hour (km/h).
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

    1. Calculate the distance traveled in kilometers.
       Distance (km) = (Speed (km/h) / 60) * Minutes

    2. Convert the direction (bearing) from degrees to radians.
       Bearing (radians) = Direction (degrees) * π / 180

    3. Compute the new latitude using the formula:
       new_lat = asin(sin(lat) * cos(d/R) + cos(lat) * sin(d/R) * cos(bearing))

    4. Compute the new longitude using the formula:
       new_lon = lon + atan2(sin(bearing) * sin(d/R) * cos(lat), cos(d/R) - sin(lat) * sin(new_lat))

    where:
    - lat and lon are the initial latitude and longitude in radians.
    - d is the distance traveled.
    - R is the Earth's radius (mean radius = 6,371 km).
    """
    distance = (speed / NUM_MINUTES_PER_HOUR) * minutes

    # Convert direction to radians
    bearing = radians(direction)

    lat_rads = radians(lat)
    ratio_d_r = distance / EARTH_RADIOUS

    # Calculate new latitude
    new_lat = degrees(
        asin(
            sin(lat_rads) * cos(ratio_d_r)
            + cos(lat_rads) * sin(ratio_d_r) * cos(bearing)
        )
    )
    # Calculate new longitude
    new_lon = degrees(
        radians(lon)
        + atan2(
            sin(bearing) * sin(ratio_d_r) * cos(lat_rads),
            cos(ratio_d_r) - sin(lat_rads) * sin(radians(new_lat)),
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
