# Native12 camera helper files: offline artifact packet

Eight camera helper files are included with the three sibling synchronization
helpers. This completes the 11-file helper inventory, not a runnable application.
Native main insertion, runtime, shutdown and hardware acceptance remain pending.

| Helper | Bytes | SHA256 |
|---|---:|---|
| `SUP_Camera_Epoch.vi` | 29372 | `84b78999901b37537f83c5c480777f22bee98a1f78d153ea93739e57738c8a3e` |
| `SUP_Camera_SetupObserve.vi` | 22419 | `4317fdaefa8e1d20950db20fc84724f50d5dee5770884d78eed9590040c2e61e` |
| `SUP_Telemetry_Begin.vi` | 22483 | `b6431ae4ac0497f8de9bb0b9cdc2f2c1c656b101f9642ea4c7d6748423a4e62d` |
| `SUP_Telemetry_End.vi` | 22389 | `bf9cdf4865fe50c16768b5e7a0ca6ede3cc8a082a53d98652dab73e08b3884c3` |
| `SUP_Camera_FrameTap.vi` | 27855 | `a08bced9a9c7115b7faf1626a4cd44b17c711c8cba63c4b533d5f5e9e19b4c1c` |
| `SUP_Camera_Observe_U8_UNCOMPILED.vi` | 26533 | `c6387a4d2d5f41ded7829ed154c89c89faa840b2aa844c1f0803d76b04c235e9` |
| `observer_v3/SUP_Camera_Queue_Latest.vi` | 10059 | `bef72a8c0a4b7cc269e1694668464ba5c75164519687fee3b428552e7bd49bb7` |
| `SUP_Camera_Transport.vi` | 14132 | `d807d598753d48c4ac6c9d38f4068ebc394eedb923e574c1a15786e2a11797f4` |

The six newly exported helpers have native LabVIEW 2020 x86 Save and stopped
fresh-project FP/BD evidence. The checks used the existing process; Epoch was already loaded as a
callee before its FP/BD were shown. No process restart or cold-process test is
claimed. Their payloads were exported by native Save for Previous Version 12.0.
Setup, FrameTap and Transport used the guarded native COM exporter.

The Epoch retains earlier generated-source history. The admitted source and
payload bytes were last written by native LabVIEW Save/export. That history is
recorded rather than described as wholly native construction. A generated-only
candidate cannot pass the release guard, even if graph/model tests pass.

The observer retains its original native20 Save-to-native12 export proof. Queue
retains its exact prior native LabVIEW12 Open/Save receipt.
Current fresh-project FP/BD evidence binds the actual retained native12 hashes,
not a fictitious native20 source or new export. Those cross-version opens showed
dirty markers in memory; no Save/Run occurred and disk bytes stayed unchanged.
The guard accepts only these two exact retained names/hashes/original receipts.
Current Transport follows the full native20 Save/fresh20/native12 export path.

`SUP_Camera_Helpers_2012.lvproj` lists all eight helpers. The earlier four-helper
`SUP_Camera_Lifecycle_2012.lvproj` adds Setup to the byte-identical native-exported
`SUP_Native_Lifecycle_Fresh_Proven_2020.lvproj` and remains available. The eight-helper
index is ordinary project XML; no VI body was serialized or patched. Native
URLs use `../file.vi` for same-folder
files, anchored at the project file. Filename-only URLs fail this check; missing
files are never admitted through a search fallback.

FrameTap links to same-folder Epoch and observer; the observer links to
`observer_v3/SUP_Camera_Queue_Latest.vi`. Retain that directory. Required NI
dependencies are Image.ctl and `vision/Basics.llb/IMAQ ImageToArray`; NI files
are not bundled or installation-qualified here. Canonical originals are unchanged.

Actual exported source checks passed: Epoch 3840 cases, Setup 48, Begin 1280,
End 256, and FrameTap 4000 admissible cases (2400 inconsistent Epoch-state inputs
excluded from a 6400-case matrix). The five new helpers retain 21 FP controls
and the native 12-port ABI. The observer retains its 17 FP/12-port source and
13450 dimension/error cases. Begin returns
the same single UTC timestamp used to initialize Epoch; End invalidates only
the matching run. Error/image identity remains intact. These are offline source
evaluations, not executed VI tests. The reader cannot decode the exported DFDS
cache (31 compressed resource bytes, 204 expanded bytes); it was not rewritten.

The universal connector retains unused fields. Begin's logical RunStamp is
output 2; End takes it at input 10. Begin/End do not start or stop workers.
Native queue ownership, stop-before-join and final reference release remain part
of later native assembly in a copy of the actual project.

FrameTap's native-source gate is nonreentrant and not inlined. Its image/error
identity outputs must precede downstream mutable image writers. Replace the
original Grab image edge to Rotate with synchronous FrameTap input6/output4,
and preserve original error through input5/output3. An independent Grab-to-Rotate
branch can mutate the same reference before the snapshot and is not acceptable.
The original edge is Grab15740 output15749 -> Rotate14726 input14771, wire19409.
The complete main has not been assembled or run by this packet work.

Current Transport is the native12 export of native20 source3035 after four native
Unbundle error sinks were added. All 13 primitive error outputs are wired:
the four additions consume stop Obtain532, stop Dequeue745, VariantToData677
and FlattenToString316. The Unbundle scalar outputs are discarded; no recovery
or stop policy was added. All 58 original nets, 19 original primitive operations,
15 literal payloads, seven FP controls and their unassigned connector mappings
are preserved. `receipts/TRANSPORT_NATIVE12_FOUR_SINKS_SOURCE_AUDIT.json` pins the
actual exported source; its native20 audit and three native event receipts are
also portable. No Run or LabVIEW2012 runtime qualification is claimed.

The 12 connector slots remain Void: control is through named Variant data and
Boolean stop queues, capacity1, TCP port8768 and a four-byte length prefix.
Automatic error handling remains enabled. ACK length is clamped to
1..16384; its InRange result is only an indicator, not a reject branch. These
are explicit runtime hazards for the next native review. TCP/ACK behavior,
modal-free errors, stop-before-join, cleanup and bounded shutdown have not been
executed or qualified. Configured waits sum to 4100 ms per iteration
(100+4*1000), excluding Close, management and scheduling; a missed stop poll can
span two iterations. That is not a wall-clock join deadline. The portable
`receipts/TRANSPORT_4AB066_READONLY_FINDING.json` remains byte-for-byte historical
evidence for nodes, timeouts and limits. Its error-output mapping and count are
superseded by `receipts/TRANSPORT20_BASELINE_AND_ERROR_OUTPUT_ERRATUM.json`
and the exact explanatory note `receipts/TRANSPORT_ERROR_OUTPUT_ERRATUM.rst`.
The correction describes historical4ab and baseline8f48, whose four unwired
outputs were corrected in current d807. It does not grant runtime qualification.
Begin/End do not fix or own worker lifecycle. Producer
exit must signal stop before the parallel worker join, then release queue refs.
The separate `NATIVE_XP_CAMERA_LIFECYCLE_WORKSHEET.rst` records the proposed
native integration ordering and its unresolved limits; it is not execution proof.

From repository root:

```text
python tools/verify_labview_native_helper_package.py
python tools/verify_labview_sync_native12_package.py
python -m unittest tests.unit.test_labview_native_helper_package
```

The preflight verifies pinned bytes, portable native receipts, project/custom
link closure and last-writer provenance. It never loads or runs LabVIEW.
