# Acquisition event envelopes and Boolean procedure entry

## Scope and source

The [source validator](../tools/validate_acq_event_envelopes.py) covers all26
event diagrams of EventStructure43 and both arms of each of the23
procedure-entry Cases. This is72 direct graphs/73 nets, including the
previously registered Timeout53. Nested sequence bodies are not promoted
to complete coverage by proving their entry envelopes.

The original root SHA256 is
`6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF`;
the pinned archive is
`legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip`,
SHA256 `6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527`.

## All procedure-entry gates

Every procedure event3..25 contains exactly two labels, one U32 literal,
one EventDataNode and one Boolean Case at its direct envelope level.
EventDataNode fields5/6 are saved Boolean `OldVal`/`NewVal`. Only field6
feeds the Case selector; OldVal is not wired into this entry predicate.

All23 False arms are empty. Each True arm contains exactly one sequence,
with one duration input wire. No ACTION, EPS or DIO-input local occurs in
these entry envelopes. This does not exclude a guard inside the nested
sequence, an upstream Supervision gate, event registration semantics or
a separate hardware interlock. An already supplied NewVal=True event
selects its True envelope regardless of the current ACTION local.

The wired U32 entry argument is1000 for event3 cooling start and150 for
events4..25. It is a source argument, not a measured pulse interval or
permission. Its downstream Wait consumers require their own frame traces.

Timeout0 and line-change events1/2 directly enter their sequences; they
do not have this Boolean entry envelope. Their direct operation/net graphs
are included, but this projection does not implement line transfer.

## Magnet-zero correction and registration limit

Event25 (`Alimentation aimant = 0V`, DDO66443) has Case38772,
False38786 and True38792. NewVal port38765 feeds selector38774;
True enters sequence38798. Thus NewVal=False does not execute its zeroing
sequence in the pinned original. The older native ledger described the
six inner frames and did not visibly include an outer wrapper. That is
not evidence that the wrapper is absent; the source correction supersedes
such an inference.

Event25 has saved `regFlags=-2147483647` (`0x80000001`), unlike1 for
events1..24. This flag is checked exactly and retained in the inert
projection, without assigning the extra bit an unproven locking, enable/
disable or delivery meaning. The source frame proof is conditional on
that event being handled; registration does not prove execution.

## Python parity and reproduction

The [entry projection](../DeviceServers/control/elyse_acq/vi_simulation/event_envelope.py)
accepts an explicit event index and Boolean NewVal, and returns only an
entry decision, entry argument and registration flag. It sends no event,
does not run a sequence and does not authorize hardware operation.

```powershell
python tools/validate_acq_event_envelopes.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python -m pytest --deny-network -q -o addopts= tests/scripts/test_elyse_acq_event_envelopes.py tests/device_servers/control/test_elyse_acq_vi_event_envelope.py
```

Mutation fixtures cover each23 NewVal field against erroneous OldVal
selection, removal of the magnet-zero gate and normalization of its
special registration flag. Projection fixtures cover all46 Boolean entry
combinations. The7 focused tests passed in76.36s with network denied.
Native screenshots, event delivery/locking semantics,
remaining nested permission/acknowledgement/fault loops and full lifecycle
restart remain separate closure gates. No VI or hardware was operated.
