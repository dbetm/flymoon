#!/usr/bin/env python3
"""
Transit Classification Logic Test

Simple, direct tests of the classification logic to ensure thresholds are correct.
Tests the core functions without complex geometric calculations.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.transit import calculate_angular_separation, get_possibility_level


def test_angular_separation_calculation():
    """Test that angular separation is calculated correctly."""
    print("Testing angular_separation calculation...")
    print("-" * 60)

    test_cases = [
        # (alt_diff, az_diff, expected_result, description)
        (0, 0, 0.0, "Perfect alignment"),
        (1, 0, 1.0, "1° altitude difference only"),
        (0, 1, 1.0, "1° azimuth difference only"),
        (3, 4, 5.0, "3-4-5 triangle (Pythagorean)"),
        (1, 1, 1.414, "45° diagonal (1° each direction)"),
        (2, 2, 2.828, "45° diagonal (2° each direction)"),
        (5, 5, 7.071, "45° diagonal (5° each direction)"),
    ]

    passed = 0
    failed = 0

    for alt_diff, az_diff, expected, description in test_cases:
        result = calculate_angular_separation(alt_diff, az_diff)
        tolerance = 0.001

        if abs(result - expected) < tolerance:
            print(f"✓ PASS: {description}")
            print(f"  Input: alt_diff={alt_diff}°, az_diff={az_diff}°")
            print(f"  Expected: {expected}°, Got: {result:.3f}°")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Input: alt_diff={alt_diff}°, az_diff={az_diff}°")
            print(f"  Expected: {expected}°, Got: {result:.3f}°")
            failed += 1
        print()

    print(f"Angular Separation Tests: {passed} passed, {failed} failed\n")
    return failed == 0


def test_classification_thresholds():
    """Test that classification thresholds are correct."""
    print("Testing classification thresholds...")
    print("-" * 60)

    test_cases = [
        # (angular_sep, expected_level, expected_name, description)
        (0.0, 3, "HIGH", "Perfect transit"),
        (0.5, 3, "HIGH", "Very close - 0.5°"),
        (0.99, 3, "HIGH", "Just inside HIGH boundary"),
        (1.0, 3, "HIGH", "Exactly at HIGH boundary"),
        (1.01, 2, "MEDIUM", "Just outside HIGH boundary"),
        (1.5, 2, "MEDIUM", "Mid MEDIUM range"),
        (1.99, 2, "MEDIUM", "Just inside MEDIUM boundary"),
        (2.0, 2, "MEDIUM", "Exactly at MEDIUM boundary"),
        (2.01, 1, "LOW", "Just outside MEDIUM boundary"),
        (4.0, 1, "LOW", "Mid LOW range"),
        (5.99, 1, "LOW", "Just inside LOW boundary"),
        (6.0, 1, "LOW", "Exactly at LOW boundary"),
        (6.01, 0, "UNLIKELY", "Just outside LOW boundary"),
        (10.0, 0, "UNLIKELY", "Far from target"),
        (50.0, 0, "UNLIKELY", "Very far from target"),
    ]

    passed = 0
    failed = 0

    for angular_sep, expected_level, expected_name, description in test_cases:
        result = get_possibility_level(angular_sep)

        if result == expected_level:
            print(f"✓ PASS: {description}")
            print(f"  Angular separation: {angular_sep}°")
            print(f"  Expected: {expected_name} ({expected_level}), Got: {expected_name} ({result})")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Angular separation: {angular_sep}°")
            print(f"  Expected: {expected_name} ({expected_level}), Got: {result}")
            failed += 1
        print()

    print(f"Classification Tests: {passed} passed, {failed} failed\n")
    return failed == 0


def test_combined_scenarios():
    """Test combined alt/az differences with classification."""
    print("Testing combined alt/az scenarios...")
    print("-" * 60)

    test_cases = [
        # (alt_diff, az_diff, expected_class, expected_name, description)
        (0.7, 0.7, 3, "HIGH", "0.99° diagonal - HIGH"),
        (0.8, 0.6, 3, "HIGH", "1.0° diagonal - HIGH"),
        (1.4, 1.4, 2, "MEDIUM", "1.98° diagonal - MEDIUM"),
        (1.5, 1.3, 2, "MEDIUM", "1.98° diagonal - MEDIUM"),
        (2.0, 2.0, 1, "LOW", "2.83° diagonal - LOW"),
        (4.0, 4.0, 1, "LOW", "5.66° diagonal - LOW"),
        (4.3, 4.2, 0, "UNLIKELY", "6.01° diagonal - UNLIKELY"),
        (5.0, 5.0, 0, "UNLIKELY", "7.07° diagonal - UNLIKELY"),
    ]

    passed = 0
    failed = 0

    for alt_diff, az_diff, expected_class, expected_name, description in test_cases:
        angular_sep = calculate_angular_separation(alt_diff, az_diff)
        result = get_possibility_level(angular_sep)

        if result == expected_class:
            print(f"✓ PASS: {description}")
            print(f"  Input: alt_diff={alt_diff}°, az_diff={az_diff}°")
            print(f"  Angular separation: {angular_sep:.3f}°")
            print(f"  Classification: {expected_name} ({result})")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Input: alt_diff={alt_diff}°, az_diff={az_diff}°")
            print(f"  Angular separation: {angular_sep:.3f}°")
            print(f"  Expected: {expected_name} ({expected_class}), Got: {result}")
            failed += 1
        print()

    print(f"Combined Scenario Tests: {passed} passed, {failed} failed\n")
    return failed == 0


def main():
    """Run all tests."""
    print("=" * 80)
    print("TRANSIT CLASSIFICATION LOGIC TEST SUITE")
    print("=" * 80)
    print()
    print("Testing the core classification logic:")
    print("  - calculate_angular_separation(alt_diff, az_diff)")
    print("  - get_possibility_level(angular_separation)")
    print()
    print("Classification thresholds:")
    print("  HIGH:     angular_separation ≤ 1.0°")
    print("  MEDIUM:   angular_separation ≤ 2.0°")
    print("  LOW:      angular_separation ≤ 6.0°")
    print("  UNLIKELY: angular_separation > 6.0°")
    print()
    print("=" * 80)
    print()

    all_passed = True

    # Run test suites
    all_passed &= test_angular_separation_calculation()
    all_passed &= test_classification_thresholds()
    all_passed &= test_combined_scenarios()

    # Summary
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print()
        print("The classification logic is working correctly:")
        print("  - Angular separation calculation is accurate")
        print("  - Threshold boundaries are exact")
        print("  - Combined scenarios produce correct classifications")
        print()
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print()
        print("Review the failures above to identify issues.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
