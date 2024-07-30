var columnNames = [
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
    "change_elev",
];

var target = getLocalStorageItem("target", "moon");
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

    fetchTransits();
}

function fetchTransits() {
    let latitude = document.getElementById("latitude").value;
    let longitude = document.getElementById("longitude").value;
    let elevation = document.getElementById("elevation").value;

    const bodyTable = document.getElementById('flightData');
    let alertMessage = document.getElementById("noResults");
    bodyTable.innerHTML = '';
    alertMessage.innerHTML = '';

    const endpoint_url = (
        `/transits?target=${encodeURIComponent(target)}`
        + `&latitude=${encodeURIComponent(latitude)}`
        + `&longitude=${encodeURIComponent(longitude)}`
        + `&elevation=${encodeURIComponent(elevation)}`
    );

    fetch(endpoint_url)
    .then(response => response.json())
    .then(data => {

        if(data.transits.length == 0) {
            alertMessage.innerHTML = "No flights!"
        }

        data.transits.forEach(item => {
            const row = document.createElement('tr');

            columnNames.forEach(column => {
                const val = document.createElement("td");
                val.textContent = item[column];

                row.appendChild(val);
            });

            if(item["is_possible_hit"] == 1) {
                if(item["alt_diff"] <= 3 && item["az_diff"] <= 3) {
                    row.classList.add('highlight-level-2');
                }
                else if(item["alt_diff"] <= 7 && item["az_diff"] <= 5) {
                    row.classList.add('highlight-level-1');
                }
            }

            bodyTable.appendChild(row);
        });

        renderTargetCoordinates(data.targetCoordinates);
    });
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
    const coordinates_str = "altitude: " + alt + " azimuthal: " + az;

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