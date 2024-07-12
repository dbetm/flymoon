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
];

var target = "sun";

function fetchList() {
    const bodyTable = document.getElementById('flightData');
    let alertMessage = document.getElementById("noResults");
    bodyTable.innerHTML = '';
    alertMessage.innerHTML = '';

    const endpoint_url = `/check_intersections?target=${encodeURIComponent(target)}`;

    fetch(endpoint_url)
    .then(response => response.json())
    .then(data => {

        if(data.list.length == 0) {
            alertMessage.innerHTML = "No flights!"
        }

        data.list.forEach(item => {
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
    });
}


function toggleTarget() {
    if(target == "moon") {
        target = "sun";

        document.getElementById("targetIcon").innerHTML = "☀️";
    }
    else {
        target = "moon";

        document.getElementById("targetIcon").innerHTML = "🌙";
    }

    document.getElementById("targetLabel").innerHTML = target;
}