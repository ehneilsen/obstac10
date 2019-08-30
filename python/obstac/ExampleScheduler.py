#!/usr/bin/env python
"""Trivial example scheduler

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory
"""
__docformat__ = "restructuredtext en"


import json
import os
import posix
import datetime
import logging
import json
import time
import datetime

from collections import OrderedDict
from argparse import ArgumentParser
from ConfigParser import ConfigParser

from obstac import Scheduler

class ExampleScheduler(Scheduler):

    def make_script(self):
        # This method get called when autoobs is first enabled, and when
        # time the SISPI OCS queue is changed while the autoobs is still
        # enabled
        with open(self.queue_fname, 'r') as fp:
            sispi_queue = json.load(fp)

        logging.debug("Found %d exposure(s) on the SISPI/OCS queue." % len(sispi_queue))
            
        with open(self.in_progress_fname, 'r') as fp:
            in_progress = json.load(fp)

        # If we don't want to add anything, return an empty list
        if len(sispi_queue) >= self.min_queue_len:
            logging.info("Queue is already %d exposures long, not adding anything"
                         % len(sispi_queue))
            # Add an empty script so autoobs knows the scheduler "passed"
            with open(self.output_fname, 'w') as fp:
                json.dump([], fp, indent=4)
            os.chmod(self.output_fname, 0o666)
            return

        try:
            self.expid += 1
        except:
            self.expid = 1
        
        # Follow Meeus chapter 12 to calculate LST
        mjd = 40587+time.time()/86400
        century = (mjd - 51544.5)/36525
        gmst = 280.46061837 + 360.98564736629*(mjd-51544.5) + 0.000387933*century*century - century*century*century/38710000
        lst = (gmst + self.longitude) % 360

        exposure = OrderedDict([
            ("expType", "object"), 
            ("object", "test_%d" % self.expid), 
            ("seqid", "Sequence of 1 test exposure"), 
            ("exptime", 90), 
            ("wait", "False"), 
            ("count", 1), 
            ("filter", "z"), 
            ("program", "test"), 
            ("RA", lst), 
            ("dec", self.latitude)])

        # List of exposures to add to the queue
        # In this case, it is a list of just one exposure, but
        # it can be any number.
        exposures = [exposure]
        
        with open(self.output_fname, 'w') as fp:
            logging.info("Sending %d exposure(s) to the SISPI/OCS queue." % len(exposures))
            json.dump(exposures, fp, indent=4)
        os.chmod(self.output_fname, 0o666)

            
if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(message)s',
                        level=logging.DEBUG)

    parser = ArgumentParser('Simple sample scheduler')
    parser.add_argument("config", help="the configuration file")
    args = parser.parse_args()
    scheduler = ExampleScheduler(args.config)
    scheduler.min_queue_len = 5
    scheduler()
