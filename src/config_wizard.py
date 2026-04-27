import os
import sys
import getpass
from pathlib import Path

from dotenv import load_dotenv, set_key, find_dotenv


class ConfigWizard:
    """Configuration wizard and validator for Flymoon. Handles first-run setup 
    and configuration validation.
    """

    def __init__(self, config_file=None):
        self.config_file = config_file or find_dotenv() or Path(".env")
        self.errors = []
        self.warnings = []

    def validate(self, interactive=False) -> bool:
        """Validate configuration and optionally run interactive setup.

        Returns:
            bool: True if config is valid, False otherwise
        """
        load_dotenv(self.config_file)

        # Check critical settings
        self._check_adsb_api_key()
        self._check_weather_key()
        self._check_pushbullet_api_key()
        # self._check_coordinates() # currently they are passed
        self._check_bounding_box()

        if interactive:
            return self._run_interactive_setup()

        return len(self.errors) == 0

    def _check_adsb_api_key(self):
        """Check FlightAware AeroAPI key."""
        aeroapi_key = os.getenv("AEROAPI_API_KEY")
        airlabs_key = os.getenv("AIRLABS_API_KEY")

        if not (aeroapi_key or airlabs_key):
            self.errors.append({
                "field": "ADSB API KEY",
                "message": (
                    "At least one ADSB API Key is required. FlightAware AeroAPI API Key"
                    " or AirLabs API Key is required for live flight data."
                ),
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

    def _check_pushbullet_api_key(self):
        """Check optionally Pushbullet API KEY"""
        key = os.getenv("PUSH_BULLET_API_KEY")
        if not key:
            self.warnings.append({
                "field": "PUSH_BULLET_API_KEY",
                "message": "Pushbullet API key missing (push notifications disabled)",
                "severity": "WARNING",
            })

    # def _check_coordinates(self):
    #     """Check observer coordinates."""
    #     lat = os.getenv("OBSERVER_LATITUDE")
    #     lon = os.getenv("OBSERVER_LONGITUDE")

    #     if not lat or not lon:
    #         self.errors.append({
    #             "field": "OBSERVER_COORDINATES",
    #             "message": "Observer coordinates not set",
    #             "severity": "ERROR",
    #         })
    #     else:
    #         try:
    #             lat_f = float(lat)
    #             lon_f = float(lon)
    #             if not (-90 <= lat_f <= 90):
    #                 self.errors.append({
    #                     "field": "OBSERVER_LATITUDE",
    #                     "message": f"Invalid latitude: {lat} (must be -90 to 90)",
    #                     "severity": "ERROR"
    #                 })
    #             if not (-180 <= lon_f <= 180):
    #                 self.errors.append({
    #                     "field": "OBSERVER_LONGITUDE",
    #                     "message": f"Invalid longitude: {lon} (must be -180 to 180)",
    #                     "severity": "ERROR"
    #                 })
    #         except ValueError:
    #             self.errors.append({
    #                 "field": "OBSERVER_COORDINATES",
    #                 "message": "Coordinates must be numeric",
    #                 "severity": "ERROR"
    #             })

    def _check_bounding_box(self):
        """Check flight search bounding box, set default if missing."""
        fields = ["LAT_LOWER_LEFT", "LONG_LOWER_LEFT", "LAT_UPPER_RIGHT", "LONG_UPPER_RIGHT"]
        values = {f: os.getenv(f) for f in fields}

        missing = [f for f, v in values.items() if not v]
        if missing:
            self.errors.append({
                "field": "BOUNDING_BOX",
                "message": f"Bounding box are required to search flights",
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

    def _prompt_secret(self, message, required=True):
        """Prompt user for a sensitive value (e.g. API key) without echoing input."""
        while True:
            value = getpass.getpass(f"{message}: ").strip()
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
            self._setup_adsb_api_keys()
            # self._setup_observer_location() # not required this time
            self._setup_bounding_box()
            self._setup_notification_api_key()
            self._setup_optional_additional_settings()
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

    def _setup_adsb_api_keys(self):
        """Setup API keys for ADSB providers (at least one required)."""
        print("-" * 40)
        print("STEP 1: ADSB Provider API Keys")
        print("-" * 40)
        print("\nAt least one provider is required for real-time flight data.")
        print("You can configure one or both.\n")

        providers = [
            {
                "label": "FlightAware AeroAPI (RECOMMENDED)",
                "env_key": "AEROAPI_API_KEY",
                "signup_url": "https://flightaware.com/aeroapi/signup/personal",
                "prompt_label": "FlightAware AeroAPI key",
            },
            {
                "label": "AirLabs",
                "env_key": "AIRLABS_API_KEY",
                "signup_url": "https://airlabs.co/register",
                "prompt_label": "AirLabs API key",
            },
        ]

        while True:
            for provider in providers:
                current = os.getenv(provider["env_key"])
                status = f"(set: {current[:8]}...)" if current else "(not set)"
                print(f"  [{provider['label']}] {status}")
                print(f"    Get a free key at: {provider['signup_url']}")

                if current:
                    if not self._prompt_yes_no(f"    Change {provider['prompt_label']}?", default=False):
                        continue
                else:
                    if not self._prompt_yes_no(f"    Set {provider['prompt_label']}?", default=True):
                        continue

                key = self._prompt_secret(f"    Enter your {provider['prompt_label']}", required=True)
                set_key(self.config_file, provider["env_key"], key)
                # Reload so os.getenv reflects the new value
                load_dotenv(self.config_file, override=True)
                print("    Saved!\n")

            # Validate at least one is set
            if os.getenv("AEROAPI_API_KEY") or os.getenv("AIRLABS_API_KEY"):
                break

            print("\n  At least one ADSB API key is required. Please set at least one.\n")

    # def _setup_observer_location(self):
    #     """Setup observer location."""
    #     print("\n" + "-" * 40)
    #     print("STEP 2: Your Location")
    #     print("-" * 40)
    #     print("\nEnter your observation location (where you'll watch transits).")
    #     print("  Find coordinates at: https://www.maps.ie/coordinates.html")
    #     print("  Or use Google Maps: right-click any location to see coordinates.")

    #     current_lat = os.getenv("OBSERVER_LATITUDE")
    #     current_lon = os.getenv("OBSERVER_LONGITUDE")
    #     current_elev = os.getenv("OBSERVER_ELEVATION", "0")

    #     if current_lat and current_lon:
    #         print(f"\n  Current location: {current_lat}, {current_lon} (elev: {current_elev}m)")
    #         if not self._prompt_yes_no("  Change location?", default=False):
    #             return

    #     print("")
    #     lat = self._prompt_float("  Latitude (e.g., 33.12)", min_val=-90, max_val=90)
    #     lon = self._prompt_float("  Longitude (e.g., -117.31)", min_val=-180, max_val=180)
    #     elev = self._prompt_float("  Elevation in meters (e.g., 35)", default=0, min_val=0, max_val=10000)

    #     set_key(self.config_file, "OBSERVER_LATITUDE", str(lat))
    #     set_key(self.config_file, "OBSERVER_LONGITUDE", str(lon))
    #     set_key(self.config_file, "OBSERVER_ELEVATION", str(elev))

    #     # Store for bounding box calculation
    #     self._observer_lat = lat
    #     self._observer_lon = lon

    #     print("  Saved!")

    def _setup_bounding_box(self):
        """Setup flight search bounding box."""
        print("\n" + "-" * 40)
        print("STEP 2: Flight Search Area")
        print("-" * 40)
        print("\nThe bounding box defines the area to search for flights.")
        print("Recommended covering roughly a 15-minute flight radius from your location.")

        fields = [
            ("LAT_LOWER_LEFT", "Lower-left latitude", -90, 90),
            ("LONG_LOWER_LEFT", "Lower-left longitude", -180, 180),
            ("LAT_UPPER_RIGHT", "Upper-right latitude", -90, 90),
            ("LONG_UPPER_RIGHT", "Upper-right longitude", -180, 180),
        ]

        current_values = {key: os.getenv(key) for key, *_ in fields}
        all_set = all(current_values.values())

        if all_set:
            print(f"\n  Current bounding box:")
            print(f"    Lower-left:  ({current_values['LAT_LOWER_LEFT']}, {current_values['LONG_LOWER_LEFT']})")
            print(f"    Upper-right: ({current_values['LAT_UPPER_RIGHT']}, {current_values['LONG_UPPER_RIGHT']})")
            if not self._prompt_yes_no("  Change bounding box?", default=False):
                return

        print("\n  Enter bounding box coordinates:")
        print("  (Lower-left is southwest corner, upper-right is northeast corner)")

        for key, label, min_val, max_val in fields:
            current = current_values[key]
            default = float(current) if current else None
            value = self._prompt_float(f"  {label}", default=default, min_val=min_val, max_val=max_val)
            set_key(self.config_file, key, str(value))

        load_dotenv(self.config_file, override=True)
        print("  Saved!")

    def _setup_optional_additional_settings(self):
        """Setup optional additional settings."""
        print("\n" + "-" * 40)
        print("STEP 4: Optional Settings")
        print("-" * 40)

        # Weather API
        print("\nOpenWeatherMap API key (optional)")
        print("  Enables weather-based filtering (skip checks when cloudy).")
        print("  Get a free key at: https://openweathermap.org/api")

        current = os.getenv("OPENWEATHER_API_KEY")
        if current:
            print(f"  Current: {current[:8]}...")
            if self._prompt_yes_no("  Change weather API key?", default=False):
                key = self._prompt_secret("  Enter OpenWeatherMap API key", required=False)
                if key:
                    set_key(self.config_file, "OPENWEATHER_API_KEY", key)
                    print("  Saved!")
        else:
            if self._prompt_yes_no("  Add weather API key?", default=False):
                key = self._prompt_secret("  Enter OpenWeatherMap API key", required=False)
                if key:
                    set_key(self.config_file, "OPENWEATHER_API_KEY", key)
                    print("  Saved!")
            else:
                print("  Skipped. Weather filtering will be disabled.")

    def _setup_notification_api_key(self):
        """Setup optional Pushbullet API key for push notifications."""
        print("\n" + "-" * 40)
        print("STEP 3: Push Notifications (Optional)")
        print("-" * 40)
        print("\nPushbullet API key (optional)")
        print("  In auto mode, receive smartphone notifications when a transit is detected.")
        print("  To get your key:")
        print("    1. Create an account at: https://www.pushbullet.com/")
        print("    2. Install the Pushbullet app on your phone.")
        print("    3. Go to Settings > Create Access Token.")

        current = os.getenv("PUSH_BULLET_API_KEY")
        if current:
            print(f"  Current: {current[:8]}...")
            if self._prompt_yes_no("  Change Pushbullet API key?", default=False):
                key = self._prompt_secret("  Enter your Pushbullet API key", required=False)
                if key:
                    set_key(self.config_file, "PUSH_BULLET_API_KEY", key)
                    load_dotenv(self.config_file, override=True)
                    print("  Saved!")
        else:
            if self._prompt_yes_no("  Add Pushbullet API key?", default=False):
                key = self._prompt_secret("  Enter your Pushbullet API key", required=False)
                if key:
                    set_key(self.config_file, "PUSH_BULLET_API_KEY", key)
                    load_dotenv(self.config_file, override=True)
                    print("  Saved!")
            else:
                print("  Skipped. Push notifications will be disabled.")

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
