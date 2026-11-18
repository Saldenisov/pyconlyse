# Gamma-spectrometer

Standalone PyQt5 application for two Avantes spectrometers and Arduino TTL control.

This subproject does not use Tango.

## Windows on the experiment laptop

With Git installed, run these commands in PowerShell to check out `Gamma-spectrometer` from the [Avantes branch](https://github.com/Saldenisov/pyconlyse/tree/Avantes).

```powershell
git clone --branch Avantes --single-branch --filter=blob:none --sparse https://github.com/Saldenisov/pyconlyse.git pyconlyse-avantes-gamma
git -C .\pyconlyse-avantes-gamma sparse-checkout set Gamma-spectrometer
cd .\pyconlyse-avantes-gamma\Gamma-spectrometer
.\run_avantes_dual_viewer.bat
```

If a previous clone stopped on a Git LFS error in `utilities/IRpy-server`, run the commands in a folder where `pyconlyse-avantes-gamma` is available as a new directory name. The sparse checkout fetches the application and drivers from `Gamma-spectrometer`.

You can also download and extract the [Avantes ZIP](https://github.com/Saldenisov/pyconlyse/archive/refs/heads/Avantes.zip), open `Gamma-spectrometer`, and double-click `run_avantes_dual_viewer.bat`.

The first launch needs internet access. The launcher checks for 64-bit Python 3.11 and Git, downloads portable copies when needed, and installs dependencies into `.gamma-tools\venv311`. It opens the viewer after checking imports, including `pyMCR 0.3.2` for MCR-ALS. A standard Windows account can run it.

Use the same BAT file for later launches. It reuses the environment and displays startup errors in the console. Run `run_gamma_demo.bat` to test with two emulated spectrometers.

When you select **Start DC**, Gamma records the active run and saves a calibration checkpoint. After a crash, the launcher opens Gamma again. It reconnects the spectrometers, restores the settings, and loads the HDF5 file. Select **Start DC** and confirm to resume recording. If the original file is unavailable for writing, Gamma prepares `*_continued.h5` from the calibration checkpoint and links to the original path in the `collection_recovered` event. Elapsed time stays relative to the original run start. Accumulated dose after the interruption is marked as unknown. Startup and error logs are under `logs`.

For recovery after a reboot, register the Windows sign-in task once.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\register_gamma_recovery.ps1
```

The sign-in task opens Gamma for an interrupted active run using the installed environment. **Pause DC**, **Stop DC**, and closing the window normally clear the active-run record. To resume manually, choose **Data → Open HDF5…**, connect the original spectrometers, and select **Start DC**.

To install packages without opening the viewer, run this command from `Gamma-spectrometer`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_gamma_packages.ps1
```

From the same directory, run the readout and HDF5 write tests with simulated faults.

```powershell
.\.gamma-tools\venv311\Scripts\python.exe -m unittest discover -s tests -v
```

## Conda Setup

```bash
cd /Users/sad/dev/pyconlyse/Gamma-spectrometer
conda env create -f environment-py311.yml
conda activate pyconlyse311
python avantes_dual_viewer.py
```

Python 3.9 stable fallback:

```bash
cd /Users/sad/dev/pyconlyse/Gamma-spectrometer
conda env create -f environment-py39.yml
conda activate pyconlyse39
python avantes_dual_viewer.py
```

Python 3.13 test env:

```bash
cd /Users/sad/dev/pyconlyse/Gamma-spectrometer
conda env create -f environment-py313.yml
conda activate pyconlyse313
python avantes_dual_viewer.py
```

## Pip Setup

```bash
cd /Users/sad/dev/pyconlyse/Gamma-spectrometer
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python avantes_dual_viewer.py
```

Pip setup is intended for Python 3.11. Use conda for Python 3.9 or 3.13.

## Emulator

On macOS/Linux emulator mode is enabled by default.

```bash
AVANTES_EMULATOR=1 python avantes_dual_viewer.py
```

## Demo Kinetics

Run:

```bash
./run_gamma_demo.command
```

or:

```bash
AVANTES_EMULATOR=1 AVANTES_DEMO_KINETICS=1 AVANTES_DEMO_DURATION_S=40 python avantes_dual_viewer.py
```

Demo kinetics adds a synthetic growing UV-visible species to sample acquisitions and a separate UV fiber-loss band to both sample and repeat reference acquisitions. The simulated signal grows while irradiation is marked on. Follow the workflow below with `Rate = 1 s`, then use **Show DC** to compare measured and corrected OD.

On Windows with real hardware:

```bat
set AVANTES_EMULATOR=0
python avantes_dual_viewer.py
```

## Recording a run and measuring references

1. Enter **Sample name**, **Measured volume** in mL, **Entrance aperture diameter** and **Sample optical path** in mm, and the sample quartz type **QZ** or **QS**. These fields are required before measurement. Add optional notes in **Sample**. Set **Probe volume** in mL or leave it on **Auto** to calculate it from the sample geometry. Choose **Repeats** and **Blocks / repeat**. **Background** switches off the probe lamp and starts writing both channels and the sample metadata to the named HDF5 file.
2. Measure **Empty**. In **Reference cell**, keep **Same cell as sample** to reuse the sample path length and quartz type, or clear it and enter both reference values before pressing **Reference**. Both cells share the entrance aperture diameter. The measured volume applies to the sample. Insert the water reference and measure **Reference**. **Set Empty Zero** and **Set Reference Zero** are optional. **Start DC** uses the measured reference as the default sample OD baseline and first drift anchor. Use those reference cell specifications for later **Add Reference** captures in the run.
3. When the apparatus permits a reference measurement, select **Pause DC**, record the external source state with **Mark irradiation off**, and insert the reference. **Add Reference** starts capture immediately. It displays the reference OD against the initial reference and archives its acquisition times. Restore the sample and record the external source state before **Resume DC**. The same file stays open. A final reference can also be taken after **Stop DC**.
4. After resuming, the live spectrum subtracts the most recent measured reference drift. In **Show DC → OD corrected for blank drift**, the archived correction interpolates between measured reference times and only fills covered intervals. **Estimated blank drift** shows the contribution being subtracted.

Before **Start DC**, you can repeat **Background**, **Empty**, or **Reference**. Each attempt is stored in `calibration_captures`. The latest completed capture of each role becomes active under `calibration`. Interrupted captures leave the selection in place. Repeating a capture archives affected manual zeros in `calibration_zero_history`.

Use **Analysis → Calibration from raw data…** in a draft, a paused or stopped series, or a reopened HDF5. Select saved calibration captures, preview detector counts and OD, and choose Empty or Reference as the OD zero. **Recalculate OD** reads the archived counts of both sample channels and, when available, the raw repeat-reference counts used for drift correction. The recalculation is published as a new processing revision. **Show DC → Recalculated OD from raw** displays the result alongside the original measured OD view.

After **Stop DC** or opening an HDF5 through **Data → Open HDF5…**, **Start DC** offers **Continue**, **New Segment**, and **Check Calibration**. A new segment places the completed interval under `/entry/acquisition_segments` and uses the same file and elapsed time scale. Calibration checks record Background and Empty separately while preserving the original zeros. Use **Add Reference** for a new drift anchor. The dialog shows the age of the latest reference and recommends a fresh capture at 30 minutes or if the timestamp is unavailable.

The HDF5 file stores every block on both native wavelength grids, with a UTC timestamp, repeat index, index within the repeat, and detector settings. With 50 repeats of three blocks, each channel has a 150-row counts matrix for that capture. Counts are the spectra returned by the SDK after its configured hardware averaging. A stopped capture retains its recorded blocks and can be repeated. Calibration can be reopened before sample acquisition.

In **Show DC**, select **OD corrected for blank drift** to see the correction. It subtracts wavelength by wavelength the drift interpolated between measured blanks. The initial blank defines zero drift at series start and retains its actual capture time in the file. Samples outside a bracket have no corrected OD. With only two blanks the interpolation assumes linear drift. **OD vs initial blank** displays the measured sample OD relative to the initial blank. The map loads up to 500 rows for display. Zoom on the time axis and use **Load Zoomed Time Range** for detail.

Legacy **Load DAT…** opens older OD measurements. To continue a DAT run, complete the calibration in a new HDF5 file and choose **Resume** at **Start DC** to import the earlier OD rows. Only new acquisitions include raw counts.

## HDF5 schema v2

Gamma v2 uses NeXus base classes. The file has `format = avantes-gamma`, `version = 2`, and `default = entry`. `/entry` is `NXentry`, with ISO 8601 start time and `od_live` as its default plot. Each `NXdata` declares its signal and axes and has HDF5 dimension scales. The Gamma fields below define the application profile. [NeXus base classes](https://manual.nexusformat.org/classes/base_classes/core-structure.html), [NXdata conventions](https://manual.nexusformat.org/classes/base_classes/NXdata.html).

| Path under `/entry` | Class or shape | Content |
| --- | --- | --- |
| `instrument/detector_1`, `instrument/detector_2` | `NXdetector` | `data[scan, pixel]` as `float64` counts straight from the SDK after hardware averaging. `wavelength[pixel]` is the native grid in nm. `count_time_set[scan]` (s), `averages_set[scan]`, `trigger_mode_set[scan]`, and `readout_ok[scan]` describe each acquisition. |
| `acquisition` | `NXcollection` | Elapsed `time[scan]` and POSIX `time_utc[scan]` in s, estimated `dose[scan]` in Gy when specified, `metadata_json[scan]` for diagnostics and settings, and `committed_rows` as a group attribute. |
| `acquisition_segments/<id>` | `NXcollection` | Bounds of a completed interval, with same-file virtual views of its raw counts, times and OD. |
| `preview_captures` | `NXcollection` | Raw counts and timestamps recorded by Live Preview, grouped separately from the sample time series. |
| `raw_ch1`, `raw_ch2` | `NXdata` | Hard links to the detector signal and its native grid and to elapsed time. Each detector can have a different pixel count. |
| `lamp_monitor` | `NXdata` | Alias of raw Ch2, captured on every paired acquisition. This represents the lamp spectrum if Ch2 follows an independent reference path. |
| `sample` | `NXsample` | Run name and description, `sample_volume` (mL), `window_diameter` (entrance aperture in mm), `cell_type` (QZ or QS), optical path (mm), and `optical_volume` (probe volume in mL). |
| `reference` | `NXsample` | Reference optical path (mm), quartz `cell_type`, `same_cell_as_sample`, and a hard link to the shared `sample/window_diameter`. |
| `irradiation` | `NXcollection` | Nominal `dose_rate_set` in Gy/h and timed `state` markers as `NXlog`. |
| `od_live` | `NXdata` | Append-only sample OD against the original reference, before drift correction, on the Ch1 grid. For older runs, `delta_od` retains the stored kinetic-zero subtraction. |
| `calibration_captures/<id>` | `NXcollection` | Both channels in `chN_counts[block, pixel]`, time and repeat indices per block, and acquisition metadata. `committed_blocks` counts written rows and `complete` marks completed captures. |
| `calibration/{background,empty,reference,initial_blank}` | `NXcollection` | Completed calibration blocks. The older `sample_t0` role can still be read. |
| `calibration_zeros/{empty,reference}` | `NXdata` | Zero OD spectrum, selected UTC time and a link to the blocks used. |
| `blanks/<id>` | `NXcollection` | Reference counts, plottable `spectrum`, `capture_time_utc` from the first block, and `anchor_time` at the mean acquisition time for a repeat reference. Times are in s. |
| `processing/<revision>_blank_correction` | `NXprocess` | Blank IDs, measured anchor spectra, source OD path, method and processing date. `data/od` is corrected OD and `data/blank_drift` is the subtracted contribution. |
| `processing/<revision>_raw_recalculation` | `NXprocess` | Selected calibration paths and OD zero, source raw detector paths, and a new OD matrix on the native Ch1 grid. |
| `processing/<revision>_mcr_als` | `NXprocess` | Correction path, fitted row and wavelength indices, settings, objective history and fit diagnostics. `spectra/loadings`, `kinetics/amplitudes`, `data/fitted_od` and `data/residual_od` are plottable results. |
| `events/metadata_json` | Event list | Acquisition starts, stops, pauses and resumes with UTC timestamps. |

Missing counts or OD are `NaN`. Detector status codes are `1` for a successful readout, `0` for a failed readout and `-1` for missing status. An unknown integer setting is `-1`. Live OD uses the ratio of dark-subtracted detector signals, with the Ch2 intensities interpolated onto the Ch1 wavelength grid. Detector counts retain both native grids and do not include that interpolation or dark subtraction.

Each blank correction version freezes its input time axis and stores a complete snapshot. Adding a blank or selecting **Analysis → Recalculate OD from blanks** publishes a new `NXprocess` group. The **Estimated blank drift** and **OD corrected for blank drift** map views show the latest version. With just the initial and final blank, the model interpolates linearly over elapsed time. An intermediate blank changes that interpolation and shortens the interval over which linearity is assumed.

## MCR-ALS

**Show MCR** opens the latest fit. On a paused or stopped run, it offers a new fit if no result exists or a new blank has changed the correction. Choose 1–3 sample components. Blank drift is carried as a separate, measured contribution. The fit runs in the background and archives a new revision in the same file. The plots show spectra, kinetics, the reconstructed sample and blank spectra at a selected time point, and the measured blank anchors at a selected wavelength. The **Analysis** menu also provides direct access to fitting and the last saved result.

The fit uses OD from the latest blank correction. Interpolation fixes the blank contribution before fitting sample components. The fit retains rows with some valid corrected OD and uses wavelengths valid across those rows. Spectra and amplitudes are nonnegative by default. They can be independently switched to signed least squares for changes such as bleaching. Amplitudes are relative to spectra normalized to unit L2 norm. Overlap or a small residual alone does not uniquely identify chemical species. [pyMCR documentation](https://pages.nist.gov/pyMCR/usage.html).

Set the known dose rate and sample geometry in **Experiment → Dose and sample geometry…** before a run. A circular 8 mm window and 10 mm optical path give a geometric probe volume of 0.503 mL. Enter the filled volume separately if known. Use the red **Radiation present** and green **Radiation absent** button to log the operator's observations of the external source. Pausing acquisition alone leaves the marker as recorded. When available, MCR plots can switch between elapsed minutes and the dose integrated from the rate and those markers. Raw Ch2 records the monitor spectrum for future lamp corrections.

Run these commands inside the Gamma environment and project folder:

```bash
python avantes_analysis.py validate run.h5
python avantes_analysis.py recalculate run.h5
python avantes_analysis.py mcr run.h5 --components 2 --wavelength 350 700
python avantes_demo.py synthetic_run.h5 --fit
python avantes_analysis.py upgrade old_v1.h5 old_v2.h5
```

The synthetic file includes 241 spectra at 15 s intervals, two growing sample bands, wavelength-dependent fiber darkening and lamp spectral drift. It also includes five measured blank spectra and a synthetic fiber recovery profile with a three-day exponential time constant. Open the generated file with **Data → Open HDF5…**, then use **Show MCR** to inspect the two-component fit and its dose axis. The `simulation_truth` group contains the independent reference arrays used to assess the correction.

Version 1 HDF5 runs can still be viewed. When you resume, add a blank or start an analysis in the app, a version 1 run is copied into a separate v2 file.

## Hardware Files

Avantes SDK DLLs are in:

```text
drivers/avaspecx64.dll
drivers/avaspec.dll
```

Keep these files next to `avantes_dual_viewer.py` when moving this subproject to another Windows computer.

## Arduino

Default Arduino HTTP address:

```text
http://10.20.30.47
```

Frequency can be changed from GUI settings or directly:

```text
http://10.20.30.47/?freq=40
```

Allowed frequency range: `1-100 Hz`.
