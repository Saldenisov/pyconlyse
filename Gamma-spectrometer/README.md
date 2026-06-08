# Gamma-spectrometer

Standalone PyQt5 application for two Avantes spectrometers and Arduino TTL control.

This subproject does not use Tango.

## Windows First Run

Run:

```text
first_run_gamma_spectrometer.bat
```

It opens an elevated PowerShell window, installs Miniconda if needed, asks which env to use, creates or updates the env, then starts the viewer.

Choices:

```text
1. pyconlyse39  - Python 3.9, recommended for real Avantes hardware
2. pyconlyse313 - Python 3.13, modern test environment
```

Second-time start:

```text
run_avantes_dual_viewer.bat
run_avantes_dual_viewer_py313.bat
```

## Conda Setup

```bash
cd /Users/sad/dev/pyconlyse/Gamma-spectrometer
conda env create -f environment-py39.yml
conda activate pyconlyse39
python avantes_dual_viewer.py
```

Python 3.13:

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

Pip setup is intended for Python 3.9. Use conda for Python 3.13.

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

Demo kinetics adds a synthetic growing UV-visible species during data collection. Measure reference, measure background, click **Start DC**, then **Show**. With `Rate = 1 s`, the OD map fills over about 40 seconds.

On Windows with real hardware:

```bat
set AVANTES_EMULATOR=0
python avantes_dual_viewer.py
```

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
