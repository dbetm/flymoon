class CelestialObject:

    def __init__(self, name, alt, az):
        self.name = name
        self.altitude = alt
        self.azimuthal = az

    def __str__(self):
        return f"{self.name=}, {self.altitude=}, {self.azimuthal=}"