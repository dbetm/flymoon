import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from tzlocal import get_localzone_name
from skyfield.api import Topos

from src.astro import CelestialObject
from src.constants import ASTRO_EPHEMERIS
from src.flight_data import get_flight_data
from src.position import (
    geographic_to_altaz, get_my_pos, predict_position
)
from src.utils import parse_fligh_data



def check_intersection(
    flight: dict,
    window_time: list,
    ref_datetime: datetime,
    my_position: Topos,
    target: CelestialObject,
    earth_ref,
    threshold_alt: float = 10,
    threshold_az: float = 10
):
    min_diff_combined = threshold_alt + threshold_az + 1
    ans = None

    for idx, minute in enumerate(window_time):
        # get future position of plane
        future_lat, future_lon = predict_position(
            lat=flight["latitude"],
            lon=flight["longitude"],
            speed=flight["speed"],
            direction=flight["direction"],
            minutes=minute,
        )

        future_time = ref_datetime + timedelta(minutes=int(minute))

        # Convert future position of plane to alt-azimuthal coordinates
        future_alt, future_az = geographic_to_altaz(
            future_lat, future_lon, flight["elevation"], earth_ref, my_position, future_time
        )

        if idx > 0 and idx % 180 == 0:
            # update target position every 180 data points (3 min)
            target.update_position(future_time)

        alt_diff = abs(future_alt - target.altitude.degrees)
        az_diff = abs(future_az - target.azimuthal.degrees)

        if future_alt > 0 and alt_diff < threshold_alt and az_diff < threshold_az:

            if (alt_diff + az_diff) < min_diff_combined:
                ans = {
                    "id": flight['name'],
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "time": round(float(minute), 2),
                    "target_alt": round(float(target.altitude.degrees), 2),
                    "plane_alt": round(float(future_alt), 2),
                    "target_az": round(float(target.azimuthal.degrees), 2),
                    "plane_az": round(float(future_az), 2), 
                    "alt_diff": round(float(alt_diff), 3),
                    "az_diff": round(float(az_diff), 3),
                    "is_possible_hit": 1,
                }

                min_diff_combined = alt_diff + az_diff

    if ans:
        return ans

    return {
        "id": flight['name'],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None, 
        "alt_diff": None,
        "az_diff": None,
        "is_possible_hit": 0,
    }



def check_intersections(target_name: str = "moon"):
    api_key = os.getenv('AEROAPI_API_KEY')
    personal_latitude = float(os.getenv('PERSONAL_LATITUDE'))
    personal_longitude = float(os.getenv('PERSONAL_LONGITUDE'))

    earth = ASTRO_EPHEMERIS["earth"]

    my_pos = get_my_pos(
        lat=personal_latitude,
        lon=personal_longitude,
        elevation=2243,
        base_ref=earth,
    )

    top_min = 15
    second_interval = 1
    # 60 * 15 = 900 datapoints

    window_time = np.linspace(0, top_min, top_min * (60 // second_interval)) # each second
    print("number of times to check for each flight:", len(window_time))
    # Get the local timezone using tzlocal
    local_timezone = get_localzone_name()
    naive_datetime_now = datetime.now()
    # Make the datetime object timezone-aware
    ref_datetime = naive_datetime_now.replace(tzinfo=ZoneInfo(local_timezone))

    celestial_obj = CelestialObject(
        name=target_name, observer_position=my_pos
    )

    print(celestial_obj.__str__())

    raw_flight_data = get_flight_data(
        # lower left
        21.659, #21.8432,
        -105.22, #-104.4433,
        # upper right
        24.803, #23.9974,
        -102.194, #-101.9982,
        "https://aeroapi.flightaware.com/aeroapi/flights/search",
        api_key,
    )

    flight_data = list()

    for flight in raw_flight_data["flights"]:
        flight_data.append(parse_fligh_data(flight))

    print(f"theres is {len(flight_data)} flights near")

    response = list()

    for flight in flight_data:
        celestial_obj.update_position(ref_datetime=ref_datetime)

        response.append(
            check_intersection(
                flight,
                window_time,
                ref_datetime,
                my_pos,
                celestial_obj,
                earth,
                threshold_alt=15,
                threshold_az=20,
            )
        )

        print(response[-1])

    return response