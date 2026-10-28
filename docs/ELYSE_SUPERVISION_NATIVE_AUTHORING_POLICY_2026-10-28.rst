SuperVision helper authoring: native-only policy and failure evidence
==================================================================

Scope and decision
------------------

New SuperVision helper diagrams must be created, wired, edited and saved by
LabVIEW 2020 x86, then exported with native Save for Previous Version 12.0.
Python may copy exact files, prepare project XML, inspect saved resources and
validate packets. Python must not serialize a new or modified VI diagram for
this integration. The generated main-VI variants and failed helper repairs are
quarantined; they are not deployment candidates.

This boundary follows observed native-load failures and the extraction tool's
explicit writer limitation. It is not a claim that every generated file is
invalid or that a single malformed field explains every load failure.

Discriminating observations
--------------------------

* Generated complete main and small Setup candidates failed while loading in
  LabVIEW 2020 x86 with ``Hex0x2 Memory is full``. A small failed Setup was only
  18,282 bytes. File size alone does not explain the failure. A later process
  snapshot after the main failure showed private memory of 474,361,856 bytes and virtual
  1,256,087,552 bytes; ordinary address-space exhaustion was not established.
  These observations do not attribute the error to LabVIEW 2012 execution.
* Stopped native main source could display both FP and BD. Its missing NI Vision
  Development Module functions prevented complete source compilation on the
  local host; that baseline is not hardware/runtime proof.
* The complete Setup wrapper was assembled through the native editor.
  Native Save produced 20,658 bytes, SHA256
  ``1de01a7e5d18fa231866dfe257dc268b067de58e4eefa54a9b10438682cf202c``.
  A byte-identical renamed copy opened FP and BD in a fresh project without
  MemoryFull or a dirty marker. No Run occurred. This establishes a working
  native-authoring path for that wrapper, not complete camera qualification.
* Qualified native Epoch remains 30,736 bytes, SHA256
  ``f6bb97d1eab2f87ca932391219fefb04e88e089db9057445f814b1d981ebcc01``.
  Its 3,840-case post-save source evaluation is an offline graph audit, not an
  executed LabVIEW test.
* Native End was then edited from that Setup copy by changing action 1 to 3 in
  the editor. Save produced 20,657 bytes, SHA256
  ``f008064011b25e240b12cd777d34124a88cef64daeddb659e8327c4ed5ed22a7``.
  Its ten native signal endpoint lists, FP/connector/link resources and original
  image/error identity remained unchanged. The saved BD changed only the U32
  action literal and one edited numeric text flag. Evaluation of the actual End
  and Epoch graphs passed 256 End cases; no LabVIEW execution occurred. The
  tracked record is ``receipts/supervision_native_end_source_20261028.json``.

The trusted native one-wire fixture is especially informative. Its Save changed
13 resource sections: DFDS 1,977->1,989 bytes, CNST 40->48, SUID 100->108;
46 VCTP TopLevel mappings, 19 TM80 client flags and 8 DSInit fields also changed.
The original DTHP count/shift stayed unchanged. In the visible diagram, the
operation added one wire and changed the connected terminal. Preserving old
compiled/default-data caches while changing graph connectivity therefore did
not reproduce the native compiler's complete transformation. Which particular
field, combination or source-only convention was loader-essential remains
unresolved.

Terminal flag values cannot be transferred between native contexts. An
intermediate one-wire native Save used input TERM 0x8000. The complete native
Setup later used input 0x9000/output 0x1000, matching the bits in an unqualified
repair. Neither observation establishes a universal flag formula or proves a
flag-only repair valid.

What lvkit and pylabview establish
--------------------------------

The locally inspected lvkit 0.8.6 source is a VI reader, renderer, comparer and
experimental Python generator. Its README states that it does not write VIs.
Its extractor installs process-wide pylabview patches intended for reading.
The warning is at:

``C:\dev\ELYSE-ACQ-analysis\converter\lvkit\src\lvkit\_pylabview_patches.py:16-22``

That source explicitly forbids writing VIs through the patched environment;
details at lines 61-73 identify password-salt, integrity-validation and type-annotation
changes. The actual builder prepended that checkout, distinct from the default
environment's ``lvkit-0.8.7-clean`` tree. Runtime source paths matter more than
the package name or a presumed installed version.

The final overlay imported ``build_native_container_probes`` ->
``lvkit.extractor`` -> read-only patches before ``saveRSRC``. It disabled
``updateRSRCData`` and supplied BDPW integrity manually. The intermediate
``repack_helpers.py`` subprocess instead used bare pylabview with seven local
compatibility/inverse patches. Working and failing candidates shared the final
overlay route. The tool warning establishes an unsupported writer boundary;
it does not isolate the particular Setup failure.

Both failed candidates and trusted native files passed ordinary UID, list,
type-reference, connector and parser checks. The raw failed Setup contained
21 FP controls while lvkit's decoded view exposed 19. Decoded graph completeness,
parser acceptance, route geometry and model agreement cannot replace a native
load test or serve as an authoritative VI writer schema.

Supported native construction route
-----------------------------------

NI documents creation from templates, labeled object lookup, replacement and
native terminal wiring:

* `Creating a New VI from a Template Using VI Scripting
  <https://www.ni.com/docs/en-US/bundle/labview/page/creating-a-new-vi-from-a-template-using-vi-scripting.html>`_
* `Wiring Objects Using VI Scripting
  <https://www.ni.com/docs/en-US/bundle/labview/page/tutorial-wiring-objects-using-vi-scripting.html>`_
* `Enabling VI Scripting
  <https://www.ni.com/docs/en-US/bundle/labview/page/enabling-vi-scripting.html>`_

The native 2020 installation contains these examples under
``C:\Program Files (x86)\National Instruments\LabVIEW 2020\examples\Application Control\VI Scripting``.
All 63 example VIs were inspected offline without changing their original bytes.
No generic path+object-label+terminal-map authoring runner was found in those
examples. Template/Scratch expose an Operation selector for fixed arithmetic
demonstrations. Add Terminals to Connector Pane has a VI-path control but performs
fixed assignments. Other wiring demos use fixed targets. The Random Strip Chart
example explicitly runs its generated VI and must not be invoked unchanged for
stopped authoring.

For a small helper, native manual editing of an exact template copy is the
shortest route. For repeated creation, native-edit one G scripting runner from
the installed template example. Use New VI for template copying, Open VI Object
Reference for labeled objects, SubVI:Replace with a matching connector, and
Terminal:Connect Wire for explicit terminal references. The Scratch example
already demonstrates SubVI Terms[], terminal indexing and Control.Terminal.
LabVIEW creates and maintains its own types, call fields, geometry and caches.

The installed COM typelib exposes Application and VI orchestration interfaces,
not NewVIObject/GObject/ConnectWire diagram interfaces. Python or LabVIEWCLI may
invoke a previously native-created scripting VI; their presence does not provide
a direct text-to-G compiler. No COM/CLI authoring operation was tested here.

Installed ``vi.lib\_script\XML Scripting`` helpers emit native XML command
strings; these are not pylabview RSRC heap XML. The reviewed SubVI(Path), Wire(BD)
and ToXMLString interfaces do not establish a supported general XML-to-VI runner.
An undocumented internal generator is not a substitute for the documented
native template/wiring route without its own qualification.

Lifecycle and integration invariants
-----------------------------------

* Begin creates exactly one RunStamp per actual producer run, initializes Epoch
  action 0 with that value and returns the same timestamp. End uses the same
  RunStamp and Epoch action 3 after producer quiescence. They do not own queues or
  start/stop workers. Renaming a Setup file to Begin/End does not implement these
  contracts; the required native edits and post-save audit must follow.
* SetupObserve passes the actual channel widened to U32 and the actual successful
  setup observation into Epoch. It returns the original error unchanged. No
  channel remap, inferred physical domain or second NI task is introduced.
* FrameTap preserves image/error identity and owns a nonreentrant
  check->copy-attempt->commit gate. Enforce the 1000 ms copy limit, U32 tick-wrap,
  current-run/capture/new-frame/error/time guards and commit after an actual
  observer attempt. Splitting permission and copy into independently unlocked
  calls would violate the atomicity requirement.
* Native queue owner retains data/stop refs across parallel producer/workers,
  signals stop before worker join and releases refs afterward. Keep existing
  SuperVision XML 8766 and camera 8768 contracts. Acquisition and SuperVision run
  on separate hosts; app-local queues do not cross that boundary.
* SyncTap observes only the existing ``C10-11 NI6602`` control. Configured values
  and control-read errors are software observations, not NI write acknowledgments
  or measured physical waveforms.

Qualification and preservation
-----------------------------

Each new helper requires native stopped FP+BD Open/Save, a fresh closed dependency
copy, and read-only validation of its actual saved connectors, constants, links,
error identity, timestamp origins and RunOnOpen=False. Then export 12 natively
and preserve the relative dependency tree and exact hashes. Offline source tests
remain separate from native load/compile, executed behavior and XP integration.

The existing three native 12.0 sync helpers under
``legacy/labview/supervision_telemetry/individual_helpers`` remain pinned by their
manifest and verifier. Native export has passed; execution on LabVIEW 2012/XP is
not established by that packet. Preserve existing canonical observer/queue files.
Do not overwrite originals, running VIs, vendor files or an open authoring copy.

Detailed local forensic evidence is retained under
``.tmp/supervision_native_candidates/individual_camera_helpers_20261028/forensic_call_profiles_20261028``:
``FINDINGS.md``, structural/resource differences, one-wire compiler deltas,
runtime importer identities, parser results, call-shape checks and bounded
DSInit/DCO readback. The alternative-tool inventory and source hashes are under
``.tmp/supervision_camera_main_builder/native_authoring_alternatives_20261028``.
These local diagnostic records are evidence references, not release payloads.
