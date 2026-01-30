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
from datetime import datetime, timedelta
from pathlib import Path


# Configurable test scenarios
SCENARIOS = {
    "dual_tracking": {
        "description": "Both Moon and Sun visible with multiple transits",
        "moon_altitude": 40,  # degrees
        "sun_altitude": 35,
        "num_moon_transits": 2,
        "num_sun_transits": 2,
        "num_regular_flights": 6,
        "cloud_cover": 15,  # percent
    },
    "moon_only": {
        "description": "Only Moon visible (daytime, Sun below horizon)",
        "moon_altitude": 25,
        "sun_altitude": -10,
        "num_moon_transits": 3,
        "num_sun_transits": 0,
        "num_regular_flights": 7,
        "cloud_cover": 20,
    },
    "sun_only": {
        "description": "Only Sun visible (daytime, Moon below horizon)",
        "moon_altitude": -5,
        "sun_altitude": 50,
        "num_moon_transits": 0,
        "num_sun_transits": 3,
        "num_regular_flights": 7,
        "cloud_cover": 10,
    },
    "cloudy": {
        "description": "Clear alignments but weather prevents tracking",
        "moon_altitude": 45,
        "sun_altitude": 40,
        "num_moon_transits": 2,
        "num_sun_transits": 2,
        "num_regular_flights": 6,
        "cloud_cover": 85,  # Above threshold
    },
    "low_altitude": {
        "description": "Targets below minimum altitude threshold",
        "moon_altitude": 12,
        "sun_altitude": 8,
        "num_moon_transits": 1,
        "num_sun_transits": 1,
        "num_regular_flights": 8,
        "cloud_cover": 5,
    },
    "perfect": {
        "description": "Perfect conditions with close transits",
        "moon_altitude": 60,
        "sun_altitude": 55,
        "num_moon_transits": 3,
        "num_sun_transits": 3,
        "num_regular_flights": 4,
        "cloud_cover": 0,
    },
}


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
    now = datetime.utcnow()
    
    return {
        "ident": flight_id,
        "ident_icao": flight_id,
        "ident_iata": flight_id[:2] + flight_id[3:],
        "fa_flight_id": f"{flight_id}-{int(now.timestamp())}-schedule-test",
        "actual_off": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actual_on": "None",
        "origin": {
            "code": origin_code,
            "code_icao": origin_code,
            "code_iata": origin_code[-3:],
            "name": origin_name,
            "city": origin_name.split()[0],
        },
        "destination": {
            "code": dest_code,
            "code_icao": dest_code,
            "code_iata": dest_code[-3:],
            "name": dest_name,
            "city": dest_name.split()[0],
        },
        "waypoints": [],  # Simplified
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
    
    print(f"Generating test data: {config.get('description', scenario_name)}")
    print(f"  Moon altitude: {config['moon_altitude']}°")
    print(f"  Sun altitude: {config['sun_altitude']}°")
    print(f"  Cloud cover: {config['cloud_cover']}%")
    
    flights = []
    
    # Observer position (Mexico region, matches real example data)
    base_lat = 23.0
    base_lon = -103.0
    
    # Generate Moon transit flights
    for i in range(config["num_moon_transits"]):
        # Position flights near Moon's predicted position for close transit
        # These will have small alt/az differences
        lat = base_lat + (i * 0.5)
        lon = base_lon + (i * 0.3)
        
        flights.append(generate_flight_data(
            f"MOON{i:03d}",
            "MMMX",
            "Mexico City International",
            "MMTJ",
            "Tijuana International",
            lat,
            lon,
            35000 + (i * 1000),
            450 + (i * 10),
            310 + (i * 5),
            altitude_change="-" if i % 2 == 0 else "C",
        ))
    
    # Generate Sun transit flights
    for i in range(config["num_sun_transits"]):
        lat = base_lat + (i * 0.4) + 1.0
        lon = base_lon + (i * 0.4) - 0.5
        
        flights.append(generate_flight_data(
            f"SUN{i:03d}",
            "MMGL",
            "Guadalajara International",
            "MMML",
            "Mexicali International",
            lat,
            lon,
            36000 + (i * 1000),
            460 + (i * 10),
            315 + (i * 5),
            altitude_change="D" if i % 2 == 0 else "-",
        ))
    
    # Generate regular flights (no transit)
    origins = ["MMMX", "MMGL", "MMHO", "MMOX"]
    destinations = ["MMTJ", "MMML", "MMMY", "MMTO"]
    for i in range(config["num_regular_flights"]):
        # Position away from celestial targets
        lat = base_lat + (i * 1.5) - 3.0
        lon = base_lon + (i * 1.2) + 2.0
        
        flights.append(generate_flight_data(
            f"REG{i:03d}",
            origins[i % len(origins)],
            f"{origins[i % len(origins)]} Airport",
            destinations[i % len(destinations)],
            f"{destinations[i % len(destinations)]} Airport",
            lat,
            lon,
            34000 + (i * 500),
            440 + (i * 5),
            300 + (i * 15),
            altitude_change=["-", "C", "D"][i % 3],
        ))
    
    result = {
        "flights": flights,
        "links": "None",
        "num_pages": 1,
        "_test_metadata": {
            "scenario": scenario_name,
            "generated_at": datetime.utcnow().isoformat(),
            "moon_altitude": config["moon_altitude"],
            "sun_altitude": config["sun_altitude"],
            "cloud_cover": config["cloud_cover"],
            "expected_moon_transits": config["num_moon_transits"],
            "expected_sun_transits": config["num_sun_transits"],
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
            "sun_altitude": float(input("Sun altitude (degrees): ")),
            "num_moon_transits": int(input("Number of Moon transits: ")),
            "num_sun_transits": int(input("Number of Sun transits: ")),
            "num_regular_flights": int(input("Number of regular flights: ")),
            "cloud_cover": float(input("Cloud cover percentage: ")),
        }
    
    data = generate_test_data(args.scenario, custom_config)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✓ Test data generated: {output_path}")
    print(f"  Total flights: {len(data['flights'])}")
    print(f"  Expected Moon transits: {data['_test_metadata']['expected_moon_transits']}")
    print(f"  Expected Sun transits: {data['_test_metadata']['expected_sun_transits']}")
    print(f"\nRun with: python3 app.py --test")


if __name__ == "__main__":
    main()
