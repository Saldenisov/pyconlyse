# Gamma-spectrometer

Standalone PyQt5 application for two Avantes spectrometers and Arduino TTL control.

This subproject does not use Tango.

## Windows на экспериментальном ноутбуке

Скачайте папку `Gamma-spectrometer` из ветки [Avantes](https://github.com/Saldenisov/pyconlyse/tree/Avantes). Если Git уже есть, скопируйте в PowerShell:

```powershell
git clone --branch Avantes --single-branch --filter=blob:none --sparse https://github.com/Saldenisov/pyconlyse.git pyconlyse-avantes-gamma
git -C .\pyconlyse-avantes-gamma sparse-checkout set Gamma-spectrometer
cd .\pyconlyse-avantes-gamma\Gamma-spectrometer
.\run_avantes_dual_viewer.bat
```

Если предыдущий клон остановился на ошибке Git LFS в `utilities/IRpy-server`, выполните команды выше в папке, где ещё нет `pyconlyse-avantes-gamma`. Выборочная выгрузка берёт программу и её драйверы из `Gamma-spectrometer`.

Если Git ещё нет, [скачайте ZIP ветки Avantes](https://github.com/Saldenisov/pyconlyse/archive/refs/heads/Avantes.zip), распакуйте его, откройте папку `Gamma-spectrometer` и дважды щёлкните `run_avantes_dual_viewer.bat`.

При первом запуске нужен интернет. BAT проверит 64-разрядный Python 3.11 и Git, скачает переносимые копии при необходимости, создаст окружение в `.gamma-tools\venv311` и установит зависимости. Для MCR-ALS используется проверенный пакет `pyMCR 0.3.2`. После проверки импортов откроется окно программы для работы со спектрометрами. Права администратора для этого запуска не требуются.

При следующих запусках используйте тот же BAT. Окружение используется повторно. Если запуск прервётся, окно покажет ошибку. Для пробы на двух эмулируемых спектрометрах запустите `run_gamma_demo.bat`.

Чтобы только установить пакеты, запустите из папки `Gamma-spectrometer`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install_gamma_packages.ps1
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

Demo kinetics injects a synthetic growing UV-visible species into the sample-channel intensity before OD is calculated. Measure reference and background, click **Start DC**, then **Show DC**. With `Rate = 1 s`, the OD map fills over about 40 seconds.

On Windows with real hardware:

```bat
set AVANTES_EMULATOR=0
python avantes_dual_viewer.py
```

## Recording a run and measuring blanks

1. Measure **Background** with the probe lamp off, then **Reference** with the lamp on. Insert the blank and click **Initial Blank**. Insert the sample and use live preview to check its spectrum. Stop the preview and click **Set Zero** to use that sample spectrum as the kinetic zero.
2. Choose the folder, file name, and collection interval (default 15 s), then click **Start DC**. Every acquisition appends to the run's `.h5` file. Existing names get a numbered sibling unless you choose **Resume** for the current or opened run.
3. Use **Stop DC** at the end, insert the blank, then choose **Add Blank…**. Enter a delay in minutes. Zero starts the capture immediately. With DC already paused or stopped, confirm only once the blank is installed. The capture starts automatically when the timer expires.
4. During DC, **Add Blank…** schedules a reminder. At the due time the series continues. When the experiment permits an interruption, use **Pause DC**, handle irradiation and the sample exchange on the apparatus, then click **Capture Blank**. Restore the sample before **Resume DC**. Pauses retain the same file and elapsed time.

The HDF5 file stores both channels in detector counts, the wavelength grids, dark and reference blocks, the kinetic zero, and the blank acquisitions. Measurement metadata include UTC acquisition times, integration times, hardware averaging counts, and trigger settings. Blank metadata include the requested delay, scheduled time, and capture time. Counts are the spectra returned by the SDK after its hardware averaging. Capturing repeated blocks is needed to estimate their repeatability.

In **Show DC**, select **OD corrected for blank drift** to see the correction. It subtracts wavelength by wavelength the drift interpolated between measured blanks. The initial blank defines zero drift at series start and retains its actual capture time in the file. Samples outside a bracket have no corrected OD. With only two blanks the interpolation assumes linear drift. **OD vs initial blank** displays the measured sample OD relative to the initial blank. The map loads up to 500 rows for display. Zoom on the time axis and use **Load Zoomed Time Range** for detail.

Use **Data → Open HDF5…** to reopen a run. Legacy **Load DAT…** still opens older measurements. If you resume a DAT run, its OD history is copied into a new HDF5 file and only the new acquisitions contain raw detector counts.

## HDF5 schema v2

Gamma v2 uses NeXus base classes. The file has `format = avantes-gamma`, `version = 2`, and `default = entry`. `/entry` is `NXentry`, with ISO 8601 start time and `od_live` as its default plot. Each `NXdata` declares its signal and axes and has HDF5 dimension scales. The Gamma fields below define the application profile. [NeXus base classes](https://manual.nexusformat.org/classes/base_classes/core-structure.html), [NXdata conventions](https://manual.nexusformat.org/classes/base_classes/NXdata.html).

| Path under `/entry` | Class or shape | Content |
| --- | --- | --- |
| `instrument/detector_1`, `instrument/detector_2` | `NXdetector` | `data[scan, pixel]` as `float64` counts straight from the SDK after hardware averaging. `wavelength[pixel]` is the native grid in nm. `count_time_set[scan]` (s), `averages_set[scan]`, `trigger_mode_set[scan]`, and `readout_ok[scan]` describe each acquisition. |
| `acquisition` | `NXcollection` | Elapsed `time[scan]` and POSIX `time_utc[scan]` in s, estimated `dose[scan]` in Gy when specified, `metadata_json[scan]` for diagnostics and settings, and `committed_rows` as a group attribute. |
| `raw_ch1`, `raw_ch2` | `NXdata` | Hard links to the detector signal and its native grid and to elapsed time. Each detector can have a different pixel count. |
| `lamp_monitor` | `NXdata` | Alias of raw Ch2, captured on every paired acquisition. This represents the lamp spectrum if Ch2 follows an independent reference path. |
| `sample` | `NXsample` | Window diameter and optical path in mm. Geometric probe and operator-entered filled volumes in mL. |
| `irradiation` | `NXcollection` | Nominal `dose_rate_set` in Gy/h and timed `state` markers as `NXlog`. |
| `od_live` | `NXdata` | Append-only `od[scan, wavelength]` against the lamp reference and `delta_od[scan, wavelength]` as displayed during acquisition. Both are dimensionless and use the Ch1 grid. `delta_od` includes **Set Zero** when configured. |
| `calibration/{background,reference,initial_blank,sample_t0}` | `NXcollection` | Available calibration blocks, both channels in counts, timestamps and acquisition metadata. |
| `blanks/<id>` | `NXcollection` | Counts, a plottable `spectrum`, and `anchor_time`, `capture_time_utc`, plus `requested_delay`, `request_time_utc` and `scheduled_time_utc` for scheduled captures. All times are in s. |
| `processing/<revision>_blank_correction` | `NXprocess` | Blank IDs, measured anchor spectra, source live-OD path, method and processing date. `data/od` is corrected OD and `data/blank_drift` is the subtracted contribution. |
| `processing/<revision>_mcr_als` | `NXprocess` | Correction path, fitted row and wavelength indices, settings, objective history and fit diagnostics. `spectra/loadings`, `kinetics/amplitudes`, `data/fitted_od` and `data/residual_od` are plottable results. |
| `events/metadata_json` | Event list | Acquisition starts, stops, pauses and blank scheduling events with UTC timestamps. |

Missing counts or OD are `NaN`. Detector status codes are `1` for a successful readout, `0` for a failed readout and `-1` for missing status. An unknown integer setting is `-1`. Live OD uses the ratio of dark-subtracted detector signals, with the Ch2 intensities interpolated onto the Ch1 wavelength grid. Detector counts retain both native grids and do not include that interpolation or dark subtraction.

Each blank correction version freezes its input time axis and stores a complete snapshot. Adding a blank or selecting **Analysis → Recalculate OD from blanks** publishes a new `NXprocess` group. The **Estimated blank drift** and **OD corrected for blank drift** map views show the latest version. With just the initial and final blank, the model interpolates linearly over elapsed time. An intermediate blank changes that interpolation and shortens the interval over which linearity is assumed.

## MCR-ALS

**Show MCR** opens the latest fit. On a paused or stopped run, it offers a new fit if no result exists or a new blank has changed the correction. Choose 1–3 sample components. Blank drift is carried as a separate, measured contribution. The fit runs in the background and archives a new revision in the same file. The plots show spectra, kinetics, the reconstructed sample and blank spectra at a selected time point, and the measured blank anchors at a selected wavelength. The **Analysis** menu also provides direct access to fitting and the last saved result.

The fit uses OD from the latest blank correction. Interpolation fixes the blank contribution before fitting sample components. The fit retains rows with some valid corrected OD and uses wavelengths valid across those rows. Spectra and amplitudes are nonnegative by default. They can be independently switched to signed least squares for changes such as bleaching. Amplitudes are relative to spectra normalized to unit L2 norm. Overlap or a small residual alone does not uniquely identify chemical species. [pyMCR documentation](https://pages.nist.gov/pyMCR/usage.html).

Set the known dose rate and sample geometry in **Experiment → Dose and sample geometry…** before a run. A circular 8 mm window and 10 mm optical path give a geometric probe volume of 0.503 mL. Enter the filled volume separately if known. Use **Mark irradiation on/off** to record changes in the external source state. Pausing acquisition alone leaves that state unchanged. When available, MCR plots can switch between elapsed minutes and the dose integrated from the rate and those markers. Raw Ch2 records the monitor spectrum for future lamp corrections.

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
