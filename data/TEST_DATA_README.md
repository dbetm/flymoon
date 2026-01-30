# Test Data Generator

## Overview
The test data generator creates configurable flight scenarios for testing and demonstration without requiring live FlightAware API access.

## Quick Start

### List Available Scenarios
```bash
python3 data/test_data_generator.py --list-scenarios
```

### Generate Test Data
```bash
# Generate dual tracking scenario (default)
python3 data/test_data_generator.py --scenario dual_tracking

# Generate moon-only scenario
python3 data/test_data_generator.py --scenario moon_only

# Generate perfect conditions
python3 data/test_data_generator.py --scenario perfect
```

### Run App with Test Data
```bash
python3 app.py --test
# Then navigate to http://localhost:8000
```

## Available Scenarios

### 1. dual_tracking (Default)
**Description**: Both Moon and Sun visible with multiple transits  
**Configuration**:
- Moon altitude: 40°
- Sun altitude: 35°
- Moon transits: 2 flights (MOON000, MOON001)
- Sun transits: 2 flights (SUN000, SUN001)
- Regular flights: 6 (REG000-REG005)
- Cloud cover: 15% (trackable)

**Expected Behavior**: Both targets tracked, results show transits for both Moon and Sun with target column indicating which celestial body.

### 2. moon_only
**Description**: Only Moon visible (Sun below horizon)  
**Configuration**:
- Moon altitude: 25°
- Sun altitude: -10° (below horizon)
- Moon transits: 3
- Sun transits: 0
- Regular flights: 7
- Cloud cover: 20%

**Expected Behavior**: Only Moon tracked, Sun skipped (below horizon).

### 3. sun_only
**Description**: Only Sun visible (Moon below horizon)  
**Configuration**:
- Moon altitude: -5° (below horizon)
- Sun altitude: 50°
- Moon transits: 0
- Sun transits: 3
- Regular flights: 7
- Cloud cover: 10%

**Expected Behavior**: Only Sun tracked, Moon skipped (below horizon).

### 4. cloudy
**Description**: Clear alignments but weather prevents tracking  
**Configuration**:
- Moon altitude: 45°
- Sun altitude: 40°
- Moon transits: 2
- Sun transits: 2
- Regular flights: 6
- Cloud cover: 85% (above 30% threshold)

**Expected Behavior**: Both targets above horizon but NOT tracked due to cloud cover. Message: "No targets available for tracking (below horizon or weather)".

### 5. low_altitude
**Description**: Targets below minimum altitude threshold  
**Configuration**:
- Moon altitude: 12° (below 15° threshold)
- Sun altitude: 8° (below 15° threshold)
- Moon transits: 1
- Sun transits: 1
- Regular flights: 8
- Cloud cover: 5%

**Expected Behavior**: Neither target tracked (below MIN_TARGET_ALTITUDE). Weather is good but altitudes too low.

### 6. perfect
**Description**: Perfect conditions with close transits  
**Configuration**:
- Moon altitude: 60°
- Sun altitude: 55°
- Moon transits: 3
- Sun transits: 3
- Regular flights: 4
- Cloud cover: 0% (perfectly clear)

**Expected Behavior**: Both targets tracked with optimal conditions. Should show HIGH possibility transits.

## Custom Configuration

### Interactive Mode
```bash
python3 data/test_data_generator.py --custom
```
You'll be prompted for:
- Moon altitude
- Sun altitude
- Number of Moon transits
- Number of Sun transits
- Number of regular flights
- Cloud cover percentage

### Custom Output Path
```bash
python3 data/test_data_generator.py --scenario perfect --output data/my_test.json
```

## Flight Naming Convention

Generated flights follow these patterns:
- **MOON###**: Flights positioned for Moon transits
- **SUN###**: Flights positioned for Sun transits
- **REG###**: Regular flights (no transit expected)

## How It Works

### Flight Positioning
The generator positions flights based on scenario requirements:

1. **Transit Flights**: Placed near the target's expected position (base lat: 23°, lon: -103°)
   - Moon transits: Slightly offset to create realistic separation angles
   - Sun transits: Different offset pattern for variety

2. **Regular Flights**: Positioned away from celestial targets to avoid false positives

### Metadata
Each generated file includes `_test_metadata` with:
- Scenario name
- Generation timestamp
- Expected celestial altitudes
- Expected cloud cover
- Expected transit counts (for validation)

Example metadata:
```json
{
  "_test_metadata": {
    "scenario": "dual_tracking",
    "generated_at": "2026-01-30T15:20:00",
    "moon_altitude": 40,
    "sun_altitude": 35,
    "cloud_cover": 15,
    "expected_moon_transits": 2,
    "expected_sun_transits": 2
  }
}
```

## Testing Workflow

### 1. Generate Test Scenario
```bash
python3 data/test_data_generator.py --scenario dual_tracking
```

### 2. Run App in Test Mode
```bash
python3 app.py --test
```

### 3. Open Browser
Navigate to http://localhost:8000

### 4. Set Observer Position
Enter coordinates (e.g., lat: 23, lon: -103, elev: 0)

### 5. Verify Behavior
- Check weather status display
- Check tracking status (which targets are active)
- Verify target column in results
- Check for transit alerts (auto mode)

## Alert Testing

### Sound Alert (Web UI)
1. Generate scenario with transits (e.g., `perfect`)
2. Run `python3 app.py --test`
3. Enable Auto mode in web UI
4. Click "Go" - should hear sound for MEDIUM/HIGH transits

### Notification Testing (Pushbullet)
1. Set `PUSH_BULLET_API_KEY` in `.env`
2. Enable Auto mode with `send-notification=true`
3. MEDIUM/HIGH transits will trigger notifications

## Troubleshooting

### No Transits Detected
- Check that test flights are in the configured bounding box (`.env`)
- Verify observer coordinates are near base position (23°, -103°)
- Check that targets meet altitude and weather thresholds

### All Flights Show Same Target
- This is expected if only one target is above horizon/trackable
- Use `dual_tracking` or `perfect` scenarios for both targets

### Weather Always Shows "Unknown"
- Weather API only called in non-test mode with real coordinates
- In test mode, weather check still happens but uses cached/default values

## Advanced Usage

### Multiple Test Files
```bash
# Generate multiple scenarios
python3 data/test_data_generator.py --scenario moon_only --output data/test_moon.json
python3 data/test_data_generator.py --scenario sun_only --output data/test_sun.json

# Switch between them
# Edit constants.py: TEST_DATA_PATH = "data/test_moon.json"
python3 app.py --test
```

### Scripted Testing
```bash
#!/bin/bash
for scenario in dual_tracking moon_only sun_only cloudy low_altitude perfect; do
    echo "Testing $scenario..."
    python3 data/test_data_generator.py --scenario $scenario
    python3 app.py --test &
    APP_PID=$!
    sleep 5
    # Run automated tests here
    kill $APP_PID
done
```

## Related Files
- `data/test_data_generator.py` - Generator script
- `data/raw_flight_data_example.json` - Current test data
- `src/constants.py` - `TEST_DATA_PATH` configuration
- `src/transit.py` - Loads test data when `test_mode=True`
