# Quick Start: Dual Tracking & Weather

## What Changed
Flymoon now tracks **both Moon and Sun** simultaneously when conditions permit, with real-time weather filtering.

## Instant Setup

### 1. Update .env file
Add these to your `.env` file:
```bash
OPENWEATHER_API_KEY=your_api_key_here  # Get free key at openweathermap.org
CLOUD_COVER_THRESHOLD=30
MIN_TARGET_ALTITUDE=15
MONITOR_TARGET=auto
```

### 2. Start the Web App
```bash
python3 app.py
```
Navigate to http://localhost:8000

### 3. Use Auto Mode
- Click the target icon to cycle through modes
- 🌙 = Moon only
- ☀️ = Sun only  
- 🌙☀️ = Auto (tracks both when visible & weather permits)

## What You'll See

### In the Web UI
- **Weather status line**: Shows current conditions and cloud cover
- **Tracking status**: Indicates which targets are currently trackable
  - Example: `🌙 moon: 23° ✓ | ☀️ sun: 8° ✗`
- **Target column**: Results show which celestial body each transit is for

### In macOS Menu Bar App
```bash
python3 menubar_monitor.py
```
Icon changes to 🌙☀️ in auto mode. Status menu shows:
- Weather conditions with icon
- Active tracking targets
- Individual transits with target indicators

### In Windows System Tray App
```bash
python windows_monitor.py
```
Same features as macOS, requires: `pip install pystray pillow`

## How It Works

### Auto Mode Logic
For each target (moon/sun):
1. ✅ Altitude ≥ 15° above horizon?
2. ✅ Cloud cover < 30%?
3. → If both YES: Track this target
4. → If NO: Skip this target

### Example Scenarios

**Scenario 1**: Day time, clear sky
- Moon: 10° altitude → ✗ (below 15°)
- Sun: 45° altitude → ✓ (tracking)
- Result: Only Sun transits shown

**Scenario 2**: Evening, partly cloudy (20%)
- Moon: 25° altitude → ✓ (tracking)
- Sun: -5° altitude → ✗ (below horizon)
- Result: Only Moon transits shown

**Scenario 3**: Rare alignment, clear sky
- Moon: 40° altitude → ✓ (tracking)
- Sun: 35° altitude → ✓ (tracking)
- Result: Both tracked, results merged with target column

**Scenario 4**: Overcast (80% clouds)
- Moon: 30° altitude → ✗ (weather)
- Sun: 50° altitude → ✗ (weather)
- Result: "No targets trackable" message

## Adjusting Settings

### Want to track in cloudy weather?
Edit `.env`:
```bash
CLOUD_COVER_THRESHOLD=80  # More permissive
```

### Lower altitude requirement?
Edit `.env`:
```bash
MIN_TARGET_ALTITUDE=10  # Track targets closer to horizon
```

### Force single target?
Edit `.env` or use web UI toggle:
```bash
MONITOR_TARGET=moon  # Only track Moon
```

## Testing

Test weather API:
```bash
python3 -c "from src.weather import get_weather_condition; import os; from dotenv import load_dotenv; load_dotenv(); print(get_weather_condition(33.0, -117.35, os.getenv('OPENWEATHER_API_KEY')))"
```

## Troubleshooting

### "No targets trackable" always shown?
- Check if Moon/Sun are above horizon at your location/time
- Verify cloud cover isn't too high
- Try lowering MIN_TARGET_ALTITUDE or increasing CLOUD_COVER_THRESHOLD

### Weather not updating?
- Cached for 1 hour by design (reduces API calls)
- Check logs for API errors
- System continues working even if weather API fails

### Want old behavior back?
Set target to "moon" or "sun" instead of "auto"

## Platform Notes

### macOS
- Universal binary compatible
- No code changes needed for Apple Silicon vs Intel

### Windows
- Install extra dependencies: `pip install pystray pillow`
- Uses system tray instead of menu bar
- Same functionality as macOS version

## Performance
- Weather API called max once per hour per location
- Dual tracking has minimal overhead vs single target
- Flight data fetched once, checked against both targets

---

**Need more details?** See `DUAL_TRACKING_WEATHER.md`
