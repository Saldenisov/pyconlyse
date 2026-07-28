# Refactoring Work Packages

Only one agent may write a given file in a work package. Read-only agents may inspect any file. Packages may run in parallel only when file scopes do not overlap.

Machine-readable scopes live in `docs/refactoring/work-packages.toml`. The manifest is authoritative for allowed paths and protected V0 paths.

Each writing agent must use a separate worktree. Before committing, validate the complete worktree, including unstaged, staged, and untracked files:

```bash
conda run -n pyconlyse39 python scripts/refactor/validate_scope.py --package T3
```

Use `--package L1` for Luna packages. A protected or out-of-scope path returns exit code `1`; an invalid package or Git/manifest error returns `2`.

For unit tests, pass files directly with repeatable `--file` arguments. This bypasses Git discovery and keeps the validator testable without a repository:

```bash
python scripts/refactor/validate_scope.py --package L1 \
  --file DeviceServers/instruments/dg645/driver.py
```

## Terra semantic packages

### T1: Shared Tango foundation

Scope:

- `DeviceServers/base/general.py`
- `DeviceServers/base/camera.py`
- `DeviceServers/base/motor.py`
- related base tests

Deliver: state model, lifecycle boundaries, validated config, transport/error contracts, regression tests.

### T2: Motion safety

Scope:

- `DeviceServers/motion/owis/DS_OWIS_PS90.py`
- OWIS tests and directly required adapters

Deliver: command cancellation, limits, readback, timeout behavior, and stable Tango facade.

### T3: Hamamatsu transport

Scope:

- `DeviceServers/cameras/hamamatsu_streak/DS_HAMAMATSU_STREAK.py`
- `remoteex_client.py`
- `hamamatsu_streak_controller.py`

Deliver: bounded socket operations, reconnect policy, async acquisition state, and error mapping.

### T4: Backend device API

Scope:

- `web/backend/device_api.py`
- directly related backend tests

Deliver: services for discovery, snapshots, Astor, PDU, camera, spectrograph, DAQmx, and generic devices.

### T5: Treatment domain

Scope:

- `web/backend/treatment_api.py`
- `web/backend/treatment_service.py`
- `web/backend/pump_probe_vd2_api.py`

Deliver: route/domain separation, explicit session state, file/storage boundaries, and contract tests.

V0 backend remains protected until a dedicated V0 package is explicitly approved in the manifest.

### T6: V0/VD2 frontend behavior

Scope only after explicit assignment:

- `web/frontend/src/PumpProbeV0.js`
- `web/frontend/src/PumpProbeVD2.js`
- `web/frontend/src/TabsControl.js`

Current dirty V0 files are protected and must not be modified by an unrelated package.

### T8: Software-only verification gate

Scope:

- `pytest.ini`, `.coveragerc`, `tests/conftest.py`, `tests/manual/**`
- `scripts/refactor/verify_refactor.py`, `scripts/refactor/verify_coverage.py`
- gate, coverage, and isolation regression tests
- refactoring test documentation

Deliver: order-independent Tango/Taurus test doubles; explicit automated,
manual, integration, legacy, main-app, and utilities lanes; focused lifecycle
coverage floors; and an executable local `--full` gate. This package does not
operate Tango, hardware, PDU, motion, shutters, or deploy tooling.

## Luna mechanical packages

### L1: DG645 extraction

Scope:

- `DeviceServers/instruments/dg645/DS_DG645.py`
- `DeviceServers/instruments/dg645/dg645_recall_configurator.py`
- `DeviceServers/instruments/dg645/add_ds_DG645.py`

Target modules: `driver.py`, `recall_config.py`, `tango_device.py`, `registration.py`.

### L2: DAQmx client/UI extraction

Scope:

- `DeviceServers/control/daqmx/DS_DAQmx_Widget.py`
- `DS_DAQmx_client.py`
- `DS_DAQmx_zmq.py`
- `DS_DAQmx_zmq_client.py`
- `DS_DAQmx_zmq_widget.py`

`DS_DAQmx.py` remains Terra-owned because it contains hardware behavior.

### L3: Treatment helpers

Scope:

- `web/backend/treatment_network_path.py`
- `web/backend/treatment_file_cache.py`
- `web/backend/folder_api.py`

Do not modify `treatment_api.py` or `treatment_service.py` in this package.

### L4: Existing web components

Scope only within:

- `web/frontend/src/components/`
- `web/frontend/src/tabs/`
- `web/frontend/src/utils/`

Do not touch current V0 files.

## Sol review packages

### R1: Contract review

Read-only review of Tango names, commands, attributes, HTTP routes, payloads, and config compatibility.

### R2: Safety review

Read-only review that no code path powers hardware, moves motors, opens shutters, starts HPD-TA, or deploys without a manual gate.

### R3: Integration review

Read-only review of import cycles, test coverage, packaging, Windows wrappers, Everest readiness, and rollback.

## Handoff format

Every agent returns changed paths, tests run, contract changes, risks, and recommended rollback commit. A package is incomplete until Sol reviews it.
