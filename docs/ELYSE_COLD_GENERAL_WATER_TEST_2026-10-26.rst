Cold General/water commissioning, 26 October 2026
================================================

Scope and installed source
--------------------------

The operator authorized one Initialize -> General -> water -> water stop ->
General stop cycle. No Chauffage, PREMA, Focales, Relais HT, HT supply or pulse
start was submitted. LabVIEW showed its start screen with no Acquisition VI
running. The canonical XP application retained its three buttons and 27-bank
telemetry envelope. All remote stage requests used the existing Everest Tango
Device Server, authenticated session/revision fencing and unique command IDs;
each command was submitted once.

r14 removed the false pre-HT cooling countdown and archived prior receiver
incidents. r15 additionally allows the reviewed water-stop procedure during an
operator-attested cold, current-owner General/water-only test. A separate RAM
fact is created only after successful startup and revoked before any non-water
stage-start effect, including a partially failed start. Missing/non-Boolean
facts and uncertain ownership do not grant the exception. This does not grant
hot-machine cooldown permission, change VI output frames, skip Chroma OFF in
General Arret, or assert physical circulation.

The 70-file matched source installer preserved configuration and ownership
evidence. r15 backup: ``C:\ACQ_Python_Control_20261022_v8\runtime\source_before_matched_20261026T124148Z``.
Installed source fingerprint:
``6392bf67aba20b5bb56d41017016ffc813eff20e392f03da6d21a56e1e641379``.

Observed cycle
--------------

Times below are UTC; Paris local time was UTC+01:00 on this date.

* At 12:43:05.455220, Initialize had completed: all 11 cards READY, 21 NI tasks,
  known retained owner, state RUNNING, FRESH inputs. Measured HT was 0.0 kV;
  Canon/Section values were 10.024414/10.000000 degrees C.
* General start was submitted at 12:43:17.970934, ID
  ``f45e015a0a2b43b28bff6c13c4e841e8``. By 12:43:27 its software sequence was
  COMPLETED. C4[19/38/45/46] changed from True to False, before the separate
  water-start request. Those raw changes alone are not proof of circulation.
* Water start was submitted at 12:43:39.412510, ID
  ``e3b3521afbff4de8912c6e63927efd4d``. All 12 source frames and 11 local writes
  completed without reported source-execution failures. The additional bounded
  feedback verifier returned COOLING_START_TIMEOUT because Canon/Section were
  not both normal. C3[0/6] remained True (the existing 220V fault indications).
  Later starts remained blocked. No extra 120-second cooling countdown started.
* At 12:44:28.158165, Canon/Section read 20.717773/21.547852 degrees C. Such an
  abrupt transition from approximately 10 degrees C, and its reversal on stop,
  can reflect energizing the measurement path. It is not evidence of heating
  by 10 degrees C, a cooling rate, or independent proof of water circulation.
* Water stop was submitted at 12:44:56.647157, ID
  ``d61402b1062f43be9d96a82e7c23a431``. Its seven source frames completed. At
  12:45:11.136606 the temperatures were 10.024414/10.195313 degrees C.
* General stop was submitted at 12:45:17.330063, ID
  ``bad723e088fa4ca3a2889820406faee1``. All 17 source frames were attempted;
  no NI output-write/restoration failure was reported. The aggregate outcome
  was FAILED because all three unpowered Chroma connections returned
  ``chr62000_init: status -1073807339``. Those helper errors did not prevent
  later NI stop frames. The runtime retained PARTIAL_STOP_FAILURE rather than
  claiming a successful full-machine stop.
* At 12:45:35.446398, C4[19/38/45/46] had returned to True, HT current was 0 A,
  and Canon/Section were 10.024414/10.048828 degrees C. The operator then
  explicitly confirmed that General and pumps were physically OFF.

The server did not crash or restart during this cycle. Its known NI owner
continued fresh diagnostic reads in FAULT; Everest acknowledgments increased.
The web received all 27 bank envelopes with no missing or stale banks. Its
INCOMPLETE label was explicit availability information: five input banks were
usable while 22 output/software/other banks were unavailable in that fault
view. This must not be described as 27 independently measured physical banks.

Remaining limits
----------------

The water-start feedback timeout and Chroma stop failures remain visible; they
were not silently cleared to declare commissioning complete. No follow-up
energizing test or serial configuration change was performed. The Everest
control metadata bridge also hides ``latest`` while EXECUTING even when the XP
verification loop reports fresh samples; this is distinct from an XP read hang
and needs a separate context/freshness-tested projection change.

Observations, exact intents and receipts are saved under
``F:\ELYSE_Telemetry\2026-10-26\cold_general_water_r15``. These bounded diagnostic
snapshots are not a lossless packet archive. No live HDF5 file was opened.
PostgreSQL was not repaired or restarted by this test.

Validation
----------

* Actual CPython 3.4.4 x86: 119 tests passed, including subprocess ownership,
  source stop behavior, cold-water permission revocation, fault diagnostics,
  HT-scoped cooling and circulation confirmation.
* Python 3.12 with external networking denied: 81 tests passed.
* Actual Python 3.4 parsed all 64 packaged executable source files and imported
  the cold control runtime without NI driver imports; fingerprint matched.

These observations supersede the pending XP handover described at the end of
``ELYSE_HT_COOLING_SCOPE_2026-10-26.rst``.

Final cleanup
-------------

After the operator's physical-OFF confirmation, local Deinitialize completed
normally. At 12:51:00.339879 UTC the same application reported IDLE, resource
count 0, ownership_uncertain=False, general_stop_required=False and no current
runtime error. The four command receipts, including the Chroma partial stop
failure, remained in history. The application remains open in IDLE and may
forward VI data if a VI is subsequently started; no VI was started by this test.
