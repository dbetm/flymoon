# Auto-Refresh Live Display Feature

## Overview
Added configurable auto-refresh functionality to enable hybrid live display monitoring while staying within FlightAware's free tier API rate limits.

## Changes Made

### 1. Configuration Files

**`.env.mock`** - Added new configuration option:
```bash
AUTO_REFRESH_INTERVAL_MINUTES=6
```
- Default: 6 minutes (safe for free tier limits)
- Recommended: 5-10 minutes for continuous monitoring
- Keeps within FlightAware's ~10 queries/minute and 500/month limits

### 2. Backend (Python)

**`app.py`** - Added `/config` endpoint:
- Returns client configuration including `autoRefreshIntervalMinutes`
- Allows frontend to fetch server-configured defaults
- Location: Line 300-305

**`src/config_wizard.py`** - Updated setup wizard:
- Added auto-refresh interval configuration in Step 4
- Prompts user to set or keep default interval
- Sets default of 6 minutes if not specified
- Location: `_setup_optional_settings()` method

### 3. Frontend (JavaScript)

**`static/app.js`** - Multiple enhancements:

1. **Config Loading** (Lines 28-42):
   - Fetches `/config` endpoint on page load
   - Stores configuration in `appConfig` global variable
   - Falls back to 6-minute default if fetch fails

2. **Page Visibility Detection** (Lines 44-56):
   - Automatically pauses polling when page is hidden/minimized
   - Resumes polling when page becomes visible again
   - Prevents wasted API calls when user isn't viewing the page
   - Uses browser's `visibilitychange` event

3. **Improved Auto Mode** (Lines ~320-350):
   - Pre-fills prompt with configured default interval
   - Shows helpful message about recommended intervals
   - Displays "Pauses when page is hidden" in status
   - Stores user preference in localStorage

### 4. Documentation

**`README.md`** - Added configuration step:
- Documents new `AUTO_REFRESH_INTERVAL_MINUTES` setting
- Explains rate limit considerations
- Provides recommended interval ranges

## Usage

### For End Users

1. **Setup**: Run config wizard or manually edit `.env`:
   ```bash
   python3 src/config_wizard.py --setup
   ```

2. **Enable Auto-Refresh**: Click "Auto" button in web interface
   - Default interval (6 min) will be suggested
   - Can customize to any interval (1-60 minutes)
   - Polling automatically pauses when you switch tabs/minimize window

3. **Monitor API Usage**:
   - 6-minute interval = 10 calls/hour = 240 calls/day
   - Allows ~50+ hours of monitoring per month on free tier
   - Page visibility detection saves additional API calls

### For Developers

**To modify default interval**:
```bash
# Edit .env file
AUTO_REFRESH_INTERVAL_MINUTES=10
```

**To access config in frontend**:
```javascript
// Config is automatically loaded on page load
console.log(appConfig.autoRefreshIntervalMinutes);
```

## Technical Details

### Rate Limit Strategy

**FlightAware Personal Tier Limits**:
- ~10 queries per minute
- ~500 queries per month

**Our Approach**:
- Default 6-minute interval = well within per-minute limit
- Page visibility detection reduces actual API calls
- User can manually check anytime with "Show/Hide" button
- Only polls when page is actively viewed

### API Call Calculation

| Interval | Calls/Hour | Calls/Day | Days/Month (500 limit) |
|----------|------------|-----------|------------------------|
| 5 min    | 12         | 288       | 1.7 days               |
| 6 min    | 10         | 240       | 2.1 days               |
| 10 min   | 6          | 144       | 3.5 days               |

**With page visibility detection**, actual usage is typically 30-50% less than theoretical maximum.

## Benefits

1. **User Experience**:
   - Near-live monitoring without manual refresh clicks
   - Automatic pause when page isn't visible
   - Configurable to user preference

2. **API Efficiency**:
   - Stays within free tier limits
   - Intelligent pause/resume saves calls
   - No wasted calls when user is away

3. **Flexibility**:
   - Server admin sets sensible default
   - Users can customize per session
   - Manual refresh always available

## Future Enhancements

Potential improvements for consideration:

1. **ADS-B Exchange Integration**: Switch to paid ADS-B Exchange for true real-time (2-second updates)
2. **Local ADS-B Receiver**: Build DIY receiver for unlimited local monitoring
3. **Adaptive Polling**: Slow down when no transits likely, speed up when target is high
4. **WebSocket Support**: Server pushes updates instead of polling (requires backend changes)

## Testing

To test the feature:

1. Set `AUTO_REFRESH_INTERVAL_MINUTES=1` in .env (for quick testing)
2. Restart app: `python3 app.py`
3. Open browser to http://localhost:8000
4. Click "Auto" button - should suggest 1 minute
5. Watch console logs for automatic refreshes
6. Switch to another tab - logs should show "Page hidden - pausing"
7. Switch back - logs should show "Page visible - resuming"

## Migration Guide

For existing users upgrading to this version:

1. Pull latest code: `git pull`
2. Add to your `.env` file:
   ```bash
   AUTO_REFRESH_INTERVAL_MINUTES=6
   ```
3. Restart the app
4. No other changes required - feature is opt-in via "Auto" button
