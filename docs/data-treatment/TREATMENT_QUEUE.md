# Treatment queue contract

Queue processing is a software-only extension of the existing treatment APIs.
It does not control Tango devices or hardware.

## Endpoints

All endpoints accept the optional `X-Treatment-Session-Id` header.

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/treatment/queue` | Return this session's queue snapshot. |
| `POST` | `/api/treatment/queue` | Validate, enqueue, and automatically start processing one recipe. |
| `POST` | `/api/treatment/queue/folder-set` | Enqueue one VD2 folder action and automatically start processing. |
| `POST` | `/api/treatment/queue/run` | Compatibility endpoint; start a stopped sequential drain worker. |
| `DELETE` | `/api/treatment/queue/<job_id>` | Remove a queued job only; running or terminal jobs remain immutable. |

`POST /queue` captures a complete recipe, including `profile`, `label`,
`convert_to_h5`, `cleaning`, output settings, input paths, map-selection state,
and input fingerprints. The response includes `queue_job.recipe` and the
updated `queue` snapshot. Output paths are reserved globally across queue jobs
and immediate saves within this backend process; normalized,
case/slash-equivalent duplicate reservations are rejected.

## Execution semantics

- Recipe and nested fields are deep-copied at enqueue. Later session edits do
  not change a queued job.
- Enqueue performs validation and fingerprint capture synchronously, then
  starts the software worker immediately. Hardware is never called.
- One worker drains each session in enqueue order. Jobs from different sessions
  are isolated. A job appended while the worker runs remains queued and is
  processed after the active job.
- Independent file conversions use up to
  `min(PYCONLYSE_TREATMENT_MAX_WORKERS, available CPUs, file tasks)` workers;
  the default configured limit is `6`.
- Job statuses are `queued`, `running`, `completed`, or `failed`; `phase`,
  `error`, preparation details, and saved-path receipt remain visible in the
  queue history.
- Queue state is process-local. Backend restart loses queued jobs; it does not
  claim durable scheduling.
- Immediate DAT saves commit through a temporary file and atomic replacement,
  so a failed write cannot leave a partial target. Writers outside this backend
  process are not covered by the reservation.

## DAT provenance manifest

Every successful DAT save also atomically upserts
`pyconlyse_treatment_manifest.json` in the DAT output folder. The manifest is
a stable JSON document with `format` `pyconlyse.treatment-manifest` and
`format_version` `1`. Its `dat_files` collection has one current record per
DAT file name; saving the same DAT again replaces that record instead of
duplicating it.

Each record contains the DAT file name and save receipt, workflow kind/profile/
queue job id, calculation settings, source folder, input role paths, and the
conversion and SAM-cleaning summaries that produced the result. This lets
downstream software discover a date folder's DAT files and reconstruct their
input and processing provenance without relying on terminal output or queue
history.

If an existing manifest is invalid JSON or has an unsupported format version,
the DAT is left intact and the save reports an error rather than overwriting
unrecognized provenance.

## Inputs and conversion

For independent `ABS`, `BASE`, and `NOISE` roles, a recipe may request
per-role HIS→H5 conversion and queued SAM cleaning. Conversion and cleaning use
private job paths/runtime state, preserving the interactive session. Queue
conversion is non-destructive: source HIS is never removed.
Raw H5 maps and their selection mask follow the [H5 map-selection contract](H5_MAP_SELECTION.md).

## Standard folder queue

`POST /queue/folder-set` captures one of `Set`, `Set/Convert`,
`Set/Convert/Clean`, `Set/Convert/Calc`, or `Set/Convert/Clean/Calc`. Queue jobs
run sequentially and preserve inherited `NOISE` from the previous completed
folder until a new `BRUIT`/`NOISE` file is present. Convert actions create and
verify canonical gzip H5 before removing HIS. Clean actions apply SAM. Calc
actions calculate OD and atomically write `<folder-name>.dat`; actions without
Calc do not save DAT.

When a Calc target already exists, it is retained as
`<folder-name>_old1_<n>.dat` before the new DAT is saved. Generic `/queue`
recipe jobs remain non-destructive: their source HIS files are never removed.

Paired HIS and HIS+NOISE recipes may queue direct calculation/save from their
original paired HIS inputs; pair-aware H5 canonicalization is deferred.

## Cleaning preview versus applied mask

`GET /cleaning/view` and `POST /cleaning/sam` create a transient preview. A
preview is not an applied H5 mask and must not silently affect OD. While a
preview is pending, immediate `POST /calc-abs` returns an error until the user
applies the mask to H5 or resets the preview.

Applying the mask writes the H5 selection mask, reassigns the cleaned output to
the active input role, and reports persisted mask status. Queue recipes must
state cleaning explicitly; a transient interactive preview is never inferred
as a queue instruction.

Existing immediate treatment endpoints retain their prior behavior, apart from
the explicit unapplied-preview guard on `/calc-abs`.
