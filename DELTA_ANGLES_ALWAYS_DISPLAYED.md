# Delta Angles Always Displayed

## Overview
Modified the transit calculation to always display delta angle (△angle) and delta azimuth (△az) for ALL aircraft, not just those with possible transits.

## Problem Before

Previously, these columns were only populated for aircraft with possible transits (angular separation ≤ 6°):
- **△angle** (alt_diff) - difference in altitude angle between plane and target
- **△az** (az_diff) - difference in azimuth angle between plane and target

For aircraft with no transit possibility, these showed as empty cells (null values).

## Solution

Now these values are **always calculated and displayed** for every aircraft, showing users:
- How close each aircraft is to the celestial target
- Why certain aircraft are not flagged as possible transits
- Real-time angular differences even for distant aircraft

## Changes Made

### Backend (`src/transit.py`)

1. **Calculate current differences for all aircraft** (Line ~160):
```python
# Calculate current differences with target for ALL aircraft
current_alt_diff = abs(current_alt - initial_target_alt)
current_az_diff = abs(current_az - initial_target_az)
current_angular_sep = calculate_angular_separation(current_alt_diff, current_az_diff)
```

2. **Update non-transit response** (Line ~276-278):
```python
# Before:
response["alt_diff"] = None
response["az_diff"] = None
response["angular_separation"] = None

# After:
response["alt_diff"] = round(float(current_alt_diff), 3)
response["az_diff"] = round(float(current_az_diff), 3)
response["angular_separation"] = round(float(current_angular_sep), 3)
```

3. **Update fallback response** (Line ~291-293):
```python
# Before:
"alt_diff": None,
"az_diff": None,
"angular_separation": None,

# After:
"alt_diff": round(float(current_alt_diff), 3),
"az_diff": round(float(current_az_diff), 3),
"angular_separation": round(float(current_angular_sep), 3),
```

4. **Updated mock data** (Lines ~530-610):
   - Added realistic angle differences for non-transit demo flights
   - Shows examples of aircraft far from targets (130°, 40°, 140° separations)

### Frontend

No changes needed! The JavaScript already handles these values correctly:
- Line 540-541: Shows empty cells for null values (no longer happens)
- Line 566-572: Formats and color-codes angle differences
- Gray color for large differences (>10°)

## Examples

### Before (Non-Transit Aircraft)
```
Flight NONE_01
  △angle: [empty]
  △az: [empty]
```

### After (Non-Transit Aircraft)
```
Flight NONE_01
  △angle: 15°
  △az: 130°
```

This immediately shows why it's not a possible transit - the aircraft is 130° away in azimuth!

## Benefits

1. **Better Situational Awareness**
   - See which aircraft are "close but not close enough"
   - Understand the geometry of the sky at a glance
   - Identify aircraft that might become transits if they change course

2. **Educational Value**
   - Users can learn what angular separations look like
   - Understand why 6° threshold makes sense for transit flagging
   - See how aircraft move relative to celestial targets

3. **Debugging & Validation**
   - Easy to verify calculations are correct
   - Can spot anomalies in flight data
   - Helps understand why certain flights are/aren't flagged

## Technical Details

### Calculation Method

For all aircraft at their current position:
```
alt_diff = |plane_altitude - target_altitude|
az_diff = |plane_azimuth - target_azimuth|
angular_separation = √(alt_diff² + az_diff²)
```

Where:
- Plane altitude/azimuth: calculated using skyfield's `altaz()` method
- Target altitude/azimuth: current position of sun/moon
- All angles in degrees

### Display Format

- Rounded to whole degrees for alt_diff and az_diff (e.g., "15°")
- Rounded to 3 decimal places in JSON (for precision)
- Color coded: gray if >10° (distant)
- Always visible in table (no more empty cells)

## Testing

Test with mock data:
```bash
python3 app.py --demo
```

Then check the web interface:
- Click "Show/Hide"
- Look at flights labeled "NONE_01", "NONE_02", "PRIV01"
- Should see large angle differences (40°, 130°, 140°)
- These demonstrate non-transit aircraft

## Impact

### User Experience
✅ More informative table - no empty cells
✅ Better understanding of sky geometry
✅ Can see "near misses" (e.g., 7° separation)

### Performance
✅ No impact - values already calculated, just not displayed
✅ Minimal extra computation (3 lines of math per aircraft)

### Data Size
✅ Negligible - changes null to numeric values (~5 bytes per field)

## Related Files

```
✓ src/transit.py          - Calculation logic
✓ static/app.js           - Display logic (no changes needed)
```

## Migration

No migration needed - this is purely additive. Existing functionality unchanged.
