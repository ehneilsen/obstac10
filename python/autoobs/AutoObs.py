#!/usr/bin/env python
"""Drive SISPI observations by triggering obstac to fill the queue whenever the state of the queue changes

:Authors: Eric H. Neilsen, Jr.
:Organization: Fermi National Accelerator Laboratory
"""
__docformat__ = "restructuredtext en"

from time import sleep
import os
import posix
import pdb
import signal
import datetime
import time
from tempfile import mkstemp
from SISPIlib.application import Application
from threading import Event, Thread
import json
import PML
from PML.core import PML_Connection
from sve.pythonclient import SVEError, SVE, SharedVariable
import obstac.debug

WAIT_TIMEOUT = 25
EXPOSURE_START_WAIT = 5

class AutoObs(Application):
    commands = ['enable', 'disable', 'is_enabled', 'start_debug']

    def init(self):
        signal.signal(signal.SIGUSR1, self.debug_signal_handler)
        obstac.debug.set_debug(True)
        obstac.debug.set_debug_out(self.debug)

    def debug_signal_handler(self, signum, frame):
        self.start_debug()

    def start_debug(self, dummy=''):
        self.info("entering pdb")
        pdb.set_trace()

    def enable(self, dummy=''):
        self.info("Received: enable %s" % dummy)
        self.enabled = True
        self.sv_enabled.write(self.enabled)
        self.update_event.set()

    def disable(self, dummy=''):
        self.info("Received: disable %s" % dummy)
        self.enabled = False
        self.sv_enabled.write(self.enabled)

    def is_enabled(self, dummy=''):
        return self.enabled

    def trigger_update(self, ocs_queue):
        self.debug("Update trigger pulled")
        ocs_queue.read()
        self.update_event.set()

    def update_queue(self):
        
        # Set up in and out files
        config = {'obstac_inbox': '/tmp/obstac_inbox.json',
                  'obstac_current_queue': '/tmp/obstac_current_queue.json',
                  'obstac_previous_queue': '/tmp/obstac_previous_queue.json',
                  'obstac_inprogress': '/tmp/obstac_inprogress.json',
                  'obstac_loaded': '/tmp',
                  'obstac_fifo': '/tmp/obstac_fifo.json'}
        for key in config:
            if key in self.config:
                config[key] = self.config[key]
                self.info("config[%s] = %s" %
                          (key, config[key]))
            else:
                self.warn("%s not found in config file, using default of %s" %
                          (key, config[key]))

        # Make sure the fifo file exists, and open it
        if not os.path.exists(config['obstac_fifo']):
            os.mkfifo(config['obstac_fifo'])
        obstac_fifo = posix.open(config['obstac_fifo'], posix.O_RDWR | posix.O_NONBLOCK)
        
        # Prepare OCS connection
        
        ocs_established = False
        ocs_attempts = 0
        max_ocs_attempts = 10

        while not ocs_established and (ocs_attempts < max_ocs_attempts):
            try:
                ocs = PML_Connection('OCS', 'OCS')
                ocs_established = True
                self.info("Established connection to OCS queue manager")
            except:
                self.warn("Failed to establish connection to OCS queue manager")
                ocs_established = False
                ocs_attempts = ocs_attempts + 1
                sleep(2)

        inprogress_established = False
        inprogress_attempts = 0
        max_inprogress_attempts = 10

        # Subscribe to inprogress shared variable

        sve = SVE()
        while not inprogress_established and (inprogress_attempts < max_inprogress_attempts):
            try:
                inprogress_sv = SharedVariable("OCS", "INPROGRESS", sve)
                ocs_queue_sv = SharedVariable("OCS", "EXPOSUREQUEUE", sve)
                inprogress_established = True
                self.info("Connected to INPROGRESS and EXPOSUREQUEUE shared variables")
            except:
                self.warn("Failed to subscribe to INPROGRESS and EXPOSUREQUEUE shared variables")
                inprogress_established = False
                inprogress_attempts = inprogress_attempts + 1
                sleep(2)


        # Infinite loop up update
        while True:
            self.debug("Waiting for event")
            self.update_event.wait()
            self.debug("Waiting %s seconds" % EXPOSURE_START_WAIT)
            sleep(EXPOSURE_START_WAIT)
            self.debug("Clearing event")
            self.update_event.clear()
            start_time = time.time()
            try:
                self.debug("Retrieving and writing EXPOSUREQUEUE")
                try:
                    ocs_queue = ocs_queue_sv.read()
                except SVEError as e:
                    try:
                        ocs_queue_sv.subscribe()
                        self.info("Subscribed to EXPOSUREQUEUE shared variable")
                        ocs_queue = ocs_queue_sv.read()
                    except Exception as e:
                        self.error("Could not get queue contents: " + str(e))
                        ocs_queue = None

                # Make sure the write is atomic, and that we store the
                # most recent So, start by writing into a temp file,
                # then move files back in time, making the temp file
                # current.
                if ocs_queue is not None:
                    queue_fp, queue_fname = mkstemp(
                        dir=os.path.dirname(config['obstac_current_queue']))
                    os.close(queue_fp)
                    with open(queue_fname, 'w') as fp:
                        json.dump(ocs_queue, fp, indent=4)
                    os.chmod(queue_fname, 0o666)
                    try:
                        os.remove(config['obstac_previous_queue'])
                    except OSError:
                        pass
                    try:
                        os.rename(config['obstac_current_queue'],
                                  config['obstac_previous_queue'])
                    except OSError:
                        pass
                    
                    os.rename(queue_fname, config['obstac_current_queue'])
                
                self.info("Retrieving and writing exposures in progress")
                try:
                    in_progress = inprogress_sv.read()
                except SVEError as e:
                    try:
                        inprogress_sv.subscribe()
                        self.info("Subscribed to INPROGRESS shared variable")
                        in_progress = inprogress_sv.read()
                    except Exception as e:
                        self.error("Could not get exposures in progress: " + str(e))
                        in_progress = None

                # Make sure the write is atomic
                if in_progress is not None:
                    inprogress_fp, inprogress_fname = mkstemp(
                        dir=os.path.dirname(config['obstac_inprogress']))
                    os.close(inprogress_fp)
                    with open(inprogress_fname, 'w') as fp:
                        json.dump(in_progress, fp, indent=4)
                    os.chmod(inprogress_fname, 0o666)
                    try:
                        os.remove(config['obstac_inprogress'])
                    except OSError:
                        pass
                    os.rename(inprogress_fname, config['obstac_inprogress'])

                # To avoid filling up the FIFO buffer if there is nothing
                # reading it, read from the FIFO until all lines are gone
                # before writing a new line.
                time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                read_bytes = None
                while read_bytes is None or read_bytes > 0:
                    try:
                        read_line = os.read(obstac_fifo, len(time_str)+1)
                    except OSError:
                        read_line = ""
                    read_bytes = len(read_line)
                    
                if self.enabled:
                    self.info("Sending the timestamp to the FIFO to the scheduler")
                    os.write(obstac_fifo, time_str + "\n")
                    self.info("Waiting for scheduler to provide a queue")
                    while not os.path.exists(config['obstac_inbox']):
                        if (time.time() - start_time) > WAIT_TIMEOUT:
                            break
                        self.debug("Still waiting...")
                        sleep(1)

                    if os.path.exists(config['obstac_inbox']):
                        # If the file is older than the trigger, do not load it, but keep waiting
                        while start_time > os.path.getmtime(config['obstac_inbox']):
                            if (time.time() - start_time) > WAIT_TIMEOUT:
                                break
                            self.debug("Still waiting...")
                            sleep(1)
                        
                    # If we reached here because we timed out, do not attempt
                    # to process the file that doesn't exist
                    if not os.path.exists(config['obstac_inbox']):
                        self.info("No new scheduler script provided")
                        continue
                    else:
                        self.info("Script from scheduler found!")

                    # Move the provided file into the archive of
                    # already loaded files, then send the path of
                    # the archived location to OCS, so we are not
                    # in danger of OCS trying to read the file
                    # after we've moved it.
                    time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    loaded_fname = os.path.join(config['obstac_loaded'],
                                                'queue_%s.json' % time_str)
                    os.rename(config['obstac_inbox'], loaded_fname)
                    try:
                        with open(loaded_fname, 'r') as fp:
                            sispi_queue = json.load(fp)
                    except:
                        self.error("Could not read scheduler queue file")
                        sispi_queue = []
                        # It's SISPI's job to complain about it
                        ocs('loadq', loaded_fname)
                            
                    if len(sispi_queue) > 0:
                        self.info("Asking SISPI to load %s" % loaded_fname)
                        ocs('loadq', loaded_fname)

                self.info("update succeeded")
            except Exception, msg:
                self.warn("update failed: %s" % msg)
                raise
                self.update_event.set()
                sleep(1)

    def main(self):
        self.info("The automated observing driver is starting up now.")
        self.info("Process id: %d" % os.getpid())
        
        self.sv_enabled = self.shared_variable("ENABLED")
        self.sv_enabled.publish()

        self.enabled = False
        self.sv_enabled.write(self.enabled)

        callback_established = False
        callback_attempts = 0
        max_callback_attempts = 10
        self.update_event = Event()

        
        self.update_thread = Thread(name="UpdateQueue",target=self.update_queue)
        self.update_thread.daemon = True
        self.update_thread.start()

        while not callback_established and (callback_attempts < max_callback_attempts):
            try:
                ocs_queue = self.shared_variable('EXPOSUREQUEUE','OCS')
                ocs_queue.subscribe(callback=self.trigger_update)
                callback_established = True
                self.info("Established callback to OCS queue")
            except:
                self.warn("Failed to establish callback to OCS queue")
                callback_established = False
                callback_attempts = callback_attempts + 1
                sleep(2)



        self.info("Waiting for shutdown event.")
        self.wait_for_shutdown()
        self.info("The automated observing driver shut down.")
        exit(0)

if __name__ == "__main__":
    AutoObs().run()

