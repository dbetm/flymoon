#!/usr/bin/env python3
"""
Test Data Integration Test

Tests the full transit detection pipeline using synthetically generated
test data. Verifies that flights positioned at known angular separations
are classified correctly.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transit import get_transits


def load_test_data():
    """Load the test flight data."""
    test_file = Path(__file__).parent.parent / "data" / "raw_flight_data_example.json"

    if not test_file.exists():
        print(f"Test data file not found: {test_file}")
        print("Run: python3 data/test_data_generator.py")
        return None

    with open(test_file) as f:
        return json.load(f)


def test_data_classification():
    """Test that test data produces expected classifications."""

    print("=" * 80)
    print("TEST DATA INTEGRATION TEST")
    print("=" * 80)
    print()

    # Load test data
    test_data = load_test_data()
    if not test_data:
        return False

    print(f"Loaded test data with {len(test_data['flights'])} flights")

    # Check if metadata exists
    if "_test_metadata" not in test_data:
        print("Warning: No _test_metadata in test data")
        print("Run: python3 data/test_data_generator.py --scenario dual_tracking")
        return False

    meta = test_data["_test_metadata"]
    print(f"Test scenario: {meta.get('scenario', 'unknown')}")
    print(f"Observer: ({meta.get('observer_latitude')}, {meta.get('observer_longitude')})")
    print(f"Moon: {meta.get('moon_altitude')}° alt, {meta.get('moon_azimuth')}° az")
    print(f"Sun: {meta.get('sun_altitude')}° alt, {meta.get('sun_azimuth')}° az")
    print()

    # Run transit detection in test mode
    print("Running transit detection...")
    print("-" * 80)

    result = get_transits(
        latitude=meta.get('observer_latitude', 33.11),
        longitude=meta.get('observer_longitude', -117.31),
        elevation=100,
        target_name='auto',
        test_mode=True,
        min_altitude=15.0
    )

    # Analyze results
    classifications = {
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
        "UNLIKELY": []
    }

    level_map = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "UNLIKELY"}

    for flight in result['flights']:
        flight_id = flight['id']
        classification = level_map.get(flight['possibility_level'], "UNKNOWN")
        angular_sep = flight.get('angular_separation')

        classifications[classification].append({
            "id": flight_id,
            "angular_sep": angular_sep,
            "alt_diff": flight.get('alt_diff'),
            "az_diff": flight.get('az_diff'),
            "target": flight.get('target')
        })

    # Print results
    print(f"\nResults by classification:")
    print()

    for level_name in ["HIGH", "MEDIUM", "LOW", "UNLIKELY"]:
        flights = classifications[level_name]
        print(f"{level_name}: {len(flights)} flights")
        for flight in flights:
            if flight['angular_sep'] is not None:
                print(f"  {flight['id']}: {flight['angular_sep']}° "
                      f"(alt={flight['alt_diff']}°, az={flight['az_diff']}°) "
                      f"[{flight['target']}]")
            else:
                print(f"  {flight['id']}: No transit [{flight['target']}]")
        print()

    # Validation checks
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)
    print()

    passed = True
    errors = []

    # Check HIGH classifications (should be ≤ 1.0°)
    for flight in classifications["HIGH"]:
        if flight['angular_sep'] and flight['angular_sep'] > 1.0:
            errors.append(f"{flight['id']}: HIGH classification but angular_sep={flight['angular_sep']}° > 1.0°")
            passed = False

    # Check MEDIUM classifications (should be > 1.0° and ≤ 2.0°)
    for flight in classifications["MEDIUM"]:
        if flight['angular_sep'] and (flight['angular_sep'] <= 1.0 or flight['angular_sep'] > 2.0):
            errors.append(f"{flight['id']}: MEDIUM classification but angular_sep={flight['angular_sep']}° not in (1.0, 2.0]")
            passed = False

    # Check LOW classifications (should be > 2.0° and ≤ 6.0°)
    for flight in classifications["LOW"]:
        if flight['angular_sep'] and (flight['angular_sep'] <= 2.0 or flight['angular_sep'] > 6.0):
            errors.append(f"{flight['id']}: LOW classification but angular_sep={flight['angular_sep']}° not in (2.0, 6.0]")
            passed = False

    # Check UNLIKELY classifications (should be > 6.0° or None)
    for flight in classifications["UNLIKELY"]:
        if flight['angular_sep'] is not None and flight['angular_sep'] <= 6.0:
            errors.append(f"{flight['id']}: UNLIKELY classification but angular_sep={flight['angular_sep']}° ≤ 6.0°")
            passed = False

    # Check expected flight IDs exist
    expected_high = ["MOON_HIGH", "SUN_HIGH"]
    expected_medium = ["MOON_MED", "SUN_MED"]
    expected_low = ["MOON_LOW", "SUN_LOW"]

    for expected_id in expected_high:
        if not any(f['id'] == expected_id for f in classifications["HIGH"]):
            errors.append(f"Expected {expected_id} to be HIGH classification")
            passed = False

    for expected_id in expected_medium:
        if not any(f['id'] == expected_id for f in classifications["MEDIUM"]):
            errors.append(f"Expected {expected_id} to be MEDIUM classification")
            passed = False

    for expected_id in expected_low:
        if not any(f['id'] == expected_id for f in classifications["LOW"]):
            errors.append(f"Expected {expected_id} to be LOW classification")
            passed = False

    # Print results
    if passed:
        print("✓ ALL VALIDATIONS PASSED")
        print()
        print("Verification:")
        print("  ✓ All HIGH classifications have angular_sep ≤ 1.0°")
        print("  ✓ All MEDIUM classifications have 1.0° < angular_sep ≤ 2.0°")
        print("  ✓ All LOW classifications have 2.0° < angular_sep ≤ 6.0°")
        print("  ✓ All UNLIKELY classifications have angular_sep > 6.0° or None")
        print("  ✓ Expected flight IDs found in correct classifications")
        print()
        return True
    else:
        print("✗ VALIDATION FAILURES")
        print()
        for error in errors:
            print(f"  - {error}")
        print()
        return False


def main():
    """Run the integration test."""

    success = test_data_classification()

    print("=" * 80)
    if success:
        print("✓ TEST DATA INTEGRATION TEST PASSED")
        print()
        print("The full transit detection pipeline is working correctly:")
        print("  - Test data loaded successfully")
        print("  - Transit detection executed without errors")
        print("  - All flights classified according to angular separation thresholds")
        print("  - Expected classifications match actual results")
        print()
        return 0
    else:
        print("✗ TEST DATA INTEGRATION TEST FAILED")
        print()
        print("Review the errors above.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
