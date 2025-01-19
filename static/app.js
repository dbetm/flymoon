const COLUMN_NAMES = [
    "id",
    "origin",
    "destination",
    "alt_diff",
    "az_diff",
    "time",
    "target_alt",
    "plane_alt",
    "target_az",
    "plane_az",
    "elevation_change",
    "direction",
];
const MS_IN_A_MIN = 60000;
// Possibility levels
const LOW_LEVEL = 1, MEDIUM_LEVEL = 2, HIGH_LEVEL = 3;
var autoMode = false;
var target = getLocalStorageItem("target", "moon");
var autoGoInterval = setInterval(go, 86400000);
var refreshTimerLabelInterval = setInterval(refreshTimer, MS_IN_A_MIN);
// By default disable auto go and refresh timer label
clearInterval(autoGoInterval);
clearInterval(refreshTimerLabelInterval);
displayTarget();


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
    if(isNaN(localStorage.getItem("latitude"))) {
        console.log("not position saved in local storage");
        return;
    }

    let lat = document.getElementById("latitude");
    let long = document.getElementById("longitude");
    let elev = document.getElementById("elevation");

    lat.value = localStorage.getItem("latitude");
    long.value = localStorage.getItem("longitude");
    elev.value = localStorage.getItem("elevation");

    console.log("Position loaded from local storage");
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
    let alertMessage = document.getElementById("noResults");
    bodyTable.innerHTML = '';
    alertMessage.innerHTML = '';

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
            alertMessage.innerHTML = "No flights!"
        }

        data.flights.forEach(item => {
            const row = document.createElement('tr');

            COLUMN_NAMES.forEach(column => {
                const val = document.createElement("td");

                if(column == "direction") val.textContent = item[column] + "°";
                else if(item[column] == "N/D") val.textContent = item[column] + " ⚠️";
                else val.textContent = item[column];

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
    });
}

function highlightPossibleTransit(possibilityLevel, row) {
    if(possibilityLevel == LOW_LEVEL) row.classList.add("possibleTransitHighlightLow");
    else if(possibilityLevel == MEDIUM_LEVEL) row.classList.add("possibleTransitHighlightMedium");
    else if(possibilityLevel == HIGH_LEVEL) row.classList.add("possibleTransitHighlightHigh");
}

function toggleTarget() {
    if(target == "moon") target = "sun";
    else target = "moon";

    document.getElementById("targetCoordinates").innerHTML = "";
    displayTarget();

    resetResultsTable();
}

function renderTargetCoordinates(coordinates) {
    let alt = coordinates.altitude;
    let az = coordinates.azimuthal;
    let time_ = (new Date()).toLocaleTimeString();
    const coordinates_str = "altitude: " + alt + "° azimuthal: " + az + "° (" + time_ + ")";

    document.getElementById("targetCoordinates").innerHTML = coordinates_str;
}

function displayTarget() {
    if(target == "moon") {
        document.getElementById("targetIcon").innerHTML = "🌙";
    }
    else {
        document.getElementById("targetIcon").innerHTML = "☀️";
    }

    localStorage.setItem("target", target);
    document.getElementById("targetLabel").innerHTML = target;
}

function resetResultsTable() {
    document.getElementById("flightData").innerHTML = "";
}

function soundAlert() {
    const audio = document.getElementById('alertSound');
    audio.play();
}