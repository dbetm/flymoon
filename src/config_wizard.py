#!/usr/bin/env python3
"""
Configuration wizard and validator for Flymoon.
Handles first-run setup and configuration validation.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key, find_dotenv


class ConfigWizard:
    """Interactive configuration wizard for first-time setup."""

    def __init__(self, config_file=None):
        self.config_file = config_file or find_dotenv() or Path(".env")
        self.errors = []
        self.warnings = []

    def validate(self, interactive=False):
        """
        Validate configuration and optionally run interactive setup.

        Returns:
            bool: True if config is valid, False otherwise
        """
        load_dotenv(self.config_file)

        # Check critical settings
        self._check_aeroapi_key()
        self._check_weather_key()
        self._check_coordinates()
        self._check_bounding_box()

        if interactive:
            return self._run_interactive_setup()

        return len(self.errors) == 0

    def _check_aeroapi_key(self):
        """Check FlightAware AeroAPI key."""
        key = os.getenv("AEROAPI_API_KEY")
        if not key:
            self.errors.append({
                "field": "AEROAPI_API_KEY",
                "message": "FlightAware AeroAPI key is required for live flight data",
                "severity": "ERROR",
            })

    def _check_weather_key(self):
        """Check OpenWeather API key."""
        key = os.getenv("OPENWEATHER_API_KEY")
        if not key:
            self.warnings.append({
                "field": "OPENWEATHER_API_KEY",
                "message": "OpenWeather API key missing (weather filtering disabled)",
                "severity": "WARNING",
            })

    def _check_coordinates(self):
        """Check observer coordinates."""
        lat = os.getenv("OBSERVER_LATITUDE")
        lon = os.getenv("OBSERVER_LONGITUDE")

        if not lat or not lon:
            self.errors.append({
                "field": "OBSERVER_COORDINATES",
                "message": "Observer coordinates not set",
                "severity": "ERROR",
            })
        else:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                if not (-90 <= lat_f <= 90):
                    self.errors.append({
                        "field": "OBSERVER_LATITUDE",
                        "message": f"Invalid latitude: {lat} (must be -90 to 90)",
                        "severity": "ERROR"
                    })
                if not (-180 <= lon_f <= 180):
                    self.errors.append({
                        "field": "OBSERVER_LONGITUDE",
                        "message": f"Invalid longitude: {lon} (must be -180 to 180)",
                        "severity": "ERROR"
                    })
            except ValueError:
                self.errors.append({
                    "field": "OBSERVER_COORDINATES",
                    "message": "Coordinates must be numeric",
                    "severity": "ERROR"
                })

    def _check_bounding_box(self):
        """Check flight search bounding box."""
        fields = ["LAT_LOWER_LEFT", "LONG_LOWER_LEFT", "LAT_UPPER_RIGHT", "LONG_UPPER_RIGHT"]
        values = {f: os.getenv(f) for f in fields}

        missing = [f for f, v in values.items() if not v]
        if missing:
            self.errors.append({
                "field": "BOUNDING_BOX",
                "message": f"Bounding box incomplete (missing: {', '.join(missing)})",
                "severity": "ERROR",
            })

    def _prompt(self, message, default=None, required=True):
        """Prompt user for input with optional default."""
        if default:
            prompt_str = f"{message} [{default}]: "
        else:
            prompt_str = f"{message}: "

        while True:
            value = input(prompt_str).strip()
            if not value and default:
                return default
            if not value and required:
                print("  This field is required. Please enter a value.")
                continue
            if not value and not required:
                return None
            return value

    def _prompt_float(self, message, default=None, min_val=None, max_val=None):
        """Prompt for a float value with validation."""
        while True:
            value = self._prompt(message, default=str(default) if default else None)
            try:
                f_val = float(value)
                if min_val is not None and f_val < min_val:
                    print(f"  Value must be at least {min_val}")
                    continue
                if max_val is not None and f_val > max_val:
                    print(f"  Value must be at most {max_val}")
                    continue
                return f_val
            except ValueError:
                print("  Please enter a valid number")

    def _prompt_yes_no(self, message, default=True):
        """Prompt for yes/no with default."""
        default_str = "Y/n" if default else "y/N"
        while True:
            value = input(f"{message} [{default_str}]: ").strip().lower()
            if not value:
                return default
            if value in ('y', 'yes'):
                return True
            if value in ('n', 'no'):
                return False
            print("  Please enter 'y' or 'n'")

    def _run_interactive_setup(self):
        """Run interactive setup wizard."""
        print("\n" + "="*60)
        print("  Flymoon Configuration Wizard")
        print("="*60)
        print("\nThis wizard will help you configure Flymoon step by step.")
        print("You can press Ctrl+C at any time to cancel.\n")

        try:
            self._setup_api_keys()
            self._setup_observer_location()
            self._setup_bounding_box()
            self._setup_optional_settings()
        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            return False

        print("\n" + "="*60)
        print("  Configuration Complete!")
        print("="*60)
        print(f"\nSettings saved to: {self.config_file}")
        print("\nTo start Flymoon:")
        print("  python3 app.py")
        print("\nThen open: http://localhost:8000")
        print("")

        return True

    def _setup_api_keys(self):
        """Setup API keys."""
        print("-" * 40)
        print("STEP 1: API Keys")
        print("-" * 40)

        # FlightAware API Key
        print("\nFlightAware AeroAPI key (REQUIRED)")
        print("  Get a free key at: https://flightaware.com/aeroapi/signup/personal")
        print("  This is needed to fetch real-time flight data.")

        current = os.getenv("AEROAPI_API_KEY")
        if current:
            print(f"  Current: {current[:8]}...")
            if not self._prompt_yes_no("  Change API key?", default=False):
                return

        key = self._prompt("  Enter your FlightAware API key")
        set_key(self.config_file, "AEROAPI_API_KEY", key)
        print("  Saved!")

    def _setup_observer_location(self):
        """Setup observer location."""
        print("\n" + "-" * 40)
        print("STEP 2: Your Location")
        print("-" * 40)
        print("\nEnter your observation location (where you'll watch transits).")
        print("  Find coordinates at: https://www.maps.ie/coordinates.html")
        print("  Or use Google Maps: right-click any location to see coordinates.")

        current_lat = os.getenv("OBSERVER_LATITUDE")
        current_lon = os.getenv("OBSERVER_LONGITUDE")
        current_elev = os.getenv("OBSERVER_ELEVATION", "0")

        if current_lat and current_lon:
            print(f"\n  Current location: {current_lat}, {current_lon} (elev: {current_elev}m)")
            if not self._prompt_yes_no("  Change location?", default=False):
                return

        print("")
        lat = self._prompt_float("  Latitude (e.g., 33.12)", min_val=-90, max_val=90)
        lon = self._prompt_float("  Longitude (e.g., -117.31)", min_val=-180, max_val=180)
        elev = self._prompt_float("  Elevation in meters (e.g., 35)", default=0, min_val=0, max_val=10000)

        set_key(self.config_file, "OBSERVER_LATITUDE", str(lat))
        set_key(self.config_file, "OBSERVER_LONGITUDE", str(lon))
        set_key(self.config_file, "OBSERVER_ELEVATION", str(elev))

        # Store for bounding box calculation
        self._observer_lat = lat
        self._observer_lon = lon

        print("  Saved!")

    def _setup_bounding_box(self):
        """Setup flight search bounding box."""
        print("\n" + "-" * 40)
        print("STEP 3: Flight Search Area")
        print("-" * 40)
        print("\nThe bounding box defines the area to search for flights.")
        print("It should cover roughly a 15-minute flight radius from your location.")

        # Check if we have observer location for auto-calculation
        obs_lat = getattr(self, '_observer_lat', None) or os.getenv("OBSERVER_LATITUDE")
        obs_lon = getattr(self, '_observer_lon', None) or os.getenv("OBSERVER_LONGITUDE")

        if obs_lat and obs_lon:
            try:
                obs_lat = float(obs_lat)
                obs_lon = float(obs_lon)

                # Calculate suggested bounding box (±2 degrees ≈ 220km ≈ 15min at 500mph)
                suggested = {
                    "LAT_LOWER_LEFT": round(obs_lat - 2, 3),
                    "LONG_LOWER_LEFT": round(obs_lon - 2, 3),
                    "LAT_UPPER_RIGHT": round(obs_lat + 2, 3),
                    "LONG_UPPER_RIGHT": round(obs_lon + 2, 3),
                }

                print(f"\n  Suggested bounding box (based on your location ±2 degrees):")
                print(f"    Lower-left:  ({suggested['LAT_LOWER_LEFT']}, {suggested['LONG_LOWER_LEFT']})")
                print(f"    Upper-right: ({suggested['LAT_UPPER_RIGHT']}, {suggested['LONG_UPPER_RIGHT']})")

                if self._prompt_yes_no("\n  Use suggested bounding box?", default=True):
                    for key, value in suggested.items():
                        set_key(self.config_file, key, str(value))
                    print("  Saved!")
                    return
            except (ValueError, TypeError):
                pass

        # Manual entry
        print("\n  Enter bounding box coordinates manually:")
        print("  (Lower-left is southwest corner, upper-right is northeast corner)")

        lat_ll = self._prompt_float("  Lower-left latitude", min_val=-90, max_val=90)
        lon_ll = self._prompt_float("  Lower-left longitude", min_val=-180, max_val=180)
        lat_ur = self._prompt_float("  Upper-right latitude", min_val=-90, max_val=90)
        lon_ur = self._prompt_float("  Upper-right longitude", min_val=-180, max_val=180)

        set_key(self.config_file, "LAT_LOWER_LEFT", str(lat_ll))
        set_key(self.config_file, "LONG_LOWER_LEFT", str(lon_ll))
        set_key(self.config_file, "LAT_UPPER_RIGHT", str(lat_ur))
        set_key(self.config_file, "LONG_UPPER_RIGHT", str(lon_ur))

        print("  Saved!")

    def _setup_optional_settings(self):
        """Setup optional settings."""
        print("\n" + "-" * 40)
        print("STEP 4: Optional Settings")
        print("-" * 40)

        # Auto-refresh interval
        print("\nAuto-refresh interval (optional)")
        print("  Sets how often the app checks for new flights when in auto mode.")
        print("  Recommended: 6 minutes (keeps within FlightAware free tier limits)")
        print("  Range: 5-15 minutes for continuous monitoring")

        current_interval = os.getenv("AUTO_REFRESH_INTERVAL_MINUTES", "6")
        print(f"\n  Current interval: {current_interval} minutes")

        if self._prompt_yes_no("  Change auto-refresh interval?", default=False):
            interval = self._prompt_float("  Enter interval in minutes (e.g., 6)",
                                         default=6, min_val=1, max_val=60)
            set_key(self.config_file, "AUTO_REFRESH_INTERVAL_MINUTES", str(int(interval)))
            print("  Saved!")
        else:
            # Set default if not already set
            if not os.getenv("AUTO_REFRESH_INTERVAL_MINUTES"):
                set_key(self.config_file, "AUTO_REFRESH_INTERVAL_MINUTES", "6")

        # Weather API
        print("\nOpenWeatherMap API key (optional)")
        print("  Enables weather-based filtering (skip checks when cloudy).")
        print("  Get a free key at: https://openweathermap.org/api")

        current = os.getenv("OPENWEATHER_API_KEY")
        if current:
            print(f"  Current: {current[:8]}...")
            if self._prompt_yes_no("  Change weather API key?", default=False):
                key = self._prompt("  Enter OpenWeatherMap API key", required=False)
                if key:
                    set_key(self.config_file, "OPENWEATHER_API_KEY", key)
                    print("  Saved!")
        else:
            if self._prompt_yes_no("  Add weather API key?", default=False):
                key = self._prompt("  Enter OpenWeatherMap API key", required=False)
                if key:
                    set_key(self.config_file, "OPENWEATHER_API_KEY", key)
                    print("  Saved!")
            else:
                print("  Skipped. Weather filtering will be disabled.")
    
    def get_status_report(self):
        """Get human-readable status report."""
        report = []
        
        if not self.errors and not self.warnings:
            report.append("✅ Configuration is valid")
        
        if self.errors:
            report.append(f"\n❌ {len(self.errors)} Error(s):")
            for err in self.errors:
                report.append(f"  • {err['field']}: {err['message']}")
        
        if self.warnings:
            report.append(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for warn in self.warnings:
                report.append(f"  • {warn['field']}: {warn['message']}")
        
        return "\n".join(report)


def quick_setup():
    """Quick setup for first-time users."""
    wizard = ConfigWizard()
    
    if not wizard.validate(interactive=False):
        print("\n🔧 First-time setup required\n")
        wizard.validate(interactive=True)
    else:
        print("✅ Configuration OK")
    
    return wizard


def main():
    """CLI entry point for config wizard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Flymoon Configuration Wizard")
    parser.add_argument("--validate", action="store_true", help="Validate configuration without interactive setup")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup")
    parser.add_argument("--config", help="Path to .env file")
    
    args = parser.parse_args()
    
    wizard = ConfigWizard(args.config)
    
    if args.setup:
        wizard.validate(interactive=True)
    elif args.validate:
        if wizard.validate(interactive=False):
            print("✅ Configuration is valid")
            sys.exit(0)
        else:
            print(wizard.get_status_report())
            sys.exit(1)
    else:
        # Default: run quick setup
        quick_setup()


if __name__ == "__main__":
    main()
