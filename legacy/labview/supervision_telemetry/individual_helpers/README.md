# Individual SuperVision helpers

This packet contains **3 of the planned 11 helpers**. The three VIs and project
are byte-identical copies of the native LabVIEW 2020 x86 **Save for Previous
Version 12.0** output. No main VI or unfinished camera/lifecycle VI is included.
Existing canonical observer and queue files outside this directory are unchanged.

## Included native export

| File | Bytes | SHA256 |
|---|---:|---|
| `sync_lifecycle/counter_only_candidate/SUP_SyncTap.vi` | 8071 | `c81604493a62a6137d78a10913e2f17eb76272e86556a949025d8d4f61d999ce` |
| `sync_lifecycle/counter_only_candidate/ACQ_SharedState_Queue_Latest.vi` | 7988 | `7762e5753c1064c41fb270f2cb756ac73ba1c0f7ca6c387c1458b58c9e6834fc` |
| `sync_lifecycle/ACQ_SharedState_Transport_Auto.vi` | 13750 | `f24df3c61e67a0c0a31d28cf891ef1e619e4b3a0c842522409e06cde9dd6d357` |

All three VI headers identify `12.0.0 release build 4` and `RunOnOpen=0`.
The native project is
`export2012_preparation/SUP_Sync_Export_Native_2020.lvproj`; its actual
`LVVersion` is `12008004`. Its filename is retained from the native export.
The exported folder structure, including `counter_only_candidate`, is retained
so the project and same-folder SyncTap→Queue link remain closed. UI-only
`.aliases` and `.lvlps` files are excluded.

`receipts/SYNC_NATIVE2012_EXPORT_SOURCE.json` records the original export audit;
its inventory includes those excluded source-side UI files. The exact delivered
subset is listed in `package_manifest.json`.

## Qualification matrix

| Helper | Included | Native 2020 editor evidence | Native 12 export | LabVIEW 2012 Open/compile/runtime |
|---|---|---|---|---|
| `SUP_SyncTap.vi` | Yes | FP+BD, Ctrl+U and Save passed; no Run | Passed | Pending |
| `ACQ_SharedState_Queue_Latest.vi` | Yes | Project/dependency binding and export; prior source receipts retained | Passed | Pending for these exported bytes |
| `ACQ_SharedState_Transport_Auto.vi` | Yes | Native project export; prior source receipts retained | Passed | Pending for these exported bytes |
| `SUP_Camera_Epoch.vi` | No | External native snapshot/model proof only | Pending | Pending |
| `SUP_Camera_SetupObserve.vi` | No | Source candidate; native-load repair pending | Pending | Pending |
| `SUP_Camera_FrameTap.vi` | No | Native-call/gate authoring in progress | Pending | Pending |
| `SUP_Telemetry_Begin.vi` | No | Source candidate; native-load repair pending | Pending | Pending |
| `SUP_Telemetry_End.vi` | No | Source candidate; native-load repair pending | Pending | Pending |
| `SUP_Camera_Observe_U8_UNCOMPILED.vi` | No | Existing canonical receipts outside this subset | Existing canonical export; not copied here | Retain existing limits |
| `SUP_Camera_Queue_Latest.vi` | No | Existing canonical receipts outside this subset | Existing canonical artifact; not copied here | Retain existing limits |
| `SUP_Camera_Transport.vi` | No | Existing canonical receipts outside this subset | Existing canonical artifact; not copied here | Retain existing limits |

Native export and offline checks do not establish LabVIEW 2012 execution or
hardware behavior. No XP deployment or runtime test was performed for this
packet. The existing `epoch_native2020_semantic_snapshot.json` is a separate
native-2020 semantic record, not an included runtime helper.

## Passive synchronization contract

`SUP_SyncTap.vi` reads exactly one existing control, `C10-11 NI6602`, through its
input connector **5**, a generic VI-server reference to the actual copied main.
Output connector **0** is the private control-read/telemetry error.

The original value is a 33-DBL cluster. The receiver forwards SuperVision values
`[16:32]` and selector `[32]`. The values describe observed software memory;
control-read errors and configured values provide no successful NI-write
acknowledgement or physical waveform measurement. No new NI task or hardware
read/write call is added.

The XML transport is a synchronous worker on a genuinely parallel native branch.
The native queue owner obtains/flushes and retains data/stop refs, signals stop
inside the producer-exit branch, joins workers, and releases refs afterward.
Calling the transport synchronously inside Begin would block that caller.

SuperVision runs on `10.20.30.2`; Acquisition runs separately on `10.20.30.10`.
Keep the existing app-local queue names and SuperVision loopback XML port `8766`.
The receiver source requires counter-only admission from commit `2edbf8a4`.
Camera metadata U32 admission is recorded separately in commit `334ae78d`.
Neither revision was installed on XP by this packaging work.

## Proposed complete layout

Future camera and lifecycle helpers remain co-located so their genuine native
same-folder Epoch links remain valid:

```text
camera/
  SUP_Camera_Epoch.vi
  SUP_Camera_SetupObserve.vi
  SUP_Camera_FrameTap.vi
  SUP_Telemetry_Begin.vi
  SUP_Telemetry_End.vi
  SUP_Camera_Observe_U8_UNCOMPILED.vi
  SUP_Camera_Transport.vi
  observer_v3/SUP_Camera_Queue_Latest.vi
sync_lifecycle/
  ACQ_SharedState_Transport_Auto.vi
  counter_only_candidate/
    SUP_SyncTap.vi
    ACQ_SharedState_Queue_Latest.vi
```

Only the three included native12 files may be staged now. Future additions need
their own native Open/BD/Save, post-save literal/state audits, native12 export,
hashes and relative-link checks. Begin/End manage the observation epoch only;
queue ownership and worker lifecycle stay in native assembly. FrameTap requires
a nonreentrant check→copy→commit gate, at most one copy per 1000 ms, U32 tick-wrap
handling and new-frame/run/capture/error/time guards.

## Reproducible offline check

From repository root:

```text
python tools/verify_labview_sync_native12_package.py
python -m unittest tests.unit.test_labview_sync_native12_package
```

The standard-library verifier supports Python 3.4. It reads the RSRC directory
and LVSR headers, verifies pinned native-export bytes and project-file-based
URLs, rejects extra VIs, and checks the previously audited relative call closure.
It neither loads LabVIEW nor proves native editability, execution or hardware
behavior.
