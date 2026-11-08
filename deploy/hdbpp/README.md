# HDB++ deployment for ELYSE

## Selected architecture

HDB++ runs in a small Ubuntu Hyper-V VM on Everest. Tango, the existing Tango
MariaDB instance, Device Servers, the web application, authentication, and the
audit journal remain on Windows.

Storage is deliberately split:

- `E:\ELYSE-VMs\HDBPP`: a dynamically expanding 60 GB Ubuntu system VHDX;
- `D:\ELYSE-Archive\MariaDB`: a separate Windows MariaDB instance containing
  the HDB++ archive;
- the existing Tango MariaDB data at
  `C:\Program Files\MariaDB 10.6\data` is not moved or modified.

At the time of design, `C:` had only 13.6 GB free, `E:` had about 645 GB free,
and `D:` had about 2.67 TB free. Separating the archive database also prevents
HDB++ write load or storage exhaustion from disrupting Tango's configuration
database.

The isolated archive database uses TCP port `3307`; the existing Tango MariaDB
continues using `3306`. Windows Firewall admits `3307` only from the reserved
Ubuntu VM address.

Astor remains the process controller. A single Tango Starter runs under
systemd in Ubuntu and owns both HDB++ servers:

```text
Starter/hdbpp-archive          -> tango/admin/<ubuntu-short-hostname>
hdb++es-srv/everest01          -> archiving/hdbpp/es01
hdb++cm-srv/everest            -> archiving/hdbpp/cm
```

No attribute is automatically added to the archive during deployment.

## Deployment order

All mutation scripts require explicit parameters or interactive passwords.
Commands that alter Windows services, firewall rules, or Hyper-V must run from
an elevated PowerShell.

1. Download and verify the Ubuntu installer:

   ```powershell
   .\deploy\hdbpp\windows\Get-UbuntuHdbppIso.ps1
   ```

2. Choose an unused, reserved laboratory IPv4 address and identify the active
   physical laboratory NIC with `Get-NetAdapter`.

3. Enable Hyper-V from an elevated PowerShell, reboot if requested, and create
   the VM. Full Hyper-V is currently disabled on Everest even though the
   lighter Virtual Machine Platform used by WSL is enabled.

   ```powershell
   .\deploy\hdbpp\windows\Enable-HdbppHyperV.ps1
   ```

   After the reboot:

   ```powershell
   .\deploy\hdbpp\windows\New-ElyseHdbppVm.ps1 `
     -UbuntuIsoPath E:\ELYSE-Install\Ubuntu\ubuntu-24.04.4-live-server-amd64.iso `
     -ExternalAdapterName ELYSE `
     -StartVm
   ```

   The external switch creation can briefly interrupt Windows networking.
   Install Ubuntu with OpenSSH, automatic security updates, and the reserved
   static address. The deployed ELYSE VM uses short hostname `elysevm` and lab
   address `10.20.30.203`. Do not install a database inside the VM.

4. Create the isolated archive database service on Windows:

   ```powershell
   .\deploy\hdbpp\windows\New-HdbppMariaDbInstance.ps1 `
     -VmIPv4Address '<reserved VM IPv4>' `
     -StartService
   ```

   The script prompts for a new local root password and a VM-scoped
   `hdbpp_writer` password. It creates only an empty `hdbpp` database; it
   neither reads nor changes credentials belonging to the existing Tango
   MariaDB service.

5. Copy `deploy/hdbpp/linux` to the Ubuntu VM and install the pinned HDB++
   sources:

   ```bash
   sudo ./install-hdbpp.sh
   ```

   The laboratory `10.20.30.0/24` segment may not provide internet access. If
   so, attach a second Hyper-V adapter named `HDBPP-Build-NAT` to `Default
   Switch`, install `linux/netplan/60-hdbpp-build-nat.yaml` as
   `/etc/netplan/60-hdbpp-build-nat.yaml`, and run `netplan apply`. This adapter
   is for package/source installation only; remove it after the build and keep
   all Tango and archive traffic on the laboratory adapter.

6. Initialize the HDB++ schema and its VM-scoped service account:

   ```bash
   sudo HDBPP_DB_HOST=10.20.30.202 HDBPP_DB_PORT=3307 \
     ./initialize-hdbpp-database.sh '<reserved VM IPv4>'
   ```

7. From the repository on Windows, preview and then register the devices:

   ```powershell
   conda run -n pyconlyse39 python scripts\hdbpp\register_hdbpp_devices.py `
     --vm-hostname elysevm

   conda run -n pyconlyse39 python scripts\hdbpp\register_hdbpp_devices.py `
     --vm-hostname elysevm `
     --apply
   ```

8. Activate Starter from Ubuntu. The password is stored in a root-owned,
   group-readable environment file with mode `0640` and is inherited by the
   two child Device Servers. It is never written to Tango properties.

   ```bash
   sudo ./activate-hdbpp.sh
   ```

9. Run the Windows and Linux verification procedures described below before
   adding the first real ELYSE attribute.

## Verification and acceptance

### Current deployment state (2026-09-02)

- Ubuntu `elysevm` is running at `10.20.30.203`; HDB++ binaries are installed.
- The Tango registrations for Starter, EventSubscriber, and
  ConfigurationManager exist, but their Linux service remains disabled and
  inactive until the database is ready.
- `DS_HealthMonitor/elyse` is registered and running at `sys/health/elyse`.
- The disposable `DS_HdbppProbe/acceptance` is registered and running at
  `test/hdbpp/probe`; it has no hardware connection.
- The first isolated `MariaDB-HDBPP` bootstrap stopped before creating the
  archive database because Windows PowerShell wrote a BOM into `my.ini`. The
  provisioner is corrected. Run and approve the guarded recovery wrapper:

  ```powershell
  Start-Process powershell.exe -Verb RunAs -ArgumentList `
    '-NoProfile -ExecutionPolicy Bypass -File "C:\dev\pyconlyse\deploy\hdbpp\windows\Repair-IncompleteHdbppMariaDbInstance.ps1" -Confirm:$false'
  ```

  The recovery refuses to act if credentials, an `hdbpp` database, an active
  listener, or an unexpected service/path is present. Completion is recorded in
  `C:\ProgramData\ELYSE-HDBPP\mariadb-provisioning-result.json`; passwords are
  generated internally and stored using Windows DPAPI, never printed.

On Windows:

```powershell
.\deploy\hdbpp\windows\Test-HdbppHost.ps1 `
  -VmIPv4Address '<reserved VM IPv4>'
```

In Ubuntu:

```bash
systemctl status elyse-tango-starter
tango_admin --ping-device tango/admin/elysevm
tango_admin --ping-device archiving/hdbpp/es01
tango_admin --ping-device archiving/hdbpp/cm
journalctl -u elyse-tango-starter --since today
```

Acceptance must use a disposable test Tango attribute first:

1. add it through ConfigurationManager;
2. change it several times with known timestamps;
3. confirm value, quality, and timestamps in the `hdbpp` database;
4. restart Starter and confirm recording resumes;
5. temporarily block database access and confirm HDB++ reports a fault without
   affecting the Tango database;
6. restore access and confirm recovery;
7. test backup and restore into a disposable MariaDB instance.

Only after these checks should an ELYSE baseline attribute profile be added.

The prepared profile commands are dry-run by default:

```powershell
conda run -n pyconlyse39 python scripts\hdbpp\configure_change_only_attributes.py `
  --profile acceptance

# Use --apply only after MariaDB, schema, CM, and EventSubscriber are healthy.
```

## Capacity and retention

The 60 GB VHDX contains only Ubuntu, binaries, and journals. Archive tables live
on `D:`. Never attach an intermittently removed USB disk as a live MariaDB data
directory. An external disk may be used as a backup target, provided backups
are verified and the primary database remains on an always-connected NTFS
volume.

Before production activation, define:

- maximum retention for baseline and experiment profiles;
- partition creation and removal schedule;
- warning thresholds at 70%, 80%, and 90% volume use;
- nightly database backup plus a second physical copy;
- recovery-time and acceptable-data-loss objectives.

HDB++ images and large spectra should normally remain in experiment HDF5 files;
archive their metadata, scalar diagnostics, quality, and file reference instead.

## Security boundaries

- MariaDB `3307` accepts only the VM address at the Windows firewall.
- Remote MariaDB root access remains disabled.
- The runtime account is limited to the `hdbpp` database and the VM address.
- Database passwords are absent from Git and Tango properties.
- HDB++ records values, timestamps, and quality; it does not identify the human
  who caused a change. Web authentication/audit and TangoAccessControl remain
  separate requirements.

## Recovery

If HDB++ must be stopped without affecting Tango:

```bash
sudo systemctl disable --now elyse-tango-starter
```

The isolated Windows archive database can then be stopped independently:

```powershell
Stop-Service MariaDB-HDBPP
```

Do not delete the VM, archive service, schema, or data directory during an
incident. Preserve them for diagnosis and restore testing.

## Source policy

This directory intentionally contains no database password, generated SQL
schema, or third-party binary.

Use the official HDB++ MySQL/MariaDB InnoDB JSON schema from
`libhdbpp-mysql/etc/create_hdb++_mysql_innodb_json.sql`. Build or install these
matching components before registering devices in Astor:

- `libhdbpp`;
- `libhdbpp-mysql`;
- `hdbpp-es` (EventSubscriber);
- `hdbpp-cm` or the supported combined ConfigurationManager package;
- optionally HDB++ Configurator and Viewer.

Keep database credentials outside Tango properties when the selected build
supports it. Current `libhdbpp-mysql` accepts `HDBPP_MYSQL_USER` and
`HDBPP_MYSQL_PWD`; the remaining non-secret `LibConfiguration` values identify
the MariaDB host, port, database, backend library, batching, and array mode.

The Linux installer pins the reviewed source revisions listed below. Update
them only after a disposable build and archive round-trip test.

The installer also applies
`linux/patches/libhdbpp-mysql-mariadb-and-read-scalar.patch` to the pinned
MySQL backend. The patch binds MariaDB JSON parameters as text and prevents the
scalar insert path from creating a write-value binding for read-only
attributes. Without these compatibility fixes, metadata insertion fails and a
read-only scalar event writes past the prepared-statement binding array,
crashing the EventSubscriber.

## Windows build investigation (2026-09-01)

Staging source and install roots:

```text
C:\dev\hdbpp-src
C:\dev\hdbpp-install
```

Source revisions:

- `hdbpp-cm`: `f8a4cccdc6f202e7680b4234c6b0e27c4b60f25b`
- `hdbpp-es`: `c2ed5aa18fcf8ba21a2568526d65e2b478fea2ef`
- fetched `libhdbpp-mysql`: `f0a78829c3e76b06073655e547e7c73a16764c81`

The ConfigurationManager was built with Visual Studio 2022, C++17, the
installed cppTango 10.3 prefix, and the existing vcpkg x64 dependencies. Its
generated class factory required adaptation to the cppTango 10.3
`DServer::register_class_factory` API. The result is
`C:\dev\hdbpp-install\bin\hdb++cm-srv.exe`; it has not been started.

The EventSubscriber configured with the MySQL backend, but its backend failed
to compile under MSVC. Confirmed incompatibilities include:

- unconditional POSIX `netdb.h` use;
- multiple runtime-sized C arrays, which are a GNU extension and not C++17;
- Windows `min`/`max` macro collisions;
- additional runtime-sized binding buffers throughout scalar and JSON-array
  insertion code.

Do not deploy the partially ported staging backend. The selected production
path is the Ubuntu Hyper-V VM described above. Completing and upstreaming an
MSVC port remains a possible future project, but it is not part of this
deployment.
