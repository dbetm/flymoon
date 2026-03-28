import math
import random
from typing import List

import numpy as np

from src.constants import ASTRO_EPHEMERIS, EARTH_RADIOUS


EARTH = ASTRO_EPHEMERIS["earth"]



def generate_test_flightaware_data(observer_position, target_names: List[str], target_coordinates: dict) -> dict:
    """Generate flight data, in which the last position is favorable to transits over the targets (Moon / Sun).

    + observer position is an object <class 'skyfield.vectorlib.VectorSum'>, you can get the latitude, longitude and elevation as follow:
        -> float(observer_position.target.latitude.degrees)
    + target_names could be moon and/or sun
    + target_coordinates is a dictionary, example: "moon": {
        "altitude": 42.2,
        "azimuthal": 160.3,
    }
    """
    num_targets = len(target_names)
    assert num_targets  > 0, "you should provide at least one target"

    obs_lat = float(observer_position.target.latitude.degrees)
    obs_lon = float(observer_position.target.longitude.degrees)

    # Use the first available target to compute flight positions
    target = target_names[0] if num_targets == 1 else target_names[random.randint(0, num_targets - 1)]

    target_alt = target_coordinates[target]["altitude"]
    target_az  = target_coordinates[target]["azimuthal"]

    def get_geo_pos_from_altaz(apparent_alt_deg: float, apparent_az_deg: float, elevation_m: float):
        """Return the lat/lon at which an aircraft flying at elevation_m
        would appear at (apparent_alt_deg, apparent_az_deg) from the observer.

        Uses the flat-Earth approximation d_horiz = h / tan(alt), which is
        accurate to <0.2° for the distances involved (~5–40 km).
        """
        alt_rad = math.radians(max(apparent_alt_deg, 1.0))  # guard tan(0)
        d_horiz_km = (elevation_m / math.tan(alt_rad)) / 1000
        d_rad = d_horiz_km / EARTH_RADIOUS

        az_rad = math.radians(apparent_az_deg)
        lat1 = math.radians(obs_lat)
        lon1 = math.radians(obs_lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(az_rad)
        )
        lon2 = lon1 + math.atan2(
            math.sin(az_rad) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    def pos_offset(lat_deg: float, lon_deg: float, bearing_deg: float, distance_km: float):
        """Move a point (lat_deg, lon_deg) by distance_km along bearing_deg (direction)"""
        d_rad = distance_km / EARTH_RADIOUS
        brng = math.radians(bearing_deg % 360)
        lat1 = math.radians(lat_deg)
        lon1 = math.radians(lon_deg)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    # parse_fligh_data converts altitude (hundreds of ft) * 100 * 0.3048 → metres.
    # Altitudes vary between 250 (25,000 ft) and 350 (35,000 ft).
    #
    # The closest-approach point is placed at (target_alt + Δalt, target_az + Δaz).
    # Angular separation at that point (small-angle approx):
    #   sep ≈ √(Δalt² + cos²(target_alt) · Δaz²)
    # Because cos²(alt) ∈ [0.12, 0.93] for alt ∈ [15°, 70°], both offsets contribute
    # but Δaz is compressed at higher elevations → classifications hold across the range.
    # For UNLIKELY, a 90° azimuth offset gives sep = acos(sin²(target_alt)) >> 12°.
    configs = [
        # id       origin         destination    type   elev. Δalt.  Δaz.  eta
        ("AMX190", "Mexico City", "Guadalajara", "B738", 350,  1.0,  1.0, 3.0),   # HIGH   sep   <=2°
        ("VOI282", "Monterrey",   "Cancun",      "A320", 330,  2.0,  1.5, 5.0),   # MEDIUM sep   <=4°
        ("VIV415", "Guadalajara", "Tijuana",     "A320", 310,  2.5,  2.5, 4.0),   # MEDIUM sep   <=4°
        ("TAR031", "Mexico City", "Merida",      "B737", 280,  5.0,  4.0, 7.0),   # LOW    sep   <=12°
        ("AMX541", "Hermosillo",  "Mexico City", "B39M", 250,  0.0, 90.0, 6.0),   # UNLIKELY sep >12°
    ]

    speed_knots = 480
    speed_kmh = speed_knots * 1.852

    flights = []
    for id, origin, dest, aircraft_type, alt_hundreds_ft, delta_alt, delta_az, eta_min in configs:
        elevation_m = alt_hundreds_ft * 100 * 0.3048
        desired_alt = min(target_alt + delta_alt, 90.0)   # cap well below zenith
        desired_az = (target_az + delta_az) % 360

        # Closest-approach point in lat/lon
        close_lat, close_lon = get_geo_pos_from_altaz(desired_alt, desired_az, elevation_m)

        # Back-project: place aircraft upstream so it reaches close_lat/lon at t=eta_min.
        # The aircraft flies toward desired_az, so it starts in the opposite direction.
        d_km = speed_kmh * eta_min / 60
        upstream_brng = (desired_az + 180) % 360
        lat, lon = pos_offset(close_lat, close_lon, upstream_brng, d_km)
        heading = int(desired_az)

        flights.append({
            "ident": id,
            "aircraft_type": aircraft_type,
            "fa_flight_id": f"{id}-demo-test",
            "origin": {"city": origin},
            "destination": {"city": dest},
            "last_position": {
                "latitude": lat,
                "longitude": lon,
                "heading": heading,
                "groundspeed": speed_knots,
                "altitude": alt_hundreds_ft,
                "altitude_change": "-",
            },
        })

    return {"flights": flights}


def get_demo_results(obs_lat: float, obs_lon: float, obs_elev: float) -> dict:
    """Generate mock transit results for demonstration purposes.

    Returns hardcoded results showing HIGH, MEDIUM, LOW, and NONE classifications
    for both moon and sun targets.
    """
    # Fixed celestial target positions
    moon_az, moon_alt = 135.0, 40.0
    sun_az, sun_alt = 225.0, 35.0

    def position_at(azimuth_deg, distance_km):
        """Helper to create aircraft position at specific azimuth and distance
        Uses haversine formula to match the map's azimuth arrow calculation
        """
        d = distance_km / EARTH_RADIOUS  # Angular distance in radians

        az_rad = math.radians(azimuth_deg)
        lat1 = math.radians(obs_lat)
        lon1 = math.radians(obs_lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d) +
            math.cos(lat1) * math.sin(d) * math.cos(az_rad)
        )

        lon2 = lon1 + math.atan2(
            math.sin(az_rad) * math.sin(d) * math.cos(lat1),
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
        "distance_km": 15,  # 15 km = 8.1 nm from observer
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
        "distance_km": 20,  # 20 km = 10.8 nm from observer
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
        "distance_km": 25,  # 25 km = 13.5 nm from observer
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
        "distance_km": 15,  # 15 km = 8.1 nm from observer
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
        "distance_km": 20,  # 20 km = 10.8 nm from observer
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
        "distance_km": 25,  # 25 km = 13.5 nm from observer
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
        "distance_km": 25,  # 25 km = 13.5 nm from observer
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
        "distance_km": 25,  # 25 km = 13.5 nm from observer
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
        "distance_km": 25,  # 25 km = 13.5 nm from observer
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