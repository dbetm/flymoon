from flask import Flask, render_template_string, jsonify

from app import run

app = Flask(__name__)


html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Flymoon app</title>
</head>
<body>
    <h1>Flymoon App</h1>
    <button onclick="fetchList()" style="font-size: 30px;">Compute</button>
    <ul id="list-container"></ul>
    
    <script>
        function fetchList() {
            fetch('/get_list')
            .then(response => response.json())
            .then(data => {
                const listContainer = document.getElementById('list-container');
                listContainer.innerHTML = '';
                data.list.forEach(item => {
                    const listItem = document.createElement('li');
                    listItem.textContent = item;
                    listContainer.appendChild(listItem);
                });
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/get_list')
def get_list():
    data = run()
    return jsonify({'list': data})


if __name__ == '__main__':
    # Expose the app on localhost
    port = 5000
    app.run(host='0.0.0.0', port=8000, debug=True)
