#!/usr/bin/env python3
"""
Windows system tray app for monitoring airplane transits.
Shows status in system tray with icon that changes based on target and alerts.
"""
import os
import subprocess
import threading
import time
import logging
from datetime import datetime, date
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Required packages not installed for Windows.")
    print("Install with: pip install pystray pillow")
    exit(1)

from dotenv import load_dotenv, set_key, find_dotenv

load_dotenv()

CONFIG_FILE = find_dotenv() or Path(__file__).parent / ".env"

from src import logger
from src.constants import PossibilityLevel, TARGET_TO_EMOJI, POSSIBLE_TRANSITS_LOGFILENAME
from src.flight_data import save_possible_transits
from src.transit import get_transits

# Setup file logging
LOG_DIR = Path(__file__).parent / "data" / "windows-logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
WINDOWS_LOG_FILE = LOG_DIR / f"monitor_{datetime.now().strftime('%Y%m%d')}.log"

file_handler = logging.FileHandler(WINDOWS_LOG_FILE)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class TransitMonitorWindows:
    def __init__(self):
        # Load configuration
        self._load_config()
        
        # State
        self.monitoring = False
        self.test_mode = False
        
        self.start_time = None
        self.total_transits_logged = 0
        self.current_transits = []
        self.last_check_time = None
        
        self.monitor_thread = None
        self.stop_monitoring_flag = threading.Event()
        
        self.last_weather = {}
        self.last_tracking_targets = []
        
        # Create tray icon
        self.icon = None
        self._create_icon()
        
        # Log app startup
        logger.info(f"=== Transit Monitor Started (Windows) ===")
        logger.info(f"Config: target={self.target}, lat={self.latitude}, lon={self.longitude}, interval={self.interval}min")
    
    def _load_config(self):
        """Load configuration from .env file."""
        load_dotenv(override=True)
        
        try:
            # Get coordinates from OBSERVER_* variables
            obs_lat = os.getenv("OBSERVER_LATITUDE")
            obs_lon = os.getenv("OBSERVER_LONGITUDE")
            obs_elev = os.getenv("OBSERVER_ELEVATION")
            
            if obs_lat and obs_lon:
                self.latitude = float(obs_lat)
                self.longitude = float(obs_lon)
                self.elevation = float(obs_elev) if obs_elev else 0.0
            else:
                # Calculate center of bounding box
                lat_ll = float(os.getenv("LAT_LOWER_LEFT", 0))
                lon_ll = float(os.getenv("LONG_LOWER_LEFT", 0))
                lat_ur = float(os.getenv("LAT_UPPER_RIGHT", 0))
                lon_ur = float(os.getenv("LONG_UPPER_RIGHT", 0))
                self.latitude = (lat_ll + lat_ur) / 2
                self.longitude = (lon_ll + lon_ur) / 2
                self.elevation = 0.0
            
            # Get monitor settings
            monitor_target = os.getenv("MONITOR_TARGET")
            monitor_interval = os.getenv("MONITOR_INTERVAL")
            
            self.target = monitor_target.lower().strip('"\'') if monitor_target else "auto"
            self.interval = int(monitor_interval.strip('"\'')) if monitor_interval else 15
            
            logger.info(f"Loaded config from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Could not parse config from .env: {e}")
            self.latitude = None
            self.longitude = None
            self.elevation = 0.0
            self.target = "auto"
            self.interval = 15
    
    def _create_icon_image(self, color='white', text=''):
        """Create icon image for system tray."""
        # Create a 64x64 image
        image = Image.new('RGB', (64, 64), color='black')
        draw = ImageDraw.Draw(image)
        
        if text:
            # Draw text emoji (simplified for Windows)
            try:
                font = ImageFont.truetype("segoeui.ttf", 40)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position (centered)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((64 - text_width) // 2, (64 - text_height) // 2)
            
            draw.text(position, text, fill=color, font=font)
        else:
            # Draw a simple circle
            draw.ellipse([10, 10, 54, 54], fill=color, outline='white')
        
        return image
    
    def _create_icon(self):
        """Create system tray icon with menu."""
        # Set icon based on target
        if self.target == "auto":
            icon_text = "🌙☀"
        elif self.target == "moon":
            icon_text = "🌙"
        else:
            icon_text = "☀"
        
        image = self._create_icon_image('white', icon_text)
        
        menu = (
            item('Status', self.show_status),
            item('---', None),
            item('Edit Config', self.edit_config),
            item('Reload Config', self.reload_config),
            item('Start Monitoring', self.toggle_monitoring, checked=lambda _: self.monitoring),
            item('---', None),
            item('View Transit Log', self.view_transit_log),
            item('View Monitor Log', self.view_monitor_log),
            item('Open Log Folder', self.open_log_folder),
            item('---', None),
            item('Quit', self.quit_app),
        )
        
        self.icon = pystray.Icon("flymoon", image, "Flymoon Transit Monitor", menu)
    
    def show_status(self):
        """Show status notification."""
        if not self.monitoring:
            status = "Not monitoring"
        else:
            uptime = self._get_uptime()
            status = (
                f"Target: {self.target}\\n"
                f"Uptime: {uptime}\\n"
                f"Transits logged: {self.total_transits_logged}\\n"
                f"Last check: {self.last_check_time or 'Never'}"
            )
            
            if self.last_weather:
                weather_desc = self.last_weather.get('description', 'unknown')
                cloud_cover = self.last_weather.get('cloud_cover')
                if cloud_cover is not None:
                    status += f"\\nWeather: {weather_desc} ({cloud_cover}% clouds)"
            
            if self.last_tracking_targets:
                status += f"\\nTracking: {', '.join(self.last_tracking_targets)}"
            
            if self.current_transits:
                status += f"\\n\\n{len(self.current_transits)} active transits:"
                for t in self.current_transits[:3]:
                    eta = t.get('time', 0)
                    flight_id = t.get('id', 'Unknown')
                    target_name = t.get('target', '')
                    status += f"\\n  {target_name}: {flight_id} in {eta:.1f}min"
        
        self.icon.notify(status, "Flymoon Status")
    
    def _get_uptime(self):
        """Calculate uptime string."""
        if not self.start_time:
            return "N/A"
        delta = datetime.now() - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if delta.days > 0:
            return f"{delta.days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def edit_config(self):
        """Open .env file in default text editor."""
        try:
            os.startfile(str(CONFIG_FILE))
            self.icon.notify("Config file opened. Edit and reload config.", "Edit Config")
        except Exception as e:
            logger.error(f"Error opening config: {e}")
            self.icon.notify(f"Error: {str(e)}", "Error")
    
    def reload_config(self):
        """Reload configuration from file."""
        was_monitoring = self.monitoring
        
        # Stop monitoring if active
        if self.monitoring:
            self.monitoring = False
            self.stop_monitoring_flag.set()
        
        # Reload config
        self._load_config()
        
        self.icon.notify(
            f"Target: {self.target}, Interval: {self.interval} min\\n"
            f"Location: ({self.latitude}, {self.longitude})",
            "Config Reloaded"
        )
        
        # Restart monitoring if it was running
        if was_monitoring:
            self.toggle_monitoring()
    
    def toggle_monitoring(self):
        """Start or stop monitoring."""
        if not self.monitoring:
            # Validate configuration
            if self.latitude is None or self.longitude is None:
                self.icon.notify("Please configure coordinates first", "Configuration Required")
                return
            
            # Validate API key unless in test mode
            if not self.test_mode and not os.getenv("AEROAPI_API_KEY"):
                self.icon.notify("Please set AEROAPI_API_KEY in .env file", "API Key Missing")
                return
            
            # Start monitoring
            self.monitoring = True
            self.start_time = datetime.now()
            self.last_check_start_time = datetime.now()
            self.total_transits_logged = 0
            self.stop_monitoring_flag.clear()
            
            logger.info(f"=== Monitoring Started ===")
            logger.info(f"Target: {self.target}, Location: ({self.latitude}, {self.longitude}), Interval: {self.interval}min")
            
            # Initialize transit log
            self._initialize_transit_log()
            
            # Start monitor thread
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            self.icon.notify(
                f"Tracking {self.target} transits\\nChecking every {self.interval} minutes",
                "Monitor Started"
            )
        else:
            # Stop monitoring
            self.monitoring = False
            self.stop_monitoring_flag.set()
            self.current_transits = []
            
            logger.info(f"=== Monitoring Stopped ===")
            logger.info(f"Total transits logged: {self.total_transits_logged}")
            
            self.icon.notify(
                f"Logged {self.total_transits_logged} transit(s)",
                "Monitor Stopped"
            )
    
    def _initialize_transit_log(self):
        """Initialize transit log CSV."""
        try:
            date_ = date.today().strftime("%Y%m%d")
            log_path = POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
            
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            
            if not os.path.exists(log_path):
                with open(log_path, 'w') as f:
                    f.write("# Transit Log\\n")
                    f.write(f"# Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
                    f.write(f"# Target: {self.target}, Observer: ({self.latitude}, {self.longitude})\\n")
                    f.write("# Flight ID,Origin,Destination,Time(min),Alt_Diff,Az_Diff,Possibility\\n")
                logger.info(f"Initialized transit log: {log_path}")
            else:
                with open(log_path, 'a') as f:
                    f.write(f"\\n# New session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
                logger.info(f"Appending to existing transit log: {log_path}")
        except Exception as e:
            logger.error(f"Error initializing transit log: {e}")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        check_count = 0
        
        while not self.stop_monitoring_flag.is_set():
            check_count += 1
            self.last_check_start_time = datetime.now()
            timestamp = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Check #{check_count} at {timestamp}")
            
            try:
                num_transits = self._check_and_log_transits()
                
                if num_transits > 0:
                    # Update icon to alert state
                    self._flash_notification()
                
            except Exception as e:
                logger.error(f"Error during check: {e}")
            
            self.last_check_time = timestamp
            
            # Wait for next check (or until stopped)
            self.stop_monitoring_flag.wait(timeout=self.interval * 60)
    
    def _check_and_log_transits(self) -> int:
        """Check for transits and log MEDIUM/HIGH ones. Returns count."""
        data = get_transits(
            self.latitude,
            self.longitude,
            self.elevation,
            self.target,
            self.test_mode
        )
        
        flights = data.get("flights", [])
        weather_info = data.get("weather", {})
        tracking_targets = data.get("trackingTargets", [])
        
        # Store weather info
        self.last_weather = weather_info
        self.last_tracking_targets = tracking_targets
        
        # Log weather and tracking info
        if weather_info:
            logger.info(f"Weather: {weather_info.get('description', 'unknown')} ({weather_info.get('cloud_cover', 'N/A')}% clouds)")
        if tracking_targets:
            logger.info(f"Tracking: {', '.join(tracking_targets)}")
        
        # Check if any targets are trackable
        if not tracking_targets:
            logger.info("No targets trackable (below horizon or weather)")
            self.current_transits = []
            return 0
        
        # Filter for medium and high possibility transits
        notable_transits = [
            f for f in flights
            if f.get("possibility_level") in (
                PossibilityLevel.MEDIUM.value,
                PossibilityLevel.HIGH.value
            )
        ]
        
        self.current_transits = notable_transits
        
        if not notable_transits:
            logger.info("No notable transits found")
            return 0
        
        # Save to CSV
        if not self.test_mode:
            try:
                date_ = date.today().strftime("%Y%m%d")
                import asyncio
                asyncio.run(
                    save_possible_transits(
                        notable_transits,
                        POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
                    )
                )
                self.total_transits_logged += len(notable_transits)
            except Exception as e:
                logger.error(f"Error saving transits: {e}")
        
        # Log each transit
        for t in notable_transits:
            logger.info(
                f"Transit: {t['id']} ({t.get('possibility_level', 'UNKNOWN')}) - "
                f"{t['origin']}→{t['destination']}, "
                f"ETA: {t['time']:.1f}min, "
                f"Δalt={t['alt_diff']:.2f}°, Δaz={t['az_diff']:.2f}°"
            )
        
        # Send notification for immediate transits (< 5 min)
        immediate_transits = [t for t in notable_transits if t.get('time', 999) < 5]
        if immediate_transits:
            t = immediate_transits[0]
            target_name = t.get('target', self.target)
            self.icon.notify(
                f"{t['id']} in {t['time']:.1f} min\\n"
                f"{t['origin']}→{t['destination']}\\n"
                f"Δalt={t['alt_diff']:.2f}° Δaz={t['az_diff']:.2f}°",
                f"Transit Alert! {target_name}"
            )
        
        logger.info(f"Found {len(notable_transits)} notable transit(s)")
        return len(notable_transits)
    
    def _flash_notification(self):
        """Flash notification for transits."""
        if self.current_transits:
            target = self.current_transits[0].get('target', self.target)
            icon = TARGET_TO_EMOJI.get(target, '✈️')
            self.icon.notify(
                f"{len(self.current_transits)} transit(s) detected!",
                f"Transit Alert {icon}"
            )
    
    def view_transit_log(self):
        """Open today's transit log file."""
        try:
            date_ = date.today().strftime("%Y%m%d")
            log_path = POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
            
            if not os.path.exists(log_path):
                self.icon.notify(f"No transits logged today", "No Transit Log")
                return
            
            os.startfile(log_path)
        except Exception as e:
            logger.error(f"Error viewing transit log: {e}")
            self.icon.notify(f"Error: {str(e)}", "Error")
    
    def view_monitor_log(self):
        """Open today's monitor log file."""
        try:
            if not WINDOWS_LOG_FILE.exists():
                self.icon.notify("Log file doesn't exist", "No Monitor Log")
                return
            
            os.startfile(str(WINDOWS_LOG_FILE))
        except Exception as e:
            logger.error(f"Error viewing monitor log: {e}")
            self.icon.notify(f"Error: {str(e)}", "Error")
    
    def open_log_folder(self):
        """Open the folder containing log files."""
        try:
            log_dir = os.path.dirname(POSSIBLE_TRANSITS_LOGFILENAME.format(date_="20260130"))
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            os.startfile(log_dir)
        except Exception as e:
            logger.error(f"Error opening log folder: {e}")
            self.icon.notify(f"Error: {str(e)}", "Error")
    
    def quit_app(self):
        """Quit the application."""
        if self.monitoring:
            self.stop_monitoring_flag.set()
            time.sleep(0.5)
        self.icon.stop()
    
    def run(self):
        """Run the system tray app."""
        self.icon.run()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Windows system tray transit monitor")
    parser.add_argument("--latitude", type=float, help="Observer latitude")
    parser.add_argument("--longitude", type=float, help="Observer longitude")
    parser.add_argument("--elevation", type=float, default=0.0, help="Observer elevation in meters")
    parser.add_argument("--target", choices=["moon", "sun", "auto"], default="auto", help="Target celestial object")
    parser.add_argument("--interval", type=int, default=15, help="Check interval in minutes")
    args = parser.parse_args()
    
    app = TransitMonitorWindows()
    
    # Override with command-line args if provided
    if args.latitude is not None:
        app.latitude = args.latitude
    if args.longitude is not None:
        app.longitude = args.longitude
    if args.elevation is not None:
        app.elevation = args.elevation
    app.target = args.target
    app.interval = args.interval
    
    app.run()


if __name__ == "__main__":
    main()
