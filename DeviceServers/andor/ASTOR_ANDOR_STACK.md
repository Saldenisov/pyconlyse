# Astor Andor Stack

Files prepared for Windows deployment:

- [add_ds_ANDOR_STACK.py](/Users/sad/dev/pyconlyse/DeviceServers/andor/add_ds_ANDOR_STACK.py)
- [register_andor_stack.bat](/Users/sad/dev/pyconlyse/DeviceServers/register_andor_stack.bat)
- [DS_ANDOR_CCD.bat](/Users/sad/dev/pyconlyse/DeviceServers/DS_ANDOR_CCD.bat)
- [DS_ANDOR_SPECTROGRAPH.bat](/Users/sad/dev/pyconlyse/DeviceServers/DS_ANDOR_SPECTROGRAPH.bat)

## Devices Registered By The Script

- `manip/CR/ANDOR_CCD1`
- `manip/CR/ANDOR_SHAMROCK1`
- `manip/CR/ANDOR_KYMERA1`

## Server Instances Expected By Astor

- `DS_ANDOR_CCD/1_ANDOR_CCD1`
- `DS_ANDOR_SPECTROGRAPH/1_ANDOR_SHAMROCK1`
- `DS_ANDOR_SPECTROGRAPH/2_ANDOR_KYMERA1`

## Before Running On Windows

Edit the paths in `add_ds_ANDOR_STACK.py` if your SDK is not under:

- `C:\Andor SDK`
- `C:\Andor SDK\Shamrock`

Also confirm:

- `camera_index`
- `spectrograph_index`
- `linked_spectrograph_ds`
- `pixel_number`
- `pixel_width_um`

## Suggested Order

1. Run `register_andor_stack.bat`
2. Open Astor and refresh
3. Start `DS_ANDOR_CCD/1_ANDOR_CCD1`
4. Start `DS_ANDOR_SPECTROGRAPH/1_ANDOR_SHAMROCK1`
5. Start `DS_ANDOR_SPECTROGRAPH/2_ANDOR_KYMERA1`

If Shamrock/Kymera communication depends on the Andor camera chain on your host, start the CCD first.
