# Manual and operator probes

This lane is excluded from the software-only gate. Files here may require a
configured Tango database, connected instruments, a GUI session, or an
operator-approved laboratory state.

Run a probe only as a direct Python script after the relevant manual safety
gate; never run this directory through pytest:

```bash
conda run -n pyconlyse39 python tests/manual/netio/netio_state_probe.py <device-name>
```

The `legacy`, `integration`, `main_app`, and `utilities` lanes are also
excluded from default collection. To diagnose one of them intentionally,
clear default pytest options explicitly, for example:

```bash
conda run -n pyconlyse39 python -m pytest -o addopts='' tests/integration
```
