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
from src.weather import get_weather_condition

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
    test_mode: bool = False,
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
    test_mode: bool
        If True, evaluates current position (t=0) for static test aircraft.

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

    # In test mode, check current position first (t=0, static aircraft)
    if test_mode:
        current_alt, current_az = geographic_to_altaz(
            flight["latitude"],
            flight["longitude"],
            flight["elevation"],
            earth_ref,
            my_position,
            ref_datetime,
        )

        alt_diff = abs(current_alt - target.altitude.degrees)
        az_diff = abs(current_az - target.azimuthal.degrees)
        diff_combined = alt_diff + az_diff

        min_diff_combined = diff_combined

        alt_threshold, az_threshold = get_thresholds(target.altitude.degrees)

        if current_alt > 0 and alt_diff < alt_threshold and az_diff < az_threshold:
            response = {
                "id": flight["name"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "alt_diff": round(float(alt_diff), 3),
                "az_diff": round(float(az_diff), 3),
                "time": 0.0,  # Current position
                "target_alt": round(float(target.altitude.degrees), 2),
                "plane_alt": round(float(current_alt), 2),
                "target_az": round(float(target.azimuthal.degrees), 2),
                "plane_az": round(float(current_az), 2),
                "is_possible_transit": 1,
                "possibility_level": get_possibility_level(
                    target.altitude.degrees, alt_diff, az_diff, 0.0
                ),
                "elevation_change": CHANGE_ELEVATION.get(
                    flight["elevation_change"], None
                ),
                "direction": flight["direction"],
                "target": target.name,
                "latitude": flight["latitude"],
                "longitude": flight["longitude"],
            }

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
                    "target": target.name,
                    "latitude": flight["latitude"],
                    "longitude": flight["longitude"],
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
        "target": target.name,
        "latitude": flight["latitude"],
        "longitude": flight["longitude"],
    }


def generate_mock_results(obs_lat: float, obs_lon: float, obs_elev: float) -> dict:
    """Generate mock transit results for demonstration purposes.

    Returns hardcoded results showing HIGH, MEDIUM, LOW, and NONE classifications
    for both moon and sun targets.
    """
    # Fixed celestial target positions
    moon_az, moon_alt = 135.0, 40.0
    sun_az, sun_alt = 225.0, 35.0

    # Helper to create aircraft position at specific azimuth and distance
    def position_at(azimuth_deg, distance_deg):
        import math
        az_rad = math.radians(azimuth_deg)
        lat = obs_lat + distance_deg * math.cos(az_rad)
        lon = obs_lon + distance_deg * math.sin(az_rad)
        return round(lat, 6), round(lon, 6)

    flights = []

    # MOON TRANSITS
    # HIGH - nearly perfect alignment
    lat, lon = position_at(moon_az, 0.15)
    flights.append({
        "id": "MOON_HIGH",
        "origin": "Los Angeles",
        "destination": "San Diego",
        "alt_diff": 0.5,
        "az_diff": 0.3,
        "time": 2.5,
        "target_alt": moon_alt,
        "plane_alt": 40.5,
        "target_az": moon_az,
        "plane_az": 135.3,
        "is_possible_transit": 1,
        "possibility_level": 3,  # HIGH
        "elevation_change": "descending",
        "direction": 315,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    # MEDIUM - moderate alignment
    lat, lon = position_at(moon_az - 2, 0.20)
    flights.append({
        "id": "MOON_MED",
        "origin": "Phoenix",
        "destination": "San Diego",
        "alt_diff": 1.8,
        "az_diff": 1.5,
        "time": 3.2,
        "target_alt": moon_alt,
        "plane_alt": 38.2,
        "target_az": moon_az,
        "plane_az": 133.5,
        "is_possible_transit": 1,
        "possibility_level": 2,  # MEDIUM
        "elevation_change": "descending",
        "direction": 310,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    # LOW - marginal alignment
    lat, lon = position_at(moon_az + 7, 0.25)
    flights.append({
        "id": "MOON_LOW",
        "origin": "San Francisco",
        "destination": "San Diego",
        "alt_diff": 6.5,
        "az_diff": 5.8,
        "time": 4.8,
        "target_alt": moon_alt,
        "plane_alt": 33.5,
        "target_az": moon_az,
        "plane_az": 140.8,
        "is_possible_transit": 1,
        "possibility_level": 1,  # LOW
        "elevation_change": "descending",
        "direction": 305,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    # SUN TRANSITS
    # HIGH - nearly perfect alignment
    lat, lon = position_at(sun_az, 0.15)
    flights.append({
        "id": "SUN_HIGH",
        "origin": "Las Vegas",
        "destination": "San Diego",
        "alt_diff": 0.4,
        "az_diff": 0.6,
        "time": 2.8,
        "target_alt": sun_alt,
        "plane_alt": 35.4,
        "target_az": sun_az,
        "plane_az": 225.6,
        "is_possible_transit": 1,
        "possibility_level": 3,  # HIGH
        "elevation_change": "descending",
        "direction": 45,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    # MEDIUM - moderate alignment
    lat, lon = position_at(sun_az + 2, 0.20)
    flights.append({
        "id": "SUN_MED",
        "origin": "Denver",
        "destination": "San Diego",
        "alt_diff": 1.9,
        "az_diff": 1.6,
        "time": 3.5,
        "target_alt": sun_alt,
        "plane_alt": 33.1,
        "target_az": sun_az,
        "plane_az": 226.6,
        "is_possible_transit": 1,
        "possibility_level": 2,  # MEDIUM
        "elevation_change": "descending",
        "direction": 40,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    # LOW - marginal alignment
    lat, lon = position_at(sun_az - 7, 0.25)
    flights.append({
        "id": "SUN_LOW",
        "origin": "Oakland",
        "destination": "San Diego",
        "alt_diff": 6.2,
        "az_diff": 5.5,
        "time": 5.2,
        "target_alt": sun_alt,
        "plane_alt": 28.8,
        "target_az": sun_az,
        "plane_az": 219.5,
        "is_possible_transit": 1,
        "possibility_level": 1,  # LOW
        "elevation_change": "descending",
        "direction": 35,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    # NONE - no transit (far from both targets)
    lat, lon = position_at(0, 0.25)  # North
    flights.append({
        "id": "NONE_01",
        "origin": "San Diego",
        "destination": "San Francisco",
        "alt_diff": None,
        "az_diff": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # NONE
        "elevation_change": "climbing",
        "direction": 0,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    lat, lon = position_at(180, 0.25)  # South
    flights.append({
        "id": "NONE_02",
        "origin": "San Diego",
        "destination": "Denver",
        "alt_diff": None,
        "az_diff": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # NONE
        "elevation_change": "level",
        "direction": 180,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    lat, lon = position_at(270, 0.25)  # West
    flights.append({
        "id": "PRIV01",
        "origin": "San Diego",
        "destination": "N/D",
        "alt_diff": None,
        "az_diff": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # NONE
        "elevation_change": "level",
        "direction": 270,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    return {
        "flights": flights,
        "targetCoordinates": {
            "moon": {"altitude": moon_alt, "azimuthal": moon_az},
            "sun": {"altitude": sun_alt, "azimuthal": sun_az}
        },
        "trackingTargets": ["moon", "sun"],
        "weather": {
            "cloud_cover": 0,
            "condition": "clear",
            "icon": "☀️",
            "description": "clear sky",
            "api_success": True
        },
        "boundingBox": {
            "latLowerLeft": obs_lat - 0.5,
            "lonLowerLeft": obs_lon - 0.5,
            "latUpperRight": obs_lat + 0.5,
            "lonUpperRight": obs_lon + 0.5,
        },
        "observerPosition": {
            "latitude": obs_lat,
            "longitude": obs_lon,
            "elevation": obs_elev,
        },
    }


def get_transits(
    latitude: float,
    longitude: float,
    elevation: float,
    target_name: str = "auto",
    test_mode: bool = False,
    min_altitude: float = None,
) -> dict:
    """Get transit predictions for celestial targets.

    Parameters
    ----------
    target_name : str
        'moon', 'sun', or 'auto' (checks both if conditions permit)
    min_altitude : float
        Minimum altitude in degrees for target to be tracked (default from env or 15)
    test_mode : bool
        If True, return mock results for demonstration
    """
    # MOCK MODE - return hardcoded demo results
    if test_mode:
        logger.info("🎭 MOCK MODE: Returning demonstration results")
        return generate_mock_results(latitude, longitude, elevation)
    API_KEY = os.getenv("AEROAPI_API_KEY")
    WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    MIN_ALTITUDE = min_altitude if min_altitude is not None else float(os.getenv("MIN_TARGET_ALTITUDE", 15))

    logger.info(f"{latitude=}, {longitude=}, {elevation=}, {target_name=}")

    # Check weather conditions
    is_clear, weather_info = get_weather_condition(latitude, longitude, WEATHER_API_KEY)
    logger.info(f"Weather check: clear={is_clear}, {weather_info}")
    
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
    ref_datetime = naive_datetime_now.replace(tzinfo=ZoneInfo(local_timezone))

    # Determine which targets to check
    targets_to_check = []
    target_coordinates = {}

    # In test mode, use fake positions from test data metadata
    test_overrides = {}
    if test_mode:
        try:
            test_data = load_existing_flight_data(TEST_DATA_PATH)
            meta = test_data.get("_test_metadata", {})
            test_overrides = {
                "moon": {
                    "altitude": meta.get("moon_altitude", 60),
                    "azimuth": meta.get("moon_azimuth", 180),
                },
                "sun": {
                    "altitude": meta.get("sun_altitude", 55),
                    "azimuth": meta.get("sun_azimuth", 200),
                },
            }
            logger.info(f"Test mode: using fake positions {test_overrides}")
        except Exception:
            pass

    if target_name == "auto":
        # Check both moon and sun if conditions permit
        for target in ["moon", "sun"]:
            overrides = test_overrides.get(target) if test_mode else None
            obj = CelestialObject(name=target, observer_position=MY_POSITION, test_overrides=overrides)
            obj.update_position(ref_datetime=ref_datetime)
            coords = obj.get_coordinates()

            target_coordinates[target] = coords

            if coords["altitude"] >= MIN_ALTITUDE and is_clear:
                targets_to_check.append(target)
                logger.info(f"{target} at {coords['altitude']}° az {coords['azimuthal']}° - tracking enabled")
            else:
                reason = "below horizon" if coords["altitude"] < MIN_ALTITUDE else "weather"
                logger.info(f"{target} at {coords['altitude']}° - skipped ({reason})")
    else:
        # Single target mode
        overrides = test_overrides.get(target_name) if test_mode else None
        obj = CelestialObject(name=target_name, observer_position=MY_POSITION, test_overrides=overrides)
        obj.update_position(ref_datetime=ref_datetime)
        coords = obj.get_coordinates()

        target_coordinates[target_name] = coords

        if coords["altitude"] >= MIN_ALTITUDE and is_clear:
            targets_to_check.append(target_name)
        else:
            reason = "below horizon" if coords["altitude"] < MIN_ALTITUDE else "weather"
            logger.warning(f"{target_name} not trackable ({reason})")

    data = list()
    tracking_targets = targets_to_check.copy()  # For response

    if targets_to_check:
        # Fetch flight data once
        if test_mode:
            raw_flight_data = load_existing_flight_data(TEST_DATA_PATH)
            logger.info("Loading existing flight data since is using TEST mode")
        else:
            raw_flight_data = get_flight_data(area_bbox, API_URL, API_KEY)

        flight_data = list()
        for flight in raw_flight_data["flights"]:
            flight_data.append(parse_fligh_data(flight))

        logger.info(f"there are {len(flight_data)} flights near")

        # Check transits for each target
        for target in targets_to_check:
            overrides = test_overrides.get(target) if test_mode else None
            celestial_obj = CelestialObject(name=target, observer_position=MY_POSITION, test_overrides=overrides)
            celestial_obj.update_position(ref_datetime=ref_datetime)

            for flight in flight_data:
                celestial_obj.update_position(ref_datetime=ref_datetime)

                transit_result = check_transit(
                    flight,
                    window_time,
                    ref_datetime,
                    MY_POSITION,
                    celestial_obj,
                    EARTH,
                    test_mode=test_mode,
                )
                data.append(transit_result)
                logger.info(transit_result)

    return {
        "flights": data,
        "targetCoordinates": target_coordinates,
        "trackingTargets": tracking_targets,
        "weather": weather_info,
        "boundingBox": {
            "latLowerLeft": float(area_bbox.lat_lower_left),
            "lonLowerLeft": float(area_bbox.long_lower_left),
            "latUpperRight": float(area_bbox.lat_upper_right),
            "lonUpperRight": float(area_bbox.long_upper_right),
        },
        "observerPosition": {
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
    }
