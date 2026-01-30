# Menu Bar Transit Monitor

macOS menu bar application for monitoring airplane transits with a persistent status icon.

## Features

- 🌙 **Menu bar icon** - Shows moon or sun emoji in your menu bar
- ⚡ **Flashing alerts** - Icon flashes when transits are detected
- 📊 **Status display** - Click icon to see uptime, transit count, and active transits
- 📝 **Auto-logging** - Only logs MEDIUM and HIGH possibility transits to CSV
- 🔔 **Smart notifications** - Extra notification for immediate transits (< 5 min)
- 🎯 **Easy configuration** - GUI dialogs for coordinates and settings

## Installation

1. Install the `rumps` dependency:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure your `.env` file with API key and bounding box

## Usage

### Start the App

```bash
source .venv/bin/activate
python3 menubar_monitor.py
```

The moon icon 🌙 will appear in your menu bar.

### First Time Setup

1. Click the menu bar icon
2. Select "Configure..."
3. Enter your coordinates: `latitude,longitude,elevation`
   - Example: `21.659,-105.22,0`
4. Choose target (moon or sun)
5. Set check interval in minutes (default: 15)

### Start Monitoring

1. Click the menu bar icon
2. Select "Start Monitoring"
3. The app runs in the background and checks at your configured interval

### Status Display

Click the menu bar icon to see:
- **Start time** and **uptime**
- **Target** being monitored
- **Total transits logged**
- **Last check time**
- **Active transits** with ETAs (when present)

Example:
```
Started: 14:23:15
Uptime: 2h 37m
Target: Moon
Transits logged: 8
Last check: 16:59:42

🔴 2 active transit(s):
  AA1234 in 8.3 min
  UA5678 in 12.7 min
```

### Visual Indicators

- **Normal**: 🌙 or ☀️ (depending on target)
- **Transit detected**: Icon flashes 3 times (🌙 ⚫ 🌙 ⚫ 🌙 ⚫)
- **Active transits**: Listed in status with 🔴 indicator

### Log Files

- **View Log** - Opens today's CSV log in default viewer
- **Open Log Folder** - Opens `data/possible-transits/` in Finder

Log format: `log_YYYYMMDD.csv`
- Only MEDIUM and HIGH possibility transits are logged
- Each transit includes: timestamp, flight ID, route, coordinates, differences

### Notifications

You'll receive notifications for:
1. **Monitor started** - Confirmation when monitoring begins
2. **Transit detected (< 5 min)** - Immediate alert with flight details
3. **Monitor stopped** - Summary when you stop monitoring

### Stop Monitoring

1. Click the menu bar icon
2. Select "Stop Monitoring"
3. You'll see a summary notification with total transits logged

### Quit the App

Click the menu bar icon → "Quit"

## Running at Login

To start the app automatically when you log in:

1. Open **System Settings** → **General** → **Login Items**
2. Click the **+** button
3. Add a script that runs:
   ```bash
   cd /Users/Tom/flymoon
   source .venv/bin/activate
   python3 menubar_monitor.py
   ```

Or use macOS Automator to create an Application that runs this command.

## Tips

- The app runs entirely in the background after starting
- Close Terminal after launching - the app stays in the menu bar
- Icon changes to ☀️ when monitoring the sun
- Status updates in real-time as transits are detected
- Logs are cumulative - multiple checks append to the same daily file

## Troubleshooting

**Icon doesn't appear:**
- Make sure `rumps` is installed: `pip install rumps`
- Check Console.app for Python errors

**No notifications:**
- Enable notifications for Terminal/Python in System Settings
- Check that your `.env` has a valid `AEROAPI_API_KEY`

**Can't start monitoring:**
- Configure coordinates first via "Configure..."
- Verify API key in `.env` file
