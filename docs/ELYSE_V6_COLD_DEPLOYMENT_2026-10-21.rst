v6 cold deployment and outstanding VI delivery check
===================================================

Observed state at 2026-10-21 18:28:26 Europe/Paris
------------------------------------------------

The operator authorized v6 deployment in IDLE, telemetry verification, commits
and push, without NI initialization or equipment commands. The source bundles
remain unchanged from their local acceptance checks. The XP site configuration
only replaces the default read-key path with the existing installation-local
relay key path. No key bytes were bundled, printed or committed.

* XP directory: ``C:\ACQ_Python_Control_20261021_v6``. The source fingerprint
  reported over the authenticated metadata channel is
  ``e7a5227772ba0fa97923d3863c4c0bf7328a6e3e607661b45ee3076470c48538``,
  matching the accepted v6 bundle. State is IDLE, NI resources zero, sequence
  zero, state revision zero and command enablement false. The window has only
  Initialize, Deinitialize and Stop server. Windows startup was not changed.
* Existing ``DS_AcqTelemetry/everest`` was stopped through its own DServer Kill
  and started through the existing Starter. PID changed from 8772 to 32928.
  The existing device remains ``elyse/acquisition/telemetry``. Its source
  property is ``unified_acquisition``, commands remain disabled and the signed
  metadata reader reports no error. The redundant receive/control-only
  ``DS_AcqTelemetryControl/everest`` process (PID12908) was also stopped through
  its own DServer. Its registration was preserved, not deleted.
* Web PID28316 was replaced by PID36828 after read-only checks confirmed no V0,
  VD2 or treatment job was running. Existing lifecycle identities and failed
  historical shutdown results were preserved, not replayed. The served
  ``/static/js/main.3cc437c2.js`` matches the accepted isolated build by SHA256.
  Pre-existing unrelated Supervision/TRANCON changes in the shared checkout
  were not reverted or included wholesale in these release commits.

Transport is reachable, but live bank values are not verified
------------------------------------------------------------

The receiver has accepted one signed boundary packet with all 27 standard
names and type descriptors. All 27 data values are null with the explicit
``LABVIEW_WAITING_FOR_NEW_SNAPSHOT`` application reason. At the check above,
``vi_accepted=0``, ``vi_rejected=0`` and the relay acknowledgement count is one.
No further packet arrived during repeated checks. The web returns HTTP200 and
READ_ERROR for these explicit unavailable records; this is not a fresh bank
measurement or evidence that LabVIEW is publishing.

Acquisition is visibly running in its existing LabVIEW window, but neither its
transport worker nor its actual publication context was proven by this check.
No VI was launched, stopped, edited or saved. A question about the running
``ACQ_SharedState_Transport_Auto.vi`` was left with the operator. Do not replace
this missing verification with synthetic live packets, saved-control probes,
a second bridge or Python NI initialization. The next discriminating check is
the existing transport-only VI in the same application context as the running
instrumented Acquisition, without restarting the hardware-owning VI.

Recording handover
------------------

The original recorder PID20708 was verified by its exact command line and
recorder identity, then stopped through its own ``stop.request``. STOPPED and
process exit were verified before its HDF5 was opened read-only. The closed
archive contains 78937 committed rows and 78926 snapshots, with gzip level9
and no storage error. No old archive content was modified.

The sole new recorder is PID11412, identity
``b5806d3c63ea43aa95c61c0d3e4f7829``, writing
``F:\ELYSE_Telemetry\2026-10-21\unified_v6_20261021T1615Z``. Its live HDF5 was
never opened by a second process. At the final check it is RUNNING with zero
storage errors, 3 snapshots and 9 committed rows. Twelve read errors occurred
during the receiver handover; that count subsequently remained unchanged.
One receiver-session change was recorded. This is an explicit handover, not a
claim of uninterrupted measurement coverage. Recording remains active; no
agent monitoring automation was created.

Checks and Git scope
--------------------

The release was copied into a clean managed worktree based on the shared
checkout's HEAD, leaving unrelated dirty changes and staging untouched. The
complete selected backend/protocol/web/recorder regression passed 125 tests
there. Three React suites passed 14 tests, including the fixed read-only web
client. The accepted source package also passed actual Python3.4.4 policy and
signed-loopback checks. Production checks covered real registered Tango startup,
served asset hashes, authenticated XP metadata and disabled command flags, not
live VI measurements or physical equipment readiness.

The commits are on ``codex/acq-unified-telemetry-v6``. The clean release branch
provides a minimal read-only telemetry tab on its existing ELYSE page and the
same-device web API registration. It does not incorporate the shared checkout's
unrelated full Supervision UI migration. The live asset build retains that
pre-existing UI. The global pre-commit hook has no tracked configuration in
this baseline; its documented ``PRE_COMMIT_ALLOW_NO_CONFIG=1`` path was used
after the explicit tests. Inherited source-byte-preserving EOF whitespace
warnings were retained rather than changing the accepted installed bundle.
