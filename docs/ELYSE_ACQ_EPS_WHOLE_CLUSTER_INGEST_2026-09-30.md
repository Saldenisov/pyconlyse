# Acquisition EPS whole-cluster ingest and local-writer coverage

## Question and source boundary

Can the saved ACQ root VI's cooling or Modulator status assignments be
treated as persistent local state until another event changes that field?
No. The saved graph contains a separate whole-cluster EPS read in the
runtime Timeout event. This is a static wire result from the hash-pinned
`0_ACQ_ELYSE_XML_sha6fe8.zip`, not an observation of the deployed VI or
PSP delivery. No VI, PSP variable, XP computer, or NI card was operated.

## Observed graph

- Exactly 27 write-side `gRef paramIdx=44` (EPS) terminals occur in the
  saved ACQ root diagram. Twenty-five receive fieldwise `nMux` outputs.
  Initialization `gRef 30267` receives a zero-valued cluster literal from
  `sRN 33056` terminal `25379`. Runtime `gRef 18021` receives the data
  terminal `20015` of `sharedVariableDynamicRead 19997`.
- The latter read is in runtime `eventStruct 43`, Timeout event 0 diagram
  `53`, ordered sequence `10111` frame 0 diagram `10115`. Its URI input
  `19999` is wired from constant terminal `20078`, decoded as
  `ni.var.psp://10.20.30.2/SUPERVISION/EPS`. The read's data terminal
  `20015` is directly wired to the EPS local writer terminal `18028`.
- Among the 25 fieldwise local writes, only three select EPS field 8:
  cooling-start event 3 sets it True via `nMux 18625`; General-Modulator
  start event 5 sets it True via `nMux 35487`; General-Modulator stop event
  6 sets it False via `nMux 28738`. Cooling-stop event 4 and Timeout
  flow-trip frame 5 do not themselves assign field 8.
- A separate [sibling-loop path](ELYSE_ACQ_EPS_PUBLICATION_CONCURRENCY_2026-09-30.md)
  writes ACQ's local EPS to the same Supervision EPS PSP variable. The
  saved code therefore contains an ACQ→PSP publisher and a later
  PSP→ACQ whole-cluster ingest. It is not a one-way status register.
- The hash-pinned Supervision root graph contains one direct literal for
  its `localhost/SUPERVISION/EPS` URI. It feeds the previously traced
  [Supervision EPS read](../tools/validate_sup_eps_ingest.py) inside runtime
  While loop `5846`, not a direct write at that literal. The saved loop
  topology makes repeated reads possible, but no actual cadence is measured.
  This does not exclude dynamically constructed URIs or writes outside the
  inspected root graph.

## Inference and unresolved timing

If the Timeout read returns an older remote EPS snapshot, its whole-cluster
assignment can replace a just-set local EPS[8] or other field. That is a
possible execution order, not a measured occurrence. Read errors,
freshness, PSP buffering, Supervision-side writes, and sibling-loop
scheduling have not been resolved. Conversely, a successful publisher
before the read may return the newer value. The direct event-frame status
tables remain valid **only at those frames**, before another writer runs.

The non-actuating Python projection
`project_timeout_remote_eps_ingest(remote_eps)` models the conditional
whole-cluster replacement with strict 77-Boolean input validation. It
performs no network read and claims no transport timing. A unit test shows
that an explicitly supplied older snapshot can replace a local True
EPS[8]; it does not assert that this occurred in the installed system.

## Reproduction

```powershell
python tools/validate_acq_eps_local_writer_coverage.py legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip
python tools/validate_sup_eps_ingest.py Supervision/analysis/source_exports/0_SUP_ELYSE_XML_sha2257.zip
python -m unittest tests.device_servers.control.test_elyse_acq_status_projection
```

The validator checks archive/member hashes, all write-side EPS local
references, upstream node classes, whole-cluster data and URI wires, and
the complete fieldwise EPS[8] writer set. It does not certify runtime
delivery or scan all subVI-internal state.
