"""Model the instrument (telescope and camera)

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory
"""
__docformat__ = "restructuredtext en"

from math import *
from ConfigParser import NoOptionError, NoSectionError
from collections import namedtuple

Coords = namedtuple('Coords',['RA','dec'])
HourAngleLimit = namedtuple('HourAngleLimit',['dec','east','west','window'])

class Instrument(object): 
    """Model the instrument (telescope and camera)

    """

    longitude = -70.815
    latitude = -30.16527778
    readout_time = 26
    short_slew_zp = 23.1
    short_slew_slope = 1.7
    long_slew_zp = 32.2
    long_slew_slope = 2.2
    longest_short_slew = 5
    serial = False
    overhead = 0

    def __init__(self, coords=None):
        if coords:
            self.coords = coords

    @property
    def coords(self):
        """Return the coordinates of the (virtual) telescope (does not actually move any telescope)

        :Return: a tuple with the RA and dec

        >>> from obstac import TestEnv
        >>> a = Instrument()
        >>> a.coords = 90, 180
        >>> print a.coords
        Coords(RA=90.0, dec=180.0)
        """
        return Coords((self.ra*180.0/pi), (self.dec*180.0/pi))

    @coords.setter
    def coords(self, coords):
        """Set the coordinates of the (virtual) telescope (does not actually move any telescope)

        :Parameters:
            - `coords`: a tuple with the RA and dec

        >>> from obstac import TestEnv
        >>> a = Instrument()
        >>> a.coords = 90, 180
        >>> # internal representation is in radians:
        >>> print "%2.2f, %2.2f" %(a.ra, a.dec)
        1.57, 3.14
        """
        ra, dec = coords
        self.ra = radians(ra)
        self.dec = radians(dec)


    def slew_time(self, ra, dec):
        """Calculate the time to slew to a given location on the sky

        :Parameters:
            - `ra`: the destination RA
            - `dec`: the destination declination

        :Returns:
            the time to slew, in seconds

        >>> from obstac import TestEnv
        >>> t = Instrument()
        >>> t.coords = 30,-45
        >>> t.slew_time(30, -44)
        20
        >>> t.slew_time(120, -45)
        50
        >>> t.slew_time(30, -30)
        41
        """
        
        ra = radians(ra)
        dec = radians(dec)

        # Following slatec
        v1 = (cos(self.ra)*cos(self.dec),
              sin(self.ra)*cos(self.dec),
              sin(self.dec))
        v2 = (cos(ra)*cos(dec),
              sin(ra)*cos(dec),
              sin(dec))
        s2 = 0.0;
        for x1, x2 in zip(v1,v2):
            d = x1-x2
            s2 += d * d;
        s2 = s2/4.0;
        c2 = 1.0-s2
        angle = degrees(2.0 * atan2( sqrt(s2), sqrt(max(0.0,c2)) ))

        # Using fit to Feb 2013 data

        if angle > self.longest_short_slew:
            t = int(round(self.long_slew_zp + angle*self.long_slew_slope))
        else:
            t = int(round(self.short_slew_zp + angle*self.short_slew_slope))

        return t

    def obs_duration(self, ra, dec, exposure_time, repetitions = 1):
        """Calculate the duration of an exposure

        :Parameters:
            - `ra`: the RA of the observation
            - `dec`: the Declination of the observation
            - `exposure_time`: the exposure time (per exposure) (in seconds)
            - `repetitions`: number of exposures (defualts to 1)

        :Returns:
            the duration of an exposure, in seconds

        >>> from obstac import TestEnv
        >>> start_ra, start_dec= 12.0, 0.0
        >>>
        >>> a = Instrument()
        >>> a.coords = start_ra, start_dec
        >>> 
        >>> # take a look at the readout time (read from the obstac config file's readout_time)
        >>> print a.readout_time
        20
        >>>
        >>> #look at some field 3 degrees away, which we know has a slew time of 20s
        >>> obs_ra, obs_dec = 12, -3
        >>> exptime = 120
        >>> repetitions = 1
        >>> print a.slew_time(obs_ra, obs_dec), repetitions, a.readout_time, exptime
        20 1 20 120
        >>> print 20 + 120
        140
        >>> a.obs_duration(obs_ra, obs_dec, exptime, repetitions)
        140
        >>>
        """
        if self.serial:
            duration = self.slew_time(ra, dec) \
                + repetitions*(exposure_time+self.readout_time) \
                + self.overhead
        else:
            duration = max(self.slew_time(ra, dec), self.readout_time) \
                + (repetitions-1)*self.readout_time \
                + repetitions*exposure_time \
                + self.overhead

        return duration

