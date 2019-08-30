#!/usr/bin/env python
"""Load the obstac package

The primary duty of the code in this file proper is to load the configuration data
and configure the logger.

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory
"""
__docformat__ = "restructuredtext en"

import numpy

from ConfigParser import SafeConfigParser
import os
import logging
import logging.config
from pdb import set_trace
from signal import signal, SIGUSR1

from Scheduler import Scheduler
from Instrument import Instrument


# When a SIGUSR1 signal is received, enter the debugger
def enter_debugger(signum,frame):
    set_trace()

signal(SIGUSR1,enter_debugger)

# Initialize logging
logger = logging.getLogger("obstac")

