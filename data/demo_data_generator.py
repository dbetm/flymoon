#!/usr/bin/env python3
"""
Generate configurable test flight data for demonstration and testing.

Usage:
    python data/test_data_generator.py --scenario dual_tracking
    python data/test_data_generator.py --scenario moon_only --num-flights 5
    python data/test_data_generator.py --custom
"""
import json
import argparse
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Observer position (from src/transit.py - must be INSIDE bounding box)
# Bounding box: 32.0-33.5 lat, -118.0 to -117.0 lon
OBSERVER_LAT = 33.11
OBSERVER_LON = -117.31

# Configurable test scenarios
SCENARIOS = {
    "dual_tracking": {
        "description": "Both Moon and Sun visible with multiple transits",
        "moon_altitude": 35,  # degrees
        "moon_azimuth": 150,  # SSE
        "sun_altitude": 30,
        "sun_azimuth": 240,   # WSW - 90 degrees separated
        "cloud_cover": 15,  # percent
    },
    "moon_only": {
        "description": "Only Moon visible (daytime, Sun below horizon)",
        "moon_altitude": 25,
        "moon_azimuth": 180,
        "sun_altitude": -10,
        "sun_azimuth": 90,
        "cloud_cover": 20,
    },
    "sun_only": {
        "description": "Only Sun visible (daytime, Moon below horizon)",
        "moon_altitude": -5,
        "moon_azimuth": 270,
        "sun_altitude": 50,
        "sun_azimuth": 180,
        "cloud_cover": 10,
    },
    "cloudy": {
        "description": "Clear alignments but weather prevents tracking",
        "moon_altitude": 45,
        "moon_azimuth": 135,
        "sun_altitude": 40,
        "sun_azimuth": 225,
        "cloud_cover": 85,  # Above threshold
    },
    "low_altitude": {
        "description": "Targets below minimum altitude threshold",
        "moon_altitude": 12,
        "moon_azimuth": 160,
        "sun_altitude": 8,
        "sun_azimuth": 250,
        "cloud_cover": 5,
    },
    "perfect": {
        "description": "Perfect conditions with well-separated targets",
        "moon_altitude": 40,
        "moon_azimuth": 135,   # SE - well separated from sun
        "sun_altitude": 35,
        "sun_azimuth": 225,    # SW - 90 degrees from moon
        "cloud_cover": 0,
    },
}


def azimuth_to_offset(azimuth_deg, distance_deg=0.5):
    """Convert azimuth and distance to lat/lon offset from observer."""
    az_rad = math.radians(azimuth_deg)

    # Approximate offsets (this is rough but good enough for test data)
    lat_offset = distance_deg * math.cos(az_rad)
    lon_offset = distance_deg * math.sin(az_rad)

    return lat_offset, lon_offset


def generate_flight_near_target(
    flight_id, target_az, target_alt, offset_factor, heading_offset,
    origin_code, origin_name, dest_code, dest_name,
    altitude_ft=35000, groundspeed=450
):
    """Generate flight positioned relative to a celestial target.

    offset_factor: 0.0 = directly on target, 1.0 = far from target
    heading_offset: degrees to add to target azimuth for heading (use 180 for approaching observer)
    """
    # Position aircraft in the direction of the target from observer
    distance = 0.3 + (offset_factor * 0.5)  # 0.3 to 0.8 degrees
    lat_offset, lon_offset = azimuth_to_offset(target_az, distance)

    # Add some angular variation based on offset_factor for medium/low probabilities
    if offset_factor > 0.15:
        # Add perpendicular offset for medium/low probabilities
        perp_az = (target_az + 90) % 360
        perp_distance = offset_factor * 0.2  # Reduced from 0.3
        perp_lat, perp_lon = azimuth_to_offset(perp_az, perp_distance)
        lat_offset += perp_lat
        lon_offset += perp_lon

    current_lat = OBSERVER_LAT + lat_offset
    current_lon = OBSERVER_LON + lon_offset

    # Clamp to bounding box (32.0-33.5 lat, -118.0 to -117.0 lon)
    current_lat = max(32.0, min(33.5, current_lat))
    current_lon = max(-118.0, min(-117.0, current_lon))

    # Calculate heading (normalize to 0-360)
    heading = (target_az + heading_offset) % 360

    return generate_flight_data(
        flight_id, origin_code, origin_name, dest_code, dest_name,
        current_lat, current_lon, altitude_ft, groundspeed, heading
    )


def generate_flight_data(
    flight_id,
    origin_code,
    origin_name,
    dest_code,
    dest_name,
    current_lat,
    current_lon,
    altitude_ft,
    groundspeed_knots,
    heading,
    altitude_change="-",
):
    """Generate a single flight data entry."""
    now = datetime.now(timezone.utc)

    # Handle N/D (no destination) flights
    destination = None
    if dest_code and dest_name:
        destination = {
            "code": dest_code,
            "code_icao": dest_code,
            "code_iata": dest_code[-3:],
            "name": dest_name,
            "city": dest_name.split()[0],
        }

    return {
        "ident": flight_id,
        "ident_icao": flight_id,
        "ident_iata": flight_id[:2] + flight_id[3:] if len(flight_id) > 3 else flight_id,
        "fa_flight_id": f"{flight_id}-{int(now.timestamp())}-schedule-test",
        "actual_off": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actual_on": "None",
        "origin": {
            "code": origin_code,
            "code_icao": origin_code,
            "code_iata": origin_code[-3:] if origin_code else "UNK",
            "name": origin_name,
            "city": origin_name.split()[0] if origin_name else "Unknown",
        },
        "destination": destination,
        "waypoints": [],
        "last_position": {
            "fa_flight_id": f"{flight_id}-{int(now.timestamp())}-schedule-test",
            "altitude": altitude_ft,
            "altitude_change": altitude_change,
            "groundspeed": groundspeed_knots,
            "heading": heading,
            "latitude": current_lat,
            "longitude": current_lon,
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "update_type": "A",
        },
        "aircraft_type": "A320",
    }


def generate_test_data(scenario_name="dual_tracking", custom_config=None):
    """Generate test flight data based on scenario."""

    if custom_config:
        config = custom_config
    else:
        config = SCENARIOS.get(scenario_name, SCENARIOS["dual_tracking"])

    moon_alt = config["moon_altitude"]
    moon_az = config.get("moon_azimuth", 180)
    sun_alt = config["sun_altitude"]
    sun_az = config.get("sun_azimuth", 200)

    print(f"Generating test data: {config.get('description', scenario_name)}")
    print(f"  Observer: lat={OBSERVER_LAT}, lon={OBSERVER_LON}")
    print(f"  Moon: alt={moon_alt}°, az={moon_az}°")
    print(f"  Sun: alt={sun_alt}°, az={sun_az}°")
    print(f"  Separation: {abs(moon_az - sun_az)}° azimuth")
    print(f"  Cloud cover: {config['cloud_cover']}%")

    flights = []

    # STATIC POSITIONING with RANDOM offsets within criteria
    # Observer at (33.11, -117.31)
    # Moon target: az=135°, alt=40°
    # Sun target: az=225°, alt=35°

    import random
    random.seed(42)  # Consistent test data

    # Fixed offsets for consistent classification
    # HIGH: both Δ < 1°, MEDIUM: both Δ 1-2°, LOW: both Δ 2-10°
    HIGH_OFFSET = 0.2    # Produces Δ ~0.2-0.5°
    MED_OFFSET = 1.0     # Produces Δ ~1-2°
    LOW_OFFSET = 3.0     # Produces Δ ~2-10°

    def position_at_azimuth(azimuth_deg, target_alt_angle, aircraft_alt_ft):
        """Calculate lat/lon at specific azimuth and distance for target altitude angle.

        For altitude angle calculation:
        altitude_angle ≈ arctan((aircraft_alt_ft - observer_alt_m*3.28) / horizontal_distance_ft)

        So: horizontal_distance_ft = (aircraft_alt_ft - observer_alt_ft) / tan(altitude_angle)
        """
        observer_alt_ft = 100 * 3.28  # 100m to feet

        # Calculate required horizontal distance for target altitude angle
        alt_angle_rad = math.radians(target_alt_angle)
        horizontal_dist_ft = (aircraft_alt_ft - observer_alt_ft) / math.tan(alt_angle_rad)

        # Convert feet to degrees (1 degree ≈ 364,000 feet at this latitude)
        distance_deg = horizontal_dist_ft / 364000.0

        # Position at the calculated distance along the azimuth
        az_rad = math.radians(azimuth_deg)
        lat = OBSERVER_LAT + distance_deg * math.cos(az_rad)
        lon = OBSERVER_LON + distance_deg * math.sin(az_rad)

        # Clamp to bounding box
        lat = max(32.0, min(33.5, lat))
        lon = max(-118.0, min(-117.0, lon))
        return lat, lon

    # Generate flights for Moon transits (if moon is visible)
    if moon_alt >= 15:
        # MOON HIGH - fixed small offsets
        target_alt_angle = moon_alt + HIGH_OFFSET
        alt_ft = 35000
        lat, lon = position_at_azimuth(moon_az + HIGH_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "MOON_HIGH", "KLAX", "Los Angeles International",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 450, random.randint(0, 360)
        ))

        # MOON MEDIUM - fixed medium offsets
        target_alt_angle = moon_alt - MED_OFFSET
        alt_ft = 36000
        lat, lon = position_at_azimuth(moon_az - MED_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "MOON_MED", "KPHX", "Phoenix Sky Harbor",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 460, random.randint(0, 360)
        ))

        # MOON LOW - fixed large offsets
        target_alt_angle = moon_alt + LOW_OFFSET
        alt_ft = 37000
        lat, lon = position_at_azimuth(moon_az + LOW_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "MOON_LOW", "KSFO", "San Francisco International",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 480, random.randint(0, 360)
        ))

    # Generate flights for Sun transits (if sun is visible)
    if sun_alt >= 15:
        # SUN HIGH - fixed small offsets
        target_alt_angle = sun_alt - HIGH_OFFSET
        alt_ft = 34000
        lat, lon = position_at_azimuth(sun_az - HIGH_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "SUN_HIGH", "KLAS", "Las Vegas McCarran",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 440, random.randint(0, 360)
        ))

        # SUN MEDIUM - fixed medium offsets
        target_alt_angle = sun_alt + MED_OFFSET
        alt_ft = 33000
        lat, lon = position_at_azimuth(sun_az + MED_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "SUN_MED", "KDEN", "Denver International",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 420, random.randint(0, 360)
        ))

        # SUN LOW - fixed large offsets
        target_alt_angle = sun_alt - LOW_OFFSET
        alt_ft = 36000
        lat, lon = position_at_azimuth(sun_az - LOW_OFFSET, target_alt_angle, alt_ft)
        flights.append(generate_flight_data(
            "SUN_LOW", "KOAK", "Oakland International",
            "KSAN", "San Diego International",
            lat, lon, alt_ft, 470, random.randint(0, 360)
        ))

    # NONE probability - far from both targets (>20° offset)
    alt_ft = random.randint(30000, 35000)
    lat, lon = position_at_azimuth(90, 20, alt_ft)  # East, random alt angle
    flights.append(generate_flight_data(
        "NONE_01", "KSAN", "San Diego International",
        "KSFO", "San Francisco International",
        lat, lon, alt_ft, 450, random.randint(0, 360)
    ))

    alt_ft = random.randint(32000, 36000)
    lat, lon = position_at_azimuth(180, 25, alt_ft)  # South, random alt angle
    flights.append(generate_flight_data(
        "NONE_02", "KSAN", "San Diego International",
        "KDEN", "Denver International",
        lat, lon, alt_ft, 460, random.randint(0, 360)
    ))

    # N/D destination flight
    alt_ft = random.randint(28000, 32000)
    lat, lon = position_at_azimuth(270, 15, alt_ft)  # West, random alt angle
    nd_flight = generate_flight_data(
        "PRIV01", "KSAN", "San Diego International",
        None, None,
        lat, lon, alt_ft, 380, random.randint(0, 360)
    )
    nd_flight["destination"] = None
    flights.append(nd_flight)

    result = {
        "flights": flights,
        "links": "None",
        "num_pages": 1,
        "_test_metadata": {
            "scenario": scenario_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "observer_latitude": OBSERVER_LAT,
            "observer_longitude": OBSERVER_LON,
            "moon_altitude": moon_alt,
            "moon_azimuth": moon_az,
            "sun_altitude": sun_alt,
            "sun_azimuth": sun_az,
            "cloud_cover": config["cloud_cover"],
        }
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Generate test flight data")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="dual_tracking",
        help="Pre-configured scenario",
    )
    parser.add_argument(
        "--output",
        default="data/raw_flight_data_example.json",
        help="Output file path",
    )
    parser.add_argument("--custom", action="store_true", help="Interactive custom configuration")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")
    
    args = parser.parse_args()
    
    if args.list_scenarios:
        print("\nAvailable test scenarios:\n")
        for name, config in SCENARIOS.items():
            print(f"  {name:20s} - {config['description']}")
        print("\nUsage: python data/test_data_generator.py --scenario <name>")
        return
    
    custom_config = None
    if args.custom:
        print("\n=== Custom Configuration ===")
        custom_config = {
            "moon_altitude": float(input("Moon altitude (degrees): ")),
            "moon_azimuth": float(input("Moon azimuth (degrees): ")),
            "sun_altitude": float(input("Sun altitude (degrees): ")),
            "sun_azimuth": float(input("Sun azimuth (degrees): ")),
            "cloud_cover": float(input("Cloud cover percentage: ")),
        }

    data = generate_test_data(args.scenario, custom_config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Test data generated: {output_path}")
    print(f"  Total flights: {len(data['flights'])}")
    meta = data['_test_metadata']
    print(f"  Moon: {meta['moon_altitude']}° alt, {meta['moon_azimuth']}° az")
    print(f"  Sun: {meta['sun_altitude']}° alt, {meta['sun_azimuth']}° az")
    print(f"\nRun with: python3 app.py --test")


if __name__ == "__main__":
    main()
