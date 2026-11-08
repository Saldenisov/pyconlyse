# Acquisition pressure reading and fault publication

The pressure path was traced from three calls in the copied Acquisition VI
through the custom TPG300 parser to the VAM-A shared-variable publication.
The relevant distinction is between a returned numeric value, the sensor's
Status output and a communication error. Acquisition stores the numeric
output without a wired Status or error predicate at these call sites. A
separate failure of the VAM-A publication sets two stop banks. These are
different conditions and must not become a single Python validity flag.

This analysis adds fixed checks of 89 direct nets across thirteen diagrams,
including the complete direct graphs of the VAM-A loop body, all three
sequence frames and both publication-error cases. It does not establish
full Acquisition coverage, pressure-based hardware protection, external
driver behavior or equivalence to a complete running Python server. All
work used saved binary resources. No VI was run or saved, and no remote,
PSP, VISA or hardware operation was issued.

## Source identity and reproduction

| Copied source | Source SHA256 | Immutable XML archive SHA256 |
| --- | --- | --- |
| TPG300/Data/TPG300-Get Pressure-Status.vi | 00EAA9357276529C2B70FF44B2AC0C64CCA88D77FD3FF2C15844AA1CC51520B8 | 5D499121F595353D24CED9F93CFABA162E9AB8AF05C912D576734FA704E166CC |
| TPG300/SubVI/TPG300 Point -- Terminator.vi | 218B7B9B12B437D65A14086DAC53FC58F7EE4C2DFEC3EFE7BA64ECBC440274CE | C5AD9A875DF3EC4A410BC28A37A9A3A50F44C352C2E97E35D227133BB660712C |

Both sources reside beneath
`C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300`.
The new archives are
`legacy/xp_acq_agent/data/source_exports/TPG300_pressure_XML_20261002.zip`
and `TPG300_point_XML_20261002.zip`; each contains three XML resources and
a source/export manifest. The source hashes were checked before and after
static extraction. The exporters refuse existing target directories or
archives. These exports do not replace any earlier archive.

The root checks use the existing pinned
`0_ACQ_ELYSE_XML_sha6fe8.zip`. Both helper archives and each XML resource
are hash-checked before graph validation. The public connector slots,
primitive slots, complete direct operation/net sets and relevant local
directions are checked independently of the simulation fixtures.

```powershell
python tools/validate_acq_tpg300_pressure.py legacy/xp_acq_agent/data/source_exports
python tools/validate_acq_vam_status.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_tpg300_pressure.py tests/scripts/test_elyse_acq_source_facet_register.py tests/device_servers/control/test_elyse_acq_vi_tpg300_pressure.py
```

## Root sensor selection and storage

Loop `59483` contains sequence `48312`, whose frames execute in order
`48320`, then `52460`. Fixed checks cover all 14 direct nets and operations
in those two frames. Each frame contains an independent 500-ms Wait.
The Wait is not wired as a pre-read delay, and the two calls within the
first frame do not acquire a dataflow ordering from their visual placement.
These facts do not establish a fixed wall-clock sampling interval: each
frame also waits for its calls to return.

| Frame | Call | Session local bank | Sensor argument | Returned pressure bank | Returned Status |
| --- | --- | --- | --- | --- | --- |
| 48320 | 46178 | 52 | 0 | 53 | unwired |
| 48320 | 53865 | 51 | 0 | 54 | unwired |
| 52460 | 52475 | 51 | 3 | 60 | unwired |

All three error outputs feed separate Simple Error Handler calls, whereas
their pressure outputs feed local writes directly. No Boolean case guards
those assignments. The incoming error and outgoing VISA/session ports
of these caller instances are unwired. This proves absence of a wired
last-good-value hold or sensor-Status gate at these sites; it does not
prove that a failed or nonreturning external call produces a particular
number. Handler behavior and blocking remain external boundaries.

The saved stop-local polarity for this loop was already checked in
`validate_acq_stop_ingress.py`; it is not counted again here.

## Custom parser and decimal separator

Pressure helper diagram `86` has 16 direct nets and no nested error case.
Index String Array appends the selected member of `[A1, A2, B1, B2]` to
the literal `P`. The four evidenced selections therefore produce `PA1`,
`PA2`, `PB1`, `PB2`. The first two root calls select `PA1`; the third selects
`PB2`. These are command strings in the projection, not transmitted
commands. The standard primitive's concatenation semantics are documented
by [NI Index String Array](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/index-string-array.html).

The helper passes WriteRead=False to Driver Core. Core timeout and retry
inputs are unwired here, so its previously checked saved defaults apply
at this boundary. The returned Core error and session flow to their public
outputs independently of numeric parsing. Core's protocol behavior is
documented separately in the
[command and error trace](ELYSE_ACQ_TPG_PROTOCOL_TRACE_2026-10-02.md).

The response flows first through `TPG300 Point -- Terminator.vi`. Its saved
comparison is the literal comma equal to the literal period, not a locale
query. False case `164` contains loop `281`; True case `166` is an unchanged
string pass-through. The saved False path starts at offset zero, searches
for an escaped period, concatenates before-match + comma + after-match,
then advances to the offset past that match. The Select primitive chooses
this changed string when a match exists and the original loop string when
none exists. Continue-if-True receives offset-past-match >= 0. Thus the
saved path replaces every period and performs a final no-match iteration
without appending an extra comma. All four diagrams and 20 direct nets,
including the unused True case, are checked. The primitive meanings are
confirmed by [NI Select](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/select.html)
and [NI comparison to zero](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/greater-or-equal-to-0.html).

The pressure helper then splits at the first comma. Decimal String To
Number receives the prefix; Fract/Exp String To Number receives the
suffix. Their numeric outputs are saved I32 and DBL, respectively.
The latter primitive's use-system-decimal-point input is unwired. Under
the documented default True, conversion depends on the system decimal
separator. For example, `0,1.23E-5` becomes `0,1,23E-5`; the two conversion
inputs are `0` and `1,23E-5`. Replacing the entire path with Python's plain
`float()` would not preserve this input handling. See
[NI Fract/Exp conversion](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/fract-exp-string-to-number.html).

The saved Status indicator default is 5, but it is not connected to the
Decimal String conversion's default terminal. That primitive's unwired
default is I32 zero, not the indicator's saved value. A missing comma
leaves the whole string on the prefix side and an empty suffix; malformed
conversion, overflow, nonfinite values and the actual LabVIEW locale
require separate verification. The distinction between indicator defaults
and parser defaults follows the saved wiring and
[NI Decimal String conversion](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/decimal-string-to-number.html).

## VAM-A consumer and publication fault

An exhaustive saved-root census finds one local writer and one local
reader for each pressure bank 53, 54 and 60. Their readers feed bundle
`21214` in diagram `45859`, updating fields 10, 11 and 20 of bank 41.
The same bundle reads bank 41 through `9174` and writes the resulting
whole cluster through `30536`. No pressure threshold or permission
predicate lies on these three direct input edges.

Another whole-cluster writer, `46917` in diagram `46898`, updates fields
63 and 32–39 using bundle `46933`. These are the only two bank-41 local
writers in the saved root. They are not independent concurrent writers:
both are in sequence `45836` of loop `20601`, with frames `45859`, `46898`,
then `77141`. The second frame reads the cluster after the first frame's
write completes and preserves its pressure fields. An earlier provisional
race interpretation was rejected after tracing this shared sequence.

All direct operations and 35 nets in the loop body and first two frames
are now checked, in addition to the publication proof below. The numeric
field transfers are:

| Saved input | Destination | Transformation |
| --- | --- | --- |
| Loop iteration I32 | VAM-A[0] and local bank 40 | DBL conversion for VAM-A; original counter for bank 40 |
| Local banks 32 and 31 | VAM-A[1] and [2] | I32 to DBL |
| Local banks 53, 54 and 60 | VAM-A[10], [11] and [20] | Pressure DBL unchanged |
| Bank 59 DBL array | VAM-A[12..18] | First seven of saved eight cluster elements; eighth unused |
| Bank 66 DBL array | VAM-A[32..35] | Saved four-element cluster, unchanged |
| Bank 67 DBL array | VAM-A[36..39] | Saved four-element cluster, unchanged |
| Bank 62 I32 | VAM-A[63] | I32 to DBL |

Array To Cluster and ordered unbundle implement the three array transfers.
Their output sizes are pinned at 8, 4 and 4; the input/output elements are
DBL. The correspondence between array index and cluster order is documented
by [NI Array To Cluster](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/array-to-cluster.html).
Short-array behavior and physical meanings or units of these raw fields
are not assigned by this proof. No pressure threshold or conversion from
pressure to a permission Boolean occurs anywhere in these three frames.

Publication diagram `77141` reads bank 41 and supplies it to
`ni.var.psp://10.20.30.2/SUPERVISION/VAM-A`. Its returned error supplies
Boolean case `28682`. False diagram `40197` is empty. True diagram `42989`
assigns literal True to local banks 30 and 45. These three diagrams have
four direct nets. This is a communication-publication stop request, not
a decoded pressure alarm or proof of a physical emergency-stop sequence.
The successful case does not clear either stop bank.

The loop body's independent Wait literal is `0x50`, or 80 ms, not 50 ms.
Its Stop-if-True terminal receives a separate snapshot of bank 30. There
is no dataflow edge forcing that read to follow publication. **Supported
inference:** a stop set by the publication-error case may first be consumed
on the next iteration if the current stop snapshot was already read.
The source therefore does not justify an immediate same-iteration stop or
a hard 80-ms emergency-response bound. Inputs read from other loops can
also represent different acquisition times; the ordered VAM-A writers do
not by themselves provide a synchronized input epoch.

## Python transfer and verification limits

`vi_simulation/tpg300_pressure.py` contains the pure separator-loop step,
first-comma split, four supported command strings and pressure assignments
from supplied I32/DBL/error snapshots. It intentionally does not emulate
localized numeric conversion. Sensor Status does not gate the root write;
the error snapshot is preserved for the handler boundary. A separate pure
function returns the publication-fault stop assignments. There is no
socket, PSP publication, VISA call, sleep, clock or hardware adapter.

`vi_simulation/vam_status.py` projects both ordered field-copy frames from
full-sized numeric bank snapshots. The second frame preserves the first
frame's new pressure values. Its stop decision uses an explicitly supplied
stop snapshot rather than substituting a later publication failure.

Golden fixtures distinguish multiple periods, a final no-match iteration,
empty and missing-comma responses, nonzero sensor Status, returned errors
and publication success versus failure. Source mutations test changed
case polarity, loop polarity, separator literals, sensor selection,
Status/pressure substitution, reader identity, bundle-field identity and
publication-fault assignment. Fixture guards delimit the ASCII/I32/DBL
projection domain; they are not additional LabVIEW control predicates.

The original-member facet register now names 40 identities; the separate
copied-vendor register names 50. These counts are not percentages or fully
closed diagrams; the original 533-diagram census is not automatically
promoted by facet presence. Native screenshot reconciliation and the
existing Word evidence document have not been updated in this continuation.

Next Acquisition work is the producers of banks 59, 66 and 67, the
physical meaning and consumers of these raw fields, all permission/interlock
predicates, cross-loop state timing, normal/fault stop and restart. The
current pressure path alone cannot certify the installation's protection logic. No
Supervision analysis is included.

## Verification and preservation

The full selected Acquisition source/mutation suite passed 293 tests in
524.92 s before the final VAM-A validator and three source-test methods
were added. The final affected pressure/VAM-A/register selection passed
23 tests in 23.93 s; the earlier full-suite count does not constitute
a full regression of the later VAM-A addition.

The final Acquisition controller/projection selection passed 216 tests in
3.08 s. Isolated VI-model tests passed 163 tests on Python 3.11 in 0.306 s.
Pytest used `--deny-network -o addopts=`. The only pytest warning concerned
an already imported module-isolation plugin, not a failed source check.

Ruff check passed on the eleven Python files touched by this continuation,
with the inherited package-name rule N999 ignored; all eleven passed the
format check. The 17 original VI
members, original LLB, both copied pressure/separator sources and existing
initialization/shutdown Word document retained their hashes. The manifest
was read explicitly as UTF-8. No unrelated worktree changes were reverted,
and no commit was created.
