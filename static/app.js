const COLUMN_NAMES = [
    "id",
    "origin",
    "destination",
    "time",
    "angular_separation",
    "target_alt",
    "plane_alt",
    "alt_diff",
    "target_az",
    "plane_az",
    "az_diff",
    "aircraft_elevation_km",
    "elevation_change",
    "direction",
    "speed",
    "distance_km",
];
const MS_IN_A_MIN = 60000;
const DEFAULT_MIN_ALT = 15;
const DEFAULT_INTERVAL_MINUTES = 10;
// Possibility levels
const LOW_LEVEL = 1, MEDIUM_LEVEL = 2, HIGH_LEVEL = 3;
var autoMode = false;
var target = getLocalStorageItem("target", "auto");
var autoGoInterval = setInterval(goFetch, 86400000);
var refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);
// By default disable auto go and refresh timer label
clearInterval(autoGoInterval);
clearInterval(refreshTimerLabelInterval);
displayTarget();


// Page visibility detection - optionally pause polling when page is hidden
document.addEventListener('visibilitychange', function() {
    const pauseWhenHidden = localStorage.getItem("pauseWhenHidden") === 'true'; // Default false

    if (document.hidden && autoMode && pauseWhenHidden) {
        console.log('Page hidden - pausing auto-refresh');
        clearInterval(autoGoInterval);
        clearInterval(refreshTimerLabelInterval);
    }
    else if (!document.hidden && autoMode && pauseWhenHidden) {
        console.log('Page visible - resuming auto-refresh');
        const freq = parseInt(localStorage.getItem("frequency")) || DEFAULT_INTERVAL_MINUTES;
        autoGoInterval = setInterval(goFetch, MS_IN_A_MIN * freq);
        refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);
    }
});

// While loading the page, play silently as answer to any click (Hack for Safari)
document.addEventListener('click', function unlockAudio() {
    const audio = document.getElementById('alertSound');
    audio.play().then(() => audio.pause());
    document.removeEventListener('click', unlockAudio);
}, { once: true });

// State tracking for toggles
var resultsVisible = false;
var mapVisible = false;

// Track mode state
var trackingFlightId = null;
var trackingInterval = null;
var trackingTimeout = null;
const TRACK_INTERVAL_MS = 6000;  // 6 seconds (max 10 queries/min on Personal tier)
const TRACK_TIMEOUT_MS = 180000; // 3 minutes

// Audio context for track mode sounds
let audioCtx = null;

function playTrackOnSound() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;

    // First tone: 400 Hz, 100ms
    const osc1 = audioCtx.createOscillator();
    const gain1 = audioCtx.createGain();
    osc1.frequency.value = 400;
    osc1.connect(gain1);
    gain1.connect(audioCtx.destination);
    gain1.gain.setValueAtTime(0.3, now);
    gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
    osc1.start(now);
    osc1.stop(now + 0.1);

    // Second tone: 700 Hz, 100ms (after 140ms pause)
    const osc2 = audioCtx.createOscillator();
    const gain2 = audioCtx.createGain();
    osc2.frequency.value = 700;
    osc2.connect(gain2);
    gain2.connect(audioCtx.destination);
    gain2.gain.setValueAtTime(0.3, now + 0.14);
    gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.24);
    osc2.start(now + 0.14);
    osc2.stop(now + 0.24);
}

function playTrackOffSound() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;

    // Single tone: 380 Hz, 120ms, quieter
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = 380;
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);
    osc.start(now);
    osc.stop(now + 0.12);
}

function updateTrackedFlight() {
    if (!trackingFlightId) return;

    let latitude = document.getElementById("latitude").value;
    let longitude = document.getElementById("longitude").value;
    let elevation = document.getElementById("elevation").value;
    const minAltitude = document.getElementById("minAltitude").value || DEFAULT_MIN_ALT;
    let adsbProvider = document.getElementById("adsbProvider").value;

    let endpoint_url = (
        `/flights?target=${encodeURIComponent(target)}`
        + `&latitude=${encodeURIComponent(latitude)}`
        + `&longitude=${encodeURIComponent(longitude)}`
        + `&elevation=${encodeURIComponent(elevation)}`
        + `&min_altitude=${encodeURIComponent(minAltitude)}`
        + `&send_notification=false`
        + `&adsb_provider=${adsbProvider}`
    );

    if (window.boundingBox) {
        endpoint_url += `&bbox_lat_lower_left=${encodeURIComponent(window.boundingBox.latLowerLeft)}`;
        endpoint_url += `&bbox_lon_lower_left=${encodeURIComponent(window.boundingBox.lonLowerLeft)}`;
        endpoint_url += `&bbox_lat_upper_right=${encodeURIComponent(window.boundingBox.latUpperRight)}`;
        endpoint_url += `&bbox_lon_upper_right=${encodeURIComponent(window.boundingBox.lonUpperRight)}`;
    }

    fetch(endpoint_url)
    .then(response => response.json())
    .then(data => {
        // Find the tracked flight in the response
        const trackedFlight = data.flights.find(f =>
            String(f.id).trim().toUpperCase() === trackingFlightId
        );

        if (!trackedFlight) {
            console.log(`Track mode: flight ${trackingFlightId} no longer in range`);
            stopTracking();
            return;
        }

        // Update only the tracked flight's row
        const row = document.querySelector(`tr[data-flight-id="${trackingFlightId}"]`);
        if (row) {
            updateFlightRow(row, trackedFlight);
        }

        // Update the marker on the map
        if (typeof updateSingleAircraftMarker === 'function') {
            updateSingleAircraftMarker(trackedFlight);
        }
    })
    .catch(error => {
        console.error('Track mode update error:', error);
    });
}

function updateFlightRow(row, flight) {
    // Update all cells except the first (target emoji)
    const cells = row.querySelectorAll('td');
    let cellIndex = 1; // Skip target emoji column

    COLUMN_NAMES.forEach(column => {
        const cell = cells[cellIndex++];
        if (!cell) return;

        const value = flight[column];

        if (value === null || value === undefined) {
            cell.textContent = "";
        } else if (column === "id") {
            const aircraftType = flight.aircraft_type || "";
            cell.textContent = aircraftType && aircraftType !== "N/A" ? `${value} (${aircraftType})` : value;
        } else if (column === "time") {
            const totalSeconds = Math.round(value * 60);
            const mins = Math.floor(totalSeconds / 60);
            const secs = totalSeconds % 60;
            cell.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        } else if (column === "aircraft_elevation_km") {
            cell.textContent = value.toLocaleString('en-US') + " km";
        } else if (column === "distance_km") {
            cell.textContent = value.toFixed(1) + " km";
        } else if (column === "direction") {
            cell.textContent = Math.round(value) + "°";
        } else if (column === "speed") {
            cell.textContent = Math.round(value) + " km/h";
        } else if (column === "alt_diff" || column === "az_diff") {
            const roundedValue = Math.round(value);
            cell.textContent = roundedValue + "º";
            cell.style.color = Math.abs(roundedValue) > 10 ? "#888" : "";
        } else if (column === "target_alt" || column === "target_az") {
            const numValue = value.toFixed(1);
            cell.textContent = numValue + "º";
            if (value < 0) {
                cell.style.color = "#888";
                cell.style.fontStyle = "italic";
            } else {
                cell.style.color = "";
                cell.style.fontStyle = "";
            }
        } else if (column === "plane_alt" || column === "plane_az") {
            const numValue = value.toFixed(1);
            cell.textContent = numValue + "º";
            if (value < 0) {
                cell.style.color = "#888";
                cell.style.fontStyle = "italic";
            } else {
                cell.style.color = "";
                cell.style.fontStyle = "";
            }
        } else if (column === "angular_separation") {
            cell.textContent = value.toFixed(2) + "º";
        } else {
            cell.textContent = value;
        }
    });
}

function startTracking(flightId) {
    // Stop any existing tracking
    stopTracking();

    trackingFlightId = flightId;
    console.log(`Track mode: started for ${flightId}`);
    playTrackOnSound();

    // Visual indicator
    updateTrackingIndicator();

    // Start polling - use updateTrackedFlight instead of fetchFlights
    trackingInterval = setInterval(updateTrackedFlight, TRACK_INTERVAL_MS);

    // Auto-stop after 3 minutes
    trackingTimeout = setTimeout(() => {
        console.log('Track mode: 3 minute timeout');
        stopTracking();
    }, TRACK_TIMEOUT_MS);

    // Immediate update
    updateTrackedFlight();
}

function stopTracking() {
    if (trackingInterval) {
        clearInterval(trackingInterval);
        trackingInterval = null;
    }
    if (trackingTimeout) {
        clearTimeout(trackingTimeout);
        trackingTimeout = null;
    }
    if (trackingFlightId) {
        console.log(`Track mode: stopped for ${trackingFlightId}`);
        trackingFlightId = null;
        playTrackOffSound();
    }
    updateTrackingIndicator();
}

function updateTrackingIndicator() {
    // Remove previous tracking highlight
    document.querySelectorAll('.tracking-row').forEach(row => {
        row.classList.remove('tracking-row');
    });

    // Add highlight to tracked row
    if (trackingFlightId) {
        const row = document.querySelector(`tr[data-flight-id="${trackingFlightId}"]`);
        if (row) {
            row.classList.add('tracking-row');
        }
        document.getElementById("trackingStatus").innerHTML += ` | 🎯 Tracking ${trackingFlightId}`;
    }
}


function savePosition() {
    let lat = document.getElementById("latitude");
    let latitude = parseFloat(lat.value);
    let long = document.getElementById("longitude");
    let longitude = parseFloat(long.value);
    let elev = document.getElementById("elevation");
    let elevation = parseFloat(elev.value);
    let minAlt = document.getElementById("minAltitude");
    let minAltitude = parseFloat(minAlt.value) || DEFAULT_MIN_ALT;

    if(isNaN(latitude) || isNaN(longitude) || isNaN(elevation)) {
        alert("Please, type all your coordinates. Use MAPS.ie or Google Earth");
        return;
    }

    localStorage.setItem("latitude", latitude);
    localStorage.setItem("longitude", longitude);
    localStorage.setItem("elevation", elevation);
    localStorage.setItem("minAltitude", minAltitude);

    alert("Position saved in local storage!");
}

function loadPositionAndBbox() {
    const savedLat = localStorage.getItem("latitude");
    const savedLon = localStorage.getItem("longitude");
    const savedElev = localStorage.getItem("elevation");
    const savedMinAlt = localStorage.getItem("minAltitude");
    const savedBoundingBox = localStorage.getItem("boundingBox");

    if (savedLat === null || savedLat === "" || savedLat === "null") {
        console.log("No position saved in local storage");
        document.getElementById("minAltitude").value = DEFAULT_MIN_ALT; // Default
        return;
    }

    document.getElementById("latitude").value = savedLat;
    document.getElementById("longitude").value = savedLon;
    document.getElementById("elevation").value = savedElev;
    document.getElementById("minAltitude").value = savedMinAlt || DEFAULT_MIN_ALT;

    // Load saved bounding box
    if (savedBoundingBox) {
        try {
            window.boundingBox = JSON.parse(savedBoundingBox);
            console.log("Bounding box loaded from local storage:", window.boundingBox);
        }
        catch (e) {
            console.error("Error parsing saved bounding box:", e);
        }
    }

    console.log("Position loaded from local storage:", savedLat, savedLon, savedElev, "minAlt:", savedMinAlt);
}

function getLocalStorageItem(key, defaultValue) {
    const value = localStorage.getItem(key);
    return value !== null ? value : defaultValue;
}

function clearPosition() {
    localStorage.clear();

    document.getElementById("latitude").value = "";
    document.getElementById("longitude").value = "";
    document.getElementById("elevation").value = "";
    document.getElementById("minAltitude").value = DEFAULT_MIN_ALT.toString();

    // reset bounding box
    window.boundingBox = null;
}

function go() {
    // Refresh flight data
    const resultsDiv = document.getElementById("results");
    const mapContainer = document.getElementById("mapContainer");

    // Validate coordinates first
    let lat = document.getElementById("latitude");
    let latitude = parseFloat(lat.value);

    if(isNaN(latitude)) {
        alert("Please, type your coordinates and save them");
        return;
    }

    // Show results and map if not already visible
    if (!resultsVisible) {
        resultsVisible = true;
        mapVisible = true;
        resultsDiv.style.display = 'block';
        mapContainer.style.display = 'block';
    }

    // Always fetch fresh data
    fetchFlights();
}

function goFetch() {
    // Internal function for auto mode - just fetches without toggling
    let lat = document.getElementById("latitude");
    let latitude = parseFloat(lat.value);

    if(isNaN(latitude)) {
        return;
    }

    // Auto-show results if in auto mode
    if (autoMode && !resultsVisible) {
        resultsVisible = true;
        mapVisible = true;
        document.getElementById("results").style.display = 'block';
        document.getElementById("mapContainer").style.display = 'block';
    }

    fetchFlights();
}

function auto() {
    if(autoMode == true) {
        document.getElementById("autoBtn").innerHTML = 'Auto';
        document.getElementById("autoGoNote").innerHTML = "";

        autoMode = false;
        clearInterval(autoGoInterval);
        clearInterval(refreshTimerLabelInterval);
    }
    else {
        // Get saved frequency or choose default value
        const savedFreq = localStorage.getItem("frequency") || DEFAULT_INTERVAL_MINUTES;

        let freq = prompt(
            `Enter refresh interval in minutes\n` +
            `Recommended: 6-10 min for continuous monitoring`,
            savedFreq
        );

        // User cancelled
        if (freq === null) {
            return;
        }

        try {
            freq = parseInt(freq);

            if(isNaN(freq) || freq <= 0) {
                throw new Error("");
            }
        }
        catch (error) {
            alert("Invalid frequency. Please try again!");
            return auto();
        }

        localStorage.setItem("frequency", freq);
        document.getElementById("autoBtn").innerHTML = "Auto " + freq  + " min ⴵ";
        document.getElementById("autoGoNote").innerHTML = `Auto-refresh every ${freq} m.`;

        autoMode = true;
        autoGoInterval = setInterval(goFetch, MS_IN_A_MIN * freq);
        refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);
    }
}

function refreshTimer() {
    let autoBtn = document.getElementById("autoBtn");
    const currentLabel = autoBtn.innerHTML;
    let currentTime = parseInt(currentLabel.match(/\d+/)[0], 10);
    const currentFreq = localStorage.getItem("frequency");

    let newTime = (currentTime - 1) > 0 ? currentTime - 1: currentFreq;

    autoBtn.innerHTML = "Auto " + newTime + " min ⴵ";
}

function fetchFlights() {
    let latitude = document.getElementById("latitude").value;
    let longitude = document.getElementById("longitude").value;
    let elevation = document.getElementById("elevation").value;
    let adsbProvider = document.getElementById("adsbProvider").value;

    let hasVeryPossibleTransits = false;

    const bodyTable = document.getElementById('flightData');
    let alertNoResults = document.getElementById("noResults");
    bodyTable.innerHTML = '';
    alertNoResults.innerHTML = '';

    const minAltitude = document.getElementById("minAltitude").value || DEFAULT_MIN_ALT;
    let endpoint_url = (
        `/flights?target=${encodeURIComponent(target)}`
        + `&latitude=${encodeURIComponent(latitude)}`
        + `&longitude=${encodeURIComponent(longitude)}`
        + `&elevation=${encodeURIComponent(elevation)}`
        + `&min_altitude=${encodeURIComponent(minAltitude)}`
        + `&send_notification=${autoMode}`
        + `&adsb_provider=${adsbProvider}`
    );

    // Add custom bounding box if user has edited it
    if (window.boundingBox) {
        endpoint_url += `&bbox_lat_lower_left=${encodeURIComponent(window.boundingBox.latLowerLeft)}`;
        endpoint_url += `&bbox_lon_lower_left=${encodeURIComponent(window.boundingBox.lonLowerLeft)}`;
        endpoint_url += `&bbox_lat_upper_right=${encodeURIComponent(window.boundingBox.latUpperRight)}`;
        endpoint_url += `&bbox_lon_upper_right=${encodeURIComponent(window.boundingBox.lonUpperRight)}`;
    }

    // Show loading spinner
    document.getElementById("loadingSpinner").style.display = "block";
    document.getElementById("results").style.display = "none";

    fetch(endpoint_url)
    .then(response => response.json())
    .then(data => {
        // Hide loading spinner
        document.getElementById("loadingSpinner").style.display = "none";
        document.getElementById("results").style.display = "block";

        if(data.flights.length == 0) {
            alertNoResults.innerHTML = "No flights!";

            if(mapVisible) clearExistingAircraftMarkers();
        }

        // Display tracking status - Sun and Moon with weather
        renderTrackingStatus(data);

        // Display coordinates for targets (alt/az)
        renderTargetCoordinates(data.targetCoordinates);

        // Check if any targets are trackable
        if(data.trackingTargets && data.trackingTargets.length === 0) {
            alertNoResults.innerHTML = "No targets available for tracking (below horizon or weather)";
        }

        // Deduplicate flights by ID for display (keep the ones with lower angular separation considering both targets)
        const uniqueFlights = deduplicateFlights(data.flights);
        console.log(`Dedupe: ${data.flights.length} flights -> ${uniqueFlights.length} unique`);

        uniqueFlights.forEach(item => {
            const row = document.createElement('tr');

            // Store normalized flight ID and possibility level for cross-referencing
            const normalizedId = String(item.id).trim().toUpperCase();
            const possibilityLevel = item.is_possible_transit === 1 ? parseInt(item.possibility_level) : 0;
            row.setAttribute('data-flight-id', normalizedId);
            row.setAttribute('data-possibility', possibilityLevel);

            // Click handler: normal click flashes, Cmd/Ctrl+click toggles tracking
            row.addEventListener('click', function(e) {
                if ((e.metaKey || e.ctrlKey) && e.altKey) {
                    // Cmd/Ctrl+Option: test sounds only
                    playTrackOnSound();
                    setTimeout(playTrackOffSound, 500);
                } else if (e.metaKey || e.ctrlKey) {
                    // Cmd/Ctrl+click: toggle track mode
                    if (trackingFlightId === normalizedId) {
                        stopTracking();
                    } else {
                        // Safety check: only track medium or high probability
                        if (possibilityLevel < MEDIUM_LEVEL) {
                            alert('Track Mode requires medium or high probability transit.\n\nThis flight has ' +
                                (possibilityLevel === LOW_LEVEL ? 'low' : 'no') +
                                ' probability of transit.');
                            return;
                        }
                        startTracking(normalizedId);
                    }
                } else {
                    // Normal click: flash aircraft on map and show route/track
                    if (typeof flashAircraftMarker === 'function') {
                        flashAircraftMarker(normalizedId);
                    }
                    if (typeof toggleFlightRouteTrack === 'function') {
                        toggleFlightRouteTrack(item.fa_flight_id, normalizedId);
                    }
                }
            });

            // Add target emoji as first column
            const targetCell = document.createElement("td");
            if (item.target === "moon") targetCell.textContent = "🌙";
            else if (item.target === "sun") targetCell.textContent = "☀️";
            else targetCell.textContent = "";
            row.appendChild(targetCell);

            COLUMN_NAMES.forEach(column => {
                const val = document.createElement("td");
                const value = item[column];

                if (value === null || value === undefined) {
                    val.textContent = "";
                } else if (column === "id") {
                    // Show "ID (TYPE)" format
                    const aircraftType = item.aircraft_type || "";
                    val.textContent = aircraftType && aircraftType !== "N/A" ? `${value} (${aircraftType})` : value;
                } else if (column === "time") {
                    // Format ETA as mm:ss
                    const totalSeconds = Math.round(value * 60);
                    const mins = Math.floor(totalSeconds / 60);
                    const secs = totalSeconds % 60;
                    val.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                } else if (column === "aircraft_elevation_km") {
                    // Show GPS altitude in km with comma formatting
                    val.textContent = value.toLocaleString('en-US') + " km";
                } else if (column === "distance_km") {
                    // Show distance in kilometers with one decimal place
                    val.textContent = value.toFixed(1) + " km";
                } else if (column === "direction") {
                    val.textContent = Math.round(value) + "°";
                } else if (column === "speed") {
                    // Show speed in km/h, rounded to whole number
                    val.textContent = Math.round(value) + " km/h";
                } else if (column === "alt_diff" || column === "az_diff" || column === "angular_separation") {
                    val.textContent = value + "º";
                    // Color code large angle differences
                    if (Math.abs(value) > 10) {
                        val.style.color = "#888"; // Gray for large differences
                    }
                } else if (column === "target_alt" || column === "target_az") {
                    // Always show target values, color code negative/invalid
                    const numValue = value.toFixed(1);
                    val.textContent = numValue + "º";
                    if (value < 0) {
                        val.style.color = "#888"; // Gray for below horizon
                        val.style.fontStyle = "italic";
                    }
                } else if (column === "plane_alt" || column === "plane_az") {
                    // Always show plane values, color code negative/invalid
                    const numValue = value.toFixed(1);
                    val.textContent = numValue + "º";
                    if (value < 0) {
                        val.style.color = "#888"; // Gray for negative angles
                        val.style.fontStyle = "italic";
                    }
                } else if (value === "N/D") {
                    val.textContent = value + " ⚠️";
                } else {
                    val.textContent = value;
                }

                row.appendChild(val);
            });

            if(item["is_possible_transit"] == 1) {
                const possibilityLevel = parseInt(item["possibility_level"]);
                highlightPossibleTransit(possibilityLevel, row);

                if(possibilityLevel == MEDIUM_LEVEL || possibilityLevel == HIGH_LEVEL) {
                    hasVeryPossibleTransits = true;
                }
            }

            bodyTable.appendChild(row);
        });

        if(autoMode == true && hasVeryPossibleTransits == true) soundAlert();

        // Save bounding box if previously there's no bbox
        if(!window.boundingBox) {
            window.boundingBox = data.boundingBox;
            localStorage.setItem("boundingBox", JSON.stringify(window.boundingBox));
        }

        // Always update map visualization when data is fetched (use deduplicated flights)
        if(mapVisible) {
            const mapData = {...data, flights: uniqueFlights};
            updateMapVisualization(
                mapData, parseFloat(latitude), parseFloat(longitude), parseFloat(elevation), window.boundingBox
            );
        }

        // Update altitude display
        updateAltitudeDisplay(data.flights);
    })
    .catch(error => {
        // Hide loading spinner on error
        document.getElementById("loadingSpinner").style.display = "none";
        document.getElementById("results").style.display = "block";
        alert("Error getting flight data. Check console for details.");
        console.error("Error:", error);
    });
}

function renderTrackingStatus(data) {
    let trackingParts = [];

    // Show Sun status
    if(data.targetCoordinates && data.targetCoordinates.sun) {
        let isTracking = data.trackingTargets && data.trackingTargets.includes('sun');
        let status = isTracking ? "Tracking" : "Not tracking";
        trackingParts.push(`☀️ ${status}`);
    }

    // Show Moon status
    if(data.targetCoordinates && data.targetCoordinates.moon) {
        let isTracking = data.trackingTargets && data.trackingTargets.includes('moon');
        let status = isTracking ? "Tracking" : "Not tracking";
        trackingParts.push(`🌙 ${status}`);
    }

    // Weather status
    if(data.weather && data.weather.cloud_cover !== null) {
        trackingParts.push(`☁️ ${data.weather.cloud_cover}% clouds`);
    }

    document.getElementById("trackingStatus").innerHTML = trackingParts.join("&nbsp;&nbsp;&nbsp;&nbsp;");
}

function renderTargetCoordinates(targetCoordinates) {
    let time_ = (new Date()).toLocaleTimeString();
    let coordParts = [];

    // Always show Sun coordinates
    if(targetCoordinates && targetCoordinates.sun) {
        let coords = targetCoordinates.sun;
        let altStr = coords.altitude !== null && coords.altitude !== undefined ? coords.altitude.toFixed(1) : "—";
        let azStr = coords.azimuthal !== null && coords.azimuthal !== undefined ? coords.azimuthal.toFixed(1) : "—";
        coordParts.push(`☀️ Alt: ${altStr}° Az: ${azStr}°`);
    }

    // Always show Moon coordinates
    if(targetCoordinates && targetCoordinates.moon) {
        let coords = targetCoordinates.moon;
        let altStr = coords.altitude !== null && coords.altitude !== undefined ? coords.altitude.toFixed(1) : "—";
        let azStr = coords.azimuthal !== null && coords.azimuthal !== undefined ? coords.azimuthal.toFixed(1) : "—";
        coordParts.push(`🌙 Alt: ${altStr}° Az: ${azStr}°`);
    }

    // Display time when the coordinates where checked
    if(coordParts.length > 0) {
        coordParts.push(`⏰ ${time_}`);
    }

    document.getElementById("targetCoordinates").innerHTML = coordParts.join("&nbsp;&nbsp;&nbsp;&nbsp;");
}

function deduplicateFlights(flights) {
    const seenFlights = {};

    flights.forEach(flight => {
        // Normalize ID (trim whitespace, consistent case)
        const id = String(flight.id).trim().toUpperCase();
        if (!seenFlights[id]) {
            seenFlights[id] = flight;
        }
        else {
            // Keep the one with lower angular separation
            const existing = seenFlights[id];
            if (flight.angular_separation < existing.angular_separation) {
                seenFlights[id] = flight;
            }
        }
    });

    return Object.values(seenFlights);
}

function highlightPossibleTransit(possibilityLevel, row) {
    if(possibilityLevel == LOW_LEVEL) row.classList.add("possibleTransitHighlightLow");
    else if(possibilityLevel == MEDIUM_LEVEL) row.classList.add("possibleTransitHighlightMedium");
    else if(possibilityLevel == HIGH_LEVEL) row.classList.add("possibleTransitHighlightHigh");
}

function updateAltitudeDisplay(flights) {
    const barsContainer = document.getElementById("altitudeBars");

    if (!flights || flights.length === 0) {
        barsContainer.innerHTML = "";
        return;
    }

    // Clear existing lines
    barsContainer.innerHTML = "";

    // Maximum altitude for scale (FL450 = 45,000 ft, 13.716 km)
    const MAX_ALTITUDE_KM = 15;

    // Create a thin line for each aircraft
    flights.forEach(flight => {
        const altitude = flight.aircraft_elevation_km || 0;

        // Skip if altitude is invalid or above max
        if (altitude > MAX_ALTITUDE_KM) return;

        // Calculate position from bottom (0 = ground, 100% = FL450)
        // Clamp negative altitudes to 0% (bottom)
        const clampedAltitude = Math.max(0, altitude);
        const percentFromBottom = (clampedAltitude / MAX_ALTITUDE_KM) * 100;

        // Create line element
        const line = document.createElement("div");
        line.style.position = "absolute";
        line.style.bottom = percentFromBottom + "%";
        line.style.left = "0";
        line.style.right = "0";
        line.style.height = "2px";
        line.style.cursor = "pointer";
        line.style.transition = "height 0.2s, opacity 0.2s";
        line.title = flight.id;

        // Color based on possibility level
        let color = "#666"; // Default gray for unlikely
        const possibilityLevel = parseInt(flight.possibility_level || 0);
        if (possibilityLevel === HIGH_LEVEL) {
            color = "#32CD32"; // Green
        } else if (possibilityLevel === MEDIUM_LEVEL) {
            color = "#FF8C00"; // Orange
        } else if (possibilityLevel === LOW_LEVEL) {
            color = "#FFD700"; // Yellow
        }
        line.style.background = color;

        // Hover effect
        line.addEventListener('mouseenter', () => {
            line.style.height = "4px";
            line.style.opacity = "1";
        });
        line.addEventListener('mouseleave', () => {
            line.style.height = "2px";
            line.style.opacity = "0.9";
        });

        // Add click handler to flash aircraft on map
        const normalizedId = flight.id.replace(/[^a-zA-Z0-9]/g, '_');
        line.addEventListener('click', () => {
            if (typeof flashAircraftMarker === 'function') {
                flashAircraftMarker(normalizedId);
            }
        });

        line.style.opacity = "0.9";
        barsContainer.appendChild(line);
    });
}

function toggleTarget() {
    if(target == "moon") target = "sun";
    else if(target == "sun") target = "auto";
    else target = "moon";

    document.getElementById("targetCoordinates").innerHTML = "";
    document.getElementById("trackingStatus").innerHTML = "";
    displayTarget();

    resetResultsTable();
}

function displayTarget() {
    if(target == "moon") {
        document.getElementById("targetIcon").innerHTML = "🌙";
    }
    else if(target == "sun") {
        document.getElementById("targetIcon").innerHTML = "☀️";
    }
    else {
        document.getElementById("targetIcon").innerHTML = "🌙☀️";
    }
    localStorage.setItem("target", target);
}

function resetResultsTable() {
    document.getElementById("flightData").innerHTML = "";
}

function soundAlert() {
    const audio = document.getElementById('alertSound');
    audio.play();
}

// Pause when hidden preference
function togglePauseWhenHidden() {
    const checkbox = document.getElementById('pauseWhenHidden');
    localStorage.setItem('pauseWhenHidden', checkbox.checked);
    console.log('Pause when hidden:', checkbox.checked);
}
