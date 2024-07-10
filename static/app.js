var columnNames = [
    "id",
    "origin",
    "destination",
    "time",
    "alt_diff",
    "az_diff",
    "target_alt",
    "plane_alt",
    "target_az",
    "plane_az",
];

function fetchList() {
    const bodyTable = document.getElementById('flightData');
    bodyTable.innerHTML = '';

    fetch('/check_intersections')
    .then(response => response.json())
    .then(data => {

        data.list.forEach(item => {
            const row = document.createElement('tr');

            columnNames.forEach(column => {
                const val = document.createElement("td");
                val.textContent = item[column];

                row.appendChild(val);
            });

            if(item["alt_diff"] <= 3 && item["az_diff"] <= 3) {
                row.classList.add('highlight-level-2');
            }
            else if(item["alt_diff"] <= 5 && item["az_diff"] <= 5) {
                row.classList.add('highlight-level-1');
            }

            bodyTable.appendChild(row);
        });
    });
}