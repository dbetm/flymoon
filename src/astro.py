from datetime import datetime

from src.constants import ASTRO_EPHEMERIS, EARTH_TIMESCALE


class CelestialObject:

    def __init__(self, name: str, observer_position):
        self.name = name
        self.altitude = None
        self.azimuthal = None
        self.observer_position = observer_position
        self.data_obj = ASTRO_EPHEMERIS[name]

    def update_position(self, ref_datetime: datetime):
        """Get the position of celestial object given the datetime reference from the
        current observer position.

        Parameters
        ----------
        ref_datetime : datetime
            Python datetime object to get the future or past position of the celestial object,
        """
        time_ = EARTH_TIMESCALE.from_datetime(ref_datetime)
        astrometric = self.observer_position.at(time_).observe(self.data_obj)
        alt, az, distance = astrometric.apparent().altaz()

        self.altitude = alt
        self.azimuthal = az

    def __str__(self):
        return f"{self.name=}, {self.altitude=}, {self.azimuthal=}"
