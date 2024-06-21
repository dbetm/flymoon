from typing import List

import requests


def get_flight_data(
    min_lat: float,
    min_long: float,
    max_lat: float,
    max_long: float,
    url_: str,
    api_key: str = ""
) -> List[dict]:
    
    # params = {
    #     "latlong": f"{min_lat} {min_long} {max_lat} {max_long}"
    # }
    headers = {
        "Accept": "application/json; charset=UTF-8",
        "x-apikey": api_key,
    }

    url = f"{url_}?query=-latlong+%22{min_lat}+{min_long}+{max_lat}+{max_long}%22&max_pages=1"
    
    # url = "https://aeroapi.flightaware.com/aeroapi/flights/search?query=-latlong+%2221.305695+-104.458904+23.925834+-101.365481%22&max_pages=1"
    
    response = requests.get(
        url=url, headers=headers
    )

    if response.status_code == 200:
        # If successful, print the response JSON
        print("OK")
        return response.json()
    else:
        # If not successful, print the status code and response text
        print(f"Error: {response.status_code}")
        print(response.text)