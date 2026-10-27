SuperVision synchronization web handoff
======================================

Inspection of active C:\dev\pyconlyse (read only)
-----------------------------------------------

The telemetry API returns the whole validated snapshot, so the new DS field
``snapshot.supervision_counter`` already survives its projection. It had no
dedicated independent-counter endpoint or visible16-value SuperVision panel.
The active Synchro page renders the Acquisition editor/legacy bank values.

The active NI1409 camera panel already exists in /elyse's ``ni1409`` tab and
the camera clients page. It reads the fixed authenticated DS video facade,
validates bounded U8 pixels and identities, and removes stale pixels after2s.
No camera code change is needed here.

New read-only path
-----------------

``GET /api/elyse/acquisition/telemetry/synchronization`` reads ONLY the fixed
existing DS attribute ``supervision_counter_json``, timeout1500ms. It never
reads C1011, XP, cards, VI or command routes. Its bounded strict observer parser
matches the active main facade: failed attributes, duplicate fields, nonfinite
JSON and payloads exceeding2MiB are rejected. Existing authentication applies.

The projection requires owner=supervision,16 finite values, explicit source,
session/sequence, read_only=true and hardware_acknowledged=false. Stale or absent
observations carry null values. These values are local counter control memory,
not physical timing measurements. UI shows8 delay/width pairs in microseconds,
source/age/selector/pending state. It has no command buttons or command client.
Polling is serial,1s after completion, with5s deadline and2s freshness expiry;
repeated observation sequences cannot renew their own freshness window.

Deployment diff for root, NOT performed here
------------------------------------------

Copy these NEW runtime files byte-identically from the release worktree::

  web/backend/acq_supervision_counter.py
  web/frontend/src/api/supervisionCounterClient.js
  web/frontend/src/components/supervisionCounterView.js
  web/frontend/src/components/SupervisionSynchronization.js
  web/frontend/src/components/SupervisionSynchronization.css

Apply only ``web/SUPERVISION_READONLY_SYNC_MAIN.patch`` to the active main after
checking these SHA256 baselines against current files and preserving dirty edits::

  web/backend/acq_telemetry_api.py
  8f9a45dbc3b4f6feffd39c2a86bfc058b165cb1b4a3cb4e266ea7046381ca34d
  web/frontend/src/LiveSupervision.js
  9a7a4036645d5607dbe76866f4eddf20c2da876c5726e024b42fdbf4da0f7ef6

The optional local BASES.json is not needed or committed. The active files use
CRLF; the read-only check
passes with ``git apply --check --unidiff-zero --ignore-space-change <patch>``. Both recorded
base SHA values still match. Use the same whitespace option when root applies
the reviewed patch. It changes:

* backend/acq_telemetry_api.py: import, protected GET registration and one route;
  existing stricter observer parser remains untouched.
* frontend/src/LiveSupervision.js: one import plus the new panel before the
  existing Synchro editor. Existing write guards and editor behavior are unchanged.

Do NOT overwrite active main's acq_telemetry_api.py or Elyse.js with release
versions. Release Elyse uses an older tab layout and only received its own small
Synchronization integration for tests. Do NOT deploy the release verification
bundle over the newer active UI. Rebuild the ACTIVE frontend after additive port,
then root may activate the backend/frontend using its existing procedure.

Safe activation order, commands not executed by this change
----------------------------------------------------------

1. Recheck both hashes above; abort on mismatch. Copy the two current dirty files
   to a new timestamped backup folder on F and record their hashes. Copy only the
   five new runtime files listed above; reject a different pre-existing target.
2. From C:\dev\pyconlyse run::

     git apply --check --unidiff-zero --ignore-space-change <release-worktree>/web/SUPERVISION_READONLY_SYNC_MAIN.patch
     git apply --unidiff-zero --ignore-space-change <release-worktree>/web/SUPERVISION_READONLY_SYNC_MAIN.patch

3. Build ACTIVE source into a new, explicitly checked sibling of the served
   build. The following PowerShell sets a new path; it does not replace the
   current build::

     $webFront = (Resolve-Path -LiteralPath 'C:\dev\pyconlyse\web\frontend').Path
     $webStamp = Get-Date -Format 'yyyyMMddTHHmmss'
     $webStage = Join-Path $webFront ('build.sup-sync-' + $webStamp)
     if ((Test-Path -LiteralPath $webStage) -or ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($webStage)) -ne $webFront)) { throw 'Unexpected build stage' }
     $env:BUILD_PATH = $webStage
     Set-Location -LiteralPath $webFront
     & 'C:\Program Files\nodejs\node.exe' '.\node_modules\react-scripts\scripts\build.js'
     if ($LASTEXITCODE -ne 0) { throw 'Active source build failed; keep current service/build' }

4. Keep the current web service running until that build succeeds. Use the
   existing activation transaction: verify plain non-reparse build/stage trees,
   exact resolved parent C:\dev\pyconlyse\web\frontend, a new rollback path,
   and a unique process whose command line is exactly::

     C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe -u start_local.py

   Its working directory must resolve to C:\dev\pyconlyse\web. Capture that
   process's environment in memory. Gracefully terminate ONLY that process and
   wait15s; abort rather than escalating to unrelated processes. Move served
   build to its new sibling rollback path, then stage to build. Start the same
   command/cwd/environment with subprocess.CREATE_NO_WINDOW and fresh stdout/
   stderr logs on F. Keep rollback source/builds; do not restart Tango, XP or VI.
5. Verify /elyse plus the fixed telemetry/video/synchronization GETs. A missing
   SuperVision observation legitimately shows unavailable; it must not be
   replaced by Acquisition values. On activation failure, restore previous
   two source files/build and restart the SAME web process command/environment.
   This is a root-owned deployment step, not performed by this implementation.

Validation
----------

*47 backend tests pass with ``--deny-network``: new17 counter tests plus existing30
  telemetry tests. Tango is stubbed; no live/device call occurs.
*76 frontend tests pass across6 suites, including existing camera codec/viewer,
  Elyse command-guard integration, and11 new counter client/view tests.
*Production webpack compilation passes with0 webpack warnings, using existing
  dependency installation without installs. Output ``frontend/build-supervision-readonly``
  is validation-only. It is not the newer active UI deployment artifact.
*No active main file, write guard, service, hardware, VI, XP or deployment was changed.
