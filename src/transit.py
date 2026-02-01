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
    observer_lat: float = 0.0,
    observer_lon: float = 0.0,
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

    # Capture target position at reference time (same for all aircraft)
    initial_target_alt = round(float(target.altitude.degrees), 2)
    initial_target_az = round(float(target.azimuthal.degrees), 2)

    # Calculate horizontal distance from observer to aircraft (km)
    from math import radians, sin, cos, sqrt, atan2
    R = 6371  # Earth radius in km
    lat1, lon1 = radians(observer_lat), radians(observer_lon)
    lat2, lon2 = radians(flight["latitude"]), radians(flight["longitude"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance_nm = R * c
    distance_nm = distance_nm * 0.539957  # Convert km to nautical miles

    # Calculate current position for ALL aircraft (for display purposes)
    current_alt, current_az = geographic_to_altaz(
        flight["latitude"],
        flight["longitude"],
        flight["elevation"],
        earth_ref,
        my_position,
        ref_datetime,
    )

    # Calculate current differences with target for ALL aircraft
    current_alt_diff = abs(current_alt - initial_target_alt)
    current_az_diff = abs(current_az - initial_target_az)
    current_angular_sep = calculate_angular_separation(current_alt_diff, current_az_diff)

    # In test mode, check current position first (t=0, static aircraft)
    if test_mode:
        alt_diff = abs(current_alt - target.altitude.degrees)
        az_diff = abs(current_az - target.azimuthal.degrees)
        angular_sep = calculate_angular_separation(alt_diff, az_diff)

        min_angular_sep = angular_sep

        # Always record if aircraft is above horizon, regardless of separation
        if current_alt > 0:
            response = {
                "id": flight["name"],
                "aircraft_type": flight.get("aircraft_type", "N/A"),
                "fa_flight_id": flight.get("fa_flight_id", ""),
                "origin": flight["origin"],
                "destination": flight["destination"],
                "alt_diff": round(float(alt_diff), 3),
                "az_diff": round(float(az_diff), 3),
                "angular_separation": round(float(angular_sep), 3),
                "time": 0.0,  # Current position
                "target_alt": initial_target_alt,
                "plane_alt": round(float(current_alt), 2),
                "target_az": initial_target_az,
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
                "aircraft_elevation": flight.get("elevation", 0),  # Actual altitude in meters
                "aircraft_elevation_feet": flight.get("elevation_feet", 0),  # Actual altitude in feet
                "distance_nm": round(distance_nm, 1),  # Distance from observer in nautical miles
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
                    "aircraft_type": flight.get("aircraft_type", "N/A"),
                    "fa_flight_id": flight.get("fa_flight_id", ""),
                    "origin": flight["origin"],
                    "destination": flight["destination"],
                    "alt_diff": round(float(alt_diff), 3),
                    "az_diff": round(float(az_diff), 3),
                    "angular_separation": round(float(angular_sep), 3),
                    "time": round(float(minute), 3),
                    "target_alt": initial_target_alt,
                    "plane_alt": round(float(future_alt), 2),
                    "target_az": initial_target_az,
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
                    "aircraft_elevation": flight.get("elevation", 0),  # Actual altitude in meters
                    "aircraft_elevation_feet": flight.get("elevation_feet", 0),  # Actual altitude in feet
                    "distance_nm": round(distance_nm, 1),  # Distance from observer in nautical miles
                }
        update_response = False

    # If response exists but is NOT a possible transit, override with current position
    if response and response.get("is_possible_transit") == 0:
        response["plane_alt"] = round(float(current_alt), 2)
        response["plane_az"] = round(float(current_az), 2)
        response["time"] = None  # No meaningful ETA for non-transits
        response["alt_diff"] = round(float(current_alt_diff), 3)
        response["az_diff"] = round(float(current_az_diff), 3)
        response["angular_separation"] = round(float(current_angular_sep), 3)
        return response

    if response:
        return response

    # No transit found - return current position with plane_alt and plane_az and current differences
    return {
        "id": flight["name"],
        "aircraft_type": flight.get("aircraft_type", "N/A"),
        "fa_flight_id": flight.get("fa_flight_id", ""),
        "origin": flight["origin"],
        "destination": flight["destination"],
        "alt_diff": round(float(current_alt_diff), 3),
        "az_diff": round(float(current_az_diff), 3),
        "angular_separation": round(float(current_angular_sep), 3),
        "time": None,
        "target_alt": initial_target_alt,
        "plane_alt": round(float(current_alt), 2),  # Show current position
        "target_az": initial_target_az,
        "plane_az": round(float(current_az), 2),  # Show current position
        "is_possible_transit": 0,
        "possibility_level": PossibilityLevel.UNLIKELY.value,
        "elevation_change": CHANGE_ELEVATION.get(flight["elevation_change"], None),
        "direction": flight["direction"],
        "target": target.name,
        "latitude": flight["latitude"],
        "longitude": flight["longitude"],
        "aircraft_elevation": flight.get("elevation", 0),  # Actual altitude in meters
        "aircraft_elevation_feet": flight.get("elevation_feet", 0),  # Actual altitude in feet
        "distance_nm": round(distance_nm, 1),  # Distance from observer in nautical miles
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
        "aircraft_type": "A320",
        "fa_flight_id": "MOON_HIGH-test-123",
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
        "aircraft_elevation": 10668,  # 35,000 ft in meters
        "aircraft_elevation_feet": 35000,  # 35,000 ft
        "distance_nm": 8.1,  # 15 km = 8.1 nm from observer
    })

    # MEDIUM - moderate alignment (≤2°)
    lat, lon = position_at(moon_az - 2, 20)  # 20 km, offset 2° from moon bearing
    alt_diff, az_diff = 1.2, 1.0
    flights.append({
        "id": "MOON_MED",
        "aircraft_type": "B737",
        "fa_flight_id": "MOON_MED-test-456",
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
        "aircraft_elevation": 10972,  # 36,000 ft in meters
        "aircraft_elevation_feet": 36000,  # 36,000 ft
        "distance_nm": 10.8,  # 20 km = 10.8 nm from observer
    })

    # LOW - marginal alignment (≤6°)
    lat, lon = position_at(moon_az + 7, 25)  # 25 km, offset 7° from moon bearing
    alt_diff, az_diff = 4.0, 3.5
    flights.append({
        "id": "MOON_LOW",
        "aircraft_type": "A321",
        "fa_flight_id": "MOON_LOW-test-789",
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
        "aircraft_elevation": 11277,  # 37,000 ft in meters
        "aircraft_elevation_feet": 37000,  # 37,000 ft
        "distance_nm": 13.5,  # 25 km = 13.5 nm from observer
    })

    # SUN TRANSITS
    # HIGH - nearly perfect alignment (≤1°)
    lat, lon = position_at(sun_az, 15)  # 15 km on sun bearing
    alt_diff, az_diff = 0.4, 0.6
    flights.append({
        "id": "SUN_HIGH",
        "aircraft_type": "B777",
        "fa_flight_id": "SUN_HIGH-test-111",
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
        "aircraft_elevation": 10363,  # 34,000 ft in meters
        "aircraft_elevation_feet": 34000,  # 34,000 ft
        "distance_nm": 8.1,  # 15 km = 8.1 nm from observer
    })

    # MEDIUM - moderate alignment (≤2°)
    lat, lon = position_at(sun_az + 2, 20)  # 20 km, offset 2° from sun bearing
    alt_diff, az_diff = 1.3, 1.1
    flights.append({
        "id": "SUN_MED",
        "aircraft_type": "A330",
        "fa_flight_id": "SUN_MED-test-222",
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
        "aircraft_elevation": 10058,  # 33,000 ft in meters
        "aircraft_elevation_feet": 33000,  # 33,000 ft
        "distance_nm": 10.8,  # 20 km = 10.8 nm from observer
    })

    # LOW - marginal alignment (≤6°)
    lat, lon = position_at(sun_az - 7, 25)  # 25 km, offset 7° from sun bearing
    alt_diff, az_diff = 3.8, 4.2
    flights.append({
        "id": "SUN_LOW",
        "aircraft_type": "B787",
        "fa_flight_id": "SUN_LOW-test-333",
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
        "aircraft_elevation": 9754,  # 32,000 ft in meters
        "aircraft_elevation_feet": 32000,  # 32,000 ft
        "distance_nm": 13.5,  # 25 km = 13.5 nm from observer
    })

    # UNLIKELY - no transit (far from both targets, >6°)
    lat, lon = position_at(0, 25)  # North, 25 km
    # This plane is heading North (0°), far from moon at 135°
    plane_alt_1, plane_az_1 = 25.0, 5.0  # Low on horizon, heading north
    alt_diff_1 = abs(plane_alt_1 - moon_alt)  # 15°
    az_diff_1 = abs(plane_az_1 - moon_az)  # 130°
    flights.append({
        "id": "NONE_01",
        "aircraft_type": "B737",
        "fa_flight_id": "NONE_01-test-444",
        "origin": "San Diego",
        "destination": "San Francisco",
        "alt_diff": round(alt_diff_1, 3),
        "az_diff": round(az_diff_1, 3),
        "angular_separation": round(np.sqrt(alt_diff_1**2 + az_diff_1**2), 3),
        "time": None,
        "target_alt": moon_alt,
        "plane_alt": plane_alt_1,
        "target_az": moon_az,
        "plane_az": plane_az_1,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
        "elevation_change": "climbing",
        "direction": 0,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
        "aircraft_elevation": 7620,  # 25,000 ft in meters
        "aircraft_elevation_feet": 25000,  # 25,000 ft
        "distance_nm": 13.5,  # 25 km = 13.5 nm from observer
    })

    lat, lon = position_at(180, 25)  # South, 25 km
    # This plane is heading South (180°), somewhat close to sun at 225°
    plane_alt_2, plane_az_2 = 32.0, 185.0  # Mid-altitude, heading south
    alt_diff_2 = abs(plane_alt_2 - sun_alt)  # 3°
    az_diff_2 = abs(plane_az_2 - sun_az)  # 40°
    flights.append({
        "id": "NONE_02",
        "aircraft_type": "A320",
        "fa_flight_id": "NONE_02-test-555",
        "origin": "San Diego",
        "destination": "Denver",
        "alt_diff": round(alt_diff_2, 3),
        "az_diff": round(az_diff_2, 3),
        "angular_separation": round(np.sqrt(alt_diff_2**2 + az_diff_2**2), 3),
        "time": None,
        "target_alt": sun_alt,
        "plane_alt": plane_alt_2,
        "target_az": sun_az,
        "plane_az": plane_az_2,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
        "elevation_change": "level",
        "direction": 180,
        "target": "sun",
        "latitude": lat,
        "longitude": lon,
        "aircraft_elevation": 9144,  # 30,000 ft in meters
        "aircraft_elevation_feet": 30000,  # 30,000 ft
        "distance_nm": 13.5,  # 25 km = 13.5 nm from observer
    })

    lat, lon = position_at(270, 25)  # West, 25 km
    # This plane is heading West (270°), far from moon at 135°
    plane_alt_3, plane_az_3 = 15.0, 275.0  # Low altitude private plane, heading west
    alt_diff_3 = abs(plane_alt_3 - moon_alt)  # 25°
    az_diff_3 = abs(plane_az_3 - moon_az)  # 140°
    flights.append({
        "id": "PRIV01",
        "aircraft_type": "SR22",
        "fa_flight_id": "PRIV01-test-666",
        "origin": "San Diego",
        "destination": "N/D",
        "alt_diff": round(alt_diff_3, 3),
        "az_diff": round(az_diff_3, 3),
        "angular_separation": round(np.sqrt(alt_diff_3**2 + az_diff_3**2), 3),
        "time": None,
        "target_alt": moon_alt,
        "plane_alt": plane_alt_3,
        "target_az": moon_az,
        "plane_az": plane_az_3,
        "is_possible_transit": 0,
        "possibility_level": 0,  # UNLIKELY
        "elevation_change": "level",
        "direction": 270,
        "target": "moon",
        "latitude": lat,
        "longitude": lon,
        "aircraft_elevation": 1524,  # 5,000 ft in meters (private plane)
        "aircraft_elevation_feet": 5000,  # 5,000 ft
        "distance_nm": 13.5,  # 25 km = 13.5 nm from observer
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
    custom_bbox: dict = None,
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

    # Use custom bounding box if provided, otherwise use default
    if custom_bbox:
        search_bbox = AreaBoundingBox(
            lat_lower_left=custom_bbox["lat_lower_left"],
            long_lower_left=custom_bbox["lon_lower_left"],
            lat_upper_right=custom_bbox["lat_upper_right"],
            long_upper_right=custom_bbox["lon_upper_right"],
        )
        logger.info(f"Using custom search area: {search_bbox}")
    else:
        search_bbox = area_bbox

    if targets_to_check:
        # Fetch flight data once
        if test_mode:
            raw_flight_data = load_existing_flight_data(TEST_DATA_PATH)
            logger.info("Loading existing flight data since is using TEST mode")
        else:
            raw_flight_data = get_flight_data(search_bbox, API_URL, API_KEY)

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
                    observer_lat=latitude,
                    observer_lon=longitude,
                )
                data.append(transit_result)
                logger.info(transit_result)

    # Determine which bounding box to return
    response_bbox = search_bbox if custom_bbox else area_bbox

    return {
        "flights": data,
        "targetCoordinates": target_coordinates,
        "trackingTargets": tracking_targets,
        "weather": weather_info,
        "boundingBox": {
            "latLowerLeft": float(response_bbox.lat_lower_left),
            "lonLowerLeft": float(response_bbox.long_lower_left),
            "latUpperRight": float(response_bbox.lat_upper_right),
            "lonUpperRight": float(response_bbox.long_upper_right),
        },
        "observerPosition": {
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
        },
    }
