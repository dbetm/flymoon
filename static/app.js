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
    "direction",
];
const MS_IN_A_MIN = 60000;
// Possibility levels
const LOW_LEVEL = 1, MEDIUM_LEVEL = 2, HIGH_LEVEL = 3;
var autoMode = false;
var target = getLocalStorageItem("target", "auto");
var autoGoInterval = setInterval(go, 86400000);
var refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);
// By default disable auto go and refresh timer label
clearInterval(autoGoInterval);
clearInterval(refreshTimerLabelInterval);
displayTarget();

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

    if(isNaN(latitude) || isNaN(longitude) || isNaN(elevation)) {
        alert("Please, type all your coordinates. Use MAPS.ie or Google Earth");
        return;
    }

    localStorage.setItem("latitude", latitude);
    localStorage.setItem("longitude", longitude);
    localStorage.setItem("elevation", elevation);

    alert("Position saved in local storage!");
}

function loadPosition() {
    const savedLat = localStorage.getItem("latitude");
    const savedLon = localStorage.getItem("longitude");
    const savedElev = localStorage.getItem("elevation");

    if (savedLat === null || savedLat === "" || savedLat === "null") {
        console.log("No position saved in local storage");
        return;
    }

    document.getElementById("latitude").value = savedLat;
    document.getElementById("longitude").value = savedLon;
    document.getElementById("elevation").value = savedElev;

    console.log("Position loaded from local storage:", savedLat, savedLon, savedElev);
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
}

function go() {
    let lat = document.getElementById("latitude");
    let latitude = parseFloat(lat.value);

    if(isNaN(latitude)) {
        alert("Please, type your coordinates and save them");
        return;
    }

    fetchFlights();
}

function auto() {
    if(autoMode == true) {
        document.getElementById("goBtn").style.display = 'inline-block';
        document.getElementById("autoBtn").innerHTML = 'Auto';
        document.getElementById("autoGoNote").innerHTML = "";

        autoMode = false;
        clearInterval(autoGoInterval);
        clearInterval(refreshTimerLabelInterval);
    }
    else {
        document.getElementById("goBtn").style.display = 'none';

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
        autoGoInterval = setInterval(go, MS_IN_A_MIN * freq);
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

    let hasVeryPossibleTransits = false;

    const bodyTable = document.getElementById('flightData');
    let alertNoResults = document.getElementById("noResults");
    let alertTargetUnderHorizon = document.getElementById("targetUnderHorizon");
    bodyTable.innerHTML = '';
    alertNoResults.innerHTML = '';
    alertTargetUnderHorizon = '';

    const endpoint_url = (
        `/flights?target=${encodeURIComponent(target)}`
        + `&latitude=${encodeURIComponent(latitude)}`
        + `&longitude=${encodeURIComponent(longitude)}`
        + `&elevation=${encodeURIComponent(elevation)}`
        + `&send-notification=${autoMode}`
    );

    fetch(endpoint_url)
    .then(response => response.json())
    .then(data => {

        if(data.flights.length == 0) {
            alertNoResults.innerHTML = "No flights!"
        }

        // Display weather info
        if(data.weather) {
            let weatherText = `${data.weather.icon} ${data.weather.description}`;
            if(data.weather.cloud_cover !== null) {
                weatherText += ` (${data.weather.cloud_cover}% clouds)`;
            }
            if(!data.weather.api_success) {
                weatherText += " ⚠️";
            }
            document.getElementById("weatherInfo").innerHTML = weatherText;
        }

        // Display tracking status for each target
        if(data.targetCoordinates) {
            let statusParts = [];
            for(let [targetName, coords] of Object.entries(data.targetCoordinates)) {
                let icon = targetName === "moon" ? "🌙" : "☀️";
                let isTracking = data.trackingTargets && data.trackingTargets.includes(targetName);
                let status = isTracking ? "Tracking" : "Not tracking";
                statusParts.push(`${status} ${icon}`);
            }
            document.getElementById("trackingStatus").innerHTML = statusParts.join(" | ");
        }

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

        uniqueFlights.forEach(item => {
            const row = document.createElement('tr');

            // Store normalized flight ID and possibility level for cross-referencing
            const normalizedId = String(item.id).trim().toUpperCase();
            const possibilityLevel = item.is_possible_transit === 1 ? parseInt(item.possibility_level) : 0;
            row.setAttribute('data-flight-id', normalizedId);
            row.setAttribute('data-possibility', possibilityLevel);

            // Click handler: normal click flashes, Cmd/Ctrl+click toggles tracking
            row.addEventListener('click', function(e) {
                if (e.metaKey || e.ctrlKey) {
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
                    // Normal click: flash aircraft on map
                    if (typeof flashAircraftMarker === 'function') {
                        flashAircraftMarker(normalizedId);
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
                } else if (column === "time") {
                    // Format ETA as mm:ss
                    const totalSeconds = Math.round(value * 60);
                    const mins = Math.floor(totalSeconds / 60);
                    const secs = totalSeconds % 60;
                    val.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                } else if (column === "direction") {
                    val.textContent = Math.round(value) + "°";
                } else if (column === "alt_diff" || column === "az_diff") {
                    val.textContent = Math.round(value) + "º";
                } else if (column === "target_alt" || column === "plane_alt" || column === "target_az" || column === "plane_az") {
                    val.textContent = Math.round(value) + "º";
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

        renderTargetCoordinates(data.targetCoordinates);
        if(autoMode == true && hasVeryPossibleTransits == true) soundAlert();
        
        // Update map visualization if map is visible (use deduplicated flights)
        const mapContainer = document.getElementById('mapContainer');
        if(mapContainer && mapContainer.style.display !== 'none') {
            const mapData = {...data, flights: uniqueFlights};
            updateMapVisualization(mapData, parseFloat(latitude), parseFloat(longitude), parseFloat(elevation));
        }
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
    document.getElementById("weatherInfo").innerHTML = "";
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
