import os
from datetime import datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo

import numpy as np
from skyfield.api import Topos
from tzlocal import get_localzone_name

from src import logger
from src.astro import CelestialObject
from src.constants import (
    API_URL,
    ASTRO_EPHEMERIS,
    CHANGE_ELEVATION,
    INTERVAL_IN_SECS,
    NUM_SECONDS_PER_MIN,
    TEST_DATA_PATH,
    TOP_MINUTE,
    Altitude,
    PossibilityLevel,
)
from src.flight_data import get_flight_data, load_existing_flight_data, parse_fligh_data
from src.position import (
    AreaBoundingBox,
    geographic_to_altaz,
    get_my_pos,
    predict_position,
)

EARTH = ASTRO_EPHEMERIS["earth"]

area_bbox = AreaBoundingBox(
    lat_lower_left=os.getenv("LAT_LOWER_LEFT"),
    long_lower_left=os.getenv("LONG_LOWER_LEFT"),
    lat_upper_right=os.getenv("LAT_UPPER_RIGHT"),
    long_upper_right=os.getenv("LONG_UPPER_RIGHT"),
)


def get_thresholds(altitude: float) -> Tuple[float, float]:
    """Receives target altitude and return the suggested threshold for both coordinates:
    altitude and azimuthal.
    """
    if Altitude.LOW(altitude):
        return (5.0, 10.0)
    elif Altitude.MEDIUM(altitude):
        return (10.0, 20.0)
    elif Altitude.MEDIUM_HIGH(altitude):
        return (10.0, 15.0)
    elif Altitude.HIGH(altitude):
        return (8.0, 180.0)

    logger.warning(f"{altitude=}")
    raise Exception(f"Given altitude is not valid!")


def get_possibility_level(
    altitude: float, alt_diff: float, az_diff: float, eta: float = None
) -> str:
    possibility_level = PossibilityLevel.IMPOSSIBLE

    if alt_diff <= 10 and az_diff <= 10 or (Altitude.HIGH(altitude) and alt_diff <= 5):
        possibility_level = PossibilityLevel.LOW

    if Altitude.LOW(altitude) and (alt_diff <= 1 and az_diff <= 2):
        possibility_level = PossibilityLevel.MEDIUM
    elif Altitude.MEDIUM(altitude) and (alt_diff <= 2 and az_diff <= 2):
        possibility_level = PossibilityLevel.MEDIUM
    elif Altitude.MEDIUM_HIGH(altitude) and (alt_diff <= 3 and az_diff <= 3):
        possibility_level = PossibilityLevel.MEDIUM
    elif Altitude.HIGH(altitude) and (alt_diff <= 5 and az_diff <= 10):
        possibility_level = PossibilityLevel.MEDIUM

    if eta is not None and (alt_diff <= 1 and az_diff <= 1):
        possibility_level = PossibilityLevel.HIGH

    return possibility_level.value


def check_transit(
    flight: dict,
    window_time: list,
    ref_datetime: datetime,
    my_position: Topos,
    target: CelestialObject,
    earth_ref,
) -> dict:
    """Given the data of a flight, compute a possible transit with the target.

    Parameters
    ----------
    flight : dict
        Dictionary containing the fligh data: latitude, longitude, speed, direction, elevation,
        name (which is the id of the flight), origin, destination, and coded elevation_change.
    window_time : array_like
        Data points of time in minutes to compute ahead from reference datetime.
    ref_datetime: datetime
        Reference datetime, deltas from window_time will be add to this reference to compute the future position
        of plane and target.
    my_position: Topos
        Object from skifield library which was instanced with current position of the observer (
        latitude, longitude and elevation).
    target: CelestialObject
        It could be the Moon or Sun, or whatever celestial object to compute a possible transit.
    earth_ref: Any
        Earth data gotten from the de421.bsp database by NASA's JPL.

    Returns
    -------
    ans : dict
        Dictionary with the results data, completely filled when it's a possible transit. The data includes:
        id, origin, destination, time, target_alt, plane_alt, target_az, plane_az, alt_diff, az_diff,
        is_possible_transit, and change_elev.
    """
    min_diff_combined = float("inf")
    response = None
    no_decreasing_count = 0
    update_response = False

    for idx, minute in enumerate(window_time):
        # Get future position of plane
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
            future_lat,
            future_lon,
            flight["elevation"],
            earth_ref,
            my_position,
            future_time,
        )

        if idx > 0 and idx % 60 == 0:
            # Update target position every 60 data points (1 min)
            target.update_position(future_time)

        alt_diff = abs(future_alt - target.altitude.degrees)
        az_diff = abs(future_az - target.azimuthal.degrees)
        diff_combined = alt_diff + az_diff

        if no_decreasing_count >= 180:
            logger.info(f"diff is increasing, stop checking, min={round(minute, 2)}")
            break

        if diff_combined < min_diff_combined:
            no_decreasing_count = 0
            min_diff_combined = diff_combined
            update_response = True
        else:
            no_decreasing_count += 1

        alt_threshold, az_threshold = get_thresholds(target.altitude.degrees)

        if future_alt > 0 and alt_diff < alt_threshold and az_diff < az_threshold:

            if update_response:
                response = {
                    "id": flight["name"],
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "alt_diff": round(float(alt_diff), 3),
                    "az_diff": round(float(az_diff), 3),
                    "time": round(float(minute), 3),
                    "target_alt": round(float(target.altitude.degrees), 2),
                    "plane_alt": round(float(future_alt), 2),
                    "target_az": round(float(target.azimuthal.degrees), 2),
                    "plane_az": round(float(future_az), 2),
                    "is_possible_transit": 1,
                    "possibility_level": get_possibility_level(
                        target.altitude.degrees, alt_diff, az_diff, minute
                    ),
                    "elevation_change": CHANGE_ELEVATION.get(
                        flight["elevation_change"], None
                    ),
                    "direction": flight["direction"],
                }
        update_response = False

    if response:
        return response

    return {
        "id": flight["name"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "alt_diff": None,
        "az_diff": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": PossibilityLevel.IMPOSSIBLE.value,
        "elevation_change": CHANGE_ELEVATION.get(flight["elevation_change"], None),
        "direction": flight["direction"],
    }


def get_transits(
    latitude: float,
    longitude: float,
    elevation: float,
    target_name: str = "moon",
    test_mode: bool = False,
) -> List[dict]:
    API_KEY = os.getenv("AEROAPI_API_KEY")

    logger.info(f"{latitude=}, {longitude=}, {elevation=}")

    MY_POSITION = get_my_pos(
        lat=latitude,
        lon=longitude,
        elevation=elevation,
        base_ref=EARTH,
    )

    window_time = np.linspace(
        0, TOP_MINUTE, TOP_MINUTE * (NUM_SECONDS_PER_MIN // INTERVAL_IN_SECS)
    )
    logger.info(f"number of times to check for each flight: {len(window_time)}")
    # Get the local timezone using tzlocal
    local_timezone = get_localzone_name()
    naive_datetime_now = datetime.now()
    # Make the datetime object timezone-aware
    ref_datetime = naive_datetime_now.replace(tzinfo=ZoneInfo(local_timezone))

    celestial_obj = CelestialObject(name=target_name, observer_position=MY_POSITION)
    celestial_obj.update_position(ref_datetime=ref_datetime)
    current_target_coordinates = celestial_obj.get_coordinates()

    logger.info(celestial_obj.__str__())

    if test_mode:
        raw_flight_data = load_existing_flight_data(TEST_DATA_PATH)
        logger.info("Loading existing flight data since is using TEST mode")
    else:
        raw_flight_data = get_flight_data(area_bbox, API_URL, API_KEY)

    flight_data = list()

    for flight in raw_flight_data["flights"]:
        flight_data.append(parse_fligh_data(flight))

    logger.info(f"there are {len(flight_data)} flights near")

    data = list()

    for flight in flight_data:
        celestial_obj.update_position(ref_datetime=ref_datetime)

        data.append(
            check_transit(
                flight,
                window_time,
                ref_datetime,
                MY_POSITION,
                celestial_obj,
                EARTH,
            )
        )

        logger.info(data[-1])

    return {"flights": data, "targetCoordinates": current_target_coordinates}
