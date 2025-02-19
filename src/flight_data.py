import json
import os
from datetime import datetime
from http import HTTPStatus
from typing import List

import requests

from src.position import AreaBoundingBox


def get_flight_data(
    area_bbox: AreaBoundingBox, url_: str, api_key: str = ""
) -> List[dict]:

    headers = {"Accept": "application/json; charset=UTF-8", "x-apikey": api_key}

    # example: https://aeroapi.flightaware.com/aeroapi/flights/search?query=-latlong+%2221.305695+-104.458904+23.925834+-101.365481%22&max_pages=1
    url = (
        f"{url_}?query=-latlong+%22{area_bbox.lat_lower_left}+{area_bbox.long_lower_left}+"
        f"{area_bbox.lat_upper_right}+{area_bbox.long_upper_right}%22&max_pages=1"
    )

    response = requests.get(url=url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        # If not successful, raise exception with the status code and response text
        raise Exception(f"Error: {response.status_code}, {response.text}")


def parse_fligh_data(flight_data: dict):
    has_destination = isinstance(flight_data.get("destination"), dict)

    return {
        "name": flight_data["ident"],
        "origin": flight_data["origin"]["city"],
        "destination": (
            "N/D"
            if not has_destination
            else flight_data.get("destination", dict()).get("city")
        ),
        "latitude": flight_data["last_position"]["latitude"],
        "longitude": flight_data["last_position"]["longitude"],
        "direction": flight_data["last_position"]["heading"],
        "speed": int(flight_data["last_position"]["groundspeed"]) * 1.852,
        "elevation": int(flight_data["last_position"]["altitude"]) * 100 * 0.3048,
        "elevation_change": flight_data["last_position"]["altitude_change"],
    }


def load_existing_flight_data(path: str) -> dict:
    with open(path, "r") as file:
        return json.load(file)


def sort_results(data: List[dict]) -> List[dict]:
    """Sort data flight results considering if it's possible transit, ETA and time."""

    def _custom_sort(a: dict) -> bool:
        total_diff = a["alt_diff"] + a["az_diff"] if a["is_possible_transit"] else 100
        return (a["is_possible_transit"], -1 * total_diff, a["time"], a["id"])

    return sorted(data, key=_custom_sort, reverse=True)


async def save_possible_transits(data: List[dict], dest_path: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = list()

    for flight in data:
        if flight["is_possible_transit"] == 1:
            line = f"{timestamp},"
            line += ",".join(map(str, flight.values()))
            log_message.append(line)

    if len(log_message) > 0:
        has_log_file = os.path.exists(dest_path)
        with open(dest_path, "a") as f:
            if not has_log_file:
                headers = "timestamp," + ",".join(flight.keys())
                f.write(headers + "\n")
            f.write("\n".join(log_message))
            f.write("\n")
