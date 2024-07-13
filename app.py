import argparse
import time

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

from src.intersection import check_intersections


# SETUP 
load_dotenv()

app = Flask(__name__)



@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check_intersections")
def get_list():
    start_time = time.time()

    target = request.args["target"]

    data = check_intersections(target, test_mode)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Elapsed time: {elapsed_time} seconds")

    return jsonify({'list': data})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test", action="store_true", help="load existing flight data"
    )
    args = parser.parse_args()

    global test_mode
    test_mode = args.test

    port = 5000
    app.run(host='0.0.0.0', port=8000, debug=True)