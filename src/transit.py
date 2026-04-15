import os
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from skyfield.api import Topos
from tzlocal import get_localzone_name

from src import logger
from src.astro import CelestialObject
from src.constants import (
    ASTRO_EPHEMERIS,
    CHANGE_ELEVATION,
    INTERVAL_IN_SECS,
    NUM_SECONDS_PER_MIN,
    TOP_MINUTE,
    WEATHER_API_KEY,
    PossibilityLevel,
)
from src.demo import generate_test_flightaware_data, generate_test_flightaware_data2
from src.flight_data import FlightAwareAeroAPIClient, AirLabsClient
from src.position import (
    AreaBoundingBox,
    geographic_to_altaz,
    get_my_pos,
    haversine_distance,
    predict_position,
)
from src.weather import get_weather_condition

EARTH = ASTRO_EPHEMERIS["earth"]

# TODO: compute from current user position
AREA_BBOX_FROM_ENV = AreaBoundingBox(
    lat_lower_left=os.getenv("LAT_LOWER_LEFT"),
    long_lower_left=os.getenv("LONG_LOWER_LEFT"),
    lat_upper_right=os.getenv("LAT_UPPER_RIGHT"),
    long_upper_right=os.getenv("LONG_UPPER_RIGHT"),
)


def calculate_angular_separation(alt_1: float, az_1: float, alt_2: float, az_2: float) -> float:
    """Calculate great-circle angular separation in alt-az space.

    Uses the spherical law of cosines, which is numerically stable
    for all separations and altitudes including near the zenith.

    Parameters
    ----------
    alt_1 : float
        Altitude in degrees for the first object
    az_1 : float
        Azimuth in degrees for the first object
    alt_2 : float
        Altitude in degrees for the first object
    az_2 : float
        Azimuth in degrees for the first object

    Returns
    -------
    float
        Angular separation in degrees
    """

    # Convert to radians
    alt_1_rad = math.radians(alt_1)
    az_1_rad  = math.radians(az_1)
    alt_2_rad = math.radians(alt_2)
    az_2_rad  = math.radians(az_2)

    ### Apply spheric cosines law ###

    # Term A: Sines product for altitud
    term_a = math.sin(alt_1_rad) * math.sin(alt_2_rad)

    # Term B: Product of cosines * cosine of the azimuth diff
    az_diff = abs(az_1_rad - az_2_rad)
    term_b = math.cos(alt_1_rad) * math.cos(alt_2_rad) * math.cos(az_diff)

    # Calculate the total angle and convert back to degrees
    # Note: We bound the value between -1 and 1 to avoid floating-point errors
    cos_theta = min(1.0, max(-1.0, term_a + term_b))
    theta_rad = math.acos(cos_theta)

    return math.degrees(theta_rad)


def get_possibility_level(angular_separation: float) -> str:
    """Classify transit probability based on angular separation.

    Using 1.0° target diameter (expanded from actual ~0.5° to increase detection
    of partial transits). Classification based on how close the aircraft passes
    to the target center.

    Parameters
    ----------
    angular_separation : float
        Angular separation in degrees between aircraft and target

    Returns
    -------
    str
        Possibility level: HIGH (≤2°), MEDIUM (≤4°), LOW (≤12°), or UNLIKELY (>12°)
    """
    if angular_separation <= 2.0:
        return PossibilityLevel.HIGH.value
    elif angular_separation <= 4.0:
        return PossibilityLevel.MEDIUM.value
    elif angular_separation <= 12.0:
        return PossibilityLevel.LOW.value
    else:
        return PossibilityLevel.UNLIKELY.value


def check_transit(
    flight: dict,
    window_time: list,
    ref_datetime: datetime,
    observer_position: Topos,
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
    observer_position: Topos
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
    min_angular_sep = float("inf")
    response = None
    no_decreasing_count = 0
    update_response = False
    POSSIBLE_TRANSIT_LEVELS = {PossibilityLevel.HIGH.value, PossibilityLevel.MEDIUM.value}

    # Calculate horizontal distance from observer to aircraft in kilometers
    distance_km = haversine_distance(
        float(observer_position.target.latitude.degrees),
        float(observer_position.target.longitude.degrees),
        flight["latitude"],
        flight["longitude"]
    )

    for idx, minute in enumerate(window_time):
        # Get future position of plane
        future_lat, future_lon = predict_position(
            lat=flight["latitude"],
            lon=flight["longitude"],
            speed=flight["speed"],
            direction=flight["direction"],
            minutes=minute,
        )

        future_time = ref_datetime + timedelta(minutes=minute)

        # Convert future position of plane to alt-azimuthal coordinates
        future_alt, future_az = geographic_to_altaz(
            future_lat,
            future_lon,
            flight["elevation"],
            earth_ref,
            observer_position,
            future_time,
        )

        if idx > 0 and idx % 30 == 0:
            # Update target position every 30 data points (0.5 min)
            target.update_position(future_time)

        alt_diff = abs(future_alt - target.altitude.degrees)
        az_diff = abs(future_az - target.azimuthal.degrees)

        angular_sep = calculate_angular_separation(
            alt_1=target.altitude.degrees,
            az_1=target.azimuthal.degrees,
            alt_2=future_alt,
            az_2=future_az,
        )

        if angular_sep < min_angular_sep:
            no_decreasing_count = 0
            min_angular_sep = angular_sep
            update_response = True
        else:
            no_decreasing_count += 1

        if no_decreasing_count >= 120:
            logger.info(f"Angular separation increasing, stop checking at min={round(minute, 2)}")
            break

        # Always track aircraft above horizon, will be classified by angular separation
        if update_response:
            possibility_level = get_possibility_level(angular_sep)

            response = {
                "id": flight["name"],
                "aircraft_type": flight.get("aircraft_type", "N/A"),
                "fa_flight_id": flight.get("fa_flight_id", ""),
                "origin": flight["origin"],
                "destination": flight["destination"],
                "alt_diff": round(float(alt_diff), 2),
                "az_diff": round(float(az_diff), 2),
                "angular_separation": round(float(angular_sep), 2),
                "time": round(float(minute), 2),
                "target_alt": round(float(target.altitude.degrees), 2),
                "plane_alt": round(float(future_alt), 2),
                "target_az": round(float(target.azimuthal.degrees), 2),
                "plane_az": round(float(future_az), 2),
                "is_possible_transit": 1 if possibility_level in POSSIBLE_TRANSIT_LEVELS else 0,
                "possibility_level": possibility_level,
                "elevation_change": CHANGE_ELEVATION.get(
                    flight["elevation_change"], None
                ),
                "direction": flight["direction"],
                "speed": flight["speed"],
                "target": target.name,
                "latitude": flight["latitude"],
                "longitude": flight["longitude"],
                "aircraft_elevation": flight.get("elevation", 0),  # Actual altitude in meters
                "aircraft_elevation_km": round(flight.get("elevation", 0) / 1_000, 2), # Actual altitude in kilometers
                "aircraft_elevation_feet": flight.get("elevation_feet", 0),  # Actual altitude in feet # TODO: deprecate
                "distance_km": round(distance_km, 1), # Distance from observer in km
            }
        update_response = False

    if not response:
        raise Exception("No response was generated!")

    return response


def get_transits(
    latitude: float,
    longitude: float,
    elevation: float,
    target_name: str = "auto",
    test_mode: bool = False,
    min_altitude: float = None,
    custom_bbox: dict = None,
    adsb_provider: str = "flightaware-aeroapi"
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
    custom_bbox : dict
        Optional custom bounding box with keys: lat_lower_left, lon_lower_left, lat_upper_right, lon_upper_right
    adsb_provider: str:
        Optional ADSB provider name to use. You must set the API Key for the choosen one. Default: `flightaware-aeroapi`.
    """
    MIN_ALTITUDE = min_altitude if min_altitude is not None else float(os.getenv("MIN_TARGET_ALTITUDE", 15))
    OBSERVER_POSITION = get_my_pos(
        lat=latitude,
        lon=longitude,
        elevation=elevation,
        base_ref=EARTH,
    )

    logger.info(f"{latitude=}, {longitude=}, {elevation=}, {target_name=}")

    # MOCK MODE - return hardcoded demo results
    # if test_mode:
    #     logger.info("🎭 MOCK MODE: Returning demonstration results")
    #     return generate_demo_flight_data(latitude, longitude, elevation, target_name)

    window_time = np.linspace(
        0, TOP_MINUTE, TOP_MINUTE * (NUM_SECONDS_PER_MIN // INTERVAL_IN_SECS)
    )
    logger.info(f"number of times to check for each flight: {len(window_time)}")

    # Get the local timezone using tzlocal
    local_timezone = get_localzone_name()
    naive_datetime_now = datetime.now()
    ref_datetime = naive_datetime_now.replace(tzinfo=ZoneInfo(local_timezone))

    # Determine which targets to check
    target_names = ["moon", "sun"] if target_name == "auto" else [target_name]
    targets_to_check = []
    target_coordinates = {}

    # Check both moon and sun if conditions permit
    for target in target_names:
        obj = CelestialObject(name=target, observer_position=OBSERVER_POSITION)
        obj.update_position(ref_datetime=ref_datetime)
        coords = obj.get_coordinates()

        target_coordinates[target] = coords

        if coords["altitude"] >= MIN_ALTITUDE and is_clear:
            targets_to_check.append(target)
            logger.info(f"{target} at {coords['altitude']}° az {coords['azimuthal']}° - tracking enabled")
        else:
            reason = "below horizon" if coords["altitude"] < MIN_ALTITUDE else "weather"
            logger.info(f"{target} at {coords['altitude']}° - skipped ({reason})")

    data = list()
    tracking_targets = targets_to_check.copy() # For response

    # Use custom bounding box if provided, otherwise use default
    if custom_bbox:
        search_bbox = AreaBoundingBox(
            lat_lower_left=custom_bbox["lat_lower_left"],
            long_lower_left=custom_bbox["lon_lower_left"],
            lat_upper_right=custom_bbox["lat_upper_right"],
            long_upper_right=custom_bbox["lon_upper_right"],
        )
    else:
        search_bbox = AREA_BBOX_FROM_ENV
        logger.info(f"Using bounding box as search area from ENV: {search_bbox}")

    # Instanciate the ADSB provider client
    if adsb_provider == "flightaware-aeroapi":
        adsb_client = FlightAwareAeroAPIClient(search_bbox, os.getenv("AEROAPI_API_KEY"))
    elif adsb_provider == "airlabs":
        adsb_client = AirLabsClient(search_bbox, os.getenv("AIRLABS_API_KEY"))
    else:
        raise ValueError("Pass a valid ADSB provider name, allowed values: flightaware-aeroapi, airlabs")

    # Check weather conditions
    if targets_to_check:
        is_clear, weather_info = get_weather_condition(latitude, longitude, WEATHER_API_KEY, test_mode)
        logger.info(f"Weather check: clear={is_clear}, {weather_info}")
    else:
        is_clear, weather_info = get_weather_condition(
            latitude, longitude, WEATHER_API_KEY, return_default_response=True
        )

    if targets_to_check and is_clear:
        # Fetch flight data once
        if test_mode:
            logger.info("🧪 TEST MODE: generating test flight data...")
            raw_flight_data = generate_test_flightaware_data(OBSERVER_POSITION, targets_to_check, target_coordinates)
        else:
            raw_flight_data = adsb_client.get_flight_data()

        flight_data = list()
        for flight in raw_flight_data["flights"]:
            #flight_data.append(parse_fligh_data(flight))
            parsed_data_flight = adsb_client.parse(flight)

            if parsed_data_flight:
                flight_data.append(parsed_data_flight)

        logger.info(f"there are {len(flight_data)} flights near")

        # Check transits for each target
        for target in targets_to_check:
            celestial_obj = CelestialObject(name=target, observer_position=OBSERVER_POSITION)
            #celestial_obj.update_position(ref_datetime=ref_datetime)

            for flight in flight_data:
                celestial_obj.update_position(ref_datetime=ref_datetime)

                transit_result = check_transit(
                    flight,
                    window_time,
                    ref_datetime,
                    OBSERVER_POSITION,
                    celestial_obj,
                    EARTH,
                )
                data.append(transit_result)
                logger.info(transit_result)

    return {
        "flights": data,
        "targetCoordinates": target_coordinates,
        "trackingTargets": tracking_targets,
        "weather": weather_info,
        "boundingBox": {
            "latLowerLeft": float(search_bbox.lat_lower_left),
            "lonLowerLeft": float(search_bbox.long_lower_left),
            "latUpperRight": float(search_bbox.lat_upper_right),
            "lonUpperRight": float(search_bbox.long_upper_right),
        },
        "observerPosition": {
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
    }
