# ELYSE archiving, authentication, and audit

## Decision

Use three complementary services:

1. **HDB++** stores timestamped Tango attribute values and device states.
2. **PYCONLYSE authentication and audit** identifies web users and records every
   authenticated HTTP mutation, including its parameters and result status.
3. **TangoAccessControl (TAC)** limits direct Tango writes from Jive, Taurus/Qt,
   LabVIEW, and scripts according to the client OS username and host.

HDB++ cannot record who issued a command. TAC authorizes writes but does not
provide a trustworthy command audit. The web audit journal therefore remains
necessary.

## Current deployment state (2026-09-01)

- MariaDB 10.6 is running on Everest.
- `TangoAccessControl/1` and `sys/access_control/1` are registered.
- TAC is stopped and `CtrlSystem.Services` does not enable it. This is kept
  passive until the access rules are reviewed, so existing clients are not
  locked out.
- A staging Windows ConfigurationManager executable was built at
  `C:\dev\hdbpp-install\bin\hdb++cm-srv.exe`; it is not registered, started,
  or operationally validated.
- The MySQL EventSubscriber is not built. The current official
  `libhdbpp-mysql` source uses GNU variable-length arrays and POSIX networking
  headers that do not compile cleanly with MSVC. A maintained Windows backend
  port or a small Linux HDB++ service host is still required.
- The selected production layout uses Ubuntu in Hyper-V for HDB++ and a second,
  isolated Windows MariaDB service on port `3307`. The VM VHDX is stored on
  `E:` and archive tables on `D:`; the existing Tango database on `C:` remains
  unchanged. Provisioning scripts and the runbook are in `deploy/hdbpp`.
- No HDB++ database/service credentials are available to this repository, and
  none are required in Tango properties.
- The legacy `DS_Archive` must not be restarted as the production archive; its
  unsafe payload decoding and HDF5 threading model need replacement.

## Identity model

The web account `sad` is intended to carry the application role `admin`. A
password is never committed or generated with a default. Provision it into an
external file using:

```powershell
conda run -n pyconlyse39 python scripts/security/provision_web_admin.py `
  --username sad `
  --role admin `
  --output C:\ProgramData\Pyconlyse\users.json

$env:PYCONLYSE_AUTH_USERS_FILE = 'C:\ProgramData\Pyconlyse\users.json'
```

The command prompts twice for the password and stores only a Werkzeug scrypt
hash. Restrict the file ACL to the web service and system administrators.

TAC does **not** use this web account. It uses the client computer's operating
system login name. On the present Windows host the profile path is
`C:\Users\elyse`, so a TAC rule for `sad` would not identify that Windows
session. Before TAC is enabled, list every actual `(OS username, host/IP)` pair
used by Windows, macOS, LabVIEW, and service processes.

Classic TAC is designed to prevent accidental changes; it is client-side,
unencrypted, and can be bypassed with `SUPER_TANGO=true`. It is not a substitute
for strong authentication.

Recommended TAC baseline:

- `All Users`: read-only access to `*/*/*` from approved laboratory networks.
- Named operators: write access only to the device families needed for their
  work and only from their registered hosts.
- Service accounts: narrowly scoped access for the web gateway, HDB++, and
  automation processes.
- Administrative access: separate from normal acquisition work.

## Web audit journal

Production startup defaults the journal to:

```text
C:\ProgramData\Pyconlyse\audit.sqlite3
```

Set a different absolute location with `PYCONLYSE_AUDIT_DB_PATH`. Each
authenticated POST, PUT, PATCH, or DELETE request records:

- UTC timestamp and unique event ID;
- JWT username and roles;
- source IP, route, method, and path;
- redacted request parameters;
- HTTP result status;
- previous-record hash and current-record hash.

The hash chain detects modification or deletion inside the chain. For stronger
tamper evidence, periodically copy the latest hash to a second, restricted
machine or signed experiment manifest.

Verify a journal offline with:

```powershell
conda run -n pyconlyse39 python scripts/security/verify_audit_log.py `
  C:\ProgramData\Pyconlyse\audit.sqlite3
```

The audit covers authenticated web HTTP mutations and WebSocket hardware
commands. Direct Tango clients require gateway instrumentation before they can
claim the same attribution quality.

## HDB++ recording model

All values to be recorded must be exposed as timestamped Tango attributes.
Commands and private LabVIEW variables cannot be archived directly.

Use two levels of recording:

- **Baseline:** device state, faults, connectivity, and slow diagnostic values.
- **Experiment session:** a selected ELYSE profile started and stopped by the
  operator, with its run ID, sample, comment, and sampling configuration.

The session service will call HDB++ `AttributeStart` and `AttributeStop` (or a
configured HDB++ context) for the selected attributes. Sampling uses
`archive_period`, `archive_abs_change`, and `archive_rel_change`.

Images and large spectra should remain in experiment HDF5 files; HDB++ should
hold their metadata, state, scalar readings, and file references.

The reviewed baseline device list, change-only event policy, missing lifecycle
timestamp attributes, disconnected-server monitor, and command reply audit
contract are specified in `HDBPP_BASELINE_MONITORING_PROPOSAL.md`.

## Deployment gates

Before HDB++ or TAC is activated:

1. A MariaDB administrator creates an `hdbpp` database and least-privilege
   schema/service accounts using the official InnoDB schema.
2. The Ubuntu VM has the pinned `libhdbpp-mysql`, EventSubscriber, and
   ConfigurationManager builds installed.
3. EventSubscriber and ConfigurationManager devices are registered in Astor and
   tested with a disposable Tango attribute.
4. Retention, backups, partitions, disk capacity, and clock synchronization are
   agreed.
5. All direct-client OS usernames and hosts are inventoried.
6. TAC is tested in read-only mode before any write grant is introduced.
7. The first ELYSE attribute profile and required sample periods are defined.

Official references:

- <https://tango-controls.readthedocs.io/en/latest/How-To/deployment/access-control.html>
- <https://tango-controls.gitlab.io/-/tango-doc/-/jobs/15931620138/artifacts/build/html/Explanation/archiving/hdbpp.html>
- <https://gitlab.com/tango-controls/hdbpp/libhdbpp-mysql>
- <https://gitlab.com/tango-controls/hdbpp/hdbpp-es>
