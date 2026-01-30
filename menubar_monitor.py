#!/usr/bin/env python3
"""
macOS menu bar app for monitoring airplane transits.
Shows status in menu bar with icon that flashes when transits are detected.
"""
import os
import subprocess
import threading
import time
import logging
from datetime import datetime, date
from pathlib import Path

import rumps
from dotenv import load_dotenv, set_key, find_dotenv

load_dotenv()

CONFIG_FILE = find_dotenv() or Path(__file__).parent / ".env"

from src import logger
from src.constants import PossibilityLevel, TARGET_TO_EMOJI, POSSIBLE_TRANSITS_LOGFILENAME
from src.flight_data import save_possible_transits
from src.transit import get_transits

# Setup file logging for menubar app
LOG_DIR = Path(__file__).parent / "data" / "menubar-logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
MENUBAR_LOG_FILE = LOG_DIR / f"monitor_{datetime.now().strftime('%Y%m%d')}.log"

file_handler = logging.FileHandler(MENUBAR_LOG_FILE)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


class TransitMonitor(rumps.App):
    def __init__(self):
        # Load configuration first to determine icon
        # Use temporary icon, will be set correctly after _load_config
        super(TransitMonitor, self).__init__("⚫", quit_button=None)
        
        # Load configuration
        self._load_config()
        
        # Now set the correct icon based on target
        if self.target == "auto":
            self.title = "🌙☀️"
        elif self.target == "moon":
            self.title = "🌙"
        else:
            self.title = "☀️"
        
        # State
        self.monitoring = False
        self.test_mode = False
        
        self.start_time = None
        self.total_transits_logged = 0
        self.current_transits = []
        self.last_check_time = None
        
        self.monitor_thread = None
        self.stop_monitoring_flag = threading.Event()
        self.flash_active = False
        self.last_weather = {}
        self.last_tracking_targets = []
        
        # Menu items
        self.menu = [
            rumps.MenuItem("Status", callback=None),
            rumps.separator,
            rumps.MenuItem("Edit Config File", callback=self.edit_config),
            rumps.MenuItem("Reload Config", callback=self.reload_config),
            rumps.MenuItem("Start Monitoring", callback=self.toggle_monitoring),
            rumps.separator,
            rumps.MenuItem("View Transit Log", callback=self.view_transit_log),
            rumps.MenuItem("View Monitor Log", callback=self.view_monitor_log),
            rumps.MenuItem("Open Log Folder", callback=self.open_log_folder),
            rumps.separator,
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]
        
        # Log app startup
        logger.info(f"=== Transit Monitor Started ===")
        logger.info(f"Config: target={self.target}, lat={self.latitude}, lon={self.longitude}, interval={self.interval}min")
        
        self.update_status_display()
    
    def _load_config(self):
        """Load configuration from .env file."""
        # Reload environment variables
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
            
            self.target = monitor_target.lower().strip("'\")") if monitor_target else "auto"
            self.interval = int(monitor_interval.strip("'\"")) if monitor_interval else 15
            
            logger.info(f"Loaded config from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Could not parse config from .env: {e}")
            self.latitude = None
            self.longitude = None
            self.elevation = 0.0
            self.target = "moon"
            self.interval = 15
    
    def update_status_display(self):
        """Update the status menu item with current info."""
        if not self.monitoring:
            status_text = "Not monitoring"
        else:
            uptime = self._get_uptime()
            next_check = self._get_next_check_countdown()
            
            status_text = (
                f"{self.target.capitalize()} | Next: {next_check} | Up: {uptime}\n"
                f"Transits: {self.total_transits_logged} | Last: {self.last_check_time or 'Never'}"
            )
            
            # Add weather info if available
            if self.last_weather:
                weather_icon = self.last_weather.get('icon', '')
                weather_desc = self.last_weather.get('description', 'unknown')
                cloud_cover = self.last_weather.get('cloud_cover')
                if cloud_cover is not None:
                    status_text += f"\n{weather_icon} {weather_desc} ({cloud_cover}% clouds)"
                else:
                    status_text += f"\n{weather_icon} {weather_desc}"
            
            # Add tracking status
            if self.last_tracking_targets:
                targets_str = ", ".join(self.last_tracking_targets)
                status_text += f"\nTracking: {targets_str}"
            elif hasattr(self, 'last_tracking_targets'):
                status_text += "\n⚠️ No targets trackable"
            
            if self.current_transits:
                status_text += f"\n🔴 {len(self.current_transits)} active:"
                for t in self.current_transits[:3]:  # Show max 3
                    eta = t.get('time', 0)
                    flight_id = t.get('id', 'Unknown')
                    target_name = t.get('target', '')
                    target_icon = "🌙" if target_name == "moon" else "☀️" if target_name == "sun" else ""
                    status_text += f"\n  {target_icon} {flight_id} in {eta:.1f}min"
        
        self.menu["Status"].title = status_text
    
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
    
    def _get_next_check_countdown(self):
        """Calculate time until next check."""
        if not self.start_time or not hasattr(self, 'last_check_start_time'):
            return "checking now..."
        
        elapsed_since_last = (datetime.now() - self.last_check_start_time).total_seconds()
        interval_seconds = self.interval * 60
        remaining_seconds = max(0, interval_seconds - elapsed_since_last)
        
        if remaining_seconds < 5:
            return "checking now..."
        
        remaining_minutes = int(remaining_seconds // 60)
        remaining_secs = int(remaining_seconds % 60)
        
        if remaining_minutes > 0:
            return f"{remaining_minutes}m {remaining_secs}s"
        else:
            return f"{remaining_secs}s"
    
    @rumps.clicked("Edit Config File")
    def edit_config(self, _):
        """Open .env file in default text editor."""
        # Ensure MONITOR_* variables exist in .env
        if not os.getenv("MONITOR_TARGET"):
            env_path = Path(CONFIG_FILE)
            if env_path.exists():
                # Add MONITOR variables to .env
                set_key(env_path, "MONITOR_TARGET", self.target)
                set_key(env_path, "MONITOR_INTERVAL", str(self.interval))
        
        try:
            subprocess.run(["open", "-t", str(CONFIG_FILE)], check=True)
            rumps.notification(
                title="Config File Opened (.env)",
                subtitle="",
                message="Edit MONITOR_TARGET and MONITOR_INTERVAL, save, then click 'Reload Config'"
            )
        except subprocess.CalledProcessError:
            rumps.alert("Error", f"Could not open config file: {CONFIG_FILE}")
    
    @rumps.clicked("Reload Config")
    def reload_config(self, _):
        """Reload configuration from file."""
        was_monitoring = self.monitoring
        
        # Stop monitoring if active
        if self.monitoring:
            self.monitoring = False
            self.stop_monitoring_flag.set()
            self.menu["Start Monitoring"].title = "Start Monitoring"
        
        # Reload config
        self._load_config()
        self.update_status_display()
        
        rumps.notification(
            title="Config Reloaded",
            subtitle="",
            message=f"Target: {self.target}, Lat: {self.latitude}, Lon: {self.longitude}\nInterval: {self.interval} min"
        )
        
        # Restart monitoring if it was running
        if was_monitoring:
            self.toggle_monitoring(self.menu["Start Monitoring"])
    
    @rumps.clicked("Start Monitoring")
    def toggle_monitoring(self, sender):
        """Start or stop monitoring."""
        if not self.monitoring:
            # Validate configuration
            if self.latitude is None or self.longitude is None:
                rumps.alert("Configuration Required", "Please configure your coordinates first")
                return
            
            # Validate API key unless in test mode
            if not self.test_mode and not os.getenv("AEROAPI_API_KEY"):
                rumps.alert("API Key Missing", "Please set AEROAPI_API_KEY in .env file")
                return
            
            # Start monitoring
            self.monitoring = True
            self.start_time = datetime.now()
            self.last_check_start_time = datetime.now()
            self.total_transits_logged = 0
            self.stop_monitoring_flag.clear()
            
            logger.info(f"=== Monitoring Started ===")
            logger.info(f"Target: {self.target}, Location: ({self.latitude}, {self.longitude}), Interval: {self.interval}min")
            
            # Initialize transit log CSV with headers
            self._initialize_transit_log()
            
            sender.title = "Stop Monitoring"
            
            # Start monitor thread
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            rumps.notification(
                title="Monitor Started",
                subtitle=f"Tracking {self.target} transits",
                message=f"Checking every {self.interval} minutes"
            )
        else:
            # Stop monitoring
            self.monitoring = False
            self.stop_monitoring_flag.set()
            sender.title = "Start Monitoring"
            self.current_transits = []
            
            logger.info(f"=== Monitoring Stopped ===")
            logger.info(f"Total transits logged: {self.total_transits_logged}")
            
            rumps.notification(
                title="Monitor Stopped",
                subtitle="",
                message=f"Logged {self.total_transits_logged} transit(s)"
            )
        
        self.update_status_display()
    
    def _initialize_transit_log(self):
        """Initialize transit log CSV with header and session info."""
        try:
            date_ = date.today().strftime("%Y%m%d")
            log_path = POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
            
            # Create directory if needed
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            
            # If file doesn't exist, create it with header
            if not os.path.exists(log_path):
                with open(log_path, 'w') as f:
                    f.write("# Transit Log\n")
                    f.write(f"# Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Target: {self.target}, Observer: ({self.latitude}, {self.longitude})\n")
                    f.write("# Flight ID,Origin,Destination,Time(min),Alt_Diff,Az_Diff,Possibility\n")
                logger.info(f"Initialized transit log: {log_path}")
            else:
                # Append session marker
                with open(log_path, 'a') as f:
                    f.write(f"\n# New session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                logger.info(f"Appending to existing transit log: {log_path}")
        except Exception as e:
            logger.error(f"Error initializing transit log: {e}")
    
    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        check_count = 0
        
        while not self.stop_monitoring_flag.is_set():
            check_count += 1
            self.last_check_start_time = datetime.now()
            timestamp = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Check #{check_count} at {timestamp}")
            self.update_status_display()
            
            try:
                # Check for transits
                num_transits = self._check_and_log_transits()
                
                if num_transits > 0:
                    # Flash icon
                    self._flash_icon()
                
            except Exception as e:
                logger.error(f"Error during check: {e}")
            
            self.last_check_time = timestamp
            self.update_status_display()
            
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
        target_coords = data.get("targetCoordinates", {})
        weather_info = data.get("weather", {})
        tracking_targets = data.get("trackingTargets", [])
        
        # Store weather info for status display
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
        
        # Save to CSV (only MEDIUM/HIGH)
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
        
        # Log each transit with details
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
            target_icon = TARGET_TO_EMOJI.get(t.get('target', self.target), '')
            rumps.notification(
                title=f"Transit Alert! {target_icon}",
                subtitle=f"{t['id']} in {t['time']:.1f} min",
                message=f"{t['origin']}→{t['destination']}\nΔalt={t['alt_diff']:.2f}° Δaz={t['az_diff']:.2f}°",
                sound=True
            )
        
        logger.info(f"Found {len(notable_transits)} notable transit(s)")
        return len(notable_transits)
    
    def _flash_icon(self):
        """Flash the menu bar icon to indicate a transit."""
        if self.flash_active:
            return
        
        self.flash_active = True
        original_icon = self.title
        
        def flash():
            for _ in range(6):  # Flash 3 times
                self.title = "⚫"
                time.sleep(0.3)
                self.title = original_icon
                time.sleep(0.3)
            self.flash_active = False
        
        threading.Thread(target=flash, daemon=True).start()
    
    @rumps.clicked("View Transit Log")
    def view_transit_log(self, _):
        """Open today's transit log file in default viewer."""
        try:
            date_ = date.today().strftime("%Y%m%d")
            log_path = POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
            
            if not os.path.exists(log_path):
                rumps.notification(
                    title="No Transit Log Found",
                    subtitle="",
                    message=f"No transits logged today. Log path: {log_path}"
                )
                return
            
            subprocess.run(["open", log_path], check=True)
        except Exception as e:
            logger.error(f"Error viewing transit log: {e}")
            rumps.notification(
                title="Error",
                subtitle="",
                message=f"Could not open log: {str(e)}"
            )
    
    @rumps.clicked("View Monitor Log")
    def view_monitor_log(self, _):
        """Open today's monitor log file in default viewer."""
        try:
            if not MENUBAR_LOG_FILE.exists():
                rumps.notification(
                    title="No Monitor Log Found",
                    subtitle="",
                    message=f"Log file doesn't exist: {MENUBAR_LOG_FILE}"
                )
                return
            
            subprocess.run(["open", str(MENUBAR_LOG_FILE)], check=True)
        except Exception as e:
            logger.error(f"Error viewing monitor log: {e}")
            rumps.notification(
                title="Error",
                subtitle="",
                message=f"Could not open log: {str(e)}"
            )
    
    @rumps.clicked("Open Log Folder")
    def open_log_folder(self, _):
        """Open the folder containing log files."""
        try:
            # Extract directory from the log filename template
            log_dir = os.path.dirname(POSSIBLE_TRANSITS_LOGFILENAME.format(date_="20260130"))
            
            # Create directory if it doesn't exist
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            
            subprocess.run(["open", log_dir], check=True)
        except Exception as e:
            logger.error(f"Error opening log folder: {e}")
            rumps.notification(
                title="Error",
                subtitle="",
                message=f"Could not open log folder: {str(e)}"
            )
    
    @rumps.clicked("Quit")
    def quit_app(self, _):
        """Quit the application."""
        if self.monitoring:
            self.stop_monitoring_flag.set()
            time.sleep(0.5)
        rumps.quit_application()


def main():
    # Check for required dependencies
    try:
        import rumps
    except ImportError:
        print("Error: rumps not installed. Run: pip install rumps")
        exit(1)
    
    import argparse
    parser = argparse.ArgumentParser(description="macOS menu bar transit monitor")
    parser.add_argument("--latitude", type=float, help="Observer latitude")
    parser.add_argument("--longitude", type=float, help="Observer longitude")
    parser.add_argument("--elevation", type=float, default=0.0, help="Observer elevation in meters")
    parser.add_argument("--target", choices=["moon", "sun", "auto"], default="auto", help="Target celestial object")
    parser.add_argument("--interval", type=int, default=15, help="Check interval in minutes")
    args = parser.parse_args()
    
    app = TransitMonitor()
    
    # Override with command-line args if provided
    if args.latitude is not None:
        app.latitude = args.latitude
    if args.longitude is not None:
        app.longitude = args.longitude
    if args.elevation is not None:
        app.elevation = args.elevation
    app.target = args.target
    app.interval = args.interval
    if app.target == "auto":
        app.title = "🌙☀️"
    elif app.target == "moon":
        app.title = "🌙"
    else:
        app.title = "☀️"
    
    app.run()


if __name__ == "__main__":
    main()
