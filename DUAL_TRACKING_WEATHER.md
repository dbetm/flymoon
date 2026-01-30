# Dual Tracking and Weather Features

## Overview
Flymoon now supports simultaneous tracking of both Moon and Sun transits with weather-based filtering. The system automatically determines which targets are visible and trackable based on altitude and weather conditions.

## New Features

### 1. Dual Target Tracking
- **Auto Mode**: Automatically tracks both Moon and Sun when conditions permit
- **Individual Modes**: Choose to track only Moon or only Sun
- **Combined Icon**: 🌙☀️ displayed when in auto mode
- **Smart Filtering**: Only tracks targets that are:
  - Above configurable minimum altitude (default 15°)
  - Under acceptable weather conditions

### 2. Weather Integration
- **OpenWeatherMap API**: Real-time weather data with hourly caching
- **Cloud Cover Threshold**: Configurable (default <30% clouds)
- **Weather Display**: Shows current conditions, cloud percentage, and tracking viability
- **Failure Handling**: Continues operation if weather API fails (logs warning)

### 3. Cross-Platform Monitor Apps

#### macOS Menu Bar App (`menubar_monitor.py`)
- Menu bar icon changes based on target mode
- Status display includes:
  - Weather conditions with icon
  - Active tracking targets
  - Individual transit alerts with target icons
- Universal binary compatible

#### Windows System Tray App (`windows_monitor.py`)
- System tray icon with context menu
- Same features as macOS version
- Notifications for transits
- Requires: `pip install pystray pillow`

## Configuration

### Environment Variables (.env)
```bash
# Weather API
OPENWEATHER_API_KEY=your_key_here
CLOUD_COVER_THRESHOLD=30          # Percentage (0-100)

# Transit settings
MIN_TARGET_ALTITUDE=15             # Degrees above horizon

# Monitor settings (for menubar/tray apps)
MONITOR_TARGET=auto                # auto, moon, or sun
MONITOR_INTERVAL=15                # Minutes between checks
```

### Web UI
- Click the target icon to cycle: 🌙 → ☀️ → 🌙☀️
- Default mode is "auto" (tracks both)
- Results table includes "target" column showing which celestial body

## Usage

### Web Application
```bash
python3 app.py
# Navigate to http://localhost:8000
# Select target mode by clicking icon
```

### macOS Menu Bar
```bash
python3 menubar_monitor.py
# Or with CLI args:
python3 menubar_monitor.py --target auto --interval 15
```

### Windows System Tray
```bash
python windows_monitor.py
# Or with CLI args:
python windows_monitor.py --target auto --interval 15
```

## API Response Format

### New Fields in `/flights` endpoint response:
```json
{
  "flights": [
    {
      "id": "ABC123",
      "target": "moon",
      ...
    }
  ],
  "targetCoordinates": {
    "moon": {"altitude": 23.5, "azimuthal": 145.2},
    "sun": {"altitude": 45.1, "azimuthal": 230.8}
  },
  "trackingTargets": ["moon", "sun"],
  "weather": {
    "cloud_cover": 15,
    "condition": "partly_cloudy",
    "icon": "⛅",
    "description": "few clouds",
    "api_success": true
  }
}
```

## Technical Details

### Weather Caching
- Cache duration: 60 minutes (configurable in `constants.py`)
- Cache key: `"{latitude:.3f},{longitude:.3f}"`
- Automatic expiration and refresh

### Transit Logic Changes
- `get_transits()` now accepts `target_name="auto"`
- Checks both targets independently when in auto mode
- Combines results into single flight list with target attribution
- Early exit if no targets are trackable

### Target Determination
For each target (moon/sun):
1. Calculate current altitude
2. Check if altitude ≥ MIN_TARGET_ALTITUDE
3. Check if weather permits (cloud_cover < CLOUD_COVER_THRESHOLD)
4. Only track if both conditions met

### Icon States
| Mode | Icon | Description |
|------|------|-------------|
| moon | 🌙 | Moon only |
| sun | ☀️ | Sun only |
| auto | 🌙☀️ | Both targets |

## Weather Condition Icons
- ☀️ Clear
- ⛅ Partly cloudy
- ☁️ Cloudy
- 🌧️ Rain
- 🌨️ Snow
- ⛈️ Thunderstorm
- ❓ Unknown/Error

## Troubleshooting

### Weather API not working
- Verify `OPENWEATHER_API_KEY` in .env
- Check logs for API errors
- System continues with warning if API fails

### No targets trackable
- Check target altitudes in UI status
- Verify MIN_TARGET_ALTITUDE setting
- Check cloud cover percentage vs threshold
- Wait for better conditions or adjust thresholds

### Windows dependencies
```bash
pip install pystray pillow
```

### macOS dependencies
```bash
pip install rumps
```

## Performance Notes
- Weather API called max once per hour per location
- Dual tracking processes flight data once, checks against both targets
- No significant performance impact vs single target mode

## Future Enhancements
- Custom weather providers
- Per-target cloud cover thresholds
- Visual sky chart overlay
- Historical tracking statistics
- Email/SMS notifications
