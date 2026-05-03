import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from http import HTTPStatus
from typing import List, Optional

import requests

from src.position import AreaBoundingBox


class ADSBProviderClient(ABC):
    def __init__(self, area_bbox: AreaBoundingBox, api_key: str) -> None:
        self.bbox = area_bbox
        self.api_key = api_key

    @abstractmethod
    def get_flight_data(self) -> List[dict]:
        """Retrieve real time aircraft data. Last positions of planes inside the bounding box."""

    @abstractmethod
    def parse(self, flight: dict) -> Optional[dict]:
        """Get useful fields from a raw flight data, convert to used units and normalize values
        between ADSB providers."""


class FlightAwareAeroAPIClient(ADSBProviderClient):
    BASE_URL = "https://aeroapi.flightaware.com/aeroapi"

    def get_flight_data(self) -> List[dict]:
        endpoint_url = f"{self.BASE_URL}/flights/search"
        headers = {
            "Accept": "application/json; charset=UTF-8",
            "x-apikey": self.api_key,
        }

        # example: https://aeroapi.flightaware.com/aeroapi/flights/search?query=-latlong+%2221.305695+-104.458904+23.925834+-101.365481%22&max_pages=1
        url = (
            f"{endpoint_url}?query=-latlong+%22{self.bbox.lat_lower_left}+{self.bbox.long_lower_left}+"
            f"{self.bbox.lat_upper_right}+{self.bbox.long_upper_right}%22&max_pages=1"
        )

        response = requests.get(url=url, headers=headers)

        if response.status_code == HTTPStatus.OK:
            return response.json()
        else:
            # If not successful, raise exception with the status code and response text
            raise Exception(f"Error: {response.status_code}, {response.text}")

    def parse(self, flight: dict) -> dict:
        has_destination = isinstance(flight.get("destination"), dict)

        return {
            "name": flight["ident"],
            "aircraft_type": flight.get("aircraft_type", "N/A"),
            "fa_flight_id": flight.get("fa_flight_id", ""),
            "origin": flight["origin"]["city"],
            "destination": (
                "N/D"
                if not has_destination
                else flight.get("destination", dict()).get("city")
            ),
            "latitude": flight["last_position"]["latitude"],
            "longitude": flight["last_position"]["longitude"],
            "direction": flight["last_position"]["heading"],
            "speed": int(flight["last_position"]["groundspeed"]) * 1.852,  # km/h
            "elevation": int(flight["last_position"]["altitude"])
            * 0.3048
            * 100,  # hundreds of feet to meters (for calculations)
            "elevation_change": flight["last_position"]["altitude_change"],
            "waypoints": (
                flight["waypoints"] if len(flight.get("waypoints", [])) > 0 else None
            ),
            "last_update": flight["last_position"]["timestamp"],
        }


class AirLabsClient(ADSBProviderClient):
    BASE_URL = "https://airlabs.co/api/v9"

    def get_flight_data(self) -> List[dict]:
        endpoint_url = f"{self.BASE_URL}/flights"

        fmt_bbox = (
            f"{self.bbox.lat_lower_left},{self.bbox.long_lower_left}"
            f",{self.bbox.lat_upper_right},{self.bbox.long_upper_right}"
        )

        query_params = f"api_key={self.api_key}&bbox={fmt_bbox}"
        url = f"{endpoint_url}?{query_params}"

        headers = {"Accept": "application/json; charset=UTF-8"}
        response = requests.get(url=url, headers=headers)

        if response.status_code == HTTPStatus.OK:
            return {"flights": response.json()["response"]}
        else:
            # If not successful, raise exception with the status code and response text
            raise Exception(f"Error: {response.status_code}, {response.text}")

    def parse(self, flight: dict) -> Optional[dict]:
        v_speed = flight.get("v_speed", 0)

        # check that exists essential data
        for col in ["speed", "lat", "lng", "dir", "alt"]:
            if not flight.get(col):
                return None

        return {
            "name": flight["flight_icao"],
            "aircraft_type": flight.get("aircraft_icao", "N/A"),
            "fa_flight_id": flight.get("flight_iata", ""),
            "origin": flight["dep_iata"],
            "destination": flight["arr_iata"],
            "latitude": flight["lat"],
            "longitude": flight["lng"],
            "direction": flight["dir"],
            "speed": flight["speed"],  # km/h
            "elevation": flight["alt"],  # meters
            "elevation_change": "-" if v_speed == 0 else ("C" if v_speed > 0 else "D"),
            "waypoints": None,
            "last_update": convert_unix_timestamp_to_datetime_str(flight["updated"]),
        }


def convert_unix_timestamp_to_datetime_str(unix_timestamp: int) -> str:
    dt = datetime.fromtimestamp(unix_timestamp)

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def load_existing_flight_data(path: str) -> dict:
    with open(path, "r") as file:
        return json.load(file)


def sort_results(data: List[dict]) -> List[dict]:
    """Sort data flight results considering if it's possible transit, angular separation, ETA and time."""

    def _custom_sort(a: dict) -> tuple:
        return (a.get("angular_separation", 1000), a.get("eta", 999))

    return sorted(data, key=_custom_sort)


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
