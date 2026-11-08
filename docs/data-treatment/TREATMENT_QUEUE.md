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
| `POST` | `/api/treatment/queue/run` | Start a stopped queue, retaining dependent-job order. |
| `DELETE` | `/api/treatment/queue/<job_id>` | Remove a queued job only; running or terminal jobs remain immutable. |
| `POST` | `/api/treatment/preview/dat` | Validate and open `file_path` in Preview without replacing input roles or calculated OD. |

In Data Treatment, `×` closes the active workspace. Files and saved server
sessions remain available; at least one workspace stays open. Project manifests
are opened from the file/folder context menu, not a permanent page row. DAT files
open in Preview on double click. Cleaning has direct Absorption/Base/Bruit buttons;
unassigned roles stay visible and disabled. Completed folder actions refresh the
role list even if the operator switches to Cleaning before the job finishes.

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
- Independent manifest sample recipes run in a bounded thread pool (up to the
  configured worker limit and available CPUs, default limit 6). Each recipe owns
  private cleaning files, runtime and an exact noise identity. Nested file pools
  are disabled for these parallel samples. Output reservations and manifest writes
  remain serialized. Failed samples retain their errors; other samples finish.
- Folder-set recipes retain enqueue order because noise can be inherited from
  the previous folder. A following dependent recipe waits for the manifest batch.
- Independent file conversions use up to
  `min(PYCONLYSE_TREATMENT_MAX_WORKERS, available CPUs, file tasks)` spawned
  processes; the default configured limit is `6`.
- Job statuses are `queued`, `running`, `completed`, `failed`, or
  `interrupted`; `phase`,
  `error`, preparation details, and saved-path receipt remain visible in the
  queue history.
- Local and production server launchers configure
  `PYCONLYSE_TREATMENT_STATE_DB` for SQLite snapshots. Sessions retain their
  input paths, folder, save target, and selection across page/server restarts;
  a previously calculated OD is recomputed from its inputs when reopened.
  Queue recipes and history survive restarts. A running job becomes
  `interrupted` and is never retried automatically; queued jobs wait for an
  explicit `POST /queue/run`. An unapplied SAM preview is reconstructed from
  its input file and saved thresholds when reopened.
- A browser backup can restore an empty server session after the first upgrade
  from process-local state. The old page must be refreshed against the still-
  running server before it is restarted, so its current session is backed up.
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
private job paths/runtime state in separate CPU worker processes for independent
roles, preserving the interactive session. Queue
conversion is non-destructive: source HIS is never removed.
Raw H5 maps and their selection mask follow the [H5 map-selection contract](H5_MAP_SELECTION.md).

## Standard folder queue

`POST /queue/folder-set` captures one of `Set`, `Set/Convert`,
`Set/Convert/Clean`, `Set/Convert/Calc (all maps)`, or
`Set/Convert/Clean/Calc`. Queue jobs
run sequentially and preserve inherited `NOISE` from the previous completed
folder until a new `BRUIT`/`NOISE` file is present. Convert actions create and
verify canonical gzip H5 before removing HIS. Clean actions apply SAM. Every
folder action keeps the selected parent as Save Folder and sets Save File Name
immediately to `<measurement-folder-name>_YYYYMMDD.dat`, with the server's local
date frozen at enqueue. A manual Save Folder override is respected. Calc
actions calculate OD and atomically write that DAT in Save Folder; actions
without Calc update the save target but do not save DAT. The measurement folder
remains the input source, and independent ABS/BASE SAM cleaning runs in parallel
worker processes after both roles are assigned.

`Set/Convert/Calc (all maps)` ignores an earlier SAM mask while averaging the
complete `raw_data` archive. It does not alter the H5 selection. Completed
queue jobs report retained/removed map counts per cleaned role; all-map jobs
report raw map counts and whether an earlier mask was bypassed. Legacy H5 files
whose `raw_data` physically omits maps require `Restore raw-map selection`
before an all-map calculation; the job fails rather than claiming a partial
archive is complete. The result's map policy is saved with the session so OD
recovery after page/server restart uses the same maps.

When a Calc target already exists, it is retained as
`<folder-name>_YYYYMMDD_old1_<n>.dat` before the new DAT is saved. Generic `/queue`
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
