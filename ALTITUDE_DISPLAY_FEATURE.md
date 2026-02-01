# Altitude Display Feature

## Overview
Implemented the altitude profile display that shows aircraft at their proper altitudes from 0 to FL450 (45,000 feet) in a side panel.

## What It Does

The altitude display is a **fixed panel on the right side** of the screen that shows:
- Aircraft positioned vertically by their altitude
- Color-coded bars based on transit possibility (green/orange/yellow/gray)
- Flight ID and altitude for each aircraft
- Scale from 0 to FL450 (45,000 ft)

## Visual Layout

```
┌─────────────────────┐
│ Aircraft Altitudes  │
├─────────────────────┤
│ 45k ─               │
│      ABC123 FL350 ← │ (Aircraft at 35,000 ft)
│                     │
│ 30k ─               │
│      XYZ789 FL280 ← │ (Aircraft at 28,000 ft)
│                     │
│ 15k ─               │
│      PRIV01 8,500ft │ (Low altitude)
│                     │
│ 0   ─               │
└─────────────────────┘
```

## Features

### 1. Altitude Positioning
- Aircraft positioned proportionally from 0 to 45,000 ft
- 0% = ground level (0 ft)
- 100% = FL450 (45,000 ft)
- Accurate vertical spacing based on altitude

### 2. Color Coding
- **Green** (#32CD32): High possibility transit (≤1°)
- **Orange** (#FF8C00): Medium possibility transit (≤2°)
- **Yellow** (#FFD700): Low possibility transit (≤6°)
- **Gray** (#666): Unlikely transit (>6°)

### 3. Altitude Display Formats
- **Below FL180** (18,000 ft): Shows as "8,500ft"
- **At or above FL180**: Shows as "FL350"
- Matches aviation standards (transition altitude)

### 4. Interactive
- **Click on bar**: Flashes aircraft marker on map
- **Hover**: Bar moves left slightly and brightens
- Integrated with map visualization

### 5. Auto Show/Hide
- **Shows**: When flight data is loaded
- **Hides**: When no flights or data is cleared
- Appears automatically on flight fetch

## Implementation Details

### JavaScript (`static/app.js`)

**Function: `updateAltitudeDisplay(flights)`**

```javascript
// Called after flight data is fetched
updateAltitudeDisplay(data.flights);
```

**Process:**
1. Clear existing bars
2. Sort flights by altitude (highest first)
3. Calculate position for each aircraft:
   ```
   percentFromBottom = (altitude / 45000) * 100
   ```
4. Create colored bar with ID and altitude
5. Add click handler for map interaction
6. Show overlay

**Filtering:**
- Skips aircraft with altitude ≤ 0
- Skips aircraft with altitude > 45,000 ft
- Only shows valid aircraft

### HTML (`templates/index.html`)

```html
<div id="altitudeOverlay" style="display: none;">
    <div class="altitude-header">Aircraft Altitudes</div>
    <div class="altitude-scale">
        <div class="altitude-tick" style="top: 0%;">45k</div>
        <div class="altitude-tick" style="top: 33.3%;">30k</div>
        <div class="altitude-tick" style="top: 66.6%;">15k</div>
        <div class="altitude-tick" style="top: 100%;">0</div>
    </div>
    <div id="altitudeBars"></div>
</div>
```

### CSS (`static/main.css`)

**Overlay positioning:**
```css
#altitudeOverlay {
    position: fixed;
    right: 0;
    top: 200px;
    width: 140px;
    height: 500px;
    background: rgba(26, 26, 26, 0.95);
    border-left: 2px solid #444;
    z-index: 1000;
}
```

**Bar styling:**
```css
.altitude-bar {
    position: relative;
    height: 18px;
    border-radius: 3px;
    cursor: pointer;
    transition: transform 0.2s;
}

.altitude-bar:hover {
    transform: translateX(-5px);
    filter: brightness(1.2);
}
```

## Usage

### For Users

1. **Load flight data**: Click "Show/Hide" or enable "Auto" mode
2. **View altitude profile**: Panel appears on right side automatically
3. **Click aircraft**: Flashes marker on map
4. **Hover over bar**: Highlights and moves slightly

### Visual Indicators

- **Vertical position**: Real altitude (proportional to scale)
- **Bar color**: Transit possibility level
- **Text format**: Aviation standard (FL or ft)
- **Spacing**: More aircraft at similar altitudes appear stacked

## Examples

### Typical Display

```
Aircraft at FL350 (35,000 ft):
├─ Position: 77.8% from bottom
├─ Color: Green (if high possibility)
└─ Label: "ABC123 FL350"

Aircraft at 8,500 ft:
├─ Position: 18.9% from bottom
├─ Color: Gray (if no transit)
└─ Label: "PRIV01 8,500ft"
```

### Multiple Aircraft

When multiple aircraft are at similar altitudes:
- Bars stack vertically with 3px spacing
- Sorted by altitude (highest on top within the overlay)
- Easy to see altitude clustering (common for airways)

## Mobile Responsive

```css
@media (max-width: 768px) {
    #altitudeOverlay {
        width: 100px;  /* Narrower on mobile */
    }
}
```

- Overlay shrinks to 100px width on mobile
- Still fully functional
- Text may be abbreviated but readable

## Benefits

1. **Quick Visual Reference**
   - See all aircraft altitudes at a glance
   - Understand vertical separation
   - Identify high/low aircraft quickly

2. **Aviation Context**
   - Shows realistic altitude distribution
   - FL notation familiar to pilots
   - Demonstrates why altitude matters for transits

3. **Map Integration**
   - Click to highlight on map
   - Consistent color coding
   - Complements horizontal (map) with vertical (profile) views

4. **Situational Awareness**
   - See which aircraft are at cruising altitude (FL300+)
   - Identify climbing/descending aircraft (lower altitudes)
   - Spot private planes (typically <10,000 ft)

## Technical Notes

### Why FL450 Maximum?

- FL450 (45,000 ft) is above typical commercial cruise (FL350-410)
- Captures virtually all aircraft
- Provides good visual spacing
- Jets rarely exceed FL450

### Positioning Accuracy

```
Formula: bottom = (altitude / 45000) * 100%

Examples:
- 0 ft     → 0%    (at bottom)
- 22,500 ft → 50%   (middle)
- 45,000 ft → 100%  (at top)
```

### Performance

- Minimal impact: Only updates when flight data fetched
- Efficient: Uses CSS positioning (GPU accelerated)
- Scales well: Handles 50+ aircraft without lag

## Future Enhancements

Potential improvements:
1. **Ground speed indicator**: Show aircraft speed on hover
2. **Climb/descent arrows**: Visual indicator of vertical movement
3. **Filter by target**: Show only moon or sun candidates
4. **Historical trail**: Show past positions fading out
5. **Toggle visibility**: Button to hide/show panel

## Testing

To test the feature:

```bash
python3 app.py --demo
```

1. Open http://localhost:8000
2. Click "Show/Hide" to load demo data
3. Look for panel on right side with "Aircraft Altitudes" header
4. Should see 9 demo aircraft at various altitudes
5. Click bars to flash markers on map

Expected results:
- 6 aircraft at cruise altitude (FL320-370) - color coded
- 3 aircraft at lower altitudes - gray

## Troubleshooting

**Panel not visible?**
- Check browser console for JavaScript errors
- Ensure flight data loaded (table should show)
- Try browser zoom (panel is fixed position)

**Aircraft missing?**
- Altitude must be 0 < alt ≤ 45,000 ft
- Check `aircraft_elevation_feet` field in data

**Wrong colors?**
- Colors based on `possibility_level` field
- Gray = 0, Yellow = 1, Orange = 2, Green = 3
