# Native12 lifecycle subset

Four native-exported helpers are included. FrameTap is unfinished and excluded;
the complete camera pipeline is not ready. No LabVIEW 2012/XP runtime or hardware
test is claimed.

| Helper | Bytes | SHA256 |
|---|---:|---|
| `SUP_Camera_Epoch.vi` | 29372 | `84b78999901b37537f83c5c480777f22bee98a1f78d153ea93739e57738c8a3e` |
| `SUP_Camera_SetupObserve.vi` | 22419 | `4317fdaefa8e1d20950db20fc84724f50d5dee5770884d78eed9590040c2e61e` |
| `SUP_Telemetry_Begin.vi` | 22483 | `b6431ae4ac0497f8de9bb0b9cdc2f2c1c656b101f9642ea4c7d6748423a4e62d` |
| `SUP_Telemetry_End.vi` | 22389 | `bf9cdf4865fe50c16768b5e7a0ca6ede3cc8a082a53d98652dab73e08b3884c3` |

Each source has native LabVIEW 2020 x86 Save and stopped fresh-project FP/BD
evidence. The checks used the existing process; Epoch was already loaded as a
callee before its FP/BD were shown. No process restart or cold-process test is
claimed. The payloads were exported by native Save for Previous Version 12.0.
Setup used the guarded native COM exporter; the other three used the native GUI.

The Epoch retains earlier generated-source history. The admitted source and
payload bytes were last written by native LabVIEW Save/export. That history is
recorded rather than described as wholly native construction. A generated-only
candidate cannot pass the release guard, even if graph/model tests pass.

`SUP_Camera_Lifecycle_2012.lvproj` lists all four helpers. It is ordinary project
XML derived from the byte-identical native-exported
`SUP_Native_Lifecycle_Fresh_Proven_2020.lvproj`, with one Setup item added. No VI
body was serialized or patched. Native URLs use `../file.vi` for same-folder
files, anchored at the project file. Filename-only URLs fail this check; missing
files are never admitted through a search fallback.

All three callers link to same-folder Epoch. All four retain the system
dependency `/<vilib>/vision/Image Controls.llb/IMAQ Image.ctl`; that NI library
is not bundled or installation-qualified here. Canonical observer/queue files
outside this subset are unchanged.

Actual exported source checks passed: Epoch 3840 cases, Setup 48, Begin 1280,
End 256. Each VI retains 21 FP controls and the native 12-port ABI. Begin returns
the same single UTC timestamp used to initialize Epoch; End invalidates only
the matching run. Error/image identity remains intact. These are offline source
evaluations, not executed VI tests. The reader cannot decode the exported DFDS
cache (31 compressed resource bytes, 204 expanded bytes); it was not rewritten.

The universal connector retains unused fields. Begin's logical RunStamp is
output 2; End takes it at input 10. Begin/End do not start or stop workers.
Native queue ownership, stop-before-join and final reference release remain part
of later native assembly in a copy of the actual project.

From repository root:

```text
python tools/verify_labview_native_helper_package.py
python tools/verify_labview_sync_native12_package.py
python -m unittest tests.unit.test_labview_native_helper_package
```

The preflight verifies pinned bytes, each native event receipt, project/custom
link closure and last-writer provenance. It never loads or runs LabVIEW.
