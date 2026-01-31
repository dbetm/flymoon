from datetime import datetime

from skyfield.units import Angle

from src.constants import ASTRO_EPHEMERIS, EARTH_TIMESCALE


class CelestialObject:

    def __init__(self, name: str, observer_position, test_overrides: dict = None):
        self.name = name
        self.altitude = None
        self.azimuthal = None
        self.observer_position = observer_position
        self.data_obj = ASTRO_EPHEMERIS[name]
        self.test_overrides = test_overrides  # {"altitude": deg, "azimuth": deg}

    def update_position(self, ref_datetime: datetime):
        """Get the position of celestial object given the datetime reference from the
        current observer position.

        Parameters
        ----------
        ref_datetime : datetime
            Python datetime object to get the future or past position of the celestial object,
        """
        if self.test_overrides:
            # Use fake test values instead of real calculations
            self.altitude = Angle(degrees=self.test_overrides.get("altitude", 60))
            self.azimuthal = Angle(degrees=self.test_overrides.get("azimuth", 180))
            return

        time_ = EARTH_TIMESCALE.from_datetime(ref_datetime)
        astrometric = self.observer_position.at(time_).observe(self.data_obj)
        alt, az, distance = astrometric.apparent().altaz()

        self.altitude = alt
        self.azimuthal = az

    def __str__(self):
        return f"{self.name=}, {self.altitude=}, {self.azimuthal=}"

    def get_coordinates(self, precision: int = 2) -> dict:
        return {
            "altitude": round(self.altitude.degrees, precision),
            "azimuthal": round(self.azimuthal.degrees, precision),
        }
