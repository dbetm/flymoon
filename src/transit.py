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


def calculate_angular_separation(alt_diff: float, az_diff: float) -> float:
    """Calculate true angular separation using Euclidean distance.

    For small angles, this is sufficiently accurate:
    angular_separation ≈ sqrt(alt_diff² + az_diff²)

    Parameters
    ----------
    alt_diff : float
        Altitude difference in degrees
    az_diff : float
        Azimuth difference in degrees

    Returns
    -------
    float
        Angular separation in degrees
    """
    return np.sqrt(alt_diff**2 + az_diff**2)


def get_possibility_level(angular_separation: float) -> str:
    """Classify transit probability based on angular separation.

    Sun and Moon are ~0.5° diameter. Classification based on how close
    the aircraft passes to the target center.

    Parameters
    ----------
    angular_separation : float
        Angular separation in degrees between aircraft and target

    Returns
    -------
    str
        Possibility level: HIGH (≤1°), MEDIUM (≤2°), LOW (≤6°), or UNLIKELY (>6°)
    """
    if angular_separation <= 1.0:
        return PossibilityLevel.HIGH.value
    elif angular_separation <= 2.0:
        return PossibilityLevel.MEDIUM.value
    elif angular_separation <= 6.0:
        return PossibilityLevel.LOW.value
    else:
        return PossibilityLevel.UNLIKELY.value


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
    min_angular_sep = float("inf")
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
        angular_sep = calculate_angular_separation(alt_diff, az_diff)

        min_angular_sep = angular_sep

        # Always record if aircraft is above horizon, regardless of separation
        if current_alt > 0:
            response = {
                "id": flight["name"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "alt_diff": round(float(alt_diff), 3),
                "az_diff": round(float(az_diff), 3),
                "angular_separation": round(float(angular_sep), 3),
                "time": 0.0,  # Current position
                "target_alt": round(float(target.altitude.degrees), 2),
                "plane_alt": round(float(current_alt), 2),
                "target_az": round(float(target.azimuthal.degrees), 2),
                "plane_az": round(float(current_az), 2),
                "is_possible_transit": 1 if angular_sep <= 6.0 else 0,
                "possibility_level": get_possibility_level(angular_sep),
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
        angular_sep = calculate_angular_separation(alt_diff, az_diff)

        if no_decreasing_count >= 180:
            logger.info(f"Angular separation increasing, stop checking at min={round(minute, 2)}")
            break

        if angular_sep < min_angular_sep:
            no_decreasing_count = 0
            min_angular_sep = angular_sep
            update_response = True
        else:
            no_decreasing_count += 1

        # Always track aircraft above horizon, will be classified by angular separation
        if future_alt > 0:
            if update_response:
                response = {
                    "id": flight["name"],
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "alt_diff": round(float(alt_diff), 3),
                    "az_diff": round(float(az_diff), 3),
                    "angular_separation": round(float(angular_sep), 3),
                    "time": round(float(minute), 3),
                    "target_alt": round(float(target.altitude.degrees), 2),
                    "plane_alt": round(float(future_alt), 2),
                    "target_az": round(float(target.azimuthal.degrees), 2),
                    "plane_az": round(float(future_az), 2),
                    "is_possible_transit": 1 if angular_sep <= 6.0 else 0,
                    "possibility_level": get_possibility_level(angular_sep),
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
        "angular_separation": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": PossibilityLevel.UNLIKELY.value,
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
    # Uses haversine formula to match the map's azimuth arrow calculation
    def position_at(azimuth_deg, distance_km):
        import math
        R = 6371  # Earth's radius in km
        d = distance_km / R  # Angular distance in radians

        brng = math.radians(azimuth_deg)
        lat1 = math.radians(obs_lat)
        lon1 = math.radians(obs_lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d) +
            math.cos(lat1) * math.sin(d) * math.cos(brng)
        )

        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d) * math.cos(lat1),
            math.cos(d) - math.sin(lat1) * math.sin(lat2)
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    flights = []

    # MOON TRANSITS
    # HIGH - nearly perfect alignment (≤1°)
    lat, lon = position_at(moon_az, 15)  # 15 km on moon bearing
    alt_diff, az_diff = 0.5, 0.3
    flights.append({
        "id": "MOON_HIGH",
        "origin": "Los Angeles",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
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

    # MEDIUM - moderate alignment (≤2°)
    lat, lon = position_at(moon_az - 2, 20)  # 20 km, offset 2° from moon bearing
    alt_diff, az_diff = 1.2, 1.0
    flights.append({
        "id": "MOON_MED",
        "origin": "Phoenix",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
        "time": 3.2,
        "target_alt": moon_alt,
        "plane_alt": 38.8,
        "target_az": moon_az,
        "plane_az": 134.0,
        "is_possible_transit": 1,
        "possibility_level": 2,  # MEDIUM
        "elevation_change": "descending",
        "direction": 310,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    # LOW - marginal alignment (≤6°)
    lat, lon = position_at(moon_az + 7, 25)  # 25 km, offset 7° from moon bearing
    alt_diff, az_diff = 4.0, 3.5
    flights.append({
        "id": "MOON_LOW",
        "origin": "San Francisco",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
        "time": 4.8,
        "target_alt": moon_alt,
        "plane_alt": 36.0,
        "target_az": moon_az,
        "plane_az": 138.5,
        "is_possible_transit": 1,
        "possibility_level": 1,  # LOW
        "elevation_change": "descending",
        "direction": 305,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    # SUN TRANSITS
    # HIGH - nearly perfect alignment (≤1°)
    lat, lon = position_at(sun_az, 15)  # 15 km on sun bearing
    alt_diff, az_diff = 0.4, 0.6
    flights.append({
        "id": "SUN_HIGH",
        "origin": "Las Vegas",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
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

    # MEDIUM - moderate alignment (≤2°)
    lat, lon = position_at(sun_az + 2, 20)  # 20 km, offset 2° from sun bearing
    alt_diff, az_diff = 1.3, 1.1
    flights.append({
        "id": "SUN_MED",
        "origin": "Denver",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
        "time": 3.5,
        "target_alt": sun_alt,
        "plane_alt": 33.7,
        "target_az": sun_az,
        "plane_az": 226.1,
        "is_possible_transit": 1,
        "possibility_level": 2,  # MEDIUM
        "elevation_change": "descending",
        "direction": 40,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    # LOW - marginal alignment (≤6°)
    lat, lon = position_at(sun_az - 7, 25)  # 25 km, offset 7° from sun bearing
    alt_diff, az_diff = 3.8, 4.2
    flights.append({
        "id": "SUN_LOW",
        "origin": "Oakland",
        "destination": "San Diego",
        "alt_diff": alt_diff,
        "az_diff": az_diff,
        "angular_separation": round(np.sqrt(alt_diff**2 + az_diff**2), 3),
        "time": 5.2,
        "target_alt": sun_alt,
        "plane_alt": 31.2,
        "target_az": sun_az,
        "plane_az": 220.8,
        "is_possible_transit": 1,
        "possibility_level": 1,  # LOW
        "elevation_change": "descending",
        "direction": 35,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    # UNLIKELY - no transit (far from both targets, >6°)
    lat, lon = position_at(0, 25)  # North, 25 km
    flights.append({
        "id": "NONE_01",
        "origin": "San Diego",
        "destination": "San Francisco",
        "alt_diff": None,
        "az_diff": None,
        "angular_separation": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
        "elevation_change": "climbing",
        "direction": 0,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
    })

    lat, lon = position_at(180, 25)  # South, 25 km
    flights.append({
        "id": "NONE_02",
        "origin": "San Diego",
        "destination": "Denver",
        "alt_diff": None,
        "az_diff": None,
        "angular_separation": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
        "elevation_change": "level",
        "direction": 180,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
    })

    lat, lon = position_at(270, 25)  # West, 25 km
    flights.append({
        "id": "PRIV01",
        "origin": "San Diego",
        "destination": "N/D",
        "alt_diff": None,
        "az_diff": None,
        "angular_separation": None,
        "time": None,
        "target_alt": None,
        "plane_alt": None,
        "target_az": None,
        "plane_az": None,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
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
