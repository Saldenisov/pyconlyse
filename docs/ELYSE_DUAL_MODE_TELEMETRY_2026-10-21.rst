One XP process with lifecycle-selected telemetry
===============================================

Decision and current boundary
-----------------------------

The operator revised the v5 deployment request before any live handover. The
replacement v6 candidate retains one XP Python 3.4 process, three local buttons
and the existing Everest telemetry device. No receiver, web, recorder, XP
process, VI, card or equipment state was changed during preparation of v6.
The preceding v5 packages and their evidence remain unchanged.

The window must be running for either telemetry path to operate. Opening it
does not initialize NI. Its only buttons remain Initialize, Deinitialize and
Stop server. A second standalone Python bridge is not part of this design.

Source selection
----------------

* Clean IDLE with no NI owner: accept framed XML from the existing copied VI
  on IPv4 loopback 127.0.0.1:8766, using the saved cp1252 XML interpretation.
  All 27 original bank records, types and error clusters are forwarded. This
  receives the existing VI publication; it does not poll PSP, launch LabVIEW
  or claim to acquire its data directly from cards.
* Initialize: under the runtime lock, reject initialization while valid VI
  traffic has arrived within two seconds. The existing explicit local startup
  confirmation still requires the Acquisition VI to be stopped and NI ownership
  released. Missing telemetry is not proof of release. Once accepted, the
  INITIALIZING state closes VI admission before the NI worker can be woken.
* Initialized owner: publish Python measurements and known last-command images
  in the same standard 27-bank contract. Twelve banks may be populated; fifteen
  remain explicit null/unavailable. No LabVIEW fallback is attempted on read
  errors or lost connectivity. A fault retaining NI ownership keeps the explicit
  stop path; it does not select the VI bridge.
* Successful Deinitialize: only a new clean IDLE enables VI admission again.
  A null/unavailable boundary replaces cached data. A fresh XML receipt is
  required; no pre-initialization VI image is revived. Failed cleanup and
  recovery-required states do not enable bridge mode.

One immutable in-flight receipt and one replaceable pending packet bound RAM.
An old receipt already in flight may finish before the source boundary packet;
it keeps its old source label and increasing age, and cannot overtake the new
source. No measurement is relabelled or refreshed by a retry. Software packets
replace all banks together, without claiming atomic physical card sampling.

Same receiver and recording
---------------------------

The existing device remains ``elyse/acquisition/telemetry``. Its single
``producer_kind_filter`` setting becomes ``unified_acquisition`` for v6. Each
packet identifies the actual source as copied LabVIEW or native Python. One
process boot, one relay identity and one monotonic publication sequence cover
both modes. This selected receiver rejects known standalone-bridge packets,
competing relays within a boot, regressed sequences and retired boots. No
receiver property change is needed when Initialize or Deinitialize is pressed.

``runtime_json`` remains lifecycle/command metadata, not another measurements
stream. The device masks equipment commands in bridge and transition modes.
Current native input telemetry is required for starts; an explicitly requested
stop remains available on an authenticated native owner with retained resources.
All existing commissioning and command-credential gates remain unchanged and
disabled in the default configuration. No remote Initialize was added.

The web reads the same telemetry attribute and preserves the actual source.
The recorder already journals both source labels, resets summary statistics
on source changes and preserves complete original packets. Source switching
tests cover both directions within one boot and receiver session. The original
live recorder has not loaded the new code; the previously authorized controlled
handover to a new archive is still pending. Its live HDF5 was not opened.

Activation constraints
----------------------

If another bridge owns loopback port 8766, startup fails closed rather than
stopping it or creating another publisher. Deployment must first identify and
replace only that bridge, not Acquisition VI or its NI tasks. Configure the
existing read/relay key without printing or bundling its contents. Do not enable
hardware commissioning flags or initialize cards during cold deployment.

The candidate and its manifest are v6, not v5. Local checks include real signed
loopback delivery, all-bank forwarding, source isolation, stale age, concurrent
XML/Initialize admission, non-IDLE admission barriers and recording source changes.
Actual CPython 3.4.4 checks run with native-library loading forbidden. These
checks do not establish registered Tango startup, XP execution or hardware
qualification. Those remain separate deployment/commissioning boundaries.

The final selected regression run passed 125 tests. Fourteen policy tests pass
under actual Python 3.4.4; its cold manifest/signed-loopback checker also passes
the new VI forwarding and Initialize fence checks with native loading forbidden.
The isolated Everest package imports with real PyTango. Artifact hashes and
the explicit not-deployed state are saved separately in
``C:\dev\ELYSE-ACQ-telemetry\2026-10-21\DUAL_MODE_RELEASE_STATUS.json``.
