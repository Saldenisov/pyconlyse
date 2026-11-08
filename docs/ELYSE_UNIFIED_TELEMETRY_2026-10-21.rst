One Acquisition owner, one telemetry device, one bank contract
=============================================================

Current boundary
----------------

The operator selected a single telemetry interface rather than two independently
formatted Device Servers. The unified source is implemented locally but has not
been deployed to XP, restarted on Everest, or switched into the running web
service. No live initialization or hardware command was performed by this work.
The earlier XP v1 window was stopped by the operator. The existing running
receiver and recorder were neither stopped nor restarted.

Data and command paths
----------------------

Python 3.4 card owner -> bounded standard-bank publisher -> signed TCP relay
on Everest port 8767 -> existing ``DS_AcqTelemetry/everest`` instance and
``elyse/acquisition/telemetry`` device -> unchanged web telemetry URL.

The owner remains responsible for local Initialize, Deinitialize and Stop
server. Its network publisher never calls NI and never blocks the NI owner on
an acknowledgement. One immutable in-flight packet and one replaceable pending
packet bound memory. Retries apply only to telemetry delivery, not equipment
commands. Source age is carried into the outbox; retransmission cannot make an
old NI snapshot fresh. This remains latest-only, not lossless acquisition.

The same Tango device exposes ``ExecuteCommand`` and ``runtime_json``. The
latter contains command admission, boot/revision, cooling policy and receipts;
it is not an alternate bank stream. Named commands return through signed HTTP
to the XP owner on port 8772. Web values always come from ``telemetry_json``;
no second web projection of six raw banks remains. The obsolete separate
``AcqTelemetryControl`` class is not required or included in the new bundle.

Source selection has one authority: the existing Tango
``producer_kind_filter`` property. ``copied_acquisition`` retains the LabVIEW
read-only path. ``python_acquisition`` exclusively accepts the Python standard
publisher. A default or LabVIEW-configured receiver rejects Python packets;
a Python-configured receiver rejects LabVIEW packets. No failover merges the
two sources. Retired Python boots and regressed sequences cannot overwrite the
current session, including through a new relay connection.

Compatibility and coverage
--------------------------

The Python publisher emits all 27 names in the original order, using the
existing snapshot version, variant/type descriptors, per-bank error clusters,
signed relay framing and authenticated ACK. The saved descriptors were read
from the cached LabVIEW receiver on 2026-10-21. Only type metadata was saved in
``legacy/xp_acq_control/data/standard_telemetry_schema.json``; no measurement
values were imported or used as a fallback. The descriptor file participates
in the installed-source fingerprint. Producer identity and capture/timestamp
provenance explicitly distinguish Python from copied LabVIEW controls.

Twelve banks can currently be populated from confirmed owner data:

* C1NI6071E, C2NI6071E: explicit legacy-calibrated arrays, not raw volts or
  values scaled a second time.
* C3_IN_DIO96, C4_IN_DIO96, C5_IN_DIO96: acquired Boolean inputs.
* C3_OUT_DIO96, C4_OUT_DIO96, C5_OUT_DIO96: last successful software commands,
  not physical output readback.
* C6NI6703, C7NI6703, C8NI6703, C9NI6703: last successful logical AO commands,
  not measured voltages or independently confirmed equipment settings.

The other 15 banks remain explicit null values with application error -80001
and an unavailable reason: C1011NI6602, DPS, DPC, EPS, EPC, C12NI1409, VDM-A,
VDM-S, VDD, VAM-A, VAM-S, VAD, VTA, VTS and VTL. Their type descriptors remain
present, but no zero-filled status, pressure, camera or history is fabricated.
The extra C11_NI6220_AI native inputs have no demonstrated mapping to the
standard counter bank and are not mislabeled as counter measurements.

This closes transport/schema compatibility, not full business-logic parity.
The web reports INCOMPLETE coverage while displaying available current banks;
an unavailable bank cannot turn into a healthy lamp. IDLE, EXECUTING, failed,
stale or simulated input snapshots do not publish current measurement values.
Unknown output-command memory remains unavailable.

Command safety
--------------

Tango and XP command enablement default false. Separate command credentials,
the current boot/revision, single-use lease, explicit operator confirmation,
named allowlist, persistent web dispatch fence and XP qualification gates are
retained. No remote initialization or arbitrary output write was added.
The current command transport cannot turn an unqualified hardware capability
on. Web commands still require authenticated operator access; the current
login-free local web startup is not a reason to remove this requirement.

Starts additionally require matching current pushed input telemetry. Stale
or absent measurement telemetry does not hide an explicitly requested stop
when the command channel authenticates the current Python owner; the XP
operation-specific gates still apply. Stale command metadata, LabVIEW mode,
disabled credentials and shutdown/reinitialization prevent dispatch. There is
no automatic command retry and no physical acknowledgement inferred from
COMPLETED. The 120-second cooling policy remains uncommissioned until its
existing HT, Chroma and indication-polarity requirements are qualified.

Non-actuating checks and deployment boundary
--------------------------------------------

Driver-free tests exercise signed loopback push/ACK, exact bank order and
types, engineering-unit selection, unavailable banks, source exclusion,
retired boots, repeated packets, preserved age, same-device command routing,
explicit stop availability and isolated package imports. The existing
LabVIEW sink tests remain in the regression set. A cold package checker runs
under actual CPython 3.4.4 with native-library loading forbidden, verifies the
manifest hashes and exchanges an authenticated ACK with a loopback-only sink.

New packages are generated without overwriting prior candidates:

``python -m tools.package_acq_web_control NEW_XP_DIRECTORY``

``python -m tools.package_acq_web_control NEW_EVEREST_DIRECTORY --everest``

The new Everest package targets the existing DS_AcqTelemetry class and device.
Activation requires an operator-approved cold release transfer, explicit
read/command-key provisioning and source selection, restart of only that
receiver and the web service, and a new XP window in IDLE. It must not initialize
cards. Restarting the receiver creates a new receiver session and clears its
RAM; a continuing recorder must not be described as retaining one uninterrupted
receiver session. Do not stop/restart the recorder or open its live HDF5 file.
Hardware commissioning remains a later, separately authorized step.

The checked software regression totals are 94 backend/protocol/policy tests,
31 legacy LabVIEW relay/snapshot tests, and 20 React tests. Fourteen policy
tests also pass under actual CPython 3.4.4, in addition to the cold signed-ACK
checker. The packaged class imports with real PyTango in an isolated process;
this is not a live registered-Tango startup or hardware test.

Recording is a separate activation constraint. The original recorder admitted
only copied LabVIEW telemetry. Its code now also validates the complete,
explicitly attributed Python envelope. A source change is journalled, and
summary statistics are reset rather than pooling unqualified cross-source
measurements. Unknown banks remain null and are excluded from numeric statistics.
All 12 recorder tests pass, including three new source/coverage checks, using
private temporary files only. The already running recorder has not been
replaced and must not be assumed to have loaded this code. A controlled handover
is required before switching sources. No live recorder status or archive was
inspected; no recorder process, checkpoint, automation or active HDF5 file changed.

The final combined backend/recorder run passed 106 tests; the 31 legacy relay
tests and 20 React tests passed separately. The isolated production frontend
build completed with warnings in unrelated camera/motor/device components.
No production web assets were replaced. The final local bundles are
``acq-unified-xp-20261021-v5.zip`` and ``acq-unified-everest-20261021-v5.zip``;
their hashes and deployment boundaries are recorded in
``C:\dev\ELYSE-ACQ-telemetry\2026-10-21\UNIFIED_RELEASE_STATUS.json``.
