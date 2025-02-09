import argparse
import asyncio
import time
from datetime import date

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from src.constants import POSSIBLE_TRANSITS_LOGFILENAME

# SETUP
load_dotenv()

from src import logger
from src.flight_data import save_possible_transits, sort_results
from src.notify import send_notifications
from src.transit import get_transits

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/flights")
def get_all_flights():
    start_time = time.time()

    target = request.args["target"]
    latitude = float(request.args["latitude"])
    longitude = float(request.args["longitude"])
    elevation = float(request.args["elevation"])
    has_send_notification = request.args["send-notification"] == "true"

    data: dict = get_transits(latitude, longitude, elevation, target, test_mode)
    data["flights"] = sort_results(data["flights"])

    end_time = time.time()
    elapsed_time = end_time - start_time
    logger.info(f"Elapsed time: {elapsed_time} seconds")

    if not test_mode:
        try:
            date_ = date.today().strftime("%Y%m%d")
            asyncio.run(
                save_possible_transits(
                    data["flights"], POSSIBLE_TRANSITS_LOGFILENAME.format(date_=date_)
                )
            )
        except Exception as e:
            logger.error(
                f"Error while trying to save possible transits. Details:\n{str(e)}"
            )

    if has_send_notification:
        try:
            asyncio.run(send_notifications(data["flights"], target))
        except Exception as e:
            logger.error(f"Error while trying to send notification. Details:\n{str(e)}")

    return jsonify(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="load existing flight data")
    args = parser.parse_args()

    global test_mode
    test_mode = args.test

    port = 8000
    app.run(host="0.0.0.0", port=port, debug=True)
