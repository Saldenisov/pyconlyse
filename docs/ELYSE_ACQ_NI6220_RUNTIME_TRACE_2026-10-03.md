# Acquisition NI6220 runtime state and VAM-A correspondence

The NI6220 runtime loop supplies six averaged measurements and two
WCM arrays to VAM-A. Current/captured array writes have four entries, but
the original saved WCM arrays are empty, as the later saved-data proof below
establishes. The copied source establishes the
relative-change predicate, explicit counter cases, sampling arguments,
local assignments and ordered frames. It does not yet establish every
implicit selector default, short Array To Cluster result or lifecycle state. This
report therefore adds source facets, not full Acquisition closure.

## Source and reproducible verification

The root is `0_ACQ_ELYSE.vi`, SHA256
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.
The hash-checked XML is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`,
SHA256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.

`tools/validate_acq_ni6220_runtime.py` pins all direct operations and
61 direct nets in 14 saved diagrams. Ten diagrams belong to the active
caller/calculation path; four belong to its Diagram Disable structure,
including two empty nested selector arms and the empty active arm. The
inactive diagram reads bank39 and extracts field3 into a selector whose
two explicit cases are empty; it is not an alternate NI6259 reader.

```powershell
& C:/Users/elyse/miniconda3/envs/pyconlyse312/python.exe tools/validate_acq_ni6220_runtime.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
& C:/Users/elyse/miniconda3/envs/pyconlyse312/python.exe -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_ni6220_runtime.py tests/device_servers/control/test_elyse_acq_vi_ni6220_runtime.py tests/device_servers/control/test_elyse_acq_vi_vam_status.py
```

## Caller order and independent stop read

While loop47483 has body47487. Call44966 invokes
`1_ACQ_READ_NI6220.vi` with sample count from bank57 and task from bank56.
Its returned array enters sequence15804 through port47134, which supplies
frame47080 through47133 and then frame48574 through48581. The sequence
orders the WCM calculation before the six point-by-point means.

The returned error is connected to `Simple Error Handler.vi` call48083,
not to the data-frame selector or the loop condition. A returned error
does not, by this caller wiring alone, suppress the data assignments or
request stop. This does not mean the error handler always returns or
that failed DAQmx reads always return a sufficiently long array.

The body also writes its iteration to bank62, requests a 15-ms Wait and
reads Boolean stop bank30 into a Stop-if-True condition. These operations
have no sequencing wire relative to the read/error handler. The stop
snapshot is not a cancellation argument. The previously verified reader
requests DAQmx timeout -1; therefore 15 ms is neither a loop-period
guarantee nor an emergency-stop latency bound.

## Relative WCM change and counter cases

Frame47080 selects returned-array indices4,5,6,7 and builds one
four-element current array. Mean call136243 receives that array. Mean
call135586 receives the prior bank65 array, whose local read48168 has
saved flags5 rather than the usual read flags1. These exact flags are
retained without assigning an unverified meaning to the additional bit.

Add18880 adds the DBL literal0.03 to the prior mean. Greater136891 tests
the current mean against that sum:

```text
change = mean(current[4:8]) > mean(bank65_before) + 0.03
```

Equality selects False. This is an offset relative to the previous
array, not an absolute0.03 threshold or a comparison against zero.
Both Boolean branches write the current array into bank65. The True
branch additionally writes the old bank65 array into bank67 through
the separate tunnel62733/62724. It does not write the new array there.

Bank68 is U32, labelled `Iteration WCM` in its saved type; both Increment
primitive ports are also U32. The selector read and the increment's local
read are separate nodes, not a shared wire. Their snapshots remain
separate in Python. Bank63, used only to select the displayed smoothed
value, is U16.

| Change branch | Bank68 selector | Diagram | Proven assignments |
|---|---:|---|---|
| False | 0 | 104729 | No counter or bank66 write |
| False | 1 or otherwise unmatched | 100537 | Read bank68 again, increment, write bank68; explicit default index01 selects this arm |
| False | 3 | 100569 | Current four-element array to bank66; U32 zero to bank68 |
| True | 0 | 81862 | Read bank68 again, increment, write bank68 |
| True | 3 | 81868 | Current four-element array to bank66; U32 zero to bank68 |
| True | Otherwise unmatched | Unresolved | SelectDefaultCase is absent; displayed dIdx1 is not proof of default dispatch |

The conditional interpretation is a delayed capture: a rising comparison
can start the counter, subsequent False/default increments can advance
it, and selector3 captures a later current array. This interpretation is
not promoted to a fully verified state machine: True selectors1/2 and
the initial/reset state still require closure. Repeated True comparisons
also replace bank67 repeatedly; the wiring is not a one-shot latch.

## Six statistical calls and the eight-element conversion

Frame48574 contains six distinct `NI_PtbyPt.lvlib:Mean PtByPt.vi` calls,
all with sample length20. Each call receives one scalar, not the whole
NI6220 sample matrix. Its remaining input slots are unwired. Their saved
reset/default behavior and hidden statistical state are not replaced by
a guessed Python moving-average implementation.

| Bank59 position | NI6220 returned-array index | Mean call UID |
|---:|---:|---|
| 0 | 0 | 48830 |
| 1 | 1 | 48930 |
| 2 | 2 | 48951 |
| 3 | 3 | 48972 |
| 4 | 8 | 48993 |
| 5 | 9 | 49014 |

Build Array49035 assembles exactly these six outputs into bank59. Bank63
indexes this six-element array for scalar indicator48792. The source-typed
Index Array returns DBL0.0 when the index is outside0..5; the later typed
default proof below closes this particular standard-function boundary.

The previously verified VAM-A frame45859 converts bank59 into a saved
eight-DBL cluster, then copies seven cluster elements into VAM-A12..18.
Thus VAM-A12..17 correspond to six Mean outputs. VAM-A18 comes from a
cluster element for which this producer supplies no array entry; the
eighth cluster element is unused. The earlier eight-element Python
fixtures were full-sized synthetic boundary fixtures, not proof that
eight measurements were produced.

The [NI Array To Cluster reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/array-to-cluster.html)
establishes configurable size and index-to-cluster ordering. Its inspected
text does not establish this short-input result. No zero, retained value
or extra measured channel is inferred. `first_frame_from_conversion`
accepts the actual six-element array only with an explicitly supplied
eight-element conversion return and checks that its existing entries
match the source array.

VAM-A's next frame46898 copies bank66 into fields32..35, bank67 into
36..39, and bank62 into field63. These are raw saved field identities;
their physical units and permission/interlock consumers are not inferred
from the array names. In particular, bank65's legacy label
`C1_NI6259_4:7` does not identify the caller hardware: the active qualified
callee is `1_ACQ_READ_NI6220.vi`.

## Python projection and remaining closure gates

`vi_simulation/ni6220_runtime.py` contains pure caller projections with
explicit NI Mean, point-mean and increment returns. The six statistical
calls retain distinct node identities and sample-length arguments.
Read errors are preserved for the handler boundary. Stop remains an
independently supplied snapshot. Unsupported True/default dispatch and
short Array To Cluster conversion remain unresolved. Missing entries in
the three typed scalar Index Array nodes instead return the documented
DBL default0.0; they are no longer treated as unknown.

The projections do not import a driver, connect a socket, sleep, send
PSP commands or change the Tango/hardware adapter. No VI was run or saved.
No new native screenshots were captured and the existing initialization/
shutdown Word artifact was not revised. Static graph identities can be
checked from saved XML; they do not replace the requested native evidence.

Remaining Acquisition work includes explicit/default dispatch closure,
statistical-helper defaults, complete reset/restart behavior, short-array
conversions and source-error returns, permission/interlock consumers,
cross-loop timing and the remaining event/stop diagrams. The original
533-diagram census remains a structural denominator, not an assertion
that all diagrams have complete behavioral proof. The named-facet overlay
at this stage referenced61 original identities and50 copied-vendor identities,
including the subsequent seven-diagram Timeout read/display proofs;
those counts are not closure percentages.

## Whole-root local-register census

The [register validator](../tools/validate_acq_runtime_local_registers.py)
adds a whole-root census of38 `gRef` sites in banks35/43/65/68. Bank65
has two writes (45510/206856) and one special-flags5 read (47080); bank68
has four writes and four reads, all inside the already inspected runtime
WCM branch. No `gRef` seed/reset writer for these two banks occurs in
initialization, cleanup or a separate event. Their runtime increment/
capture resets remain exactly those described above.

Bank35, saved typeBoolean/ACTION, has26 root-local writes and zero
root-local reads:25 literalTrue assignments and oneFalse in DPS case0.
Bank43 has one I32 root-local write, the dispatcher search result, and
zero root-local reads. Neither population establishes a permission gate.
This is not a full audit of primary terminals, property/VI Server access,
UI edits or hidden external effects. Saved control defaults, clear-on-call
properties and restart memory behavior remain separate gaps. The simulator
must require explicit prior WCM snapshots, not invent an initializer reset.

Three source/mutation tests passed in4.41s, rejecting an added ACTION read
and movement of the WCM counter writer into initialization. No original
census row was promoted to behavioral completion by this local-reference
facet. The current named direct-diagram overlay contains104 identities;
the separate vendor overlay remains50.

## Typed Index Array defaults and shared-lvkit correction 2026-10-04

The source audit now distinguishes a datatype's standard Index Array
default from absent Case metadata, loaded control defaults and short
Array To Cluster conversion. The archived
[NI LabVIEW User Manual](https://download.ni.com/support/manuals/320999e.pdf)
states that an index beyond array bounds returns the element-type default
(printed 6-11, PDF page 110), and lists the DBL default as 0.0
(table 5-1, printed 5-2, PDF page 72). This predates the saved 2012 program.
The current
[NI Index Array reference](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/index-array.html)
also documents defaults for empty arrays and expandable unwired indices.
These references establish primitive semantics, not actual failed DAQmx
returns or native execution of the copied VI.

`tools/validate_acq_ni6220_index_defaults.py` rechecks the existing
14-diagram/61-net caller proof, then independently pins all 25 terminals of
three Index Array nodes: one-dimensional DBL input, all 11 DBL outputs,
I32 index representations, expansion order, flags and display-index coercion.
No additional diagram identities or closure percentage are claimed.

| Frame / node | Supplied array | Index / output use | Missing-entry result |
|---|---|---|---|
| 47080 / 52275 | NI6220 reader return via47133→52281 | 4,5,6,7 → four-entry current WCM Build Array15699 | Each missing scalar is DBL0.0; four outputs still exist |
| 48574 / 48881 | Same reader return via48581→48884 | 0,1,2,3,8,9 → six separate Mean PtByPt input scalars | Each missing input is DBL0.0; Mean outputs/history remain supplied |
| 48574 / 48810 | Six Mean outputs from Build Array49035 | Bank63/U16→I32 port48818 → scalar indicator48792 | Indices6..65535 return DBL0.0 |

Conditional consequence: if a completed reader call returns an empty DBL
array, both data frames still receive it. WCM current has four zeros;
Selector 3 captures those zeros into bank66 in either threshold branch.
All six point-mean input scalars are zero, but their returned means are
not thereby proved zero. Read error status has no gating wire to these
frames or Stop-if-True. The Python fixture therefore retains a read fault,
data assignments and continued operation when the independent stop
snapshot is False. This is not evidence that a real fault returns an empty
array, that the error handler returns, or that hardware remains safe.

The current shared converter was not correct for expanded nodes52275 and
48881. Its generated source attempted scalar-to-tuple unpacking:

```python
element_0, out_3, out_5, out_7 = _lv.index_array(values, 4, 0.0)
element_0, out_3, out_5, out_7, out_9, out_11 = _lv.index_array(values, 0, 0.0)
```

Each right-hand side produces one DBL, not four or six values. Subsequent
wired indices were lost, including the nonconsecutive 8/9 pair. The
qualification grammar rejected these fragments before execution; it was
not relaxed to accept unpacking.

The shared checkout correction adds `generate_1d_index_array` to
`src/lvkit/codegen/nodes/ops/index_array.py`, with a narrow dispatch hook
in `primitive.py`. Each saved output/index row receives its own guarded
scalar lookup and unique variable; the array expression is evaluated once.
Unwired indices retain initial 0 / previous+1 progression even when an
earlier output is unwired. Explicit catalog templates still take precedence,
and unknown operation confidence cannot bypass the resolution gate.
Wired but unresolved array/index inputs fail explicitly rather than taking
unwired defaults. The
rank must be explicitly 1; unknown rank and N-D retain the previous path
and are not qualified by this correction. Floating-to-integer index
coercion is not qualified here; the ACQ indices are explicit I32 literals
or a U16 integer carried into I32.

The independent inert model now accepts any supplied immutable DBL reader
array length, including 0. Its four WCM entries and six statistical inputs
use typed scalar indexing; the six-result display uses the same rule.
At that stage, prior banks65/66/67 required explicit four-entry snapshots;
the subsequent saved-data correction below removes that overly narrow bound. Mean,
Mean PtByPt and Increment returns remain supplied. The downstream six-to-eight
Array To Cluster result is still an explicit supplied boundary, not silently
padded by this Index Array correction. NaN, infinities and signed zero
are copied at existing indexed entries, not sanitized; native statistical
arithmetic and NaN payload bits are not qualified.

`tools/qualify_acq_ni6220_index_defaults.py` generates only the three
original nodes using the updated shared checkout. Its execution grammar
permits pure assignments and `_lv.index_array` with DBL0.0 default; no
whole VI, Mean, driver, local/property writer or wait is executed.
The fixture corpus contains 85 array fixtures for each reader-index node
(lengths 0..16, nonfinite/signed-zero cases and 64 seeded random arrays),
65536 integer selectors for the display plus 28 special-value fixtures:
65734 comparisons across all 11 outputs.
The [receipt](../legacy/xp_acq_agent/data/converter_qualification/20261004_ni6220_index_shared/receipt.json)
pins generated fragments, source hash, converter fingerprint and fixture
SHA256 `B65199E05C644CE7D96F855614CE1106963D7CFE8EC2F4916A7B87F390B6EA4E`.
The final shared converter fingerprint is
`B2DA5EEF6B26C9B1C8741BF35B8C13F56C4933B4EAA3B996E9DD968238D1BBAC`.
The separate [stop regression receipt](../legacy/xp_acq_agent/data/converter_qualification/20261004_ni6220_index_shared/stop_regression_receipt.json)
requalifies the four earlier stop fragments against the same fingerprint:
826 fixtures retain their earlier result corpus SHA256
`1637573327704746DEC69DA69854C05A93A3028C6A51286F56829FAC64E29C9D`.

Reproduce the source/model and differential lanes using Python 3.11:

```powershell
$env:PYTHONPATH='C:/dev/ELYSE-ACQ-analysis/converter/lvkit/src;C:/dev/ELYSE-ACQ-analysis/converter/test-deps;C:/dev/pyconlyse/tools;C:/dev/pyconlyse'
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe tools/qualify_acq_ni6220_index_defaults.py
& C:/dev/pyconlyse/Supervision/analysis/lvkit_eval/.venv/Scripts/python.exe -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_ni6220_index_defaults.py tests/scripts/test_elyse_acq_ni6220_runtime.py tests/device_servers/control/test_elyse_acq_vi_ni6220_runtime.py tests/device_servers/control/test_elyse_acq_vi_vam_status.py
```

The affected selection passed 35 tests, 45 subtests, one pytest rewrite
warning in 316.69 s with external network denied. The final grammar additions
passed a separate 2-test/11-subtest lane in 0.15 s. The complete VI-projection
selection passed 315 tests, 1770 subtests and the same warning in 5.29 s.
The converter's 52 new scalar-index tests plus 35 neighboring array/catalog/
property regressions passed 87 tests in 0.91 s with the same explicit outbound
network guard installed; the external checkout does not expose the
repository's `--deny-network` option by itself.

The generic 1D expanded-node correction and its isolated tests form an
upstream commit candidate: `fix(codegen): lower expanded 1D Index Array per row`.
Its scope is `ops/index_array.py`, the dispatch hook in `primitive.py`, and
`tests/test_index_array_expanded_codegen.py`. The proposal must exclude apparatus files,
the ACQ receipt and other chats' existing converter edits, including the
separate DBL division change in `primitive.py`. No commit, push or PR was
created. Whole Acquisition remains open; next NI6220 gates include native
True-counter Default 81854, Mean state/default inputs, loaded WCM register
defaults and the eight-element conversion. No new native screenshot,
VI Run/Save, XP control or hardware command occurred.

## Saved measurement state and variable length correction 2026-10-04

The [saved measurement proof](ELYSE_ACQ_SAVED_MEASUREMENT_STATE_2026-10-04.md)
joins banks59/62/63/65/66/67/68 to original DCO/DFDS/front-panel identities.
Four arrays are stored empty; I32 loop iteration, U16 display index and U32
WCM counter are stored zero. Independent decoding checks26 bytes and all21
root local references. No initializer/final-cleanup gRef reset for these
arrays or counter is added; actual loading and restart remain unqualified.

The Python counter projection now accepts variable-length prior WCM arrays.
Supplied NaN and finite Mean(empty) fixtures distinguish first-pass False/0
from True/0 without guessing native Mean output. The True arm copies old
empty bank65 into bank67; either explicit counter3 arm captures the current
four-entry array into bank66. True unmatched-counter dispatch remains open.

VAM-A's two four-entry WCM conversions now require independent explicit
cluster returns for short arrays, just as its eight-entry bank59 conversion
already did. Mixed capture epochs are permitted fixtures, not atomic-sampling
claims. The consistency check retains NaN class, infinity and signed zero
without certifying native NaN payload bits or padding. Final verification:
410 model/register tests and1942 subtests passed in7.81s;64 focused source/model
tests and2560 subtests passed in89.19s, both with network denied and one warning.
No source diagram identity, native screenshot or whole-Acquisition closure
was added; no apparatus or live adapter changed.
