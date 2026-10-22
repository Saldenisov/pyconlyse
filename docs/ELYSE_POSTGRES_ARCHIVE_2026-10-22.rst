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

The entire new PostgreSQL storage root has a protected inheritable Windows ACL
for EVEREST\elyse and SYSTEM only; data, logs, spool and backups were checked.
The previous root ACL is retained in secrets\storage_acl_before.sddl. This does
not change permissions on the original HDF5 archive directories or other F: data.

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
row. Engineering data, wide integers, booleans and nulls are not downsampled or
rounded. The compressed original record also preserves the original source
timestamp. An audit identified float8-to-numeric rounding in the auxiliary
source_seconds_1904 column of the initial receiver/import release: a sampled
3875499601.810625 became 3875499601.81063, a 5-microsecond difference. Updated
writer source adapts this value through Decimal(str(value)); an integration test
covers that case. Already imported auxiliary copies and the frozen running v3
receiver can retain this rounding; original payloads remain exact. The audit
reports this qualification separately rather than relabeling it exact equality.
History uses Everest observed_utc, not this unqualified source-clock column.
Frame/bank writes are one transaction; source bank capture itself is not made
atomic by database storage.

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

A subsequent 120-observation window, 2026-10-22 16:02:19--16:04:19 Europe/Paris,
passed without issues: 118 distinct observed receipts, maximum bank age 1.36 s,
and twelve complete 27-bank value/error comparisons against PostgreSQL. Ingress
counter advanced 9726 to 10021; the disk queue peaked at 15 and ended at one.
This finite window is not a guarantee against later upstream stale data.

All three selected import ledgers reached COMPLETE at 2026-10-22 16:20:15
Europe/Paris. File attributes and original status documents were also imported.
The closed HDF5 inputs remain on F:, unchanged by the read-only audit.

=================================== ============== ================
Archive folder                      Committed rows Snapshot records
=================================== ============== ================
baseline_20261021T063029Z                       5708             5706
resumed_20261021T093441Z                       78937            78926
unified_v6_20261021T1615Z                      99329            91950
Total                                       183974           176582
=================================== ============== ================

Every committed frame identity and kind matched. Across the three files,
78 selected original records and 1674 bank instances were checked. The only
sampled typed-column qualification was the auxiliary source-clock rounding
described above (54 bank instances in the main file; maximum 5 microseconds).
Original source timestamps and engineering values in those records matched.

Original file SHA256 values, in the same order as the table, are::

    6d88aeaf56d6feec387a0d7039aa8c5877fc14d1ab01fdd447a0d61f4e218cc0
    27a348bd7fd08bca298d1b75c2904c6ec6f29393337f4f61eb05f4a7db05fa80
    de9296eec4f9e6b2a1ebd130144c680a4333b45597988c2236ebb514b07a4e9c

Audit reports are main-import-audit.json and earlier-import-audit.json in
F:\ELYSE_PostgreSQL\deployment_20261022. A separate production audit found zero
test-fixture frames. The final regression run passed 90 tests in 12.35 seconds
with four warnings.

During backup, another 120-observation acceptance window passed, 16:24:52--16:26:53
Europe/Paris: 120 distinct observations, receiver counter 13242--13638, twelve
complete 27-bank database comparisons, maximum bank age 0.735 seconds, no issues
and no archive errors. Queue peak was four, ending at one. The verified history
page loaded 2128 HT points for 13:35--13:45 Europe/Paris, with CSV available.

The compressed backup completed and passed full archive traversal/decompression
at 2026-10-22 16:44:00 Europe/Paris::

    F:\ELYSE_PostgreSQL\backups\elyse_telemetry_20261022.dump
    3327890471 bytes
    SHA256 adb881b02c8cc4698edba45c040b2370e34f874093dbcfd6e5dfb4771c72bc95

Its adjacent .dump.json records the consistent pg_dump operation and verification.
This check did not execute a restore into another database. Backup began at
16:24:42; later live arrivals remain in the running database, not retroactively in
that backup. A same-disk copy does not protect against failure of F:.

Live PostgreSQL recording continues. No automatic history deletion, recurring
backup schedule or HDF5 recorder restart is configured. Original recording gaps
remain gaps. The Windows startup helper starts the cluster at user logon only;
it is not a Windows service or a machine-sleep continuity guarantee.
