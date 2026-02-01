# Distance Unit Change: Kilometers to Nautical Miles

## Overview
Changed the distance display in the results table from kilometers (km) to nautical miles (nm), as nautical miles are the standard unit for aviation.

## Conversion Factor
- **1 kilometer = 0.539957 nautical miles**
- **1 nautical mile = 1.852 kilometers**

## Changes Made

### 1. Backend (Python) - `src/transit.py`

**Distance Calculation** (Line ~142-148):
```python
distance_km = R * c
distance_nm = distance_km * 0.539957  # Convert km to nautical miles
```

**All Response Objects** - Changed field name:
- Old: `"distance_km": round(distance_km, 1)`
- New: `"distance_nm": round(distance_nm, 1)`

**Mock Data** - Updated all hardcoded values:
- 15 km → 8.1 nm
- 20 km → 10.8 nm
- 25 km → 13.5 nm

### 2. Frontend (JavaScript) - `static/app.js`

**Column Names Array** (Line ~15):
```javascript
// Old:
"distance_km"

// New:
"distance_nm"
```

**Display Logic** (Line ~561):
```javascript
// Old:
else if (column === "distance_km") {
    // Show distance in km with one decimal place

// New:
else if (column === "distance_nm") {
    // Show distance in nautical miles with one decimal place
```

### 3. Frontend (HTML) - `templates/index.html`

**Table Header** (Line ~123):
```html
<!-- Old: -->
<th>dist (km)</th>

<!-- New: -->
<th>dist (nm)</th>
```

## Examples

### Distance Conversions
| Kilometers | Nautical Miles | Use Case                    |
|------------|----------------|------------------------------|
| 10 km      | 5.4 nm         | Very close aircraft          |
| 15 km      | 8.1 nm         | Typical transit distance     |
| 20 km      | 10.8 nm        | Medium distance              |
| 25 km      | 13.5 nm        | Farther aircraft             |
| 50 km      | 27.0 nm        | Edge of search area          |

### Before vs After Display

**Before:**
```
Flight ABC123 - dist: 15.0 km
```

**After:**
```
Flight ABC123 - dist: 8.1 nm
```

## Why Nautical Miles?

Nautical miles are the standard unit in aviation because:

1. **Aviation Standard**: All aviation charts, ATC communications, and flight plans use nautical miles
2. **Earth-Related**: 1 nautical mile = 1 minute of latitude (easy calculations)
3. **Speed Consistency**: Aircraft speeds are measured in knots (nautical miles per hour)
4. **International**: Used worldwide in aviation (ICAO standard)

## Impact

### User Interface
- Table column header now shows "dist (nm)" instead of "dist (km)"
- All distance values are ~54% of their previous values
- More consistent with aviation terminology

### Calculations
- Internal calculations remain unchanged (still use km for haversine formula)
- Only the final display value is converted to nautical miles
- No impact on transit detection accuracy

### Data Storage
- JSON field renamed from `distance_km` to `distance_nm`
- CSV logs (if any) will now show nm values
- Historical data may need conversion if comparing with old logs

## Testing

To verify the change:

1. Start the app: `python3 app.py`
2. Click "Show/Hide" to fetch flights
3. Check the "dist (nm)" column in the results table
4. Verify values are reasonable (typically 5-30 nm for visible aircraft)

Example validation:
- If you see a plane ~15-20 km away on FlightAware
- It should show ~8-11 nm in your app
- Use: `km * 0.54 ≈ nm` for quick mental math

## Backward Compatibility

### Breaking Changes
- API response field name changed: `distance_km` → `distance_nm`
- If you have external tools reading the JSON, update them to use `distance_nm`

### Migration
No migration needed for:
- End users (just see different units)
- Existing .env configuration
- Saved positions or settings

## Related Files Changed

```
✓ src/transit.py          - Calculation and field name
✓ static/app.js           - Column name and display
✓ templates/index.html    - Table header
```

## Files NOT Changed (Intentional)

```
○ tests/transit_validator.py  - Uses km internally (correct)
○ data/test_data_generator.py - Internal calculations (correct)
○ src/position.py             - Internal position math (correct)
```

These files use km for internal calculations (haversine formula), which is correct and doesn't need changing.
