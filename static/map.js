// Map visualization for Flymoon
// Shows observer location, bounding box, aircraft positions, and azimuth arrows

let map = null;
let observerMarker = null;
let boundingBoxLayer = null;
let azimuthArrows = {};  // Store arrows by target name
let aircraftMarkers = {};
let mapInitialized = false;
let boundingBoxUserEdited = false;

// Arrow colors for each target
const ARROW_COLORS = {
    sun: '#FF4500',   // Orange-red
    moon: '#4169E1'   // Royal blue
};

// Color scheme for possibility levels
const COLORS = {
    LOW: '#FFD700',      // Yellow/Gold
    MEDIUM: '#FF8C00',   // Dark Orange
    HIGH: '#32CD32',     // Lime Green
    DEFAULT: '#808080'   // Gray
};

function initializeMap(centerLat, centerLon) {
    if (mapInitialized) {
        return;
    }

    map = L.map('map', {
        editable: true
    }).setView([centerLat, centerLon], 9);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    mapInitialized = true;
}

function updateObserverMarker(lat, lon, elevation) {
    if (!map) return;

    // Remove existing marker
    if (observerMarker) {
        map.removeLayer(observerMarker);
    }

    // Create custom icon for observer
    const observerIcon = L.divIcon({
        html: '📍',
        iconSize: [30, 30],
        className: 'observer-icon'
    });

    observerMarker = L.marker([lat, lon], { icon: observerIcon })
        .addTo(map)
        .bindPopup(`<b>Observer</b><br>Lat: ${lat.toFixed(4)}°<br>Lon: ${lon.toFixed(4)}°<br>Elev: ${elevation}m`);

    // Center map on observer
    map.setView([lat, lon], map.getZoom());
}

function updateBoundingBox(latLowerLeft, lonLowerLeft, latUpperRight, lonUpperRight) {
    if (!map) return;

    // Skip if user has manually edited the bounding box
    if (boundingBoxUserEdited && boundingBoxLayer) {
        return;
    }

    // Remove existing bounding box
    if (boundingBoxLayer) {
        map.removeLayer(boundingBoxLayer);
    }

    // Create rectangle for bounding box
    const bounds = [
        [latLowerLeft, lonLowerLeft],
        [latUpperRight, lonUpperRight]
    ];

    boundingBoxLayer = L.rectangle(bounds, {
        color: '#FF0000',
        weight: 2,
        fillOpacity: 0.1,
        dashArray: '5, 10'
    }).addTo(map).bindPopup('<b>Search Bounding Box</b><br>Drag corners to resize');

    // Enable editing (draggable corners)
    if (boundingBoxLayer.enableEdit) {
        boundingBoxLayer.enableEdit();

        // Track when user edits the bounding box
        boundingBoxLayer.on('editable:vertex:dragend', function() {
            boundingBoxUserEdited = true;
        });
    }

    // Fit map to show both observer and bounding box
    const extendedBounds = L.latLngBounds(bounds);
    map.fitBounds(extendedBounds, { padding: [50, 50] });
}

function clearAzimuthArrows() {
    // Remove all existing arrows
    Object.values(azimuthArrows).forEach(arrow => {
        if (arrow) map.removeLayer(arrow);
    });
    azimuthArrows = {};
}

function updateAzimuthArrow(observerLat, observerLon, azimuth, targetName) {
    if (!map) return;

    // Remove existing arrow for this target
    if (azimuthArrows[targetName]) {
        map.removeLayer(azimuthArrows[targetName]);
    }

    // Calculate endpoint for arrow (15km in azimuth direction)
    const distance = 15; // km
    const endPoint = calculateDestination(observerLat, observerLon, azimuth, distance);

    // Create arrow polyline
    const arrowPoints = [
        [observerLat, observerLon],
        [endPoint.lat, endPoint.lon]
    ];

    const targetIcon = targetName === 'moon' ? '🌙' : '☀️';
    const color = ARROW_COLORS[targetName] || '#FF4500';

    azimuthArrows[targetName] = L.polyline(arrowPoints, {
        color: color,
        weight: 6,
        opacity: 0.9
    }).addTo(map).bindPopup(`<b>Azimuth to ${targetIcon} ${targetName}</b><br>${azimuth.toFixed(1)}°`);
}

function updateAircraftMarkers(flights, observerLat, observerLon) {
    if (!map) return;

    // Clear existing aircraft markers
    Object.values(aircraftMarkers).forEach(marker => {
        map.removeLayer(marker);
    });
    aircraftMarkers = {};

    // Add new aircraft markers
    flights.forEach(flight => {
        // Calculate current position (use flight data directly)
        // For future position visualization, we'd need to add predicted coordinates
        const flightId = flight.id;
        
        // Determine color based on possibility level
        let color = COLORS.DEFAULT;
        if (flight.is_possible_transit === 1) {
            const level = parseInt(flight.possibility_level);
            if (level === 1) color = COLORS.LOW;
            else if (level === 2) color = COLORS.MEDIUM;
            else if (level === 3) color = COLORS.HIGH;
        }

        // Use diamond for transit aircraft (NTDS style), airplane emoji for others
        const isTransit = flight.is_possible_transit === 1;
        const aircraftIcon = L.divIcon({
            html: isTransit
                ? `<div style="font-size: 32px; color: ${color};">◆</div>`
                : `<div style="transform: rotate(${flight.direction}deg); font-size: 20px;">✈️</div>`,
            iconSize: [32, 32],
            className: 'aircraft-icon'
        });

        // Since we don't have current lat/lon in flight results, we'll need to add them
        // For now, create a note that position data is needed
        // This will be updated after backend changes
        
        const popupContent = `
            <b>${flight.id}</b><br>
            ${flight.origin} → ${flight.destination}<br>
            Target: ${flight.target || 'N/A'}<br>
            ETA: ${flight.time ? flight.time.toFixed(1) + ' min' : 'N/A'}<br>
            Alt diff: ${flight.alt_diff ? flight.alt_diff.toFixed(2) + '°' : 'N/A'}<br>
            Az diff: ${flight.az_diff ? flight.az_diff.toFixed(2) + '°' : 'N/A'}<br>
            Heading: ${flight.direction}°<br>
            <span style="color: ${color};">●</span> ${getPossibilityText(flight.is_possible_transit, flight.possibility_level)}
        `;

        // Note: We'll add actual position after backend is updated
        // For now, markers won't appear until we have lat/lon data
        if (flight.latitude && flight.longitude) {
            const marker = L.marker([flight.latitude, flight.longitude], { icon: aircraftIcon })
                .addTo(map)
                .bindPopup(popupContent);
            
            // Color the marker based on possibility
            marker.getElement()?.style.setProperty('filter', `drop-shadow(0 0 5px ${color})`);
            
            aircraftMarkers[flightId] = marker;
        }
    });
}

function getPossibilityText(isPossible, level) {
    if (isPossible !== 1) return 'No transit';
    const levelInt = parseInt(level);
    if (levelInt === 1) return 'Low probability';
    if (levelInt === 2) return 'Medium probability';
    if (levelInt === 3) return 'High probability';
    return 'Unknown';
}

// Haversine formula to calculate destination point given start, bearing, and distance
function calculateDestination(lat, lon, bearing, distance) {
    const R = 6371; // Earth's radius in km
    const d = distance / R; // Angular distance
    const brng = bearing * Math.PI / 180; // Convert to radians
    const lat1 = lat * Math.PI / 180;
    const lon1 = lon * Math.PI / 180;

    const lat2 = Math.asin(
        Math.sin(lat1) * Math.cos(d) +
        Math.cos(lat1) * Math.sin(d) * Math.cos(brng)
    );

    const lon2 = lon1 + Math.atan2(
        Math.sin(brng) * Math.sin(d) * Math.cos(lat1),
        Math.cos(d) - Math.sin(lat1) * Math.sin(lat2)
    );

    return {
        lat: lat2 * 180 / Math.PI,
        lon: lon2 * 180 / Math.PI
    };
}

function toggleMap() {
    const mapContainer = document.getElementById('mapContainer');
    const isHidden = mapContainer.style.display === 'none';
    
    if (isHidden) {
        mapContainer.style.display = 'block';
        
        // Initialize map if not already done
        const lat = parseFloat(document.getElementById('latitude').value);
        const lon = parseFloat(document.getElementById('longitude').value);
        
        if (!isNaN(lat) && !isNaN(lon)) {
            if (!mapInitialized) {
                initializeMap(lat, lon);
            }
            // Refresh map display
            setTimeout(() => {
                if (map) map.invalidateSize();
            }, 100);
        } else {
            alert('Please enter your coordinates first');
            mapContainer.style.display = 'none';
        }
    } else {
        mapContainer.style.display = 'none';
    }
}

// Update map with all data from API response
function updateMapVisualization(data, observerLat, observerLon, observerElev) {
    if (!map || !mapInitialized) {
        initializeMap(observerLat, observerLon);
    }

    updateObserverMarker(observerLat, observerLon, observerElev);

    // Update bounding box if provided
    if (data.boundingBox) {
        updateBoundingBox(
            data.boundingBox.latLowerLeft,
            data.boundingBox.lonLowerLeft,
            data.boundingBox.latUpperRight,
            data.boundingBox.lonUpperRight
        );
    }

    // Update azimuth arrows - one for each trackable target
    clearAzimuthArrows();
    if (data.targetCoordinates && data.trackingTargets) {
        // Show arrow for each target that is currently being tracked (above horizon)
        data.trackingTargets.forEach(targetName => {
            const coords = data.targetCoordinates[targetName];
            if (coords && coords.azimuthal !== undefined) {
                updateAzimuthArrow(observerLat, observerLon, coords.azimuthal, targetName);
            }
        });
    } else if (data.targetCoordinates && data.targetCoordinates.azimuthal !== undefined) {
        // Single target mode (legacy)
        updateAzimuthArrow(observerLat, observerLon, data.targetCoordinates.azimuthal, target);
    }

    // Update aircraft markers
    if (data.flights && data.flights.length > 0) {
        updateAircraftMarkers(data.flights, observerLat, observerLon);
    }
}
