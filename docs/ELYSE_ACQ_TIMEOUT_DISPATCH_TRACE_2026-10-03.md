# Timeout procedure and NI6602 caller: complete explicit source graphs

## Boundary and evidence

The scope is Timeout frame22247, all25 explicit DPS selector diagrams,
both counter Boolean arms and its three ordered True frames. The
hash-pinned original root export is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`
(SHA256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`).
Root VI SHA256 is
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`.

The [validator](../tools/validate_acq_timeout_dispatch.py) checks all31
direct operation/net graphs, 60 nets, selector ranges, saved tunnel links,
local read/write identities, bank shapes, property targets/order/codes,
event registration, constants, call connectors and PSP destination.
The [inert projection](../DeviceServers/control/elyse_acq/vi_simulation/timeout_dispatch.py)
does not import a driver or send an event, PSP command or physical write.

## Procedure ingress

Bank36 is a29-Boolean DPS cluster. ClusterToArray21295 feeds
Search1DArray22203, which searches for literalTrue; its start-index input
is unwired. The first match index goes to bank43 (`indice de l'élément`)
and Increment17616. The incremented value selects Case8105.

For an all-False snapshot, first match is-1 and selector0 writes
`ACTION` bank35=False. For selectors1..24, the selected property node
writes `Value=True` followed by `Val(Sgnl)=True` to its saved DDO. Property
error-in/out terminals have no direct wires. This frame does not clear
DPS bits or write ACTION in these24 request arms.

The [24-row mapping](ELYSE_ACQ_DPS_DISPATCH_MAP_2026-09-29.csv) is now
checked against fixed independent source identities, not trusted as an
unverified generated artifact. Event indices in DPS field order are:

```
DPS0..23 -> event3,4,5,6,12,7,13,8,14,9,15,10,11,18,19,20,
                  22,21,23,24,16,25,NONE,17
```

DPS22, selector23, targets DDO66459 (`Alimentation aimant = PT`). No
registered event in EventStructure43 uses that DDO. Its property writes
exist; a downstream hardware procedure must not be invented. A registered
event is a target correspondence, not proof that its handler completes.

All29 fields enter Search1DArray. DPS24..28 can therefore produce
selectors25..29, outside every explicit saved range. `SelectDefaultCase`
is absent in this original export. An older native review describes a
case0 Default, but the visible selected-case index alone cannot establish
this for the pinned source. The projection preserves these tail selectors
and marks their effects UNSUPPLIED; it does not silently truncate DPS to24
fields or replace a tail request with no request. Multiple True bits select
only the first match; this is not an atomic multi-command dispatcher.

## NI6602 ingress and ordered effects

This is an independent graph within the same frame, not an error chain
from the DPS properties. A bank39 snapshot supplies field32 as selector n
and supplies the complete33-DBL timing cluster. Bank21 supplies eight task
references. Case23199 is selected by the strict predicate
`n > 0 AND n < 17`; False23208 is empty.

True23214 has Sequence23633 in the following fixed order:

| Frame | Source graph | Proven controller operation |
|---|---|---|
|0|23641|Compute q=floor((n-1)/2), task[q], timing[2q] and timing[2q+1]; call1_ACQ_WRITE_NI6602; returned error to Simple Error Handler|
|1|22979|Read bank39 again, replace field32 with-1.0, write whole bank39|
|2|1507|Read bank39 again, publish to C1011NI6602; error-in/out are unwired|

For integer n=1..16, adjacent pairs select the same task and same C10
delay/width fields0..15. C11 timing fields16..31 are not selected by this
Acquisition caller. The helper call's input7 is task, input9 is delay and
input10 is width; error-in8 is unwired. Its returned error0 reaches handler
input9. Handler outputs are unwired, and no error condition gates the
subsequent reset/publication frames. This is a controller completion path,
not successful reconfiguration or guaranteed modal-handler completion.
The [helper proof](../tools/validate_acq_ni6602_writer.py) covers the helper's
stop/poll/property/restart wiring separately.

The visible guard also admits fractional DBL n. Their numeric IndexArray
coercion is not closed. The projection records acceptance but leaves task
and timing indices UNSUPPLIED instead of truncating or rounding silently.
Timing values are passed unchanged; negative fixture values do not create
a caller-side validation rule absent from this source.

Reset/publication each use a fresh local read. Another independent writer
may change timing or field32 between them. A golden fixture can therefore
publish a newer field32 value rather than the reset-1.0. No atomic snapshot,
successful acknowledgement or fault-stop guarantee follows from the frame
order alone.

## Reproduction and remaining gates

Verification:18 focused source/projection tests passed in201.04s. Mutation
subtests cover every24 property target and every24 True literal, orphan
event registration, counter guards/tunnels/reset gates and fabricated
default metadata. Projection fixtures cover all24 targets, five tail
selectors, all16 admitted integer requests, fractional acceptance,
error-return reset and independent publication snapshots.

```powershell
python tools/validate_acq_timeout_dispatch.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_timeout_dispatch.py tests/device_servers/control/test_elyse_acq_vi_timeout_dispatch.py
```

Remaining: source-matched native screenshots of every arm, numeric default
dispatch, fractional coercion, event scheduling/handler outcomes, concurrent
local epochs and the subsequent cooling-flow frame. Complete direct graphs
do not close Acquisition as a whole. Original LLB and VI members are not
modified, run or saved.
