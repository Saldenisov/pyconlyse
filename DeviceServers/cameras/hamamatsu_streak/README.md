# Hamamatsu Streak Camera Tango Notes

Date:
- 2026-04-13

Purpose:
- collect the local facts, vendor protocol notes, and external research needed to implement a future Tango device server for the Hamamatsu streak camera setup controlled by HPD-TA

This directory is documentation-first on purpose. The current setup is not a generic Hamamatsu DCAM camera. It is a streak system managed by HPD-TA and exposed through the RemoteEx TCP interface. That changes the design substantially: the safest first device server is a Tango wrapper around HPD-TA/RemoteEx, not a direct low-level camera driver.

## Documents

- `HPDTA_REMOTEEX_RESEARCH_NOTES.md`
  - confirmed protocol facts from the vendor manuals and local HPD-TA configuration
- `EXTERNAL_SOLUTIONS_SURVEY.md`
  - what public device-server-like solutions already exist, and what does not seem to exist publicly
- `TANGO_DEVICE_SERVER_DEVELOPMENT_PLAN.md`
  - recommended architecture, attribute/command split, and phased implementation plan

## Local source material already verified

- `/Volumes/Everest/HPDTA950.zip`
  - contains `RemoteExProgrammersHandbook.pdf`
  - contains `HPDTA.pdf`
  - contains `Spectro.pdf`
  - contains `TaRemoteEx.exe`
  - contains `RemoteExClient.exe`
  - contains script examples under `ScriptProgramming/*.hsc`
- `/Volumes/Everest/Hamamatsu.zip`
  - contains `HPDTA/HPDTA8.INI`
  - contains `HPDTA/Streaker.ini`
  - contains `HPDTA/defaultHW.hwp`
  - contains time-scaling calibration files `*.scl`
  - contains `RemoteExClient.INI`

## Current working assumptions

- HPD-TA is the authoritative control layer for the streak experiment.
- RemoteEx is the correct remote-control API for this installation.
- The first Tango server should serialize commands through a single RemoteEx command channel.
- Data transfer should start with file-based export (`ImgSave`, `SeqSave`, `ImgDataDump`) before moving to direct binary transfer on the RemoteEx data port.
- The user-reported spectrograph is a Kymera. HPD-TA documentation also shows support for Shamrock/Kymera-family spectrographs.

## Immediate next implementation target

Build a minimal Python package that provides:

- a `RemoteExClient` transport
- a `HamamatsuStreakController` service layer
- a Tango device class on top of that service
- a simulation or replay mode for development away from hardware

The detailed plan lives in `TANGO_DEVICE_SERVER_DEVELOPMENT_PLAN.md`.
