import argparse
import asyncio
import json
import os
import time
from datetime import date, datetime

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from src.constants import FLIGHT_ROUTE_URL, FLIGHT_TRACK_URL, POSSIBLE_TRANSITS_LOGFILENAME

# SETUP
load_dotenv()

from src import logger
from src.config_wizard import ConfigWizard
from src.flight_data import save_possible_transits, sort_results
from src.notify import send_notifications
from src.transit import get_transits

# Validate configuration on startup
wizard = ConfigWizard()
if not wizard.validate(interactive=False):
    print("\n⚠️  Configuration issues detected:")
    print(wizard.get_status_report())
    print("\n💡 Run 'python3 src/config_wizard.py --setup' to configure\n")

app = Flask(__name__)

# Gallery configuration
UPLOAD_FOLDER = 'static/gallery'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    has_send_notification = request.args["send-notification"] == "true"

    # Check for custom bounding box from user
    custom_bbox = None
    if all(key in request.args for key in ["bbox_lat_ll", "bbox_lon_ll", "bbox_lat_ur", "bbox_lon_ur"]):
        custom_bbox = {
            "lat_lower_left": float(request.args["bbox_lat_ll"]),
            "lon_lower_left": float(request.args["bbox_lon_ll"]),
            "lat_upper_right": float(request.args["bbox_lat_ur"]),
            "lon_upper_right": float(request.args["bbox_lon_ur"]),
        }
        logger.info(f"Using custom bounding box: {custom_bbox}")

    data: dict = get_transits(latitude, longitude, elevation, target, test_mode, min_altitude, custom_bbox)
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


@app.route("/flights/<fa_flight_id>/route")
def get_flight_route(fa_flight_id):
    """Get the filed route for a specific flight."""
    API_KEY = os.getenv("AEROAPI_API_KEY")
    url = FLIGHT_ROUTE_URL.format(fa_flight_id)
    headers = {"Accept": "application/json; charset=UTF-8", "x-apikey": API_KEY}

    try:
        response = requests.get(url=url, headers=headers, timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"API returned status {response.status_code}"}), response.status_code
    except Exception as e:
        logger.error(f"Error fetching route for {fa_flight_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/flights/<fa_flight_id>/track")
def get_flight_track(fa_flight_id):
    """Get the historical track positions for a specific flight."""
    API_KEY = os.getenv("AEROAPI_API_KEY")
    url = FLIGHT_TRACK_URL.format(fa_flight_id)
    headers = {"Accept": "application/json; charset=UTF-8", "x-apikey": API_KEY}

    try:
        response = requests.get(url=url, headers=headers, timeout=10)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"API returned status {response.status_code}"}), response.status_code
    except Exception as e:
        logger.error(f"Error fetching track for {fa_flight_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/gallery")
def gallery():
    """Display the transit image gallery page."""
    return render_template("gallery.html")


@app.route("/gallery/upload", methods=['POST'])
def upload_transit_image():
    """Upload a transit image with metadata."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        flight_id = request.form.get('flight_id', 'UNKNOWN').replace('/', '_')
        ext = file.filename.rsplit('.', 1)[1].lower()

        # Create year/month directories
        now = datetime.now()
        year_month_path = os.path.join(app.config['UPLOAD_FOLDER'], str(now.year), f"{now.month:02d}")
        os.makedirs(year_month_path, exist_ok=True)

        # Save image
        filename = secure_filename(f"{timestamp}_{flight_id}.{ext}")
        filepath = os.path.join(year_month_path, filename)
        file.save(filepath)

        # Save metadata
        metadata = {
            "flight_id": request.form.get('flight_id', ''),
            "aircraft_type": request.form.get('aircraft_type', ''),
            "timestamp": datetime.now().isoformat(),
            "target": request.form.get('target', ''),
            "caption": request.form.get('caption', ''),
            "equipment": request.form.get('equipment', ''),
            "observer_lat": request.form.get('observer_lat', ''),
            "observer_lon": request.form.get('observer_lon', ''),
        }

        metadata_path = filepath.rsplit('.', 1)[0] + '.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Uploaded transit image: {filename}")
        return jsonify({"success": True, "filename": filename}), 200

    return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif"}), 400


@app.route("/gallery/list")
def list_gallery():
    """List all gallery images with metadata."""
    gallery_path = app.config['UPLOAD_FOLDER']
    images = []

    # Create gallery directory if it doesn't exist
    os.makedirs(gallery_path, exist_ok=True)

    # Walk directory structure
    for root, dirs, files in os.walk(gallery_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, 'static')
                # Use forward slashes for web paths
                rel_path = rel_path.replace('\\', '/')
                metadata_path = full_path.rsplit('.', 1)[0] + '.json'

                metadata = {}
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                    except Exception as e:
                        logger.error(f"Error reading metadata for {file}: {str(e)}")

                images.append({
                    "path": rel_path,
                    "filename": file,
                    "full_path": full_path,  # For delete operations
                    "metadata": metadata
                })

    # Sort by timestamp (most recent first)
    images.sort(key=lambda x: x['metadata'].get('timestamp', ''), reverse=True)
    return jsonify(images)


@app.route("/gallery/delete/<path:filepath>", methods=['DELETE'])
def delete_gallery_image(filepath):
    """Delete a gallery image and its metadata."""
    try:
        # Security check - ensure filepath is within gallery directory
        full_path = os.path.join('static', filepath)
        abs_path = os.path.abspath(full_path)
        gallery_abs = os.path.abspath(app.config['UPLOAD_FOLDER'])

        if not abs_path.startswith(gallery_abs):
            return jsonify({"error": "Invalid file path"}), 403

        # Delete image file
        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted image: {filepath}")

        # Delete metadata file
        metadata_path = abs_path.rsplit('.', 1)[0] + '.json'
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
            logger.info(f"Deleted metadata: {metadata_path}")

        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"Error deleting image {filepath}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/gallery/update/<path:filepath>", methods=['POST'])
def update_gallery_metadata(filepath):
    """Update metadata for a gallery image."""
    try:
        # Security check - ensure filepath is within gallery directory
        full_path = os.path.join('static', filepath)
        abs_path = os.path.abspath(full_path)
        gallery_abs = os.path.abspath(app.config['UPLOAD_FOLDER'])

        if not abs_path.startswith(gallery_abs):
            return jsonify({"error": "Invalid file path"}), 403

        # Get metadata file path
        metadata_path = abs_path.rsplit('.', 1)[0] + '.json'

        # Read existing metadata
        metadata = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

        # Update with new values from request
        metadata.update({
            "flight_id": request.form.get('flight_id', metadata.get('flight_id', '')),
            "aircraft_type": request.form.get('aircraft_type', metadata.get('aircraft_type', '')),
            "target": request.form.get('target', metadata.get('target', '')),
            "caption": request.form.get('caption', metadata.get('caption', '')),
            "equipment": request.form.get('equipment', metadata.get('equipment', '')),
            "observer_lat": request.form.get('observer_lat', metadata.get('observer_lat', '')),
            "observer_lon": request.form.get('observer_lon', metadata.get('observer_lon', '')),
        })

        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Updated metadata for: {filepath}")
        return jsonify({"success": True, "metadata": metadata}), 200
    except Exception as e:
        logger.error(f"Error updating metadata for {filepath}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/config")
def get_config():
    """Get client configuration settings."""
    auto_refresh_interval = int(os.getenv("AUTO_REFRESH_INTERVAL_MINUTES", "6"))
    return jsonify({
        "autoRefreshIntervalMinutes": auto_refresh_interval
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flymoon Transit Monitor")
    parser.add_argument("--test", action="store_true", help="Use test data (deprecated, use --demo)")
    parser.add_argument("--demo", action="store_true", help="Use mock demonstration data with guaranteed classifications")
    args = parser.parse_args()

    global test_mode
    test_mode = args.test or args.demo

    if test_mode:
        mode = "DEMO" if args.demo else "TEST"
        logger.info(f"🎭 Starting in {mode} mode - using mock data")

    port = 8000
    app.run(host="0.0.0.0", port=port, debug=True)
