# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project type: Python 3.9, Tango/Taurus-based device control UIs (PyQt5), auxiliary Flask web UI, and data-treatment tools.

- Package/deps: Declared via Poetry (pyproject.toml). A legacy requirements.txt also exists.
- Tests: unittest (no pytest/tox).
- Linting/formatting: no configured linters/formatters found.

Common commands (PowerShell on Windows)

- Create and activate a virtualenv

```powershell path=null start=null
# Poetry (preferred)
poetry env use 3.9
poetry install
poetry run python --version

# Or: venv + pip
py -3.9 -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python --version
```

- Run tests (unittest)

```powershell path=null start=null
# Run the full pypylon/genicam test suite
python -m unittest discover utilities\mytests\test_pypylon -p "*test.py"

# Run only GenICam tests
python -m unittest discover utilities\mytests\test_pypylon\genicam_tests -p "*test.py"

# Run a single test module
python -m unittest utilities.mytests.test_pypylon.genicam_tests.booleantest

# Run a single test case or method
python -m unittest utilities.mytests.test_pypylon.genicam_tests.booleantest.BooleanTest
python -m unittest utilities.mytests.test_pypylon.genicam_tests.booleantest.BooleanTest.test_boolean_feature
```

- Launch the main control UI (PyQt5/Taurus)

```powershell path=null start=null
python bin\main_ctrl.py
```

Notes:
- This UI queries a Tango DB (e.g., Database().get_device_exported) and expects ELYSE/manip namespaces to be present. Without a live Tango environment, many widgets will be inert.
- It spawns device-specific clients via Windows .cmd launchers (e.g., start_NETIO_client.cmd). If those .cmd files aren’t set up on your machine, launch the Python clients directly (see next section).

- Launch a specific device client (pattern)

Each client script under bin/ expects at least one argument: a key from its local layouts dict; an optional second argument selects visualization type: full or min.

```powershell path=null start=null
# Examples
python bin\DS_STANDA_client.py ELYSE full
python bin\DS_BASLER_client.py V0 full
python bin\DS_NETIO_client.py V0 full
python bin\DS_OWIS_client.py all min
python bin\DS_ANDOR_CCD_client.py V0 full
python bin\DS_AVANTES_CCD_client.py Spectrometer full
python bin\DS_laser_pointing_client.py 3P full
python bin\DS_Experiment_client.py "Streak-Camera" full
```

- Run the Flask web UI

```powershell path=null start=null
# Direct execution
python web\run.py

# Or using FLASK_APP if you prefer
$env:FLASK_APP = "web/run.py"
python -m flask run
```

Notes:
- web/run.py currently binds to host=129.175.100.128, port=5000, debug=True. Update to 127.0.0.1 or 0.0.0.0 for local development if needed.
- web/config.py sets a placeholder SECRET_KEY; change it for any deployed use.
- routes expect an SQLite database file pyconlyse.db in the CWD; without it, /tango_status will raise.

- Run a Tango device server (example)

```powershell path=null start=null
# Example: Experiment server (requires a Tango ecosystem configured)
python DeviceServers\Experiment\DS_Experiment.py
```

Build, lint, and formatting

- Build: no library packaging/build steps are defined beyond Poetry metadata; typical workflow is “install deps and run”.
- Lint/format: no ruff/flake8/black/isort configs found. If you want linting/formatting added, ask Warp to set them up.

High-level architecture

The codebase centers on Tango device servers with Taurus/PyQt5 client UIs, plus a data-treatment GUI and a minimal Flask site.

1) Device servers (hardware abstraction, Tango)
- Base: DeviceServers/General/DS_general.py (not shown here) provides DS_General. Concrete servers, like DeviceServers/Experiment/DS_Experiment.py, subclass DS_General to expose attributes/commands and manage state (DevState.*).
- Servers run as Python processes (e.g., DS_Experiment.run_server()) and depend on a Tango DB. RULES are merged from the base class.

2) GUI clients (Taurus/PyQt5 frontends)
- Common widget base: DeviceServers/DS_Widget.py defines DS_General_Widget and VisType (min/full). It wires Taurus widgets (TaurusLabel, TaurusLed, TaurusValueCheckBox) to Tango attribute models and provides helper methods like execute_action and set_state_status.
- Per-device UIs: Each DeviceServers/<DEVICE>/ has a DS_*_Widget.py configuring device-specific controls. gui/Panels.py composes those widgets into higher-level panels.
- Launchers: bin/DS_*_client.py files import a panel and a widget class, declare a layouts dict mapping to Tango device names, and delegate to bin/DS_General_Client.py:main(), which creates a TaurusApplication and shows the selected layout. The second CLI arg selects visualization (min/full).

3) Main control panel
- bin/main_ctrl.py builds a tabbed PyQt5/Taurus UI that:
  - Enumerates Tango devices via Database().get_device_exported for namespaces like ELYSE and manip, updating status labels by polling Device.state()/State().
  - Spawns device client processes via Windows .cmd launchers.
  - Shows a facility “map” using pyqtgraph, imageio, and numpy for visualization overlays.
  - Exchanges numeric parameter updates over ZeroMQ: a WorkerThread binds a PULL socket (default tcp://129.175.100.128:6050) to ingest updates; a PUSH socket targets tcp://127.0.0.1:5556 for outbound changes. These endpoints are environment-specific and may require adjustment.

4) Data-treatment MVC
- Controller: gui/controllers/TreatmentController.py orchestrates user actions (file selection, ranges, averaging) and delegates to the model; it also writes cleaned/averaged HDF5 using h5py.
- Model: gui/models/ClientGUIModels.py (TreatmentModel) manages data paths, invokes file openers (gui/controllers/openers/*), computes optical density from ABS/BASE/NOISE maps, and notifies observers. It uses concurrent.futures.ProcessPoolExecutor for heavy work. Data structures live under utilities/datastructures.
- Views: gui/views/* provide UI elements and matplotlib/pyqtgraph canvases used by the controller.

5) Web application
- Minimal Flask app (web/pyconlyse_control) with create_app(), routes.py, and config.py. The /tango_status endpoint pings MySQL (via TCP) and multiple Tango starter devices (via PyTango) and reports uptime/downtime; it expects an SQLite DB pyconlyse.db to be present for configuration tables (servers, tango_starters).

6) Utilities and messaging
- utilities/ contains multiple helper modules (errors, logging, database tools, ZeroMQ helpers, previous projects) and an IRpy-server prototype using ZeroMQ REP for LabView-style integrations. A custom metaclass (utilities/meta/meta.py) resolves PyQt metaclass conflicts (Meta extends QObject’s metaclass and ABCMeta).

Repository docs and rules
- README.md: “Pyconlyse is client-server-service application written in pure python.”
- No CLAUDE.md, .cursor rules, or Copilot instructions were found.

Environment-specific notes
- Python 3.9 is pinned in pyproject.toml.
- Several IPs/paths are hard-coded (e.g., 129.175.100.128 for ZeroMQ or Flask; Windows icon paths). Adjust these when running outside the original lab network.
- If Windows .cmd launchers referenced by main_ctrl.py are absent, call the corresponding Python bin\DS_*_client.py scripts directly using the examples above.
