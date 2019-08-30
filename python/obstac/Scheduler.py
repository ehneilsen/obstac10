#!/usr/bin/env python
"""Base class for schedulers that work through the AUTOOBS named pipe mechanism.

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory
"""
__docformat__ = "restructuredtext en"

import datetime
import logging
from abc import ABCMeta, abstractmethod
from ConfigParser import ConfigParser

logging.basicConfig(format='%(asctime)s %(message)s',
                    level=logging.DEBUG)

class Scheduler(object):
    __metaclass__ = ABCMeta

    def __init__(self, config_fname):
        self.configure(config_fname)
        

    def configure(self, config_fname):
        config = ConfigParser() 
        config.read(config_fname)

        self.longitude = config.getfloat('observatory', 'longitude')
        self.latitude = config.getfloat('observatory', 'latitude')

        self.stale_time_delta = datetime.timedelta(0, config.getfloat('timeouts', 'fifo'))
        
        self.output_fname = config.get('paths', 'outbox')
        self.queue_fname = config.get('paths', 'current_queue')
        self.previous_queue_fname = config.get('paths', 'previous_queue')
        self.in_progress_fname = config.get('paths', 'inprogress')
        self.fifo_fname = config.get('paths', 'fifo')  


    @abstractmethod
    def make_script(self):
        pass

    
    def __call__(self):
        logging.info("Scheduler starting")
        while True:
            # open block until something is sent to the fifo
            # (should by sent by obstac)
            logging.info("Waiting for autoobs")
            with open(self.fifo_fname, 'r') as fp:
                time_string = fp.readline().strip()

            logging.info("Triggered by autoobs")

            if len(time_string) == 0:
                continue
            
            try:
                queue_time = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                logging.info("Invalid marker in FIFO: %s" % time_string)
                continue

            marker_age =  datetime.datetime.now()-queue_time
            if marker_age > self.stale_time_delta:
                logging.info("FIFO has time %s, more than %s ago; not calling scheduler" %
                            (time_string, str(self.stale_time_delta)))
                continue

            new_sispi_script = self.make_script()
