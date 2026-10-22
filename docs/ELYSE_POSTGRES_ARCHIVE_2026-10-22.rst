ELYSE telemetry: PostgreSQL archive on F:
========================================

Scope and deployment
--------------------

The user authorized PostgreSQL deployment on F:, a controlled HDF5 recorder stop,
Everest telemetry receiver replacement and import of the closed archives. No XP
software, LabVIEW VI, NI task, acquisition ownership, interlock or hardware
command was changed. The existing 27-bank live contract remains in place.

PostgreSQL 17.11 Windows x64 binaries came from the EDB archive linked by the
official PostgreSQL Windows download page. The downloaded ZIP SHA256 is::

    80379B2C04D51C30225532E0AE04509899141E9957ED096FE749D7FD9DF8F82F

The installed driver is psycopg 3.3.6. Installation paths are::

    F:\ELYSE_PostgreSQL\17.11\pgsql       PostgreSQL binaries
    F:\ELYSE_PostgreSQL\data              cluster, WAL and temporary tables
    F:\ELYSE_PostgreSQL\logs              PostgreSQL and receiver logs
    F:\ELYSE_PostgreSQL\spool             durable ingress queue
    F:\ELYSE_PostgreSQL\alarms            preserved cooling incident journal
    F:\ELYSE_PostgreSQL\backups           database backup destination
    F:\ELYSE_PostgreSQL\secrets           ACL-restricted local credentials
    F:\ELYSE_PostgreSQL\python-packages   dedicated archive driver

The cluster listens only on 127.0.0.1:5432 and uses SCRAM authentication. No
database credentials are in Git, telemetry, URLs or command-line arguments.
The application role owns only elyse_telemetry; ordinary history connections
set transaction_read_only, statement_timeout=2s and lock_timeout=100ms.

The current Windows account is not elevated. The database therefore runs under
that account, not as a newly installed Windows system service. A dedicated
HKCU Run entry starts the existing cluster at user logon through a hidden,
idempotent Python helper. This is logon startup, not pre-logon boot availability;
the helper never initializes a missing cluster. Persistent database settings,
including the F: log directory, are in postgresql.auto.conf.

The active Tango device remains elyse/acquisition/telemetry, source filter
unified_acquisition, commands_enabled=false. Its immutable runtime package is::

    F:\ELYSE_Telemetry_Server\postgres_v3

The existing Starter launcher now selects that telemetry-only release. XP v8
remains the same cold IDLE bridge. The release manifest pins its deployed files;
later importer batching optimizations in the source tree do not hot-patch that
running Python process.

Data path and failure semantics
------------------------------

Authentication, schema, session and FIFO validation precede archival admission.
The receiver commits a compressed packet into an F: SQLite WAL/FULL spool before
publishing the new RAM snapshot. A separate non-daemon writer transfers queued
records transactionally to PostgreSQL. Queue rows are removed only after the
database commit. Database retry is idempotent by relay/message identity; changed
content under the same identity is rejected. Retransmission age does not change
the archived first-observation timestamp.

The existing XP ACK deliberately still reports ram_latest/durable=false for wire
compatibility. Separate archive status reports the stronger durable-ingress
behavior. Live telemetry remains RAM-backed, with actual age and errors; it never
silently falls back to old database values. RAM views do not acquire the spool
I/O lock. A slow/full recording disk can still backpressure durable admission;
this system does not provide hard real-time or disk-failure guarantees.

The spool is bounded at 100000 pending packets and a 5-GiB free-space guard.
Database failure leaves pending rows on disk. Spool admission failure withholds
positive acceptance; it is not converted into a successful archive write.
Upstream XP forwarding is still latest-only, so no claim is made to capture every
original VI publication or to recover source packets replaced before Everest.

PostgreSQL retains losslessly compressed complete records, source/receiver
identities, timestamps, original quality/error flags, and JSONB bank values.
LabVIEW type definitions are content-addressed rather than repeated in each bank
row. Wide integers, booleans, nulls and double values are not downsampled or
rounded. Frame/bank writes are one transaction; source bank capture itself is
not made atomic by database storage.

History and user interface
--------------------------

The device exposes archive_status_json, read-only ReadHistory and ArchiveSummary.
History queries require a known bank, index 0..8191, timezone-qualified interval
and limit 1..5000, with a time/UID cursor. Non-scalar fields are explicitly marked
unavailable in the scalar-series response; their original values remain stored.
SQL uses bound parameters. Ordinary Tango history reads retain a two-second
statement timeout. Synchronous Tango history calls can occupy device request
serialization until that bounded query completes. Cold historical reads under
backfill load did hit this limit; it was not concealed as an empty result.

The deployed web history reader therefore uses a separate, explicitly configured
local PostgreSQL connection with transaction_read_only and a ten-second statement
timeout. It does not acquire the Tango request queue. Its configuration path is
in the ignored local web .env file; credentials remain on F:. History pages fetch
128-point cursor pages to bound individual disk reads. Live telemetry continues
to read the same Tango device; historical data never becomes a live fallback.

Web endpoints are::

    /api/elyse/acquisition/telemetry/archive
    /api/elyse/acquisition/telemetry/history
    /api/elyse/acquisition/telemetry/history-view

The read-only history page offers HT, current, temperatures, software stage OKs
and selected raw cooling inputs, time selection and CSV export. It shows import
progress separately from live recording status. The plot breaks across stale or
error samples, source-session changes and gaps longer than two seconds; it does
not interpolate across the receiver handover. Plotting these gaps is not a claim
that physical equipment stopped. A 25000-point browser limit is explicit and
does not truncate the underlying archive. CSV neutralizes formula-like text.

The previous frontend bundle was not replaced. Only the scoped telemetry backend
and standalone history page changed, after inactive web lifecycle/acquisition/
treatment guards. Existing backend sources and process metadata were backed up
under F:\ELYSE_PostgreSQL\deployment_20261022.

HDF5 handover and import boundary
--------------------------------

Recorder PID 11412, recorder_id b5806d3c63ea43aa95c61c0d3e4f7829, was stopped only
through its documented stop.request. STOPPED and process exit were verified
before any HDF5 open. Its final storage error count was zero, with 91950 recorded
snapshots and 99329 committed archive rows. No HDF5 file was repaired or modified.

Last old snapshot observation: 2026-10-22 14:47:07.360774 Europe/Paris.
First new PostgreSQL ingress: 2026-10-22 14:47:29.768459 Europe/Paris.
The observed archive gap is 22.407685 seconds. It must not be presented as a
continuous recording or as an exact physical transition interval.

Imports preserve only rows below each file's committed_rows marker. They require
a final STOPPED/FAILED status and no surviving recorder process by default, retain
original records, and use recorder_id/row identities with resumable monotonic progress.
The earliest baseline retained an old RUNNING status after its recorder died.
An explicit --allow-orphaned option additionally requires a Windows recorder PID
absence check, an old timezone-qualified status and matching file identity. It
never changes that original status or clears HDF5 flags; orphan SWMR files are
opened read-only. A surviving/inaccessible recorder or recent status is refused.
The current acquisition interval from 13:35 Europe/Paris was prefetched first;
the remainder is being backfilled. Known earlier recording/receiver outages
remain outages. Parallel backfill initially caused a lock timeout; the affected
import stopped at its committed checkpoint. Source inputs were retained. Import
transactions now retry transient database errors, avoid repeated DDL on existing
tables, and commit type metadata separately from large bank batches.

Verification and completion status
----------------------------------

Before handover, 75 driver-free/unit/web/PostgreSQL tests passed. A later expanded
suite passed 90 tests; PostgreSQL integration fixtures now use unique isolated
schemas and private temporary configuration files. Coverage includes precise
numeric round trips, duplicate/conflicting identity handling, spool failure and
recovery, nonblocking RAM views, bulk copy, pagination/read-only queries, and
closed-HDF5 committed-row/resume checks. No test invokes hardware.

The import audit checks every committed frame identity and kind, its completed
ledger and preserved status metadata. Deterministically spread original records
and typed bank values are compared against the source, including first/last
occurrences of each event kind. This is sampled payload verification, not a claim
that every payload was independently compared. Source files are hashed and their
size/modification time is checked before and after the read-only audit.

The backup tool refuses a final backup while an import ledger is incomplete. It
creates a new compressed custom pg_dump on F: without stopping PostgreSQL and
checks both its table of contents and complete decompression through pg_restore
without executing SQL. A same-F: backup is not protection against F: disk loss.

Initial live acceptance observed temporary archive lock retry and recovered with
the disk queue retained. Another window included two unclassified quality/archive
observations; it is not counted as a clean acceptance. Reports are retained under
the deployment directory rather than relabeled as successful.

Migration is still in progress at the time of this source checkpoint. Required
remaining work: finish and audit all selected closed archives, persist their file
metadata, rerun clean live acceptance, verify a database backup and update this
completion section. Do not stop or restart XP/Acquisition or initialize NI cards.
