import argparse
import asyncio
import json
import os
import time
from datetime import date, datetime
from http import HTTPStatus

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from src.constants import POSSIBLE_TRANSITS_LOGFILENAME

# SETUP
load_dotenv()

from src import logger
from src.config_wizard import ConfigWizard
from src.flight_data import save_possible_transits, sort_results
from src.notify import send_notifications
from src.transit import get_transits

app = Flask(__name__)

# Gallery configuration
UPLOAD_FOLDER = "static/gallery"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def check_config():
    """Validate configuration from .env"""
    wizard = ConfigWizard()
    is_valid = wizard.validate(interactive=False)
    print(wizard.get_status_report())

    if not is_valid:
        logger.error("\n🚨  Critical issues detected:")
        print(
            "\n💡 Please run 'python3 src/config_wizard.py --setup' to configure"
            " or manuallu add the required values to .env\n"
        )
        exit(1)


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
    min_altitude = float(request.args.get("min_altitude", 15))
    has_send_notification = request.args["send_notification"] == "true"
    adsb_provider = request.args["adsb_provider"]
    check_weather = request.args["check_weather"] == "true"

    # Check for custom bounding box from user
    custom_bbox = None
    bbox_args = [
        "bbox_lat_lower_left",
        "bbox_lon_lower_left",
        "bbox_lat_upper_right",
        "bbox_lon_upper_right",
    ]
    if all(key in request.args for key in bbox_args):
        custom_bbox = {
            "lat_lower_left": float(request.args["bbox_lat_lower_left"]),
            "lon_lower_left": float(request.args["bbox_lon_lower_left"]),
            "lat_upper_right": float(request.args["bbox_lat_upper_right"]),
            "lon_upper_right": float(request.args["bbox_lon_upper_right"]),
        }
        logger.info(f"Given bounding box: {custom_bbox}")

    data: dict = get_transits(
        latitude,
        longitude,
        elevation,
        target,
        test_mode,
        min_altitude,
        custom_bbox,
        adsb_provider,
        check_weather,
    )
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
            logger.error(
                f"Error while trying to send push notification. Details:\n{str(e)}"
            )

    return jsonify(data)


@app.route("/gallery")
def gallery():
    """Display the transit image gallery page."""
    return render_template("gallery.html")


@app.route("/gallery/upload", methods=["POST"])
def upload_transit_image():
    """Upload a transit image with metadata."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), HTTPStatus.BAD_REQUEST

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), HTTPStatus.BAD_REQUEST

    if file and allowed_file(file.filename):
        transit_date_str = request.form.get("transit_date", "")
        try:
            transit_dt = (
                datetime.strptime(transit_date_str, "%Y-%m-%d")
                if transit_date_str
                else datetime.now()
            )
        except ValueError:
            transit_dt = datetime.now()

        flight_id = request.form.get("flight_id", "UNKNOWN").replace("/", "_")
        ext = file.filename.rsplit(".", 1)[1].lower()

        # Create year/month directories based on transit date
        year_month_path = os.path.join(
            app.config["UPLOAD_FOLDER"], str(transit_dt.year), f"{transit_dt.month:02d}"
        )
        os.makedirs(year_month_path, exist_ok=True)

        # Save image
        date_prefix = transit_dt.strftime("%Y%m%d")
        filename = secure_filename(f"{date_prefix}_{flight_id}.{ext}")
        filepath = os.path.join(year_month_path, filename)
        file.save(filepath)

        # Save metadata
        metadata = {
            "flight_id": request.form.get("flight_id", ""),
            "aircraft_type": request.form.get("aircraft_type", ""),
            "upload_date": datetime.now().isoformat(),
            "target": request.form.get("target", ""),
            "caption": request.form.get("caption", ""),
            "equipment": request.form.get("equipment", ""),
            "transit_date": transit_dt.strftime("%Y-%m-%d"),
        }

        metadata_path = filepath.rsplit(".", 1)[0] + ".json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Uploaded transit image: {filename}")
        return jsonify({"success": True, "filename": filename}), HTTPStatus.OK

    return (
        jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif"}),
        HTTPStatus.BAD_REQUEST,
    )


@app.route("/gallery/list")
def list_gallery():
    """List all gallery images with metadata."""
    gallery_path = app.config["UPLOAD_FOLDER"]
    images = []

    # Create gallery directory if it doesn't exist
    os.makedirs(gallery_path, exist_ok=True)

    # Walk directory structure
    for root, dirs, files in os.walk(gallery_path):
        for file in files:
            if file.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, "static")
                # Use forward slashes for web paths
                rel_path = rel_path.replace("\\", "/")
                metadata_path = full_path.rsplit(".", 1)[0] + ".json"

                metadata = {}
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                    except Exception as e:
                        logger.error(f"Error reading metadata for {file}: {str(e)}")

                images.append(
                    {"path": rel_path, "filename": file, "metadata": metadata}
                )

    # Sort by timestamp (most recent first)
    images.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)
    return jsonify(images)


@app.route("/gallery/delete/<path:filepath>", methods=["DELETE"])
def delete_gallery_image(filepath):
    """Delete a gallery image and its metadata."""
    try:
        # Security check - ensure filepath is within gallery directory
        full_path = os.path.join("static", filepath)
        abs_path = os.path.abspath(full_path)
        gallery_abs = os.path.abspath(app.config["UPLOAD_FOLDER"])

        if not abs_path.startswith(gallery_abs):
            return jsonify({"error": "Invalid file path"}), HTTPStatus.FORBIDDEN

        # Delete image file
        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted image: {filepath}")

        # Delete metadata file
        metadata_path = abs_path.rsplit(".", 1)[0] + ".json"
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
            logger.info(f"Deleted metadata: {metadata_path}")

        return jsonify({"success": True}), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error deleting image {filepath}: {str(e)}")
        return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR


@app.route("/gallery/update/<path:filepath>", methods=["POST"])
def update_gallery_metadata(filepath):
    """Update metadata for a gallery image."""
    try:
        # Security check - ensure filepath is within gallery directory
        full_path = os.path.join("static", filepath)
        abs_path = os.path.abspath(full_path)
        gallery_abs = os.path.abspath(app.config["UPLOAD_FOLDER"])

        if not abs_path.startswith(gallery_abs):
            return jsonify({"error": "Invalid file path"}), HTTPStatus.FORBIDDEN

        # Get metadata file path
        metadata_path = abs_path.rsplit(".", 1)[0] + ".json"

        # Read existing metadata
        metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

        # Update with new values from request
        metadata.update(
            {
                "flight_id": request.form.get(
                    "flight_id", metadata.get("flight_id", "")
                ),
                "aircraft_type": request.form.get(
                    "aircraft_type", metadata.get("aircraft_type", "")
                ),
                "target": request.form.get("target", metadata.get("target", "")),
                "caption": request.form.get("caption", metadata.get("caption", "")),
                "equipment": request.form.get(
                    "equipment", metadata.get("equipment", "")
                ),
                "transit_date": request.form.get(
                    "transit_date", metadata.get("transit_date", "")
                ),
            }
        )

        # Save updated metadata
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Updated metadata for: {filepath}")
        return jsonify({"success": True, "metadata": metadata}), HTTPStatus.OK
    except Exception as e:
        logger.error(f"Error updating metadata for {filepath}: {str(e)}")
        return jsonify({"error": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flymoon Transit Monitor")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use test generated flights data with some possible transits",
    )
    # parser.add_argument("--demo", action="store_true", help="Use mock demonstration data with guaranteed classifications")
    args = parser.parse_args()

    global test_mode
    # test_mode = args.test or args.demo
    test_mode = args.test

    if test_mode:
        logger.info(f"🧪 Starting in test mode - using generated flight data")

    check_config()

    port = 8000
    app.run(host="0.0.0.0", port=port, debug=True)
