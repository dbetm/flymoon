# Attribution & Acknowledgments

## Original Project

**Flymoon** was originally created by **David Betancourt Montellano (dbetm)**

- **Original Repository**: https://github.com/dbetm/flymoon
- **License**: MIT License
- **Original Concept**: Web app to check for airplane transits over the Moon or Sun

### Original Features
The baseline Flymoon application provided:
- Web-based interface for transit detection
- FlightAware AeroAPI integration for real-time flight data
- Skyfield-based astronomical calculations
- Alt-azimuthal coordinate computation
- 15-minute predictive window
- Visual highlighting of possible transits (yellow/orange/green)
- Audio alerts for detected transits
- Pushbullet notification support
- Auto-refresh mode

All core transit detection algorithms, astronomical calculations, and the fundamental concept of predicting aircraft-celestial body intersections are credited to the original author.

---

## Enhancements in This Version (v2.0)

This version builds upon the excellent foundation provided by dbetm with the following additions:

### 1. Dual Target Tracking
- **Added**: Simultaneous tracking of both Moon and Sun
- **Implementation**: New "auto" mode in `src/transit.py`
- **UI**: Combined icon (🌙☀️) and target toggle
- **Original Code**: Single target selection (moon OR sun)
- **Enhancement**: Automatic selection based on altitude and weather

### 2. Weather Integration
- **Added**: OpenWeatherMap API integration (`src/weather.py`)
- **Feature**: Cloud cover-based filtering
- **Feature**: Hourly weather caching
- **Feature**: Configurable thresholds
- **Original Code**: No weather consideration
- **Enhancement**: Prevents tracking in poor weather conditions

### 3. Desktop Notifications (Web)
- **Added**: Browser Notification API integration
- **Feature**: Desktop popup notifications
- **Feature**: Permission management
- **Original Code**: Audio alerts only
- **Enhancement**: Native OS-level notifications in browser

### 4. Configuration Wizard
- **Added**: Interactive setup wizard (`src/config_wizard.py`)
- **Feature**: First-run guided configuration
- **Feature**: Validation with helpful error messages
- **Original Code**: Manual .env editing
- **Enhancement**: User-friendly setup process

### 5. Cross-Platform Native Apps
- **Added**: macOS menu bar application (`menubar_monitor.py`)
- **Added**: Windows system tray application (`windows_monitor.py`)
- **Feature**: Background monitoring
- **Feature**: Native OS notifications
- **Original Code**: Web-only interface
- **Enhancement**: Three distribution formats

### 6. Distribution System
- **Added**: Automated build system (`build/build_all.sh`)
- **Added**: PyInstaller configurations
- **Feature**: Packaged distributions with installers
- **Feature**: Setup scripts for all platforms
- **Original Code**: Git clone + manual setup
- **Enhancement**: One-click installation experience

### 7. Test Data Generator
- **Added**: Configurable test scenarios (`data/test_data_generator.py`)
- **Feature**: 6 pre-configured scenarios
- **Feature**: Custom scenario creation
- **Original Code**: Single example data file
- **Enhancement**: Comprehensive testing capabilities

### 8. Enhanced Documentation
- **Added**: Complete technical documentation suite
- **Files**: DUAL_TRACKING_WEATHER.md, QUICKSTART_DUAL_TRACKING.md, DISTRIBUTION.md, TEST_RESULTS.md
- **Original Code**: README.md only
- **Enhancement**: Comprehensive user and developer guides

---

## Code Preservation

All original algorithms and core functionality remain intact:
- Transit detection logic (`src/transit.py` - `check_transit()` function)
- Position prediction using Haversine formula (`src/position.py`)
- Astronomical calculations (`src/astro.py`)
- Flight data parsing (`src/flight_data.py`)
- Web interface structure (`templates/index.html`, `static/`)

The enhancements are **additive** - they extend the original functionality without replacing or removing the baseline code.

---

## Changes to Original Files

### Modified Files:
1. **src/transit.py**
   - Original: Single target processing
   - Added: Dual target support, weather checking
   - Preserved: All original transit detection algorithms

2. **src/constants.py**
   - Added: Weather-related constants, dual target emoji
   - Preserved: All original constants

3. **static/app.js**
   - Added: Desktop notification functions, weather display
   - Preserved: Original UI logic, audio alerts, auto-refresh

4. **templates/index.html**
   - Added: Weather status, tracking status, notification button
   - Preserved: Original layout and functionality

5. **app.py**
   - Added: Config validation on startup
   - Preserved: All original Flask routes and logic

6. **menubar_monitor.py** (existing file, enhanced)
   - Added: Dual tracking, weather display
   - Preserved: Original monitoring logic

### New Files Created:
- `src/weather.py` - Weather API integration
- `src/config_wizard.py` - Configuration wizard
- `windows_monitor.py` - Windows version
- `build/*` - Build system
- `data/test_data_generator.py` - Test data
- Documentation files (*.md)

---

## License Compliance

This enhanced version maintains the **MIT License** from the original project.

All enhancements are contributed under the same MIT License terms, ensuring:
- Free use and modification
- Attribution to original author required
- No warranty
- Commercial use permitted

---

## Credits

### Original Author
**David Betancourt Montellano (dbetm)**
- Original concept and implementation
- Core transit detection algorithms
- FlightAware API integration
- Skyfield astronomical calculations

### Enhancements
**Version 2.0 Enhancements**
- Dual tracking system
- Weather integration
- Cross-platform native apps
- Distribution system
- Configuration wizard
- Enhanced documentation

---

## Contributing

When contributing to this project, please:
1. Acknowledge the original work by dbetm
2. Maintain the MIT License
3. Document your enhancements clearly
4. Keep the original algorithms intact
5. Add features additively when possible

---

## References

- **Original Project**: https://github.com/dbetm/flymoon
- **FlightAware AeroAPI**: https://flightaware.com/aeroapi
- **Skyfield Library**: https://rhodesmill.org/skyfield/
- **OpenWeatherMap API**: https://openweathermap.org

---

## Thank You

Special thanks to **dbetm** for creating Flymoon and sharing it as open source. This project wouldn't exist without that excellent foundation. The core idea of predicting aircraft transits across celestial bodies is brilliant, and the implementation is solid. These enhancements aim to make it even more accessible and useful to a wider audience.

If you use this enhanced version, please consider:
- ⭐ Starring the original repository: https://github.com/dbetm/flymoon
- 📸 Sharing your transit photos on the original project's issue tracker
- 🤝 Contributing back to the original project
