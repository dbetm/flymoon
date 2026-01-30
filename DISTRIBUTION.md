# Flymoon Distribution Guide

## Overview
Flymoon is distributed in three formats:
1. **macOS Menu Bar App** - Native .app bundle with installer (.dmg)
2. **Windows System Tray App** - Native .exe with installer
3. **Web Application** - Cross-platform Flask app (tar.gz/zip)

---

## Building Distributions

### Prerequisites

**All Platforms**:
- Python 3.9+
- PyInstaller: `pip install pyinstaller`

**macOS DMG** (optional):
```bash
brew install create-dmg
```

**Windows Installer** (optional):
- NSIS (Nullsoft Scriptable Install System)

### Build Commands

```bash
cd build/

# Build everything (macOS + Web)
./build_all.sh

# Build only macOS app
./build_all.sh --mac-only

# Build only web distribution
./build_all.sh --web-only
```

### Build Outputs

After building, check `dist/` directory:
- `Flymoon.app` - macOS application bundle
- `Flymoon-macOS.dmg` - macOS installer (if create-dmg installed)
- `Flymoon-Web-v2.0.tar.gz` - Web distribution (Linux/macOS)
- `Flymoon-Web-v2.0.zip` - Web distribution (Windows)

---

## Installation Instructions

### macOS Menu Bar App

**From DMG** (Recommended):
1. Download `Flymoon-macOS.dmg`
2. Open the DMG file
3. Drag `Flymoon.app` to Applications folder
4. Launch from Applications or Spotlight
5. First run will prompt for configuration

**From .app Bundle**:
1. Download/extract `Flymoon.app`
2. Move to `/Applications/`
3. Right-click → Open (first time only, due to Gatekeeper)
4. Configure settings when prompted

**Configuration**:
- Icon appears in menu bar
- Click icon → "Edit Config" to set API keys
- Or edit `~/.flymoon/.env` manually

---

### Windows System Tray App

**From Installer** (Recommended):
1. Download `Flymoon-Windows-Setup.exe`
2. Run the installer
3. Follow the setup wizard
4. Launch from Start Menu or Desktop shortcut
5. Configure when prompted

**From .exe**:
1. Download `FlymoonTray.exe`
2. Place in desired location (e.g., `C:\Program Files\Flymoon\`)
3. Run the executable
4. Right-click tray icon → "Edit Config"

**Configuration**:
- Icon appears in system tray
- Right-click icon → "Edit Config"
- Or edit `.env` file in installation directory

---

### Web Application

**macOS/Linux**:
```bash
# Extract archive
tar -xzf Flymoon-Web-v2.0.tar.gz
cd Flymoon-Web

# Run setup
./setup.sh

# Start server
source .venv/bin/activate
python3 app.py

# Open browser
open http://localhost:8000
```

**Windows**:
```
# Extract Flymoon-Web-v2.0.zip
# Open folder in Command Prompt

# Run setup
setup.bat

# Start server
.venv\Scripts\activate.bat
python app.py

# Open browser to http://localhost:8000
```

**Docker** (Advanced):
```bash
cd Flymoon-Web
docker build -t flymoon .
docker run -p 8000:8000 \
  -e AEROAPI_API_KEY=your_key \
  -e OPENWEATHER_API_KEY=your_key \
  flymoon
```

---

## First-Run Configuration

All versions include an interactive configuration wizard.

### Required Settings:
1. **FlightAware AeroAPI Key**
   - Get free key: https://flightaware.com/aeroapi
   - Required for live flight data
   - Test mode works without key

2. **Observer Coordinates**
   - Your location (latitude, longitude, elevation)
   - Used for transit calculations
   - Can use maps.ie or Google Earth

3. **Bounding Box**
   - Area to search for flights
   - Should cover ~15-minute flight radius
   - Can use same coords as observer location ±2°

### Optional Settings:
4. **OpenWeatherMap API Key**
   - Get free key: https://openweathermap.org
   - Enables weather-based filtering
   - Not required, system works without

5. **Pushbullet API Key**
   - For mobile notifications
   - Optional convenience feature

### Configuration Files:
- **Menu Bar/Tray Apps**: Config stored in installation directory
- **Web App**: `.env` file in project directory
- **All versions**: Can run config wizard anytime

---

## Features by Version

| Feature | Web | macOS | Windows |
|---------|-----|-------|---------|
| Dual Tracking (🌙☀️) | ✅ | ✅ | ✅ |
| Weather Filtering | ✅ | ✅ | ✅ |
| Auto Mode | ✅ | ✅ | ✅ |
| Manual Refresh | ✅ | ❌ | ❌ |
| Background Monitoring | ❌ | ✅ | ✅ |
| Audio Alerts | ✅ | ❌ | ❌ |
| Desktop Notifications | ✅* | ✅ | ✅ |
| Visual UI | ✅ | ❌ | ❌ |
| Status Menu | ❌ | ✅ | ✅ |
| Test Mode | ✅ | ✅ | ✅ |

*Browser notification permission required

---

## Distribution Checklist

### Before Building:
- [ ] Update version numbers in spec files
- [ ] Update CHANGELOG.md
- [ ] Test all three versions
- [ ] Run linting: `make lint`
- [ ] Update documentation
- [ ] Create git tag: `git tag v2.0.0`

### Build Process:
- [ ] Clean previous builds: `rm -rf dist/ build/`
- [ ] Run build script: `./build/build_all.sh`
- [ ] Test generated packages
- [ ] Create checksums: `shasum -a 256 dist/*`

### Distribution:
- [ ] Upload to GitHub Releases
- [ ] Update README with download links
- [ ] Post release notes
- [ ] Update website (if applicable)

---

## Troubleshooting

### macOS: "App can't be opened"
```bash
# Remove quarantine attribute
xattr -dr com.apple.quarantine /Applications/Flymoon.app
```

### Windows: SmartScreen Warning
- Click "More info" → "Run anyway"
- Or: Sign the executable with a code signing certificate

### Web: Port Already in Use
```bash
# Change port in app.py
app.run(host="0.0.0.0", port=8001)  # Use different port
```

### Missing Dependencies
```bash
# Reinstall all dependencies
pip install --force-reinstall -r requirements.txt
```

### Configuration Issues
```bash
# Run config wizard manually
python3 src/config_wizard.py --setup

# Or validate existing config
python3 src/config_wizard.py --validate
```

---

## Advanced: Custom Builds

### Custom Icons
Replace `static/images/icon.icns` (macOS) or `icon.ico` (Windows) before building.

### Custom Branding
Edit build spec files:
- `build/macos_menubar.spec`
- `build/windows_tray.spec`

Change:
- `name` - Application name
- `bundle_identifier` - macOS bundle ID
- `version` - Version number
- `icon` - Icon file path

### Environment-Specific Builds
Create custom `.env.dist` for specific deployments:
```bash
cp .env .env.production
# Edit .env.production with production values
# Include in build: add to `datas` in spec file
```

---

## Support & Updates

### Check for Updates
- Web: `git pull origin main`
- macOS/Windows: Download new installer

### Automatic Updates
Not currently implemented. Manual update required.

### Version Information
```bash
# Check current version
python3 -c "import app; print(app.__version__)"

# Or check menubar/tray app "About" menu
```

---

## License & Distribution Rights

See LICENSE file for terms.

**TL;DR**:
- Free to use and modify
- Include attribution
- No warranty provided
- Commercial use allowed with attribution

---

## Building from Source

If you prefer to build from source instead of using releases:

```bash
# Clone repository
git clone https://github.com/yourusername/flymoon.git
cd flymoon

# Setup development environment
make setup

# Build distributions
cd build
./build_all.sh
```

See `README.md` for full development setup instructions.
