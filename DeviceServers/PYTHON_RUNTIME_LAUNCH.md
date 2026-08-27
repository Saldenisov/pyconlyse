# Device-server Python runtime selection

All `DS_*.bat` wrappers use `launch_device_server.cmd` or
`run_logged_server.cmd`. Terminal-tab behavior and server script arguments stay
unchanged. `run_logged_server.cmd` selects an interpreter before starting the
server.

Python starts in the background before any terminal UI is requested. Tabbed
wrappers then target the named Windows Terminal window `PyconlyseTango` and
tail the standard server log. A slow Windows Terminal tab no longer delays
Tango registration. Override only with `PYCONLYSE_WT_WINDOW`; a missing Windows
Terminal still falls back to a separate visible log-tail window.

The runner invokes the interpreter directly with `PYTHONUNBUFFERED=1` and CMD
output redirection. It does not start PowerShell or Tee before Python; those
added about 2.6 seconds of cold-start latency on Elysium 2. Keeping the script
as Python's first command-line argument preserves Starter's process parser.

Selection order:

1. Existing absolute `PYCONLYSE_PYTHON` ending in `.exe`.
2. `%ANACONDA%`, `%CONDA_PREFIX%`, and common `%USERPROFILE%`/`%LOCALAPPDATA%`
   Conda environment locations for `%PYCONLYSE_ENV%`.
3. No Conda activation fallback. Startup fails clearly when no absolute
   interpreter can be resolved.

The direct path is added with its Conda `Library\bin` and `Scripts` folders to
the child `PATH`; the wrapper never changes system-wide environment variables.
The selected path/source is written to the standard Tango Starter log. Missing
direct paths fail instead of activating Conda or selecting an arbitrary
`python` from `PATH`.

Set the following machine or interactive-user variables once on each Windows
host when the known runtime path differs from discovered locations:

```cmd
setx PYCONLYSE_ENV pyconlyse39
setx PYCONLYSE_PYTHON C:\Users\operator\miniconda3\envs\pyconlyse39\python.exe
```

Use an absolute path. Verify a single wrapper in an interactive terminal first;
do not restart a server fleet merely to change this setting.

## Astor executable compatibility

`DS_*.exe` wrappers are intentionally absent, so Astor resolves the reviewed
`DS_*.bat` launchers. `compile_wrapper.bat` and the DG645 EXE build helper are
hard-disabled to prevent accidental recreation of stale Conda-launching EXEs.
