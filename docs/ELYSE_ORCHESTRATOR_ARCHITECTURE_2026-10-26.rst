Two independent XP orchestrators
===============================

The applications have separate entrypoints, configuration, sessions, keys,
ownership markers, native processes and command authority. A shared source
package supplies reusable transport and lifecycle libraries; it does not make
Acquisition the supervisor of the SuperVision computer.

::

   Acquisition XP 10.20.30.10               SuperVision XP 10.20.30.2
   acquisition_control_server.pyw          supervision_control_server.pyw
   main local orchestrator                 main local orchestrator
       |-- card 1 process                      |-- Dev1 NI6602 process
       |-- ...                                 |-- img0 NI1409 process
       |-- card 11 process
       |-- Chroma helper when commanded
            |                                       |
            +-- signed telemetry -------------------+
                                |
                    one Everest Tango Device Server
                    elyse/acquisition/telemetry
                                |
                         web / archive readers

Every NI card process is a direct child of its own local orchestrator. There
is no intermediate Acquisition native controller owning eleven grandchildren.
The main process performs business sequencing and validated software-state
updates; card children alone import/query NI drivers and own native tasks.
Chroma native operations retain their existing separate helper processes.

Thread and queue boundaries
--------------------------

The Acquisition runtime thread serializes cross-card business procedures.
Each card has a dispatcher thread, bounded request queue and retained child
process. Periodic input reads run independently on those dispatchers. A blocked
card call cannot block another card's input loop. Explicit foreground reads
used for HT stopping are distinct from cached background samples.

The HTTP reader, command admission worker, telemetry publisher/relay, GUI
state cache and journal writer have separate bounded execution paths.
Acceptance, execution, returned driver calls and physical feedback remain
different observations. Neither a successful HTTP response nor remembered
output values establish a physical acknowledgement.

The SuperVision runtime owns two independent dispatchers. Its Initialize may
start the healthy synchronization card even if video initialization fails,
or video may run while synchronization preparation fails. The application
reports FAULT and retains both owners. DS/web command admission additionally
requires full current host readiness. There is no global two-card commit
barrier and no automatic replay of partially completed initialization.

Acquisition starts the six source-initialized counters and writes startup
images only after all eleven card preparation results have returned ready.
The SuperVision counter profile starts all eight source counters. Configuration
ticks follow the VI's factor-of-20 conversion; actual PFI11 frequency and
physical pulse timing still require measurement on the equipment.

Telemetry and authority
-----------------------

In the cold rollout, the running Acquisition VI continues supplying all 27
banks through the Acquisition orchestrator. No Python card is initialized.
The deployed Device Server keeps the legacy mode active; the independent
SuperVision orchestrator can be inspected over its authenticated API while
its publisher remains disabled.

Explicit federation activation is a later configuration step, after VI task
release and native qualification. Each host then sends directly to Everest;
SuperVision traffic does not pass through Acquisition. Fixed bank ownership,
independent keys, independent boot/session histories and source ages prevent
one healthy host from refreshing or overwriting the other host's data.
The counter bank combines two current 16-value command memories plus the
explicit idle selector. This is not a simultaneous hardware measurement.

The 27-bank public envelope remains fixed. Unsupported data stays unavailable.
NI1409 raw U8 frames use a separate bounded video field/attribute; the original
C12 string bank is not repurposed as pixels. Legacy Vision processing,
interlace handling, BCG and profile extraction have not been reproduced.

Failure and maintenance limits
------------------------------

Returned card errors, blocked native calls and exited processes are distinct
states. A timed-out or crashed driver owner is retained as uncertain; another
process is not automatically allowed to acquire its NI resources. A clean
private card replacement requires matching generation, affected-output OFF
confirmation, confirmed native cleanup and joined previous process. It does
not replay another card's outputs or restart the synchronization card.
No public HTTP restart/recovery operation has been added.

Changing low-level card service code after a clean isolated stop can leave
other owners running. Changing the main cross-card business engine still
requires a controlled application release; transparent hot replacement of
that engine or adoption of orphaned owners is not implemented.

Cold imports, real Python 3.4 subprocess tests and source/manifest checks do
not establish live NI compatibility, electrical interlocks, driver recovery,
camera geometry or calibrated timing. Those are commissioning observations.
