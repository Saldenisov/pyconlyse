# TRANCON-DAQ direct device server

`DS_DAQmx` controls the NI PCIe-6320 card installed in Everest. It is separate
from `DS_DAQmx_ZMQ`, which only receives network supervision values.

## Tango and Astor identity

- Physical card: `TRANCON-DAQ`
- Tango device: `control/DAQ/TRANCON-DAQ`
- Astor server: `DS_DAQmx/TRANCON-DAQ`
- Everest startup level: `1`

Register or refresh the entry with:

```powershell
python add_ds_DAQmx.py
```

The channel map is in `daqmx_transcon.ini`. The direct server currently accepts
`DigitalIn`, `DigitalOut`, `AIcurrent`, `AIVoltage`, and `DigitalCounter`.

## Operator interfaces

- Web: open `/daqmx-clients`, select `control/DAQ/TRANCON-DAQ`, and choose
  **Open card**.
- Standalone PyQt5: run `python DS_DAQmx_client.py`. The physical card is the
  default instance, so no command-line argument is required.

Digital outputs use explicit **ON** and **OFF** commands. Their state is shown as
`UNKNOWN` after a server restart until the server has issued a command. This is
intentional: reading an output line by temporarily configuring it as a digital
input could stop driving the physical output.

Web mutations use the hardware-approval transport. Counter reset has its own
`daqmx.reset` authorization route; output writes use `daqmx.write`.
