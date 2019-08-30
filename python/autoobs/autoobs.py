#!/usr/bin/env python
"""Start or stop automatic observing

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory

"""

from PML.core import PML_Connection
from time import sleep
from sys import argv

def print_help():
    print "Usage: autoobs [go|stop]"
    exit()

if len(argv) != 2:
    print_help()

action = argv[1]

if action == 'go':
    autoobs = PML_Connection('SISPI','AUTOOBS')
    exposure_queue = PML_Connection('OCS','OCS')
    exposure_queue('configure','')

    # You seem to need to wait a bit here
    sleep(5)            
    exposure_queue('go','')            
    autoobs('enable','')
    exit()

if action == 'stop':
    autoobs = PML_Connection('SISPI','AUTOOBS')
    exposure_queue = PML_Connection('OCS','OCS')
    autoobs('disable','')
    exposure_queue('go','stop') 
    sleep(10)
    exit()

print_help()    
