import math
import random
from typing import List

from src.constants import EARTH_RADIOUS



def generate_test_flightaware_data(observer_position, target_names: List[str], target_coordinates: dict) -> dict:
    """Generate flight data, in which the last position is favorable to transits over the targets (Moon / Sun).

    + observer position is an object <class 'skyfield.vectorlib.VectorSum'>, you can get the latitude, longitude and elevation as follow:
        -> float(observer_position.target.latitude.degrees)
    + target_names could be moon and/or sun
    + target_coordinates is a dictionary, example: "moon": {
        "altitude": 42.2,
        "azimuthal": 160.3,
    }
    """
    num_targets = len(target_names)
    assert num_targets  > 0, "you should provide at least one target"

    obs_lat = float(observer_position.target.latitude.degrees)
    obs_lon = float(observer_position.target.longitude.degrees)

    # Use the first available target to compute flight positions
    target = target_names[0] if num_targets == 1 else target_names[random.randint(0, num_targets - 1)]

    target_alt = target_coordinates[target]["altitude"]
    target_az  = target_coordinates[target]["azimuthal"]

    def get_geo_pos_from_altaz(apparent_alt_deg: float, apparent_az_deg: float, elevation_m: float):
        """Return the lat/lon at which an aircraft flying at elevation_m
        would appear at (apparent_alt_deg, apparent_az_deg) from the observer.

        Uses the flat-Earth approximation d_horiz = h / tan(alt), which is
        accurate to <0.2° for the distances involved (~5–40 km).
        """
        alt_rad = math.radians(max(apparent_alt_deg, 1.0))  # guard tan(0)
        d_horiz_km = (elevation_m / math.tan(alt_rad)) / 1000
        d_rad = d_horiz_km / EARTH_RADIOUS

        az_rad = math.radians(apparent_az_deg)
        lat1 = math.radians(obs_lat)
        lon1 = math.radians(obs_lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(az_rad)
        )
        lon2 = lon1 + math.atan2(
            math.sin(az_rad) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    def pos_offset(lat_deg: float, lon_deg: float, bearing_deg: float, distance_km: float):
        """Move a point (lat_deg, lon_deg) by distance_km along bearing_deg (direction)"""
        d_rad = distance_km / EARTH_RADIOUS
        brng = math.radians(bearing_deg % 360)
        lat1 = math.radians(lat_deg)
        lon1 = math.radians(lon_deg)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    # The closest-approach point is placed at (target_alt + Δalt, target_az + Δaz).
    configs = [
        # id       origin         destination    type   elev. Δalt.  Δaz.  eta
        # ("AMX190", "Mexico City", "Guadalajara", "B738", 350,  1.0,  1.0, 3.0),   # HIGH   sep   <=2°
        # ("VOI282", "Monterrey",   "Cancun",      "A320", 330,  2.0,  1.5, 5.0),   # MEDIUM sep   <=4°
        # ("VIV415", "Guadalajara", "Tijuana",     "A320", 310,  2.5,  2.5, 4.0),   # MEDIUM sep   <=4°
        # ("TAR031", "Mexico City", "Merida",      "B737", 280,  5.0,  4.0, 7.0),   # LOW    sep   <=12°
        # ("AMX541", "Hermosillo",  "Mexico City", "B39M", 250,  0.0, 90.0, 6.0),   # UNLIKELY sep >12°
        ("AMX190", "Mexico City", "Guadalajara", "B738", 350,  0.5,  1.0, 3.0),   # HIGH     sep <= 2°
        ("VOI282", "Monterrey",   "Cancun",      "A320", 330,  2.5,  1.0, 5.0),   # MEDIUM   sep <= 4° (min sep 2.5°)
        ("VIV415", "Guadalajara", "Tijuana",     "A320", 310,  3.0,  1.5, 4.0),   # MEDIUM   sep <= 4° (min sep 3.0°)
        ("TAR031", "Mexico City", "Merida",      "B737", 280,  6.0,  4.0, 7.0),   # LOW      sep <= 12° (min sep 6.0°)
        ("AMX541", "Hermosillo",  "Mexico City", "B39M", 250, 15.0, 10.0, 6.0),   # UNLIKELY sep > 12° (min sep 15.0°)
    ]

    speed_knots = 465
    speed_kmh = speed_knots * 1.852

    flights = []
    for id, origin, dest, aircraft_type, alt_hundreds_ft, delta_alt, delta_az, eta_min in configs:
        elevation_m = alt_hundreds_ft * 100 * 0.3048
        desired_alt = min(target_alt + delta_alt, 90.0)   # cap well below zenith
        desired_az = (target_az + delta_az) % 360

        # Closest-approach point in lat/lon
        close_lat, close_lon = get_geo_pos_from_altaz(desired_alt, desired_az, elevation_m)

        # Back-project: place aircraft upstream so it reaches close_lat/lon at t=eta_min.
        # The aircraft flies toward desired_az, so it starts in the opposite direction.
        d_km = speed_kmh * eta_min / 60
        upstream_brng = (desired_az + 180) % 360
        lat, lon = pos_offset(close_lat, close_lon, upstream_brng, d_km)
        heading = int(desired_az)

        flights.append({
            "ident": id,
            "aircraft_type": aircraft_type,
            "fa_flight_id": f"{id}-demo-test",
            "origin": {"city": origin},
            "destination": {"city": dest},
            "last_position": {
                "latitude": lat,
                "longitude": lon,
                "heading": heading,
                "groundspeed": speed_knots,
                "altitude": alt_hundreds_ft,
                "altitude_change": "-",
            },
        })

    return {"flights": flights}




def generate_test_flightaware_data2(observer_position, target_names: List[str], target_coordinates: dict) -> dict:
    EARTH_RADIUS = 6371.0 

    num_targets = len(target_names)
    assert num_targets  > 0, "you should provide at least one target"

    obs_lat = float(observer_position.target.latitude.degrees)
    obs_lon = float(observer_position.target.longitude.degrees)

    target = target_names[0] if num_targets == 1 else target_names[random.randint(0, num_targets - 1)]

    target_alt = target_coordinates[target]["altitude"]
    target_az  = target_coordinates[target]["azimuthal"]

    def get_geo_pos_from_altaz(apparent_alt_deg: float, apparent_az_deg: float, elevation_m: float):
        alt_rad = math.radians(max(apparent_alt_deg, 1.0))
        d_horiz_km = (elevation_m / math.tan(alt_rad)) / 1000
        d_rad = d_horiz_km / EARTH_RADIUS

        az_rad = math.radians(apparent_az_deg)
        lat1 = math.radians(obs_lat)
        lon1 = math.radians(obs_lon)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(az_rad)
        )
        lon2 = lon1 + math.atan2(
            math.sin(az_rad) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    def pos_offset(lat_deg: float, lon_deg: float, bearing_deg: float, distance_km: float):
        d_rad = distance_km / EARTH_RADIUS
        brng = math.radians(bearing_deg % 360)
        lat1 = math.radians(lat_deg)
        lon1 = math.radians(lon_deg)

        lat2 = math.asin(
            math.sin(lat1) * math.cos(d_rad)
            + math.cos(lat1) * math.sin(d_rad) * math.cos(brng)
        )
        lon2 = lon1 + math.atan2(
            math.sin(brng) * math.sin(d_rad) * math.cos(lat1),
            math.cos(d_rad) - math.sin(lat1) * math.sin(lat2),
        )

        return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)

    # 1 HIGH, 2 MEDIUM, 1 LOW, 1 UNLIKELY
    # Al volar tangencialmente, la separación mínima (target_sep) será EXACTA a lo largo de toda su trayectoria.
    configs = [
        # id       origin         destination    type   elev. target_sep eta
        ("AMX190", "Mexico City", "Guadalajara", "B738", 350,   1.5,     3.0),   # HIGH     (<= 2°)
        ("VOI282", "Monterrey",   "Cancun",      "A320", 330,   3.0,     5.0),   # MEDIUM   (<= 4°)
        ("VIV415", "Guadalajara", "Tijuana",     "A320", 310,   3.8,     4.0),   # MEDIUM   (<= 4°)
        ("TAR031", "Mexico City", "Merida",      "B737", 280,   8.0,     7.0),   # LOW      (<= 12°)
        ("AMX541", "Hermosillo",  "Mexico City", "B39M", 250,  15.0,     6.0),   # UNLIKELY (> 12°)
    ]

    speed_knots = 480
    speed_kmh = speed_knots * 1.852

    flights = []
    for id, origin, dest, aircraft_type, alt_hundreds_ft, target_sep, eta_min in configs:
        elevation_m = alt_hundreds_ft * 100 * 0.3048
        
        # Prevenimos cruzar el cenit, si la altitud sube de 85, le restamos la separación en vez de sumarla
        if target_alt + target_sep < 85.0:
            desired_alt = target_alt + target_sep
        else:
            desired_alt = target_alt - target_sep
            
        desired_az = target_az

        # Posición de máximo acercamiento
        close_lat, close_lon = get_geo_pos_from_altaz(desired_alt, desired_az, elevation_m)

        # Hacemos que el avión vuele TANGENCIALMENTE (perpendicular al azimut del target).
        # Esto garantiza que al extrapolar, nunca se acerque más de lo configurado en 'target_sep'.
        heading = int((desired_az + 90) % 360)

        # Retrocedemos la posición del avión sobre su propia línea de vuelo invertida
        d_km = speed_kmh * eta_min / 60
        upstream_brng = (heading + 180) % 360
        lat, lon = pos_offset(close_lat, close_lon, upstream_brng, d_km)

        flights.append({
            "ident": id,
            "aircraft_type": aircraft_type,
            "fa_flight_id": f"{id}-demo-test",
            "origin": {"city": origin},
            "destination": {"city": dest},
            "last_position": {
                "latitude": lat,
                "longitude": lon,
                "heading": heading,
                "groundspeed": speed_knots,
                "altitude": alt_hundreds_ft,
                "altitude_change": "-",
            },
        })

    return {"flights": flights}