#!/usr/bin/env python3
"""
Transit Algorithm Validator

Comprehensive test suite to validate the transit detection and classification
algorithm. Generates synthetic test cases with known geometric properties and
verifies the algorithm produces correct results.

Test Categories:
1. Threshold Boundaries - Test exact classification boundaries
2. Direct Transits - Aircraft passing through target center
3. Approach Angles - Various flight path geometries
4. Altitude Variations - Different aircraft altitudes
5. Edge Cases - Minimum altitude, horizon proximity

Classification Thresholds:
- HIGH: angular_separation ≤ 1.0°
- MEDIUM: angular_separation ≤ 2.0°
- LOW: angular_separation ≤ 6.0°
- UNLIKELY: angular_separation > 6.0°
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from skyfield.api import Topos, wgs84

from src.astro import CelestialObject
from src.constants import ASTRO_EPHEMERIS, EARTH_TIMESCALE
from src.position import geographic_to_altaz, predict_position
from src.transit import calculate_angular_separation, check_transit, get_possibility_level


# Test configuration
OBSERVER_LAT = 33.11
OBSERVER_LON = -117.31
OBSERVER_ELEV = 100  # meters

TARGET_ALT = 40.0  # degrees
TARGET_AZ = 180.0  # degrees (due south)
MIN_ALTITUDE_THRESHOLD = 15.0  # degrees

EARTH = ASTRO_EPHEMERIS["earth"]


class TestCase:
    """Represents a single test case with expected results."""

    def __init__(self, name, description, aircraft_lat, aircraft_lon, aircraft_alt_m,
                 aircraft_speed_kmh, aircraft_heading, expected_separation,
                 expected_classification):
        self.name = name
        self.description = description
        self.aircraft_lat = aircraft_lat
        self.aircraft_lon = aircraft_lon
        self.aircraft_alt_m = aircraft_alt_m
        self.aircraft_speed_kmh = aircraft_speed_kmh
        self.aircraft_heading = aircraft_heading
        self.expected_separation = expected_separation
        self.expected_classification = expected_classification

    def to_flight_dict(self):
        """Convert to flight data dictionary format."""
        return {
            "name": self.name,
            "latitude": self.aircraft_lat,
            "longitude": self.aircraft_lon,
            "elevation": self.aircraft_alt_m,
            "speed": self.aircraft_speed_kmh,
            "direction": self.aircraft_heading,
            "origin": "TEST_ORIGIN",
            "destination": "TEST_DEST",
            "elevation_change": "-",
        }


def calculate_position_at_bearing(lat, lon, bearing_deg, distance_km):
    """Calculate lat/lon at a specific bearing and distance from a point.

    Uses Haversine formula for accurate positioning on sphere.
    """
    R = 6371  # Earth radius in km
    d = distance_km / R  # Angular distance

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_deg)

    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(d) +
        math.cos(lat_rad) * math.sin(d) * math.cos(bearing_rad)
    )

    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(d) * math.cos(lat_rad),
        math.cos(d) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )

    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)


def calculate_ground_truth_separation(aircraft_lat, aircraft_lon, aircraft_alt_m,
                                      observer_lat, observer_lon, observer_elev_m,
                                      target_alt_deg, target_az_deg):
    """Calculate the true angular separation using geometric calculations.

    This is our "ground truth" - independent calculation to verify algorithm.
    """
    # Calculate aircraft alt-az from observer
    my_position = EARTH + wgs84.latlon(observer_lat, observer_lon, elevation_m=observer_elev_m)

    ref_datetime = datetime.now(timezone.utc)
    time_ = EARTH_TIMESCALE.from_datetime(ref_datetime)

    aircraft_position = EARTH + wgs84.latlon(aircraft_lat, aircraft_lon, elevation_m=aircraft_alt_m)
    aircraft_alt, aircraft_az, _ = (aircraft_position - my_position).at(time_).altaz()

    # Calculate angular separation from target
    alt_diff = abs(aircraft_alt.degrees - target_alt_deg)
    az_diff = abs(aircraft_az.degrees - target_az_deg)

    # Handle azimuth wrap-around (e.g., 359° vs 1°)
    if az_diff > 180:
        az_diff = 360 - az_diff

    angular_sep = math.sqrt(alt_diff**2 + az_diff**2)

    return angular_sep, alt_diff, az_diff, aircraft_alt.degrees, aircraft_az.degrees


def generate_test_cases():
    """Generate comprehensive set of test cases."""

    test_cases = []

    # Distance that puts aircraft at roughly 40° altitude (matching target)
    # For 35,000 ft altitude, this is approximately 15-20 km
    base_distance_km = 15

    # ========================================================================
    # CATEGORY 1: Threshold Boundary Tests
    # ========================================================================

    # HIGH/MEDIUM boundary (1.0°)
    test_cases.append(TestCase(
        name="BOUNDARY_HIGH_0.99",
        description="Just inside HIGH threshold (0.99°)",
        aircraft_lat=OBSERVER_LAT + 0.007,  # Offset to create ~0.99° separation
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,  # 35,000 ft
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=0.99,
        expected_classification=3  # HIGH
    ))

    test_cases.append(TestCase(
        name="BOUNDARY_MED_1.01",
        description="Just outside HIGH threshold (1.01°)",
        aircraft_lat=OBSERVER_LAT + 0.0072,  # Offset to create ~1.01° separation
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=1.01,
        expected_classification=2  # MEDIUM
    ))

    # MEDIUM/LOW boundary (2.0°)
    test_cases.append(TestCase(
        name="BOUNDARY_MED_1.99",
        description="Just inside MEDIUM threshold (1.99°)",
        aircraft_lat=OBSERVER_LAT + 0.014,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=1.99,
        expected_classification=2  # MEDIUM
    ))

    test_cases.append(TestCase(
        name="BOUNDARY_LOW_2.01",
        description="Just outside MEDIUM threshold (2.01°)",
        aircraft_lat=OBSERVER_LAT + 0.0143,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=2.01,
        expected_classification=1  # LOW
    ))

    # LOW/UNLIKELY boundary (6.0°)
    test_cases.append(TestCase(
        name="BOUNDARY_LOW_5.99",
        description="Just inside LOW threshold (5.99°)",
        aircraft_lat=OBSERVER_LAT + 0.0427,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=5.99,
        expected_classification=1  # LOW
    ))

    test_cases.append(TestCase(
        name="BOUNDARY_UNLIKELY_6.01",
        description="Just outside LOW threshold (6.01°)",
        aircraft_lat=OBSERVER_LAT + 0.0428,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=6.01,
        expected_classification=0  # UNLIKELY
    ))

    # ========================================================================
    # CATEGORY 2: Direct Transit Tests
    # ========================================================================

    # Perfect alignment - aircraft exactly at target position
    lat, lon = calculate_position_at_bearing(OBSERVER_LAT, OBSERVER_LON, TARGET_AZ, base_distance_km)
    test_cases.append(TestCase(
        name="DIRECT_TRANSIT_0.0",
        description="Perfect alignment - aircraft at target center",
        aircraft_lat=lat,
        aircraft_lon=lon,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=0.0,
        expected_classification=3  # HIGH
    ))

    # ========================================================================
    # CATEGORY 3: Approach Angle Tests
    # ========================================================================

    # Same angular separation (0.5°) but different approach directions
    for angle_name, heading in [("HEAD_ON", 0), ("PERPENDICULAR", 90),
                                  ("OBLIQUE_45", 45), ("RECEDING", 180)]:
        lat, lon = calculate_position_at_bearing(OBSERVER_LAT, OBSERVER_LON, TARGET_AZ + 2, base_distance_km)
        test_cases.append(TestCase(
            name=f"APPROACH_{angle_name}_0.5",
            description=f"0.5° separation, {angle_name} approach",
            aircraft_lat=lat,
            aircraft_lon=lon,
            aircraft_alt_m=10668,
            aircraft_speed_kmh=800,
            aircraft_heading=heading,
            expected_separation=0.5,
            expected_classification=3  # HIGH
        ))

    # ========================================================================
    # CATEGORY 4: Altitude Variation Tests
    # ========================================================================

    # Same angular separation but different aircraft altitudes
    for alt_name, alt_ft, alt_m in [("LOW", 10000, 3048), ("MED", 25000, 7620),
                                      ("HIGH", 45000, 13716)]:
        lat, lon = calculate_position_at_bearing(OBSERVER_LAT, OBSERVER_LON, TARGET_AZ + 1, base_distance_km)
        test_cases.append(TestCase(
            name=f"ALTITUDE_{alt_name}_1.0",
            description=f"1.0° separation at {alt_ft} ft",
            aircraft_lat=lat,
            aircraft_lon=lon,
            aircraft_alt_m=alt_m,
            aircraft_speed_kmh=800,
            aircraft_heading=0,
            expected_separation=1.0,
            expected_classification=3  # HIGH (should be altitude-independent)
        ))

    # ========================================================================
    # CATEGORY 5: Edge Cases
    # ========================================================================

    # Target at minimum altitude threshold
    test_cases.append(TestCase(
        name="EDGE_MIN_ALTITUDE",
        description="Target exactly at minimum altitude (15°)",
        aircraft_lat=OBSERVER_LAT + 0.007,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=800,
        aircraft_heading=0,
        expected_separation=0.5,
        expected_classification=3  # HIGH
    ))

    # Very fast aircraft
    test_cases.append(TestCase(
        name="EDGE_FAST_AIRCRAFT",
        description="Very fast aircraft (600 kts = 1111 km/h)",
        aircraft_lat=OBSERVER_LAT + 0.007,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=10668,
        aircraft_speed_kmh=1111,
        aircraft_heading=0,
        expected_separation=0.5,
        expected_classification=3  # HIGH (speed shouldn't affect classification)
    ))

    # Very slow aircraft
    test_cases.append(TestCase(
        name="EDGE_SLOW_AIRCRAFT",
        description="Very slow aircraft (100 kts = 185 km/h)",
        aircraft_lat=OBSERVER_LAT + 0.007,
        aircraft_lon=OBSERVER_LON,
        aircraft_alt_m=3048,  # Lower altitude for slow plane
        aircraft_speed_kmh=185,
        aircraft_heading=0,
        expected_separation=0.5,
        expected_classification=3  # HIGH (speed shouldn't affect classification)
    ))

    return test_cases


def run_test(test_case, my_position, target, ref_datetime):
    """Run a single test case and return results."""

    # Generate flight data
    flight = test_case.to_flight_dict()

    # Calculate ground truth
    ground_truth_sep, gt_alt_diff, gt_az_diff, aircraft_alt, aircraft_az = \
        calculate_ground_truth_separation(
            test_case.aircraft_lat, test_case.aircraft_lon, test_case.aircraft_alt_m,
            OBSERVER_LAT, OBSERVER_LON, OBSERVER_ELEV,
            TARGET_ALT, TARGET_AZ
        )

    # Run algorithm
    window_time = np.linspace(0, 15, 900)  # 15 minutes, 1 second intervals
    result = check_transit(
        flight,
        window_time,
        ref_datetime,
        my_position,
        target,
        EARTH,
        test_mode=False
    )

    # Extract results
    algorithm_sep = result.get("angular_separation")
    algorithm_classification = result.get("possibility_level")
    algorithm_alt_diff = result.get("alt_diff")
    algorithm_az_diff = result.get("az_diff")

    # Verify classification
    expected_classification_value = test_case.expected_classification

    # Check if test passed
    passed = True
    errors = []

    if algorithm_classification != expected_classification_value:
        passed = False
        errors.append(f"Classification mismatch: expected {expected_classification_value}, got {algorithm_classification}")

    # Allow small tolerance for angular separation (0.1°)
    if algorithm_sep is not None and abs(ground_truth_sep - algorithm_sep) > 0.1:
        passed = False
        errors.append(f"Separation mismatch: ground_truth={ground_truth_sep:.3f}°, algorithm={algorithm_sep:.3f}°")

    return {
        "test_name": test_case.name,
        "description": test_case.description,
        "passed": passed,
        "errors": errors,
        "ground_truth": {
            "angular_separation": round(ground_truth_sep, 3),
            "alt_diff": round(gt_alt_diff, 3),
            "az_diff": round(gt_az_diff, 3),
            "aircraft_alt": round(aircraft_alt, 2),
            "aircraft_az": round(aircraft_az, 2),
        },
        "algorithm": {
            "angular_separation": algorithm_sep,
            "alt_diff": algorithm_alt_diff,
            "az_diff": algorithm_az_diff,
            "classification": algorithm_classification,
        },
        "expected": {
            "classification": expected_classification_value,
        }
    }


def main():
    """Run the complete test suite."""

    print("=" * 80)
    print("TRANSIT ALGORITHM VALIDATION SUITE")
    print("=" * 80)
    print()
    print("Testing configuration:")
    print(f"  Observer: ({OBSERVER_LAT}, {OBSERVER_LON}) at {OBSERVER_ELEV}m")
    print(f"  Target: altitude={TARGET_ALT}°, azimuth={TARGET_AZ}°")
    print(f"  Minimum altitude threshold: {MIN_ALTITUDE_THRESHOLD}°")
    print()
    print("Classification thresholds:")
    print("  HIGH:     angular_separation ≤ 1.0°")
    print("  MEDIUM:   angular_separation ≤ 2.0°")
    print("  LOW:      angular_separation ≤ 6.0°")
    print("  UNLIKELY: angular_separation > 6.0°")
    print()
    print("=" * 80)
    print()

    # Setup
    my_position = EARTH + wgs84.latlon(OBSERVER_LAT, OBSERVER_LON, elevation_m=OBSERVER_ELEV)

    # Create mock target with fixed position (use "moon" as name, but override position)
    target = CelestialObject(
        name="moon",
        observer_position=my_position,
        test_overrides={"altitude": TARGET_ALT, "azimuth": TARGET_AZ}
    )

    ref_datetime = datetime.now(timezone.utc)
    target.update_position(ref_datetime)

    # Generate test cases
    test_cases = generate_test_cases()
    print(f"Generated {len(test_cases)} test cases\n")

    # Run tests
    results = []
    passed_count = 0
    failed_count = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] Running: {test_case.name}...")
        result = run_test(test_case, my_position, target, ref_datetime)
        results.append(result)

        if result["passed"]:
            passed_count += 1
            print(f"  ✓ PASS")
        else:
            failed_count += 1
            print(f"  ✗ FAIL")
            for error in result["errors"]:
                print(f"    - {error}")
        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests:  {len(test_cases)}")
    print(f"Passed:       {passed_count} ({100*passed_count/len(test_cases):.1f}%)")
    print(f"Failed:       {failed_count} ({100*failed_count/len(test_cases):.1f}%)")
    print()

    if failed_count > 0:
        print("FAILED TESTS:")
        print("-" * 80)
        for result in results:
            if not result["passed"]:
                print(f"\n{result['test_name']}: {result['description']}")
                print(f"  Expected classification: {result['expected']['classification']}")
                print(f"  Algorithm classification: {result['algorithm']['classification']}")
                print(f"  Ground truth separation: {result['ground_truth']['angular_separation']}°")
                print(f"  Algorithm separation: {result['algorithm']['angular_separation']}°")
                for error in result["errors"]:
                    print(f"  ERROR: {error}")
        print()

    # Save detailed results to JSON
    output_file = Path(__file__).parent / "test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to: {output_file}")
    print()

    # Return exit code
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
