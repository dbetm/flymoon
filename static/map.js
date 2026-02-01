// Map visualization for Flymoon
// Shows observer location, bounding box, aircraft positions, and azimuth arrows

let map = null;
let observerMarker = null;
let boundingBoxLayer = null;
let azimuthArrows = {};  // Store arrows by target name
let aircraftMarkers = {};
let mapInitialized = false;
let boundingBoxUserEdited = false;
let aircraftRouteCache = {};  // Cache fetched routes/tracks
let currentRouteLayer = null;  // Currently displayed route/track

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

// Track currently selected row
let selectedRowId = null;

// Flash a table row by flight ID and keep it highlighted
function flashTableRow(flightId) {
    const row = document.querySelector(`tr[data-flight-id="${flightId}"]`);
    if (row) {
        // Remove highlight from previously selected row
        if (selectedRowId && selectedRowId !== flightId) {
            const prevRow = document.querySelector(`tr[data-flight-id="${selectedRowId}"]`);
            if (prevRow) {
                prevRow.classList.remove('selected-row');
            }
        }

        // Flash animation
        row.classList.remove('flash-row');
        void row.offsetWidth; // Trigger reflow
        row.classList.add('flash-row');

        // Add persistent highlight
        row.classList.add('selected-row');
        selectedRowId = flightId;

        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// Flash an aircraft marker by flight ID
function flashAircraftMarker(flightId) {
    const marker = aircraftMarkers[flightId];
    if (marker) {
        const element = marker.getElement();
        if (element) {
            // Apply animation to the inner div, not the positioned container
            const innerDiv = element.querySelector('div');
            if (innerDiv) {
                innerDiv.classList.remove('flash-marker');
                void innerDiv.offsetWidth; // Trigger reflow
                innerDiv.classList.add('flash-marker');
            }
        }
        // Pan to marker
        map.panTo(marker.getLatLng());
    }
}

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

            // Save the new bounding box coordinates
            const bounds = boundingBoxLayer.getBounds();
            const newBoundingBox = {
                latLowerLeft: bounds.getSouth(),
                lonLowerLeft: bounds.getWest(),
                latUpperRight: bounds.getNorth(),
                lonUpperRight: bounds.getEast()
            };
            window.lastBoundingBox = newBoundingBox;
            console.log("Bounding box updated:", newBoundingBox);
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

function updateAzimuthArrow(observerLat, observerLon, azimuth, altitude, targetName) {
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
    }).addTo(map).bindPopup(`<b>${targetIcon} ${targetName}</b><br>Altitude: ${altitude.toFixed(1)}°<br>Azimuth: ${azimuth.toFixed(1)}°`);
}

function updateSingleAircraftMarker(flight) {
    if (!map) return;

    const normalizedId = String(flight.id).trim().toUpperCase();

    // Remove existing marker for this flight
    if (aircraftMarkers[normalizedId]) {
        map.removeLayer(aircraftMarkers[normalizedId]);
        delete aircraftMarkers[normalizedId];
    }

    // Determine color based on possibility level
    let color = COLORS.DEFAULT;
    if (flight.is_possible_transit === 1) {
        const level = parseInt(flight.possibility_level);
        if (level === 1) color = COLORS.LOW;
        else if (level === 2) color = COLORS.MEDIUM;
        else if (level === 3) color = COLORS.HIGH;
    }

    // Use diamond for transit aircraft, airplane emoji for others
    const isTransit = flight.is_possible_transit === 1;
    const rotation = (flight.direction - 90);

    const aircraftIcon = L.divIcon({
        html: isTransit
            ? `<div style="font-size: 36px; color: ${color}; text-shadow: 0 0 3px black, 0 0 3px black, 0 0 8px ${color}, 1px 1px 0 black, -1px -1px 0 black, 1px -1px 0 black, -1px 1px 0 black; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; line-height: 1;">◆</div>`
            : `<div style="transform: rotate(${rotation}deg); font-size: 20px;">✈️</div>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        className: 'aircraft-icon'
    });

    // Add marker if we have coordinates
    if (flight.latitude !== undefined && flight.latitude !== null &&
        flight.longitude !== undefined && flight.longitude !== null) {
        const marker = L.marker([flight.latitude, flight.longitude], { icon: aircraftIcon })
            .addTo(map);

        marker.getElement()?.style.setProperty('filter', `drop-shadow(0 0 8px ${color}) drop-shadow(0 0 4px rgba(0,0,0,0.8))`);
        marker.flightId = normalizedId;

        marker.on('click', function() {
            toggleFlightRouteTrack(flight.fa_flight_id, normalizedId);
            flashTableRow(normalizedId);
        });

        aircraftMarkers[normalizedId] = marker;
    }
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
        // Airplane emoji points right (90°), so subtract 90 to align with compass heading
        const isTransit = flight.is_possible_transit === 1;
        const rotation = (flight.direction - 90);

        // Debug: Log heading and rotation for verification
        if (!isTransit && flight.direction) {
            console.log(`Aircraft ${flightId}: heading=${flight.direction}°, rotation=${rotation}°, isTransit=${isTransit}`);
        }

        const aircraftIcon = L.divIcon({
            html: isTransit
                ? `<div style="font-size: 36px; color: ${color}; text-shadow: 0 0 3px black, 0 0 3px black, 0 0 8px ${color}, 1px 1px 0 black, -1px -1px 0 black, 1px -1px 0 black, -1px 1px 0 black; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; line-height: 1;">◆</div>`
                : `<div style="transform: rotate(${rotation}deg); font-size: 20px;">✈️</div>`,
            iconSize: [36, 36],
            iconAnchor: [18, 18],  // Center the icon on coordinates
            className: 'aircraft-icon'
        });

        // Since we don't have current lat/lon in flight results, we'll need to add them
        // For now, create a note that position data is needed
        // This will be updated after backend changes
        
        // Add marker if we have coordinates (check for undefined/null, not falsy)
        if (flight.latitude !== undefined && flight.latitude !== null &&
            flight.longitude !== undefined && flight.longitude !== null) {
            const marker = L.marker([flight.latitude, flight.longitude], { icon: aircraftIcon })
                .addTo(map);

            // Add strong shadow for visibility
            marker.getElement()?.style.setProperty('filter', `drop-shadow(0 0 8px ${color}) drop-shadow(0 0 4px rgba(0,0,0,0.8))`);

            // Store normalized ID for cross-referencing
            const normalizedId = String(flightId).trim().toUpperCase();
            marker.flightId = normalizedId;

            // Click handler to show route/track and flash table row
            marker.on('click', function() {
                toggleFlightRouteTrack(flight.fa_flight_id, normalizedId);
                flashTableRow(normalizedId);
            });

            aircraftMarkers[normalizedId] = marker;
        }
    });
}

function updateAltitudeOverlay(flights) {
    const container = document.getElementById('altitudeBars');
    if (!container) return;

    container.innerHTML = '';

    // Sort by aircraft elevation descending
    const sortedFlights = [...flights].sort((a, b) =>
        (b.aircraft_elevation || 0) - (a.aircraft_elevation || 0)
    );

    const MAX_ALT = 45000; // feet

    sortedFlights.forEach(flight => {
        const altMeters = flight.aircraft_elevation || 0;
        if (altMeters <= 0) return; // Skip if no altitude data

        const altFeet = Math.round(altMeters * 3.28084); // meters to feet
        const barWidthPercent = (altFeet / MAX_ALT) * 100;

        // Determine color
        let color = '#808080'; // Gray default
        if (flight.is_possible_transit === 1) {
            const level = parseInt(flight.possibility_level);
            if (level === 3) color = '#32CD32'; // GREEN
            else if (level === 2) color = '#FF8C00'; // ORANGE
            else if (level === 1) color = '#FFD700'; // YELLOW
        }

        const bar = document.createElement('div');
        bar.className = 'altitude-bar';
        bar.style.background = color;
        bar.style.width = `${Math.max(barWidthPercent, 20)}%`; // Minimum 20% visible

        const idLabel = document.createElement('span');
        idLabel.className = 'altitude-bar-id';
        idLabel.textContent = flight.id;

        const altLabel = document.createElement('span');
        altLabel.className = 'altitude-bar-value';
        altLabel.textContent = `${(altFeet/1000).toFixed(1)}k`;

        bar.appendChild(idLabel);
        bar.appendChild(altLabel);

        // Click to flash on map
        bar.addEventListener('click', () => {
            const normalizedId = String(flight.id).trim().toUpperCase();
            if (typeof flashAircraftMarker === 'function') {
                flashAircraftMarker(normalizedId);
            }
        });

        container.appendChild(bar);
    });
}

async function toggleFlightRouteTrack(faFlightId, flightId) {
    if (!map || !faFlightId) return;

    // If already showing this flight's route, hide it
    if (currentRouteLayer && currentRouteLayer.flightId === flightId) {
        map.removeLayer(currentRouteLayer);
        currentRouteLayer = null;
        return;
    }

    // Remove previous route if showing different flight
    if (currentRouteLayer) {
        map.removeLayer(currentRouteLayer);
    }

    // Check cache first
    if (aircraftRouteCache[flightId]) {
        displayRouteTrack(aircraftRouteCache[flightId], flightId);
        return;
    }

    // Fetch route and track
    try {
        const [routeResponse, trackResponse] = await Promise.all([
            fetch(`/flights/${faFlightId}/route`).then(r => r.json()).catch(e => ({ error: e.message })),
            fetch(`/flights/${faFlightId}/track`).then(r => r.json()).catch(e => ({ error: e.message }))
        ]);

        // Cache the data
        aircraftRouteCache[flightId] = { route: routeResponse, track: trackResponse };
        displayRouteTrack(aircraftRouteCache[flightId], flightId);
    } catch (error) {
        console.error('Error fetching route/track:', error);
        alert('Could not fetch route/track data. This may be because the aircraft is not currently transmitting data or API rate limits have been reached.');
    }
}

function displayRouteTrack(data, flightId) {
    if (!map) return;

    const layerGroup = L.layerGroup();

    console.log('Route/Track data for', flightId, ':', data);

    // Display route (blue dashed)
    if (data.route && !data.route.error) {
        console.log('Route data:', data.route);

        // Check different possible response structures
        const waypoints = data.route.waypoints || data.route.route_waypoints || [];

        if (waypoints.length > 0) {
            const routePoints = waypoints
                .filter(pt => pt.latitude && pt.longitude)
                .map(pt => [pt.latitude, pt.longitude]);

            if (routePoints.length > 0) {
                console.log('Drawing route with', routePoints.length, 'points');
                const routeLine = L.polyline(routePoints, {
                    color: '#4169E1',
                    weight: 3,
                    dashArray: '10, 10',
                    opacity: 0.7
                });
                layerGroup.addLayer(routeLine);
                routeLine.bindPopup('📍 Planned Route (' + routePoints.length + ' waypoints)');
            } else {
                console.log('Route has waypoints but no valid lat/lon coordinates');
            }
        } else {
            console.log('No waypoints in route data. Route may not be available for this flight.');
        }
    } else if (data.route && data.route.error) {
        console.log('Route error:', data.route.error);
    } else {
        console.log('No route data available');
    }

    // Display track (green solid with dots)
    if (data.track && !data.track.error) {
        console.log('Track data:', data.track);

        const positions = data.track.positions || [];

        if (positions.length > 0) {
            const trackPoints = positions
                .filter(pt => pt.latitude && pt.longitude)
                .map(pt => [pt.latitude, pt.longitude]);

            if (trackPoints.length > 0) {
                console.log('Drawing track with', trackPoints.length, 'positions');
                const trackLine = L.polyline(trackPoints, {
                    color: '#32CD32',
                    weight: 3,
                    opacity: 0.8
                });
                layerGroup.addLayer(trackLine);
                trackLine.bindPopup('✈️ Historical Track (' + trackPoints.length + ' positions)');

                // Add position dots every 10th point
                positions.forEach((pt, idx) => {
                    if (idx % 10 === 0 && pt.latitude && pt.longitude) {
                        const dot = L.circleMarker([pt.latitude, pt.longitude], {
                            radius: 3,
                            fillColor: '#32CD32',
                            color: 'white',
                            weight: 1,
                            fillOpacity: 0.8
                        });
                        layerGroup.addLayer(dot);
                    }
                });
            } else {
                console.log('Track has positions but no valid lat/lon coordinates');
            }
        } else {
            console.log('No positions in track data');
        }
    } else if (data.track && data.track.error) {
        console.log('Track error:', data.track.error);
    } else {
        console.log('No track data available');
    }

    layerGroup.addTo(map);
    layerGroup.flightId = flightId;
    currentRouteLayer = layerGroup;
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
    const altOverlay = document.getElementById('altitudeOverlay');
    const mapButton = document.querySelector('[onclick="toggleMap()"]');
    const isHidden = mapContainer.style.display === 'none';

    if (isHidden) {
        mapVisible = true;
        mapContainer.style.display = 'block';
        if (altOverlay) altOverlay.style.display = 'block';

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
            mapVisible = false;
            mapContainer.style.display = 'none';
            if (altOverlay) altOverlay.style.display = 'none';
        }
    } else {
        mapVisible = false;
        mapContainer.style.display = 'none';
        if (altOverlay) altOverlay.style.display = 'none';
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
            if (coords && coords.azimuthal !== undefined && coords.altitude !== undefined) {
                updateAzimuthArrow(observerLat, observerLon, coords.azimuthal, coords.altitude, targetName);
            }
        });
    } else if (data.targetCoordinates && data.targetCoordinates.azimuthal !== undefined) {
        // Single target mode (legacy)
        updateAzimuthArrow(observerLat, observerLon, data.targetCoordinates.azimuthal, data.targetCoordinates.altitude || 0, target);
    }

    // Update aircraft markers
    if (data.flights && data.flights.length > 0) {
        updateAircraftMarkers(data.flights, observerLat, observerLon);
        updateAltitudeOverlay(data.flights);
    }
}
