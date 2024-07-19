import os
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

import numpy as np

from tzlocal import get_localzone_name
from skyfield.api import Topos

from src.astro import CelestialObject
from src.constants import (
    ALTITUDE_THRESHOLD,
    API_URL,
    ASTRO_EPHEMERIS,
    AZIMUTHAL_THRESHOLD,
    CHANGE_ELEVATION,
    INTERVAL_IN_SECS,
    NUM_SECONDS_PER_MIN,
    TEST_DATA_PATH,
    TOP_MINUTE,
)
from src.flight_data import get_flight_data, load_existing_flight_data, parse_fligh_data
from src.position import (
    AreaBoundingBox, geographic_to_altaz, get_my_pos, predict_position
)


EARTH = ASTRO_EPHEMERIS["earth"]

area_bbox = AreaBoundingBox(
    lat_lower_left=os.getenv("LAT_LOWER_LEFT"),
    long_lower_left=os.getenv("LONG_LOWER_LEFT"),
    lat_upper_right=os.getenv("LAT_UPPER_RIGHT"),
    long_upper_right=os.getenv("LONG_UPPER_RIGHT"),
)


def check_intersection(
    flight: dict,
    window_time: list,
    ref_datetime: datetime,
    my_position: Topos,
    target: CelestialObject,
    earth_ref,
    alt_threshold: float = 10,
    az_threshold: float = 10
):
    min_diff_combined = alt_threshold + az_threshold + 1
    last_diff_combined = 10000
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
        diff_combined = alt_diff + az_diff

        if idx % 240 == 0:
            # check if the diff is increasing
            if last_diff_combined < diff_combined:
                print(
                    f"diff is increasing, stop checking intersection, min={round(minute, 2)}"
                )
                break
            else:
                last_diff_combined = diff_combined

        if future_alt > 0 and alt_diff < alt_threshold and az_diff < az_threshold:

            if diff_combined < min_diff_combined:
                ans = {
                    "id": flight['name'],
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "time": round(float(minute), 3),
                    "target_alt": round(float(target.altitude.degrees), 2),
                    "plane_alt": round(float(future_alt), 2),
                    "target_az": round(float(target.azimuthal.degrees), 2),
                    "plane_az": round(float(future_az), 2), 
                    "alt_diff": round(float(alt_diff), 3),
                    "az_diff": round(float(az_diff), 3),
                    "is_possible_hit": 1,
                    "change_elev": CHANGE_ELEVATION.get(flight["elevation_change"], None),
                }

                min_diff_combined = diff_combined

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
        "change_elev": CHANGE_ELEVATION.get(flight["elevation_change"], None),
    }



def check_intersections(
    latitude: float,
    longitude: float,
    elevation: float,
    target_name: str = "moon",
    test_mode: bool = False
) -> List[dict]:
    API_KEY = os.getenv("AEROAPI_API_KEY")

    print(f"{latitude=}, {longitude=}, {elevation=}")

    MY_POSITION = get_my_pos(
        lat=latitude,
        lon=longitude,
        elevation=elevation,
        base_ref=EARTH,
    )

    window_time = np.linspace(
        0, TOP_MINUTE, TOP_MINUTE * (NUM_SECONDS_PER_MIN // INTERVAL_IN_SECS)
    )
    print("number of times to check for each flight:", len(window_time))
    # Get the local timezone using tzlocal
    local_timezone = get_localzone_name()
    naive_datetime_now = datetime.now()
    # Make the datetime object timezone-aware
    ref_datetime = naive_datetime_now.replace(tzinfo=ZoneInfo(local_timezone))

    celestial_obj = CelestialObject(
        name=target_name, observer_position=MY_POSITION
    )

    print(celestial_obj.__str__())

    if test_mode:
        raw_flight_data = load_existing_flight_data(TEST_DATA_PATH)
    else:
        raw_flight_data = get_flight_data(area_bbox, API_URL, API_KEY)

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
                MY_POSITION,
                celestial_obj,
                EARTH,
                alt_threshold=ALTITUDE_THRESHOLD,
                az_threshold=AZIMUTHAL_THRESHOLD,
            )
        )

        print(response[-1])

    return response