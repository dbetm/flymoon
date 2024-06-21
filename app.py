import os

from src.astro import CelestialObject
from src.flight_data import get_flight_data
from src.position import (
    geographic_to_altaz, get_my_pos, load_astro_position_relative_to_me, predict_position
)
from src.utils import get_relevant_fligh_data

import numpy as np
from dotenv import load_dotenv
from skyfield.api import Topos, load


# SETUP 
load_dotenv()


def check_intersection(
    flight: dict,
    window_time: list,
    my_position: Topos,
    target: CelestialObject,
    ts,
    earth_ref,
    threshold_alt: float = 10,
    threshold_az: float = 10
):
    min_diff_combined = 200
    ans = None

    for minute in window_time:
        # get future position
        future_lat, future_lon = predict_position(
            lat=flight["latitude"],
            lon=flight["longitude"],
            speed=flight["speed"],
            direction=flight["direction"],
            minutes=minute,
        )

        # Convertir la posición futura a coordenadas altazimutales
        future_alt, future_az = geographic_to_altaz(
            future_lat, future_lon, flight["elevation"], earth_ref, my_position, ts
        )

        alt_diff = abs(future_alt - target.altitude.degrees)
        az_diff = abs(future_az - target.azimuthal.degrees)

        if alt_diff < threshold_alt and az_diff < threshold_az:

            if (alt_diff + az_diff) < min_diff_combined:
                ans = str({
                    "id": flight['name'],
                    "t": float(minute),
                    "orig": flight["origin"],
                    "dest": flight["destination"],
                    # "name_target": target.name,
                    "target_alt": float(target.altitude.degrees),
                    "plane_alt": float(future_alt),
                    "target_az": float(target.azimuthal.degrees),
                    "plane_az": float(future_az), 
                    "alt_diff": float(alt_diff),
                    "az_diff": float(az_diff),
                })

                min_diff_combined = alt_diff + az_diff

    if ans:
        return ans

    return str(
        {
            "id": flight['name'],
            "origin": flight["origin"],
            "dest": flight["destination"],
        }
    )



def run():
    api_key = os.getenv('AEROAPI_API_KEY')
    personal_latitude = float(os.getenv('PERSONAL_LATITUDE'))
    personal_longitude = float(os.getenv('PERSONAL_LONGITUDE'))

    print(api_key, personal_latitude, personal_longitude)

    raw_flight_data = get_flight_data(
        21.8432,
        -104.4433,
        23.9974,
        -101.9982,
        "https://aeroapi.flightaware.com/aeroapi/flights/search",
        api_key,
    )

    flight_data = list()

    for flight in raw_flight_data["flights"]:
        try:
            flight_data.append(get_relevant_fligh_data(flight))
        except:
            print("error parsing data")
        

    print(f"theres is {len(flight_data)} flights near")

    e = load("de421.bsp")
    earth = e["earth"]
    ts = load.timescale()

    my_pos = get_my_pos(
        lat=personal_latitude,
        lon=personal_longitude,
        elevation=2243,
        base_ref=earth,
    )

    top_min = 15
    second_interval = 1

    window_time = np.linspace(0, top_min, top_min * (60 // second_interval)) # each second
    print("number of times to check for each flight:", len(window_time))

    obj = load_astro_position_relative_to_me(my_pos, "moon", ts)

    response = list()

    for flight in flight_data:
        response.append(
            check_intersection(
                flight, window_time, my_pos, obj, ts, earth, threshold_alt=20, threshold_az=20
            )
        )

        print(response[-1])

    return response


if __name__ == "__main__":
    run()