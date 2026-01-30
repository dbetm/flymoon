#!/usr/bin/env python3
"""
Background transit monitor with macOS notifications.
Runs continuously, checking for transits at specified intervals.
"""
import argparse
import asyncio
import os
import subprocess
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from src import logger
from src.constants import PossibilityLevel, TARGET_TO_EMOJI
from src.transit import get_transits


def send_macos_notification(title: str, message: str, sound: bool = True):
    """Send a native macOS notification using osascript."""
    sound_setting = "sound name \"Submarine\"" if sound else ""
    
    # Escape quotes in message and title
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')
    
    script = f'''
    display notification "{message}" with title "{title}" {sound_setting}
    '''
    
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Notification sent: {title}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to send notification: {e.stderr}")


def format_transit_details(flight: dict) -> str:
    """Format a single transit for notification display."""
    time_min = flight['time']
    flight_id = flight['id']
    origin = flight['origin']
    dest = flight['destination']
    alt_diff = flight['alt_diff']
    az_diff = flight['az_diff']
    
    return (
        f"{flight_id} in {time_min:.1f} min\n"
        f"{origin}→{dest}\n"
        f"Δalt={alt_diff:.2f}° Δaz={az_diff:.2f}°"
    )


def check_and_notify(
    latitude: float,
    longitude: float,
    elevation: float,
    target: str,
    test_mode: bool = False
) -> int:
    """
    Check for transits and send notifications if found.
    Returns the number of medium/high possibility transits found.
    """
    try:
        data = get_transits(latitude, longitude, elevation, target, test_mode)
        flights = data.get("flights", [])
        target_coords = data.get("targetCoordinates", {})
        
        # Check if target is visible
        if target_coords.get("altitude", -1) < 0:
            logger.info(f"{target.capitalize()} is below horizon, skipping...")
            return 0
        
        # Filter for medium and high possibility transits
        notable_transits = [
            f for f in flights
            if f.get("possibility_level") in (
                PossibilityLevel.MEDIUM.value,
                PossibilityLevel.HIGH.value
            )
        ]
        
        if not notable_transits:
            logger.info("No notable transits found")
            return 0
        
        # Sort by time (closest first)
        notable_transits.sort(key=lambda x: x.get("time", float('inf')))
        
        # Save to CSV (only MEDIUM/HIGH)
        if not test_mode:
            try:
                from datetime import date
                from src.flight_data import save_possible_transits
                from src.constants import POSSIBLE_TRANSITS_LOGFILENAME
                import asyncio
                
                date_ = date.today().strftime("%Y%m%d")
                asyncio.run(
                    save_possible_transits(
                        notable_transits,
                        POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
                    )
                )
                logger.info(f"Saved {len(notable_transits)} transit(s) to log")
            except Exception as e:
                logger.error(f"Error saving transits: {e}")
        
        # Send notification for top transit(s)
        num_transits = len(notable_transits)
        emoji = TARGET_TO_EMOJI.get(target, "")
        
        if num_transits == 1:
            transit = notable_transits[0]
            level = "HIGH" if transit["possibility_level"] == PossibilityLevel.HIGH.value else "MEDIUM"
            title = f"{level} possibility transit {emoji}"
            message = format_transit_details(transit)
        else:
            # Multiple transits - show count and first one
            title = f"{num_transits} possible transits {emoji}"
            message = format_transit_details(notable_transits[0])
            if num_transits > 1:
                message += f"\n+ {num_transits - 1} more"
        
        send_macos_notification(title, message, sound=True)
        
        logger.info(f"Found {num_transits} notable transit(s)")
        return num_transits
        
    except Exception as e:
        logger.error(f"Error checking transits: {e}")
        return 0


def monitor_loop(
    latitude: float,
    longitude: float,
    elevation: float,
    target: str,
    interval_minutes: int,
    test_mode: bool = False
):
    """
    Main monitoring loop. Checks for transits at specified intervals.
    """
    logger.info(f"Starting transit monitor:")
    logger.info(f"  Position: {latitude}, {longitude}, {elevation}m")
    logger.info(f"  Target: {target}")
    logger.info(f"  Check interval: {interval_minutes} minutes")
    logger.info(f"  Test mode: {test_mode}")
    
    # Send startup notification
    send_macos_notification(
        "Flymoon Monitor Started",
        f"Monitoring {target} transits every {interval_minutes} min",
        sound=False
    )
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"\n--- Check #{check_count} at {timestamp} ---")
            
            check_and_notify(latitude, longitude, elevation, target, test_mode)
            
            logger.info(f"Waiting {interval_minutes} minutes until next check...")
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        logger.info("\nMonitor stopped by user")
        send_macos_notification(
            "Flymoon Monitor Stopped",
            "Transit monitoring has been stopped",
            sound=False
        )


def main():
    parser = argparse.ArgumentParser(
        description="Background transit monitor with macOS notifications"
    )
    parser.add_argument(
        "--latitude",
        type=float,
        required=True,
        help="Observer latitude in decimal degrees"
    )
    parser.add_argument(
        "--longitude",
        type=float,
        required=True,
        help="Observer longitude in decimal degrees"
    )
    parser.add_argument(
        "--elevation",
        type=float,
        required=True,
        help="Observer elevation in meters"
    )
    parser.add_argument(
        "--target",
        type=str,
        default="auto",
        choices=["moon", "sun", "auto"],
        help="Target to monitor (default: auto)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Check interval in minutes (default: 15)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use cached flight data for testing"
    )
    
    args = parser.parse_args()
    
    # Validate API key unless in test mode
    if not args.test and not os.getenv("AEROAPI_API_KEY"):
        logger.error("AEROAPI_API_KEY not set in .env file")
        exit(1)
    
    monitor_loop(
        args.latitude,
        args.longitude,
        args.elevation,
        args.target,
        args.interval,
        args.test
    )


if __name__ == "__main__":
    main()
