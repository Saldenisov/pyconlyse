# Cooling alarms and 120-second shutdown policy

## Boundary

This is a new operator-requested policy, not a claim that the original VI has a
120-second shutdown timer. Existing Acquisition/NI interlocks and stop sequences
are unchanged. No live service was restarted, no device was contacted, and no
hardware test or production deployment was performed for this change.

The HDF5 recorder and its files are outside this implementation. Only discrete
alarm transitions and countdown state enter the separate SQLite alarm journal.

## Detection

`legacy/xp_acq_agent/elyse_agent/cooling_safety.py` decodes the saved Fluides
software indications from C3/C4. These mappings agree with the preserved
`web/frontend/src/elyseLiveDisplayMap.json` and `elyseFluidesPanel.json`.

| Circuit | 220 V fault indication | Controller fault indication | Pressure indication faulty | Flow indication faulty |
| --- | --- | --- | --- | --- |
| CANON | C3[0] = true | C3[1] = false | C3[4] = false | C4[19] = true |
| SECTION | C3[6] = true | C3[7] = false | C3[10] = false | C4[38] = true |

The table describes software indications, not independently verified physical
contact polarity or proof that the pump is mechanically stopped. It is distinct
from the original raw Acquisition flow-trip predicate, which is not modified.
No alarm is inferred from valve contacts, temperature noise, missing values, or
a stale/error bank. A known fault in a fresh signal still raises an alarm if
another signal is unknown. Recovery requires every relevant signal to be fresh
and normal across at least two distinct observations spanning two seconds.

The LabVIEW receiver arms new incidents when fresh EPS[8] is true. The Python
owner arms them after its explicit General Marche request, retaining the existing
stop-required ownership latch. Physical/manual operation outside those software
state paths is not commissioned by this change.

## Countdown and journal

Each circuit records its first fault time and a deadline 120 seconds later. A
second circuit, repeated fault packet, browser reload, lost telemetry, or absent
operator acknowledgement cannot extend the earliest outstanding deadline.
Fresh stable recovery before expiry cancels only the recovered circuit's timer.
After expiry, the stop request remains latched; recovery does not cancel a stop
already requested. A completed stop plus fresh stable recovery allows a later
cycle. Unknown data never counts as restored circulation.

The runtime has an independent 100-ms watchdog thread which only queues a stop.
All NI/Chroma calls remain on `ACQ-card-owner`. Expiry requests the existing
`general_stop` chain; it does not terminate the server, deinitialize/reinitialize
cards, invent an OFF readback, or bypass HT feedback/Chroma checks. The deadline
is a software request deadline, not a certified real-time guarantee of physical
isolation. Blocking drivers or a failed stop are explicit failures and retain
NI ownership for intervention.

SQLite stores discrete transitions and pending deadlines in a single transaction
with synchronous FULL. Restarts recover an outstanding deadline from its UTC
timestamp, never grant a new 120 seconds, and label a previously queued request
INTERRUPTED rather than completed. Journal errors remain visible and cannot
suppress an in-memory stop request. No acknowledgement/reset HTTP route exists.

## Authority and deployment

Automatic stopping requires all of:

- the Python runtime owns initialized tasks;
- `control_profile = "extended_ht_stop"`;
- existing `ht_shutdown.feedback_verified = true`;
- existing `focal_stop.resources_verified = true`;
- new `cooling_safety.polarity_verified = true`, only after commissioning.

No qualification flag is enabled by this change. Legacy/general-only profiles
or unqualified adapters explicitly report automatic stop unavailable. In
particular, the receive-only LabVIEW bridge/DS_AcqTelemetry cannot stop the
accelerator and its web warning must not promise that it can.

The XP GUI creates `cooling_alarms.sqlite3` beside its configuration by default.
Optional `cooling_safety.journal_file` selects another path. The production
Everest receiver uses `logs/elyse_cooling_alarms.sqlite3`; its optional
`cooling_journal_file` Tango property overrides that path. Loopback test receivers
remain RAM-only unless explicitly supplied a journal.

The new read-only `/api/elyse/acquisition/telemetry/cooling` endpoint uses explicit
`ELYSE_COOLING_SOURCE` selection:

- `labview` (default): fixed existing telemetry receiver, alarm/countdown only;
- `xp_runtime`: existing AcqRuntime facade registered as
  `tango://10.20.30.202:10000/elyse/acquisition/runtime`, reading only
  `runtime_json`. Registration/configuration is a later deployment step.

There is no automatic source fallback. A stale/unavailable selected source is
an explicit observation failure. The global web banner retains its last alarm,
shows circuit/time/deadline/cause/journal, and cannot send a device command.

## Non-actuating checks

Tests use synthetic banks, fake clocks, temporary journal databases and fake card
owners. Coverage includes exact 120-second expiry, two circuits, stale data,
stable recovery, repeated observations, restart persistence, storage failures,
same-owner stop dispatch, failed-stop ownership retention, receiver-only mode,
read-only API source selection and web warning rendering. These are software
tests, not hardware commissioning or a safety certification.

Verification commands (Windows, Python 3.12 test runtime; XP sources also parsed
with Python-3.4 syntax rules):

```powershell
python -m unittest tests.unit.test_elyse_cooling_safety tests.unit.test_xp_acquisition_runtime tests.unit.test_xp_acquisition_general_stop tests.unit.test_xp_acquisition_general_only tests.unit.test_acq_telemetry_sink
python -m pytest tests/web/test_acq_telemetry_api.py -q
npm test -- --watchAll=false --runInBand --runTestsByPath src/CoolingAlarm.test.js src/Elyse.test.js src/SupervisionHeader.test.js
```

The candidate package is `.tmp/acq-cooling-candidate-20261021.zip`; it contains
21 source/config/data files plus its manifest, no key, journal or live telemetry.
Its commissioning permissions remain false and auto-initialization is disabled.

Package SHA-256:
`0B55B80FDCF6FB701B44432C9A7825B0C2CF5CEA184C5316BC5A4D77F8192D57`.
The focused backend/owner/sink suite passed 107 tests; the read-only API suite
passed 19 tests. Legacy deprecation and unrelated existing frontend hook/bundle
warnings are not treated as hardware qualification.
