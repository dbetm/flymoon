def get_relevant_fligh_data(flight_data: dict):
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