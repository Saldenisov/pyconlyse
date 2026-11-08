# Acquisition command procedure evidence

Every direct graph inside command events 3–25 of the original Acquisition VI is now checked against independently recorded, non-actuating Python plans. The scope contains 159 stacked frames, seven nested focal cells, four For bodies and two While bodies: 172 diagram identities and 694 direct nets. Typed assignments, waits, task selection, publication chains and retained cluster fields are covered.

This closes the nested command-procedure **graph facet**, not the whole Acquisition program. External-call completion, event delivery, concurrent snapshots, restart and source-matched native images remain separate obligations. No VI was run or saved, and no XP, NI, PSP, VISA or serial operation was performed.

## Source and reproducibility

Original `0_ACQ_ELYSE.vi` SHA256:
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
Pinned export: `legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`, SHA256
`6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.
Archive and BDHb hashes are checked before qualification. The source is not the modified `ACQUISITION_VIs_verified` review copy.

The existing envelope validator checks every NewVal gate: True enters the sequence; False is empty; OldVal is unwired. The duration argument is 1000 ms for event 3 and 150 ms for events 4–25; not every procedure consumes it. The new `tools/validate_acq_linear_procedures.py` classifies every operation and consumes every direct net, including literal fanout. Unexplained nodes or wires fail. Specialized validators cover conditioning recurrence and counter task graphs. Their interpretation is compared with `DeviceServers/control/elyse_acq/vi_simulation/procedure_sequences.py`, whose plans are stored independently of the decoder.

```powershell
$env:PYTHONPATH='C:/dev/pyconlyse/tools;C:/dev/pyconlyse;C:/dev/ELYSE-ACQ-analysis/converter/test-deps'
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/validate_acq_linear_procedures.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest tests/device_servers/control/test_elyse_acq_vi_procedure_sequences.py tests/scripts/test_elyse_acq_linear_procedures.py tests/scripts/test_elyse_acq_source_facet_register.py --deny-network -q
```

## Command correspondence

Indices below denote local-cluster fields, not physical pins. C3 is bank 17, C4 bank 15, DPS bank 36 and EPS bank 44. Transitions are requested software assignments, not measured hardware states. Every procedure writes ACTION=True; no ACTION permission predicate occurs inside these procedures. The complete field lists, frame UIDs and publication order are retained in the Python plans.

| Event | Registered request | Stacked frames | Principal operations |
|---|---|---:|---|
| 3 | Cooling start | 12 | C3[0,3] and C4[0,2] True→False;1000-ms waits; intermediate800/500-ms waits; status completion; DPS publication with independent5000-ms wait |
| 4 | Cooling stop | 7 | C3[1] False→True;400-ms wait; C3[4] False→True with150-ms waits in both assignment frames; EPS/DPS completion |
| 5 | General modulator start | 10 | C4[0] True→False;1000-ms wait; C4[2] True→False twice, with another1000-ms wait |
| 6 | General modulator stop | 17 | Focales OFF with cleared error; then C4[8,17,6,4,1] False→True pairs and status completion |
| 7 | Heater stop | 4 | C4[4] False→True; EPS[14,15]=False, EPS[17]=True; DPS[5]=False |
| 8 | PREMA stop | 4 | C4[6] False→True; EPS[20,21]=False, EPS[23]=True; DPS[7]=False |
| 9 | HT relay stop | 4 | C4[17] False→True; EPS[26,27]=False, EPS[29]=True; DPS[9]=False |
| 10 | FOCAL stop | 5 | Focales OFF with error handler; C4[8] False→True; EPS[32,33]=False, EPS[35]=True; DPS[11]=False |
| 11 | Modulator reset | 4 | C4[2] True→False; EPS[36]=False; DPS[12]=False |
| 12 | Heater start | 7 | C4[3] True→False;3000-ms wait; C4[2] True→False; EPS/DPS completion |
| 13 | PREMA start | 8 | C4[5] True→False;500-ms wait; C4[2] True→False;250-ms wait; EPS/DPS completion |
| 14 | HT relay start | 8 | C4[16] True→False;500-ms wait; C4[2] True→False;250-ms wait; EPS/DPS completion |
| 15 | FOCAL start | 8 | C4[7] True→False;29000-ms wait, Focales ON,1500-ms wait; C4[2] True→False;250-ms wait |
| 16 | Magnet supply start | 16 | Three C3 enabling groups; selected C6/C7 fields zeroed; four C7 conditioning ramps; command/status publication |
| 17 | Magnet supply stop | 7 | Selected C6/C7 fields zeroed and published;1000-ms wait; eighteen C3 fields False; status/output publication;200-ms wait |
| 18 | Attenuator and phase start | 4 | C4[29]=True; EPS[39]=True, EPS[42]=False; DPS[13]=False; DPS→EPS→C4 publication |
| 19 | Attenuator and phase stop | 4 | C4[29]=False; EPS[39]=False, EPS[42]=True; DPS[14]=False; same publication order |
| 20 | HT supply start | 5 | C4[18] True→False; EPS[45]=True, EPS[49]=False; DPS[15]=False; DPS→EPS→C4 publication |
| 21 | HT supply stop | 5 | C4[19] False→True; EPS[45]=False, EPS[49]=True; DPS[17]=False; same publication order |
| 22 | HT supply reset | 5 | C4[20] True→False; DPS[16]=False; DPS→EPS→C4 publication without an EPS assignment |
| 23 | Modulator pulse start | 4 | Start task3, clear its error, start task4, clear its error; EPS[52]=True, EPS[55]=False; DPS[18]=False |
| 24 | Modulator pulse stop | 5 | Poll/stop task3, then task4; clear errors; EPS[52]=False, EPS[42]=True; DPS[19]=False |
| 25 | Magnet supply zero | 6 | Selected C6/C7 fields zeroed and published;1000-ms wait; EPS/DPS completion;200-ms wait |

Event 14 is the HT relay request; event 15 is FOCAL. These labels must not be swapped during migration.

## Focal stabilization and error routes

Event 15 frame 40293 contains three cells: 46840 requests 29000 ms, 48404 calls `1_Focales ON.vi` and passes its error to Simple Error Handler, and 49054 requests 1500 ms. C4[7] precedes these cells; C4[2] follows them. Converting this path into a simple on/off call would omit the stabilization interval.

General-stop event 6 sends Focales OFF error to `Clear Errors.vi`, whose error output is unused. Separate focal-stop event 10 sends the same helper error to `Simple Error Handler.vi`. Both subsequently request 500 ms in their nested sequence. Neither caller has an error-status Case that selects whether to advance. This does not prove immediate handler return: modal UI and external-call behavior remain boundaries. Existing focal-helper source proofs remain separate; no instrument communication was repeated.

## Magnet conditioning

Each event 16 For body reads C7 and replaces fields 0,1,3,4,6,7,8,9 with its arithmetic result, preserving fields 2 and 5. The result also feeds the right shift register. An independent 100-ms Wait shares the body; it does not order the local write.

| Parent frame | Body | Iterations | Initialized seed | Per-iteration operation | Approximate final request |
|---|---|---:|---:|---|---:|
| 44981 | 48496 | 160 | 0.0 | previous +0.1 | 16.0 |
| 41847 | 41875 | 320 | 16.0 | previous −0.1 | −16.0 |
| 39014 | 39041 | 320 | −16.0 | previous +0.1 | 16.0 |
| 42572 | 42635 | 160 | 16.0 | previous −0.1 | approximately0.0 |

First written values are 0.1,15.9,−15.9,15.9, not the seeds. A 20000-ms frame follows each of the first three ramps. The sum of requested waits is 157200 ms: 960×100 ms, three 20000-ms holds, two 500-ms startup waits and a final 200-ms wait. This is not a measured duration or upper stop deadline.

The recurrence uses initialized [LabVIEW shift-register semantics](https://knowledge.ni.com/KnowledgeArticleDetails?id=kA03q000000YKYuCAO&l=en-US). Repeated binary64 addition is retained; seed+i×step would alter accumulated rounding. No native numeric oracle was run. The independent test oracle converts binary64 operands exactly into high-precision Decimal and rounds after each addition.

Magnet-stop event 17 zeros C7 field 5; magnet-zero event 25 retains it. Both retain C7 field 2 and C6 field 8. The approximately ±16 values are saved requests, not a claim about actual DAC output range, scaling or applied voltage.

## Counter task sequencing

Event 23 unbundles task fields 3 and 4 from local 21. Task 3 Start error feeds Clear Errors, whose output supplies task 4 Start error-in. Task 4 error feeds another Clear Errors with unused output. This establishes ordered dependencies and removal of the preceding error, not successful task execution.

Event 24 polls task 3 in body 2745, then task 4 in 49233. Each loop has ordinary task/error tunnels and no shift register. Done property 6414 is compared with True; index i is compared with 40 using Greater; their non-inverted OR feeds Stop-if-True. Property error goes to Stop Task rather than an exit predicate. Each body independently requests 1 ms.

If all calls return and Done stays False, indices 0–41 produce 42 polls. This is not a 42-ms upper deadline. Each poll is followed by `DAQmx Stop Task.vi` and `Clear Errors.vi`; Clear Errors is not DAQmx Clear Task. Task 4 is reached only after the first poll/stop/clear frame completes.

Saved completion assigns EPS[42]=True and EPS[52]=False while retaining EPS[55]. Field 42 also appears in the attenuator/phase stop path. The projection preserves this cross-subsystem assignment; treating it as a defect and changing it would require a separate decision.

## Concurrency and external outcomes

Bundle updates produce whole-cluster writes from explicit local-read snapshots. They are not atomic patches into the latest global state. A concurrent change to an otherwise untouched field can therefore be overwritten. The projection returns complete writes without silently adding a lock or merging new state.

PSP publications retain saved error-chain order and finish at Simple Error Handler. First error inputs are unwired. Publication requests are not delivery evidence: PSP success, behavior under incoming errors and handler completion are not executed. Same-frame waits and writes remain unordered; the 150-ms argument does not establish an exact physical pulse width.

## Verification and remaining coverage

The focused source/model selection passed 21 tests in 52.32 s with network denied. The final source/envelope/register selection passed 14 tests in 135.31 s; the complete `test_elyse_acq*.py` controller/projection lane passed 286 tests in 4.07 s. These are separate selections, not a claimed rerun of every Acquisition source validator. Mutations visit all 166 sequence/cell frames, focal error routes, conditioning feedback graphs and counter property/comparison/stop polarity. All 960 conditioning iterations and both 42-index Done fixtures pass. Eight affected Python files pass Ruff after formatting.

The broader regression initially rejected `types.MappingProxyType`. The package boundary test now permits only that named immutable, in-memory wrapper; other imports from `types` and all hardware/network imports remain disallowed. The final lane passes. All 17 original member byte hashes and the source LLB hash still match the source manifest.

The named-facet register now contains 347 original source identities, up from 175. The 172 additions have no overlap. Of the 533 census identities, 186 lack register entries: 143 root-VI diagrams and 43 helper diagrams. These are registration counts, not complete-coverage percentages; earlier partial evidence for some unregistered diagrams remains valid. Neither global completion flag was changed to True.

Next critical paths: initialization caller frames and error arms, both beam-line selection event bodies, remaining lifecycle/controlled-stop graphs and restart integration. Unmatched dispatch selectors, active Diagram Disable metadata and short-array returns remain unresolved. Native source-matched screenshots and the initialization/deinitialization Word revision are still required. No Supervision completion or full-VI lvkit qualification follows from this command-procedure proof.

Native review was attempted after static qualification. The returned local 32-bit LabVIEW window was `0_ACQ_ELYSE.vi Front Panel *`, window ID 1245628, marked disabled. Listing owned windows did not expose a modal or diagram. After one activation/re-observation, the tool returned a ChatGPT window instead of the selected LabVIEW target. App input stopped; no coordinates or keyboard actions were sent. Those screenshots are not Acquisition evidence. The source identity of the open VI was not established by this attempt.

## Initializer caller and AI-test continuation

`validate_acq_initializer_caller_frame.py` adds fourteen original direct graphs and 52 nets, without overlap with the 347 preceding registrations. Frame 227 and its eight error arms account for 29 nets; frame 133 and four fallback arms account for 23. Qualified call identities, complete net sets, connected/unwired connector slots, typed literals and task-reference destinations are checked. Existing narrower selector/sequence-local proofs are reused rather than counted as new observations.

| Caller order | Saved node | Arguments and returned assignments | Error path |
|---|---|---|---|
| NI6602 | 593 | Eight task references to local 21 | Initial error input unwired; returned error selects pass/Clear Errors 383 |
| NI6071E | 262 | /1/PFI0, /2/PFI0, 5000 Hz, 10 samples; task references to locals 23 and 24 | Previous gate output supplies error input; returned error selects pass/Clear Errors 1532 |
| DIO96 | 500 | Six task references to local 22 | Previous gate output supplies error input; returned error selects pass/Clear Errors 1416 |
| NI6703 | 620 | Four task references to local 25 | Previous gate output supplies error input; returned error selects pass/Clear Errors 1843 |

Task assignments lie outside error Cases. A returned error therefore does not prevent the saved caller from assigning returned task references or reaching the next initializer after boundary calls complete. Error clearing does not establish task validity, successful initialization or apparatus readiness. The final gate result reaches the next-frame NI6071E read through sequence local 1063. Clear Errors returns are explicit Python fixtures, not assumed success.

Frame 133 reads C1/C2 task snapshots through locals 23/24. Its sample-count connector 2642 is **unwired**; the initializer's literal 10 must not be silently copied into this separate read call. Returned arrays are unused here. Returned error 1309 fans out to selector 2107 and raw-error sequence-local terminal 25688. The raw error remains distinct from the fallback result held in sequence local 306.

Any `error.status=True` selects the fallback, regardless of code. The annotation −200284 is not an equality predicate. The error arm orders Clear Errors 2134 → Clear Task 4034 (C1) → Clear Task 7931 (C2) → NI6071E initializer 1198. Reinitialization uses /1/20MHzTimebase and /2/20MHzTimebase, 5000 Hz and 10 samples, and replaces locals 23/24. Its returned error selects pass-through or Clear Errors 2268. No second test read or retry loop is present in these five direct graphs. Standard-call completion remains supplied.

`initialization_caller.py` preserves these dependencies using opaque task tokens and explicitly supplied error returns. Its fixtures cover all 81 combinations of the four initializer error arms and selected Clear Errors returned statuses. Errors with status False pass through even when code is nonzero. The original pilot-read error remains available after a cleared fallback; clearing must not turn pilot presence into an aggregate initialization-success indication. NI6071E public error-output seeding remains unresolved at the integration boundary.

Five further parent graphs add four nets: outer initialization frame 188, first frame 20362, both clock-sync flat cells and final startup parent 7580. The first clock cell requests 200 ms. The next contains the saved command `net time \\10.20.30.2 /set /y` and routes System Exec error to Simple Error Handler. Return code, stdout and stderr are unused. No error-status or return-code gate prevents card initialization after these calls return. The command was read from source, never executed. Handler completion and unwired System Exec defaults remain boundaries. The final parent passes the original pilot-read error into the five-frame startup sequence, whose order is pinned independently of fallback clearing.

Two discovery graphs add fourteen nets. Their exact operation and literal populations complement the earlier property/open, auto-indexing and error-register proof in `validate_acq_psp_discovery.py`. Enumeration of `ni.var.psp://10.20.30.2/SUPERVISION` supplies child references. For each child, Data Type property output supplies dynamic-open type, returned property reference supplies open reference, and returned error feeds the next iteration through a paired shift register. Returned open references form the array written to local 61. A 1-ms Wait shares each body without ordering against open. There is no expected-name/count whitelist, successful-open filter, retry or exterior handler for final loop error.

`psp_discovery.py` records this path with explicit enumeration/property/open fixtures and opaque reference/type tokens. Zero children preserves the supplied enumeration error as the unused final error. Other fixtures retain every returned reference even when supplied errors are True. No actual enumeration, property read, dynamic open or network command occurs.

Initialization Diagram Disable 76550 has explicit saved `activeDiag=01`, `defaultDiag=01`, `commentMode=True` and `CommentSelLabFlags=1C`. This metadata is **present here**, unlike the separately reviewed cooling structure. Its two saved arms are 76558 (73 nets and named variable-open operations) and 76564 (empty). Parent 1356 and empty arm 76564 add two direct-graph facets and one net. They do not establish native compilation/runtime activation from a display caption. The metadata distinction is pinned by rejecting mutations.

The separate `validate_acq_named_variable_open_arm.py` qualifies all 73 direct nets in sibling 76558. Its 24 operations are ordered by the error chain: C1, C2, six DIO input/output banks, four AO banks, C1011, C12, DPC, DPS, EPC, EPS, VAD, VAM-A, VDM-A, VTA, VTL and VTS. All 24 local references are **reads** feeding dynamic-open type terminal 0A. They do not write values into these banks, send command publications or actuate cards. Every returned variable reference and access output is unwired. Error arrives through comment tunnel 76736, passes through all opens and reaches Simple Error Handler; handler outputs are unused. Exact URI lengths/content, six-port contracts, local identities/directions and matching data types are pinned. The inert sibling trace requires explicit branch selection and 24 returned errors; activation is not silently inferred.

The source-facet register now contains 371 identities. The remaining 162 unregistered census identities comprise 119 root diagrams and 43 helper diagrams. These counts remain registrations, not complete behavioral coverage. Both completion flags remain False. All saved initialization parent/direct-frame graphs now have named graph facets, but helper integration, native activation, restart and whole-program coverage remain open. Next critical paths are both beam-line events, lifecycle/restart and the previously listed dispatch/native gaps.

The census cross-index explicitly selects the complete original outer initialization subtree `0_ACQ_ELYSE.vi/root/sequence:359[1]`: 29 diagram identities, with no missing facet registration. Its independently enumerated identity set is tested. This establishes graph-facet accounting across every saved initialization frame/arm/body, not successful external initialization or complete callee/native/runtime behavior. The new continuation contributes 24 of these identities and 144 direct nets; five final-startup identities already had their own proofs.

Final continuation verification: 310 Acquisition controller/projection tests passed in 4.50 s; the final caller/named-open/register selection passed 41 tests in 125.07 s. After adding the explicit initialization-subtree assertion, all three register tests passed in 0.11 s. The earlier 63-test caller/gate/fallback/discovery selection passed in 77.36 s before the last metadata/named-open additions; it is not claimed as a complete final source-suite rerun. Mutations cover every new caller/parent/fallback graph, all 73 named-open nets, every named URI/local-read direction and saved activation fields. Ten affected Python files pass Ruff and its format check. All 17 original VI byte hashes and the original LLB hash still match the manifest. No LabVIEW Run/Save, remote control, PSP/VISA/serial call or apparatus write occurred.
