# Background Transit Monitor

Run Flymoon as a background service that sends native macOS notifications when transits are detected.

## Features

- Continuous monitoring at configurable intervals
- Native macOS notifications with sound alerts
- Shows flight details (ID, route, ETA, angular differences)
- Only notifies for MEDIUM and HIGH possibility transits
- Automatically skips checks when target is below horizon

## Usage

### Quick Start

1. Edit `start_monitor.sh` with your coordinates:
```bash
LATITUDE=21.659
LONGITUDE=-105.22
ELEVATION=0
TARGET=moon
INTERVAL=15
```

2. Run the monitor:
```bash
./start_monitor.sh
```

### Manual Invocation

```bash
python3 monitor.py \
    --latitude 21.659 \
    --longitude -105.22 \
    --elevation 0 \
    --target moon \
    --interval 15
```

### Command Options

- `--latitude`: Observer latitude (required)
- `--longitude`: Observer longitude (required)
- `--elevation`: Observer elevation in meters (required)
- `--target`: Either `moon` or `sun` (default: moon)
- `--interval`: Check interval in minutes (default: 15)
- `--test`: Use cached flight data instead of live API calls

### Test Mode

Test the monitor without using API credits:
```bash
python3 monitor.py --latitude 21.659 --longitude -105.22 --elevation 0 --test
```

## Notifications

When a transit is detected, you'll receive:
- **Title**: Possibility level (MEDIUM/HIGH) and count
- **Body**: Flight ID, ETA, route, angular differences
- **Sound**: macOS "Submarine" alert sound

Example notification:
```
HIGH possibility transit 🌙
AA1234 in 8.3 min
Los Angeles→New York
Δalt=0.45° Δaz=1.23°
```

## Running in Background

To keep the monitor running even when the terminal is closed:

```bash
nohup ./start_monitor.sh > monitor.log 2>&1 &
```

View the log:
```bash
tail -f monitor.log
```

Stop the background process:
```bash
pkill -f monitor.py
```

## Tips

- Set interval to match the 15-minute prediction window (e.g., 10-15 min)
- Monitor logs to see check activity: transits found, target visibility, errors
- Press `Ctrl+C` to stop gracefully (sends a "stopped" notification)
- Make sure system notifications are enabled for Terminal in macOS System Settings
