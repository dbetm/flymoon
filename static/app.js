const COLUMN_NAMES = [
    "id",
    "origin",
    "destination",
    "time",
    "target_alt",
    "plane_alt",
    "alt_diff",
    "target_az",
    "plane_az",
    "az_diff",
    "elevation_change",
    "aircraft_elevation_feet",
    "direction",
    "distance_km",
];
const MS_IN_A_MIN = 60000;
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

function startTracking(flightId) {
    // Stop any existing tracking
    stopTracking();

    trackingFlightId = flightId;
    console.log(`Track mode: started for ${flightId}`);
    playTrackOnSound();

    // Visual indicator
    updateTrackingIndicator();

    // Start polling
    trackingInterval = setInterval(fetchFlights, TRACK_INTERVAL_MS);

    // Auto-stop after 3 minutes
    trackingTimeout = setTimeout(() => {
        console.log('Track mode: 3 minute timeout');
        stopTracking();
    }, TRACK_TIMEOUT_MS);

    // Immediate fetch
    fetchFlights();
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
    let minAltitude = parseFloat(minAlt.value) || 15;

    if(isNaN(latitude) || isNaN(longitude) || isNaN(elevation)) {
        alert("Please, type all your coordinates. Use MAPS.ie or Google Earth");
        return;
    }

    localStorage.setItem("latitude", latitude);
    localStorage.setItem("longitude", longitude);
    localStorage.setItem("elevation", elevation);
    localStorage.setItem("minAltitude", minAltitude);

    // Save bounding box if user has edited it
    if (window.lastBoundingBox) {
        localStorage.setItem("boundingBox", JSON.stringify(window.lastBoundingBox));
    }

    alert("Position saved in local storage!");
}

function loadPosition() {
    const savedLat = localStorage.getItem("latitude");
    const savedLon = localStorage.getItem("longitude");
    const savedElev = localStorage.getItem("elevation");
    const savedMinAlt = localStorage.getItem("minAltitude");
    const savedBoundingBox = localStorage.getItem("boundingBox");

    if (savedLat === null || savedLat === "" || savedLat === "null") {
        console.log("No position saved in local storage");
        document.getElementById("minAltitude").value = 15; // Default
        return;
    }

    document.getElementById("latitude").value = savedLat;
    document.getElementById("longitude").value = savedLon;
    document.getElementById("elevation").value = savedElev;
    document.getElementById("minAltitude").value = savedMinAlt || 15;

    // Load saved bounding box
    if (savedBoundingBox) {
        try {
            window.lastBoundingBox = JSON.parse(savedBoundingBox);
            console.log("Bounding box loaded from local storage:", window.lastBoundingBox);
        } catch (e) {
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
    document.getElementById("minAltitude").value = "15";
}

function go() {
    // Toggle results visibility
    const resultsDiv = document.getElementById("results");
    const mapContainer = document.getElementById("mapContainer");

    if (resultsVisible) {
        // Hide results and map
        resultsVisible = false;
        mapVisible = false;
        resultsDiv.style.display = 'none';
        mapContainer.style.display = 'none';
        document.getElementById("goBtn").textContent = 'Show/Hide';
    } else {
        // Validate coordinates first
        let lat = document.getElementById("latitude");
        let latitude = parseFloat(lat.value);

        if(isNaN(latitude)) {
            alert("Please, type your coordinates and save them");
            return;
        }

        // Show results and fetch data
        resultsVisible = true;
        mapVisible = true;
        resultsDiv.style.display = 'block';
        mapContainer.style.display = 'block';
        document.getElementById("goBtn").textContent = 'Show/Hide';

        fetchFlights();
    }
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
        let freq = prompt("Enter a frequency in minutes, recommended 15");

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
        document.getElementById("autoGoNote").innerHTML = `Auto check every ${freq} minute(s).`;

        autoMode = true;
        autoGoInterval = setInterval(goFetch, MS_IN_A_MIN * freq);
        refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);

        // Trigger initial fetch
        goFetch();
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

    let hasVeryPossibleTransits = false;

    const bodyTable = document.getElementById('flightData');
    let alertNoResults = document.getElementById("noResults");
    let alertTargetUnderHorizon = document.getElementById("targetUnderHorizon");
    bodyTable.innerHTML = '';
    alertNoResults.innerHTML = '';
    alertTargetUnderHorizon = '';

    const minAltitude = document.getElementById("minAltitude").value || 15;
    let endpoint_url = (
        `/flights?target=${encodeURIComponent(target)}`
        + `&latitude=${encodeURIComponent(latitude)}`
        + `&longitude=${encodeURIComponent(longitude)}`
        + `&elevation=${encodeURIComponent(elevation)}`
        + `&min_altitude=${encodeURIComponent(minAltitude)}`
        + `&send-notification=${autoMode}`
    );

    // Add custom bounding box if user has edited it
    if (window.lastBoundingBox) {
        endpoint_url += `&bbox_lat_ll=${encodeURIComponent(window.lastBoundingBox.latLowerLeft)}`;
        endpoint_url += `&bbox_lon_ll=${encodeURIComponent(window.lastBoundingBox.lonLowerLeft)}`;
        endpoint_url += `&bbox_lat_ur=${encodeURIComponent(window.lastBoundingBox.latUpperRight)}`;
        endpoint_url += `&bbox_lon_ur=${encodeURIComponent(window.lastBoundingBox.lonUpperRight)}`;
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
            alertNoResults.innerHTML = "No flights!"
        }

        // LINE 1: Tracking status - Sun and Moon with weather
        let trackingParts = [];

        // Always show Sun status
        if(data.targetCoordinates && data.targetCoordinates.sun) {
            let isTracking = data.trackingTargets && data.trackingTargets.includes('sun');
            let status = isTracking ? "Tracking" : "Not tracking";
            trackingParts.push(`☀️ ${status}`);
        }

        // Always show Moon status
        if(data.targetCoordinates && data.targetCoordinates.moon) {
            let isTracking = data.trackingTargets && data.trackingTargets.includes('moon');
            let status = isTracking ? "Tracking" : "Not tracking";
            trackingParts.push(`🌙 ${status}`);
        }

        // Weather
        if(data.weather && data.weather.cloud_cover !== null) {
            trackingParts.push(`☁️ ${data.weather.cloud_cover}% clouds`);
        }

        document.getElementById("trackingStatus").innerHTML = trackingParts.join("&nbsp;&nbsp;&nbsp;&nbsp;");

        // LINE 3: Target coordinates - Sun and Moon alt/az
        let coordParts = [];

        // Always show Sun coordinates
        if(data.targetCoordinates && data.targetCoordinates.sun) {
            let coords = data.targetCoordinates.sun;
            let altStr = coords.altitude !== null && coords.altitude !== undefined ? coords.altitude.toFixed(1) : "—";
            let azStr = coords.azimuthal !== null && coords.azimuthal !== undefined ? coords.azimuthal.toFixed(1) : "—";
            coordParts.push(`☀️ Alt: ${altStr}° Az: ${azStr}°`);
        }

        // Always show Moon coordinates
        if(data.targetCoordinates && data.targetCoordinates.moon) {
            let coords = data.targetCoordinates.moon;
            let altStr = coords.altitude !== null && coords.altitude !== undefined ? coords.altitude.toFixed(1) : "—";
            let azStr = coords.azimuthal !== null && coords.azimuthal !== undefined ? coords.azimuthal.toFixed(1) : "—";
            coordParts.push(`🌙 Alt: ${altStr}° Az: ${azStr}°`);
        }

        document.getElementById("targetCoordinates").innerHTML = coordParts.join("&nbsp;&nbsp;&nbsp;&nbsp;");


        // Check if any targets are trackable
        if(data.trackingTargets && data.trackingTargets.length === 0) {
            alertNoResults.innerHTML = "No targets available for tracking (below horizon or weather)";
        }

        // Deduplicate flights by ID for display (keep highest possibility level)
        const seenFlights = {};
        data.flights.forEach(flight => {
            // Normalize ID (trim whitespace, consistent case)
            const id = String(flight.id).trim().toUpperCase();
            if (!seenFlights[id]) {
                seenFlights[id] = flight;
            } else {
                // Keep the one with higher possibility (transit > non-transit, higher level wins)
                const existing = seenFlights[id];
                if (flight.is_possible_transit > existing.is_possible_transit) {
                    seenFlights[id] = flight;
                } else if (flight.is_possible_transit === existing.is_possible_transit) {
                    if (parseInt(flight.possibility_level || 0) > parseInt(existing.possibility_level || 0)) {
                        seenFlights[id] = flight;
                    }
                }
            }
        });
        const uniqueFlights = Object.values(seenFlights);
        console.log(`Dedupe: ${data.flights.length} flights -> ${uniqueFlights.length} unique`);
        // Debug: show final dedupe results
        uniqueFlights.forEach(f => {
            if (f.is_possible_transit) {
                console.log(`  ${f.id} (${f.target}): level=${f.possibility_level}, is_transit=${f.is_possible_transit}`);
            }
        });

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
                } else if (column === "aircraft_elevation_feet") {
                    // Show GPS altitude in feet with comma formatting, or as flight level if > 18000
                    const altitude = Math.round(value);
                    if (altitude > 18000) {
                        const flightLevel = Math.round(altitude / 100);
                        val.textContent = `FL${flightLevel}`;
                    } else {
                        val.textContent = altitude.toLocaleString('en-US');
                    }
                } else if (column === "distance_km") {
                    // Show distance in km with one decimal place
                    val.textContent = value.toFixed(1);
                } else if (column === "direction") {
                    val.textContent = Math.round(value) + "°";
                } else if (column === "alt_diff" || column === "az_diff") {
                    val.textContent = Math.round(value) + "º";
                } else if (column === "target_alt" || column === "target_az") {
                    // Only show target values for possible transits
                    if (item.is_possible_transit === 1) {
                        val.textContent = value.toFixed(1) + "º";
                    } else {
                        val.textContent = "";
                    }
                } else if (column === "plane_alt" || column === "plane_az") {
                    val.textContent = value.toFixed(1) + "º";
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

        // renderTargetCoordinates(data.targetCoordinates); // Disabled - now using inline display above
        if(autoMode == true && hasVeryPossibleTransits == true) soundAlert();

        // Always update map visualization when data is fetched (use deduplicated flights)
        if(mapVisible) {
            const mapData = {...data, flights: uniqueFlights};
            updateMapVisualization(mapData, parseFloat(latitude), parseFloat(longitude), parseFloat(elevation));
        }

        // Save bounding box for next time
        if(data.boundingBox) {
            window.lastBoundingBox = data.boundingBox;
        }
    })
    .catch(error => {
        // Hide loading spinner on error
        document.getElementById("loadingSpinner").style.display = "none";
        document.getElementById("results").style.display = "block";
        alert("Error getting flight data. Check console for details.");
        console.error("Error:", error);
    });
}

function highlightPossibleTransit(possibilityLevel, row) {
    if(possibilityLevel == LOW_LEVEL) row.classList.add("possibleTransitHighlightLow");
    else if(possibilityLevel == MEDIUM_LEVEL) row.classList.add("possibleTransitHighlightMedium");
    else if(possibilityLevel == HIGH_LEVEL) row.classList.add("possibleTransitHighlightHigh");
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

function renderTargetCoordinates(coordinates) {
    let time_ = (new Date()).toLocaleTimeString();
    let coordinates_str;

    // Check if coordinates is nested (auto mode) or direct (single target mode)
    if (coordinates.altitude !== undefined && coordinates.azimuthal !== undefined) {
        // Single target mode
        coordinates_str = "altitude: " + coordinates.altitude + "° azimuthal: " + coordinates.azimuthal + "° (" + time_ + ")";
    } else {
        // Auto mode - coordinates is an object with target names as keys
        let parts = [];
        for (let [targetName, coords] of Object.entries(coordinates)) {
            let icon = targetName === "moon" ? "🌙" : "☀️";
            parts.push(`${icon} alt: ${coords.altitude}° az: ${coords.azimuthal}°`);
        }
        coordinates_str = parts.join(" | ") + " (" + time_ + ")";
    }

    document.getElementById("targetCoordinates").innerHTML = coordinates_str;
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
    
    // Also show desktop notification if permitted
    showDesktopNotification();
}

function showDesktopNotification() {
    // Check if browser supports notifications
    if (!('Notification' in window)) {
        console.log('Browser does not support desktop notifications');
        return;
    }
    
    // Check permission
    if (Notification.permission === 'granted') {
        createNotification();
    } else if (Notification.permission !== 'denied') {
        // Request permission
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                createNotification();
            }
        });
    }
}

function createNotification() {
    const targetIcon = target === 'auto' ? '🌙☀️' : (target === 'moon' ? '🌙' : '☀️');
    const title = `Transit Alert! ${targetIcon}`;
    const body = 'Possible aircraft transit detected. Check the results table for details.';
    
    const notification = new Notification(title, {
        body: body,
        icon: '/static/images/favicon.ico',
        badge: '/static/images/favicon.ico',
        tag: 'flymoon-transit',
        requireInteraction: false
    });
    
    notification.onclick = function() {
        window.focus();
        this.close();
    };
    
    // Auto-close after 10 seconds
    setTimeout(() => notification.close(), 10000);
}

function requestNotificationPermission() {
    if (!('Notification' in window)) {
        alert('Your browser does not support desktop notifications');
        return;
    }

    if (Notification.permission === 'granted') {
        alert('Alerts are already enabled!');
        return;
    }

    if (Notification.permission === 'denied') {
        alert('Alerts were previously denied. Please enable them in your browser settings.');
        return;
    }

    Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
            alert('Alerts enabled successfully!');
        } else {
            alert('Alerts were not enabled.');
        }
    });
}
