import time

from flask import Flask, render_template, jsonify

from app import run

app = Flask(__name__)


@app.route('/')
def index():
    return render_template("index.html")

@app.route('/check_intersections')
def get_list():
    start_time = time.time()

    data = run()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time} seconds")

    return jsonify({'list': data})


if __name__ == '__main__':
    port = 5000
    app.run(host='0.0.0.0', port=8000, debug=True)
