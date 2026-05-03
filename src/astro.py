from datetime import datetime

from src.constants import ASTRO_EPHEMERIS, EARTH_TIMESCALE


class CelestialObject:

    def __init__(self, name: str, observer_position):
        self.name = name
        self.altitude = None
        self.azimuthal = None
        self.observer_position = observer_position
        self.data_obj = ASTRO_EPHEMERIS[name]
        self._position_cache: dict = {}

    def update_position(self, ref_datetime: datetime, use_cache: bool = False):
        """Get the position of celestial object given the datetime reference from the
        current observer position.

        Results are cached so repeated calls for the same time (e.g. across
        multiple aircraft in the same transit window) skip the skyfield computation.

        Parameters
        ----------
        ref_datetime : datetime
            Python datetime object to get the future or past position of the celestial object.
        use_cache : bool
            Check if the position was before calculeted for the same ref_datetime, then cache the coordinates
        """
        if use_cache and ref_datetime in self._position_cache:
            self.altitude, self.azimuthal = self._position_cache[ref_datetime]
            return

        time_ = EARTH_TIMESCALE.from_datetime(ref_datetime)
        astrometric = self.observer_position.at(time_).observe(self.data_obj)
        alt, az, distance = astrometric.apparent().altaz()

        self.altitude = alt
        self.azimuthal = az
        self._position_cache[ref_datetime] = (alt, az)

    def __str__(self):
        return f"{self.name=}, {self.altitude=}, {self.azimuthal=}"

    def get_coordinates(self, precision: int = 2) -> dict:
        return {
            "altitude": round(self.altitude.degrees, precision),
            "azimuthal": round(self.azimuthal.degrees, precision),
        }
