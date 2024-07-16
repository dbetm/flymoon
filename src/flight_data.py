import json
from http import HTTPStatus
from typing import List

import requests

from src.position import AreaBoundingBox


def get_flight_data(
    area_bbox: AreaBoundingBox,
    url_: str,
    api_key: str = ""
) -> List[dict]:

    headers = {
        "Accept": "application/json; charset=UTF-8",
        "x-apikey": api_key,
    }

    # example
    # "https://aeroapi.flightaware.com/aeroapi/flights/search?query=-latlong+%2221.305695+-104.458904+23.925834+-101.365481%22&max_pages=1"
    url = (
        f"{url_}?query=-latlong+%22{area_bbox.lat_lower_left}+{area_bbox.long_lower_left}+"
        f"{area_bbox.lat_upper_right}+{area_bbox.long_upper_right}%22&max_pages=1"
    )

    response = requests.get(
        url=url, headers=headers
    )

    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        # If not successful, print the status code and response text
        print(f"Error: {response.status_code}")
        print(response.text)


def parse_fligh_data(flight_data: dict):
    has_destination = isinstance(flight_data.get("destination"), dict)

    return {
        "name": flight_data["ident"],
        "origin": flight_data["origin"]["city"],
        "destination": (
            "unknown ⚠️" if not has_destination else flight_data.get("destination", dict()).get("city")
        ),
        "latitude": flight_data["last_position"]["latitude"],
        "longitude": flight_data["last_position"]["longitude"],
        "direction": flight_data["last_position"]["heading"],
        "speed": int(flight_data["last_position"]["groundspeed"]) * 1.852,
        "elevation": int(flight_data["last_position"]["altitude"]) * 100 * 0.3048
    }


def load_existing_flight_data(path: str) -> dict:
    print("loading existing flight data")

    with open(path, "r") as file:
        return json.load(file)