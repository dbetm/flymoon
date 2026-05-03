import argparse
import asyncio
import os
import platform
import subprocess
import time
from datetime import date, datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # noqa

from src import logger
from src.constants import (
    POSIBILITY_LEVEL_TO_COLOR,
    POSSIBLE_TRANSITS_LOGFILENAME,
    TARGET_TO_EMOJI,
    PossibilityLevel,
)
from src.flight_data import save_possible_transits, sort_results
from src.notify import send_notifications
from src.transit import get_transits


class TransitClient:
    ALERT_SOUND_PATH = os.path.join(
        "static", "sounds", "tissman-alert1-maximum-distortion.mp3"
    )

    def __init__(
        self,
        target: str,
        lat: float,
        long: float,
        elevation: float,
        interval_min: int,
        send_app_notification: bool = False,
        adsb_provider: str = "flightaware-aeroapi",
        min_altitude: float = 15,
        check_weather: bool = False,
        test_mode: bool = False,
    ):
        self.target = target
        self.latitude = lat
        self.longitude = long
        self.elevation = elevation
        self.interval = interval_min
        self.min_altitude = min_altitude
        self.test_mode = test_mode
        self.send_app_notification = send_app_notification
        self.total_transits = 0
        self.adsb_provider = adsb_provider
        self.check_weather = check_weather

    def __get_next_check_time(self) -> str:
        current_datetime = datetime.now()

        next_datetime = current_datetime + timedelta(minutes=self.interval)

        return next_datetime.strftime("%H:%M:%S")

    def __play_sound(self, filepath: Optional[str] = None) -> None:
        system = platform.system()
        num_times_play_sound = 1
        time_between_sounds = 0.1

        if system == "Windows":
            import winsound

            if filepath:
                winsound.PlaySound(filepath, winsound.SND_FILENAME)
            else:
                for _ in range(num_times_play_sound):
                    winsound.Beep(440, 500)  # 440 Hz for 500 ms
                    time.sleep(time_between_sounds)
        elif system == "Darwin":  # macOS
            ruta = filepath or "/System/Library/Sounds/Glass.aiff"

            for _ in range(num_times_play_sound):
                subprocess.run(["afplay", ruta], check=True)
                time.sleep(time_between_sounds)
        elif system == "Linux":
            if filepath:
                # try aplay first, then paplay as fallback
                for cmd in ("aplay", "paplay"):
                    try:
                        for _ in range(num_times_play_sound):
                            subprocess.run(
                                [cmd, filepath],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            time.sleep(time_between_sounds)
                        return
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        continue
                logger.warning("Neither aplay nor paplay were found")
            else:
                # Beep ASCII as fallback
                for _ in range(num_times_play_sound):
                    print("\a", end="", flush=True)
                    time.sleep(time_between_sounds)
        else:
            logger.warning(f"Not supported system: {system}")
            for _ in range(num_times_play_sound):
                print("\a", end="", flush=True)
                time.sleep(time_between_sounds)

    def run(self):
        while True:
            self.check_transits()
            next_check_time = self.__get_next_check_time()

            for i in range(self.interval * 60, 0, -1):
                print(
                    f"\rNext check at ⏰ {next_check_time} ({i} seconds)",
                    end="",
                    flush=True,
                )
                time.sleep(1)
            print()

    def check_transits(self):
        data = get_transits(
            self.latitude,
            self.longitude,
            self.elevation,
            self.target,
            self.test_mode,
            min_altitude=self.min_altitude,
            adsb_provider=self.adsb_provider,
            check_weather=self.check_weather,
        )

        data["flights"] = sort_results(data["flights"])

        flights = data.get("flights", [])
        weather_info = data.get("weather", {})
        tracking_targets = data.get("trackingTargets", [])

        # Store weather info for status display
        self.last_weather = weather_info
        self.last_tracking_targets = tracking_targets

        # Log weather and tracking info
        if weather_info:
            logger.info(
                f"Weather: {weather_info.get('description', 'unknown')} ({weather_info.get('cloud_cover', 'N/A')}% clouds)"
            )
        if tracking_targets:
            logger.info(f"Tracking: {', '.join(tracking_targets)}")

        # Check if any targets are trackable
        if not tracking_targets:
            logger.info(
                "No targets trackable (below horizon, threshold alt. or weather)"
            )
            self.current_transits = []
            return

        logger.info(data["targetCoordinates"])

        # Filter for medium and high possibility transits
        possible_transits = [
            f
            for f in flights
            if f.get("possibility_level")
            in (PossibilityLevel.MEDIUM.value, PossibilityLevel.HIGH.value)
        ]

        if not possible_transits:
            logger.info("No possible transits found")
            return

        # Save to CSV (only MEDIUM/HIGH)
        if not self.test_mode:
            try:
                date_ = date.today().strftime("%Y%m%d")
                asyncio.run(
                    save_possible_transits(
                        possible_transits,
                        POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_),
                    )
                )
                self.total_transits += len(possible_transits)
            except Exception as e:
                logger.error(f"Error saving transits: {e}")

        # if there's possible transits, make a sound
        num_possible_transits = len(possible_transits)
        if num_possible_transits > 0:
            transit_word = "transits" if num_possible_transits > 1 else "transit"

            msg = "\n\n".join(
                ["-" * 21]
                + [
                    f"{POSIBILITY_LEVEL_TO_COLOR[flight['possibility_level']]}"
                    f" {TARGET_TO_EMOJI[flight['target']]} {flight['id']} ({flight['aircraft_type']}) in {flight['eta']} min."
                    f" {flight['origin']} -> {flight['destination']}."
                    f" Angular separation: {flight['angular_separation']}°"
                    for flight in possible_transits
                ]
                + ["-" * 42]
            )
            logger.info(msg)

            self.__play_sound(self.ALERT_SOUND_PATH)

        self.total_transits += num_possible_transits
        logger.info(
            f"Found {num_possible_transits} possible {transit_word}. Session total: {self.total_transits}"
        )

        if self.send_app_notification and not self.test_mode:
            try:
                asyncio.run(send_notifications(data["flights"], self.target))
            except Exception as e:
                logger.error(
                    f"Error while trying to send push notification. Details:\n{str(e)}"
                )


def main():
    parser = argparse.ArgumentParser(description="Flymoon for the Terminal")
    parser.add_argument("--lat", type=float, help="Observer latitude", required=True)
    parser.add_argument("--long", type=float, help="Observer longitude", required=True)
    parser.add_argument(
        "--elev", type=float, help="Observer elevation in meters", required=True
    )
    parser.add_argument(
        "--target",
        choices=["moon", "sun", "auto"],
        default="auto",
        help="Target celestial object",
    )
    parser.add_argument(
        "--adsb",
        choices=["flightaware-aeroapi", "airlabs"],
        default="flightaware-aeroapi",
    )
    parser.add_argument(
        "--interval", type=int, default=12, help="Check interval in minutes"
    )
    parser.add_argument("--notify", action="store_true", help="Send push notification")
    parser.add_argument(
        "--min-alt", type=float, default=15, help="Minimum altitude for targets"
    )
    parser.add_argument("--weather", action="store_true", help="Check weather")
    parser.add_argument("--test", action="store_true", help="Use test mode")

    args = parser.parse_args()
    logger.info(args)

    app = TransitClient(
        args.target,
        args.lat,
        args.long,
        args.elev,
        args.interval,
        args.notify,
        adsb_provider=args.adsb,
        min_altitude=args.min_alt,
        test_mode=args.test,
    )

    app.run()


if __name__ == "__main__":
    main()
