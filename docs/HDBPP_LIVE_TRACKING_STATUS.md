# HDB++ and audit tracking live status

Date: 2026-09-02

## Running now

- `sys/health/elyse` passively observes 52 selected Tango devices.
- It emits only state, reachability, process-restart, and new-error transitions.
- Its scan timestamp is for UI diagnostics and is not event/archive enabled.
- `test/hdbpp/probe` is a disposable no-hardware source for archive acceptance.
- Web HTTP and WebSocket mutation audit code records authenticated identity,
  request, reply/error, outcome, and duration in a hash-chained SQLite journal.

The initial monitor baseline reported the known offline Andor, Hamamatsu, and
ML servers, the not-yet-active Ubuntu Starter, plus real motion-axis reachability
changes. A five-second stability check produced no repeated transition records.

## Prepared but intentionally not activated

- HDB++ Tango Starter, EventSubscriber, and ConfigurationManager are registered.
- Ubuntu HDB++ binaries are installed; `elyse-tango-starter` is disabled and
  inactive.
- Change-only acceptance and health-monitor profiles are implemented in
  `scripts/hdbpp/configure_change_only_attributes.py`.
- The `laser-pointing-sessions` profile is prepared for both LaserPointing
  controllers. Until HDB++ is activated, accepted references and their
  append-only revision histories remain per-device Tango database properties.
- Common ELYSE Device Servers expose and push lifecycle, state, initialization,
  and error timing after their next controlled restart.

## Current blocker

The first elevated MariaDB bootstrap exposed a Windows PowerShell encoding
issue: a UTF-8 BOM at the beginning of `my.ini` caused MariaDB 10.6 to exit.
The service is stopped, no port is listening, no credential file was written,
and no `hdbpp` database exists. The provisioner now writes BOM-free UTF-8.

`Repair-IncompleteHdbppMariaDbInstance.ps1` performs a guarded recovery. It
requires the recorded failed result, exact service command line and data path,
stopped/non-listening state, no credential file, and no `hdbpp` database before
it will remove and recreate the incomplete bootstrap. Its UAC approval is the
current blocker. It never targets the existing Tango MariaDB service or data.

Do not start HDB++ or add production attributes until the disposable probe has
been archived, queried from MariaDB with correct timestamps/quality, and tested
through EventSubscriber restart and a temporary database outage.

## Command attribution boundary

The web controller can identify the authenticated caller and record the full
reply. Direct Jive, LabVIEW, HPD-TA, or raw Tango/hardware access cannot be
attributed to a human unless it is routed through the audited gateway. HDB++
will still record the resulting attribute changes, but it cannot reconstruct
who issued a bypassing command.
