from math import radians, degrees, sin, cos, asin, atan2

from skyfield.api import wgs84, load

from src.astro import CelestialObject
from src.constants import NUM_MINUTES_PER_HOUR, EARTH_RADIOUS


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


def geographic_to_altaz(lat: float, lon: float, elevation, earth_ref, your_location, timescale):
    t = timescale.now()

    plane_location = earth_ref + wgs84.latlon(lat, lon, elevation_m=elevation)
    #plane_location = earth_ref + wgs84.latlon(lat, lon)
    plane_alt, plane_az, _ = (plane_location - your_location).at(t).altaz()

    return plane_alt.degrees, plane_az.degrees



def get_my_pos(lat, lon, elevation, base_ref):
    return base_ref + wgs84.latlon(lat, lon, elevation_m=elevation)


def load_astro_position_relative_to_me(my_pos, astro_name: str, ts):
    e = load("de421.bsp")
    t = ts.now()

    obj = e[astro_name]
    astrometric = my_pos.at(t).observe(obj)
    alt, az, distance = astrometric.apparent().altaz() 

    celestial_obj = CelestialObject(
        name=astro_name,
        alt=alt,
        az=az,
    )

    print(str(celestial_obj))

    return celestial_obj

