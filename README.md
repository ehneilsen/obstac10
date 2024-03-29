obstac version 10
=================

`obstac` version 10 provides an interface by which exposure schedulers
written by "visitor" observers using DECam can automate the addition
of exposures to the SISPI observing queue. `obstac 10` has a
significantly reduced scope relative to previous versions: earlier
versions incorporated the Dark Energy Survey scheduler itself, while
version 10 merely provides a way for external schedulers to interact
with SISPI.

Sequence of events
==================

`obstac` is part of SISPI, and started as the `AUTOOBS` SISPI "role."
It writes data needed by a schuduler to files, sends a trigger to a
named pipe, and loads SISPI scripts produced by a scheduler onto the
SISPI queue: in version 10, an external scheduling script does the
actual work of creating SISPI scripts

The sequence of events for using `obstac` 10 is as follows:

1. Telescope operaters start SISPI, which (if configured -- see below)
will start the `AUTOOBS` role.

2. On starting, `AUTOOBS` opens a named pipe, whose path is defined by
the `obstac_fifo` parameter in the SISPI configuration file.

3. The visiting observer(s) start their scheduler.

4. The scheduler opens the named pipe, and performs a (blocking) read.

5. Every time either the queue changes or `autoobs` is enabled in the
SISPI interface:

5.a. `AUTOOBS` copies the `obstac_current_queue` file (if any) over the
`obstac_previous_queue` file.

5.b. `AUTOOBS` writes the current contents of the SISPI/OCS queue into
the `obstac_current_queue` file in a `json` format (much like that of
a SISPI script).

5.c. `AUTOOBS` writes the "in progress" exposure(s) into the
`obstac_inprogress` file.

5.d. If and only if `autoobs` is "enabled":

5.d.1 `AUTOOBS` writes a timestamp (and ISO 8601 time string) into the
named pipe

5.d.2 The "read" started in step 4 by the scheduler succeeds and
unblocks

5.d.3 The scheduler reads the various files written by `AUTOOBS`,
chooses exposures, writes a SISPI script to `obstac_inbox`, and
returns to the blocking "read" of the named pipe.

5.d.4 `AUTOOBS` moves the contents of `obstac_inbox` to a datestamped
file in `obstac_loaded`, adds it to the SISPI queue, and returns to
the start of step 5.



SISPI roles and configuration
=============================

`obstac` version 10 implements a single SISPI role: `AUTOOBS`. This
role's entry in the `SISPI` `ini` file will look something like this:

```
   [[AUTOOBS]]
    xterm = True
    xterm_args = -hold, -iconic,
    product = obstac
    keep = True
    loglevel = DEBUG
    application_name = autoobs
    dependencies = OCS
    obstac_inbox = /home/sispi/obstac/inbox/queue.json
    obstac_loaded = /home/sispi/obstac/loaded
    obstac_current_queue = /home/sispi/obstac/queue/current.json
    obstac_previous_queue = /home/sispi/obstac/queue/previous.json
    obstac_inprogress = /home/sispi/obstac/queue/inprogress.json
    obstac_fifo = /tmp/obstac_fifo.txt
```

The role-specific configuration parmeters have the following meanings:

- `obstac_inbox` :: the full path of the file into which a schedule can
  write a SISPI queue to add the contents. The parent directory must
  exist and be readable and writeable by both the `sispi` account and
  whatever account the visitor program's scheduler runs in.
  
- `obstac_loaded` :: a directory in which obstac will archive all
  scripts that it has loaded into the SISPI. This directory must
  exist, and be writeable by the `sispi` account.

- `obstac_current_queue` :: the file into which `obstac` will write
  the current contents of the queue for reading by the scheduler. The
  parent directory of this file must exist, and be writeable by the
  `sispi` account.

- `obstac_previous_queue` :: the file into which `obstac` will copy
  the previous contents of `obstac_current_queue` each time it writes
  a new one. This will be useful if the scheduler wants to determine
  what change in the queue initiated the write of the new queue. The
  parent directory of this file must exist, and be writeable by the
  `sispi` account.
  
- `obstac_inprogress` :: the file into which `obstac` will write
  limited information on the exposure(s) in progress. The parent
  directory of this file must exist, and be writeable by the `sispi`
  account.

- `obstac_fifo` :: a POSIX named pipe (fifo) into which `obstac` will
  write a time stamp each time the scheduler needs to be initiated
  (when `autoobs` is enabled, and whenever the queue changes while it
  is still enabled). The parent directory of this file must exist, and
  be writeable by the `sispi` account. If the named pipe itself does
  not exist when `autoobs` is started, ``autoobs` will create it
  itself.

An example `ini` file can be found in `$OBSTAC_DIR/samples/obstac_test.ini`.

Make sure you put the AUTOOBS role on the same node you will run the
scheduler on.

Writing a scheduler for use with `obstac`
=========================================

The `obstac` product includes an example implementation of a scheduler
that shows the necessary interaction with the `AUTOOBS` role. Three
files are of particular relevance:

- `$OBSTAC_DIR/python/obstac/Scheduler.py` defines an abstract base
  class for writinc `obstac` schedulers. It imprements two bits of
  functionality that will be needed by most schedulers: reading the
  needed file paths from a confiration file, and the loop that waits
  for the named pipe and initiates selection of exposures when
  something appears there.
- `$OBSTAC_DIR/python/obstac/ExampleScheduler.py` subclasses
  `Scheduler` with a trivial exposure selection implementation,
  demonstrating how `Scheduler` needs to be extended for use.
- `$OBSTAC_DIR/etc/example_scheduler.conf` is an example configuration
  file for `Scheduler`.

There is a symbolic link to
`$OBSTAC_DIR/python/obstac/ExampleScheduler.py` from
`$OBSTAC_DIR/bin/example_scheduler`, so the example scheduler can be
started thus:

```
setup obstac
example_scheduler $OBSTAC_DIR/etc/example_scheduler.conf
```
