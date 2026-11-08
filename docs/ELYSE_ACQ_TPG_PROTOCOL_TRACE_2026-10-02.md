# Acquisition TPG300 command and error control

The copied `TPG300-Driver Core.vi` has 30 saved diagrams. Fixed operation and
wire checks now cover their direct graphs: the previously checked three
outer facets contain 25 nets, and the remaining 27 contain 199 nets. The
analysis also traces both polling conditions, nine Boolean case structures,
command framing, byte recognition, sequence locals and returned-error
replacement. This closes those named static facets, not all Acquisition
behavior, external VISA behavior or native screenshot coverage.

The control question is whether an unsuccessful pressure-controller exchange
must return within its nominal timeout and what error Acquisition receives.
The saved graph does not establish a universal time bound: both byte-read
branches bypass the elapsed-time predicate. The warning helper can also
clear an entire returned error independently of its incoming status.

## Source identity and reproducible checks

Driver Core source SHA256:
`7A0ECCF170459E5B56F49E38AA613246B17D09E9E118ABC73BE2C0B019488F2B`.
The immutable startup export remains
`legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip`,
SHA256 `AE6CC7EE631BEE764738D09E1E9787916BC1AAC01B843A50DB669C60F5A2CDB1`.

The additional copied `TPG300 suppress warning.vi` source SHA256 is
`1F2EF5A5BA6309D0077D9B7E944B4DA8C9F08DEE08D95B859D70FA91C4FC7FC9`.
Its new static export is
`legacy/xp_acq_agent/data/source_exports/TPG300_warning_XML_20261002.zip`,
SHA256 `98D236E7CFEC98086E9E81260CF9483AA7E6DA50B677F6C79122361B8ADAD92E`.
The helper contains three diagrams and seven direct nets. The export script
refuses to overwrite evidence and checks the copied VI before and after
resource extraction. It does not load LabVIEW.

```powershell
python tools/validate_acq_tpg300_protocol.py legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip
python tools/validate_acq_tpg300_warning.py legacy/xp_acq_agent/data/source_exports/TPG300_warning_XML_20261002.zip
```

The source checks bind primitive identities and argument indices, every
case's False/True frame order and tunnel identities, register pairing,
ordinary error/session inputs, sequence-local origins, byte concatenation
order, fixed literals and saved front-panel token bindings. XML has not
been substituted for a new native screenshot. No VI was run or saved.

## Command and acknowledgement sequence

The outer sequence orders four frames: command construction `184`,
acknowledgement `229`, response `987`, and retry/error processing `155`.

| Step | Saved nodes and diagrams | Observed dataflow |
| --- | --- | --- |
| Frame command | Case 1674, diagrams 1636/1642, String Subset 1720, concatenate 170 | WriteRead=False selects the first three command bytes; True selects the full command. Append one CR byte in either case. |
| Check serial buffer | Property 1968, case 1677 | Query Number of Bytes at Serial Port. Returned error.status selects normal 826 or error bypass 829. |
| Begin normal exchange | Read 3151, sequence 269, Write 1940, Wait 318 | Request a read of the available old bytes, then write the framed command, then request a 50-ms wait. The timestamp is supplied by Tick Count 298 in the write frame. |
| Recognize acknowledgement | Loop 2041, body 371, case 1678, nested case 1683 | Poll byte count. Initially offset=-1 and buffer is empty. Search fresh bytes for saved ACK=06 and NAK=15 only while offset<0. |
| Enter response phase | OR 1580, NOT 1592, case 1685 | Execute response only when both phase-one flags are False. This is not a test of error.status or WriteRead. |

The acknowledgement parser's Match Pattern node `1856` uses output slot 5,
**after substring**, on terminal `1873`. It appends the bytes after ACK to
the old buffer. It does not append the prefix before ACK. The independent
NAK search uses node `1830`, offset output `1849`; its absence predicate
feeds both Boolean outputs of the fresh-byte branch. Once a previous ACK
offset is nonnegative, diagram `583` appends the whole fresh chunk, stores
constant offset=1 and supplies True. NAK is not searched again in that arm.

The Match Pattern primitive semantics are checked against [NI documentation](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/match-pattern.html):
a missing match yields offset=-1, an empty after substring, and the original
before substring. Thus fresh noise without ACK is discarded by this initial
arm, even if the fresh chunk contains CR. The pure projection is restricted
to the saved one-byte tokens; it is not a general regular-expression engine.
Command truncation uses the byte-based [String Subset semantics](https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/functions/string-subset.html).

## Polling conditions and their limits

Both loops use Continue if True. Their actual conditions are `381` and
`1162`, not the Boolean error outputs at the loop boundary. Tick-difference
arithmetic is saved as U32; the comparison is strictly elapsed<timeout.
The timeout control's saved value is 600 ms. Initialization explicitly
supplies 700 ms to its PNR calls, as established in the startup report.

| Branch | Buffer and offset | Continue gate before CR test | Returned flags A and B |
| --- | --- | --- | --- |
| ACK, no fresh bytes, 475 | Keep buffer and previous offset | elapsed<timeout | NOT elapsed<timeout; NOT offset>=0 |
| ACK, fresh bytes before recognition, 625 | Append after ACK; use offset past ACK or -1 | NAK not found | NAK found; NAK found |
| ACK, fresh bytes after recognition, 583 | Append whole chunk; offset=1 | True | False; False |
| Response, no fresh bytes, 1258 | Keep buffer and previous offset | elapsed<timeout | NOT elapsed<timeout; NOT offset>=0 |
| Response, fresh bytes, 1357/1387 | Append whole chunk; offset=1 in both arms | True | False; False |

Each candidate buffer is searched for CR. Store the prefix before CR in the
buffer register; continue only if CR was absent AND the branch gate above.
The no-data arm requests another 50-ms wait only while elapsed<timeout.
The fresh-byte arm has no such wait and does not use elapsed<timeout as its
continuation guard. Response writes saved ENQ=05 through sequence `1058`,
then requests a 50-ms wait before its polling loop `2059`.

**Supported inference:** a continuing stream without a terminating CR can
keep a fresh-byte arm running beyond 600 or 700 ms. ACK search can likewise
continue if fresh chunks contain neither ACK nor NAK. The outer Retry=3
limit is therefore not a total exchange deadline: its comparison runs only
after the inner sequence returns. This source-level counterexample does
not establish that the installed hardware generates such a stream, nor
does it quantify VISA call latency.

The error/session inputs of both polling loops are ordinary tunnels, not
feedback registers. Their returned errors are published but do not feed
the checked Continue AND gates. The standalone projection consequently
does not invent an additional `if error.status: stop` condition. Actual
property/read returns, blocking calls and runtime error effects remain
external boundaries. A no-data timeout after recognition produces A=True,
B=False; a NAK in the initial ACK search produces True/True. These flags
must not be collapsed prematurely into a generic communication status.

## Returned error and retry relationship

The phase-two gate's False arm `1025` forwards phase-one buffer, flags and
error. Its True arm `1044` supplies the response loop outputs. Sequence
locals `1542` and `1521` then feed the final OR; local `688` supplies the
error cluster. Bundle `798` replaces error.status with this OR and leaves
code/source unchanged. The outer loop continues only while this status is
True AND Retry>i; default Retry=3 permits four returning attempts.

The final helper unbundles error field 1, code, and compares it to the I32
literal `0x3FFF0006` (1073676294). False diagram `108` forwards the entire
input cluster. True diagram `116` replaces it with a literal zero cluster:
status=False, code=0, source="". No incoming status condition accompanies
this comparison. This is a replacement of the whole cluster, not merely
removal of a warning flag. It happens after the outer loop returns, so it
cannot retroactively change the preceding retry decisions.

## Non actuating Python transfer and remaining work

`vi_simulation/tpg300_protocol.py` projects command bytes, the phase gate,
the property-error bypass and one polling iteration from supplied state,
byte-count, read-byte, elapsed-time and error snapshots. It never accesses
a clock or sleeps. The requested wait is returned as metadata.
`vi_simulation/tpg300_warning.py` projects the returned-cluster replacement.
Neither file connects to Tango, PSP, sockets, VISA or a hardware adapter.

Golden tests distinguish ACK from NAK, ACK split from subsequent CR, noise
without ACK, NAK after recognition, both response subcases, strict timeout,
the fresh-byte timeout bypass, returned VISA faults and code-only warning
replacement. Representation checks are Python-only constraints; they do
not claim that every supplied fixture is physically reachable.

Remaining Acquisition gates include the root's full concurrent scheduling,
all event/stop bank writers and permission predicates, shared-state faults,
cancellation/restart, malformed numeric/array behavior and reconciliation
with native diagram screenshots. Vendor graph facets remain separate from
the original 533-diagram census. No Supervision analysis occurred here.

## Verification and preservation

The complete selected `tests/scripts/test_elyse_acq*.py` source/mutation
suite passed 287 tests in 524.63 s. The current ELYSE controller/projection
selection passed 276 tests in 3.46 s, and the isolated VI-model selection
passed 151 tests on Python 3.11 in 0.377 s. The controller selection includes
historical Supervision projections; their execution does not constitute
additional Supervision review. Pytest used `--deny-network -o addopts=`.
The nonfatal warning concerned an already imported pytest isolation plugin.

Ruff check passed for the ten changed Python files with the inherited
package-name rule N999 ignored; their format check passed. The original
17-member manifest, source LLB, four copied TPG VI sources and existing
initialization/shutdown Word document were rehashed without drift. The
first preservation command used the Windows default text encoding for
the manifest and failed to locate an accented filename; the corrected
explicit UTF-8 read verified all 17 originals. It was not a missing source.

The new helper export is additional immutable evidence, not a replacement
for the original startup archive. The vendor register names 45 diagram
identities, while the original-member register remains at 32. Neither
register declares whole-program or native-evidence closure. No physical
operation, VI run/save, remote control or Word revision occurred.
