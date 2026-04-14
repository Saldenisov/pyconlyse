# External Solutions Survey

Date:
- 2026-04-13

Purpose:
- summarize what already exists publicly for Hamamatsu camera control and what appears to be missing for HPD-TA / streak-camera / RemoteEx control

## Bottom line

Publicly visible solutions do exist for ordinary Hamamatsu DCAM-compatible cameras under Tango or EPICS.

Publicly visible solutions specific to:

- Hamamatsu streak camera
- HPD-TA
- TaRemoteEx / RemoteEx
- Tango device server

were not found during this pass.

That means the likely path for this project is a custom Tango device server that wraps HPD-TA RemoteEx directly.

## What does exist publicly

### 1. Hamamatsu DCAM support through LIMA/Tango

Public GitHub repository found:

- `tiagocoutinho/hamamatsu`
  - describes itself as a Python library for Hamamatsu detectors
  - includes an optional LIMA plugin
  - mentions an optional Tango device class
  - explicitly says it was tested on model `C11440-36U`
  - describes itself as control for basic Hamamatsu camera features

Important limitation for our use case:
- this repository is for DCAM detector control, not HPD-TA streak-system control
- the repository also says its simulator only simulates a `RemoteEx TCP interface` and is still under development

Practical value:
- useful as a reference for Tango packaging patterns and camera-server layering
- not a drop-in solution for HPD-TA streak systems

## 2. Hamamatsu official third-party plugin ecosystem for DCAM cameras

Hamamatsu officially advertises third-party integrations for DCAM-compatible cameras, including:

- LabVIEW
- MATLAB
- EPICS
- Micro-Manager

Important limitation:
- these official plugins are described as applying to `Hamamatsu DCAM compatible B/W cameras`
- that is a different control stack than HPD-TA / streak camera RemoteEx

Practical value:
- confirms that Hamamatsu is comfortable with external control stacks
- provides architectural references for ordinary camera integration
- does not solve the HPD-TA streak-camera problem directly

### 3. Hamamatsu EPICS path for DCAM cameras

Hamamatsu points to:

- `ADHamamatsuDCAM`

and describes it as:

- an EPICS plugin for Hamamatsu cameras with the EPICS areaDetector module
- supporting DCAM-compatible B/W cameras

Practical value:
- useful if the lab ever wants EPICS instead of Tango for ordinary Hamamatsu cameras
- not directly applicable to HPD-TA streak systems

### 4. Official Hamamatsu streak-system software

Public Hamamatsu support pages show:

- `HPD-TA`
- `TOKUSTREAK`

This confirms that Hamamatsu's official control story for streak systems is application-centric. In other words, Hamamatsu expects users to operate streak systems through dedicated vendor software rather than through a public low-level control server such as Tango.

Practical value:
- supports the design choice to wrap vendor software rather than bypass it

## What I did not find publicly

No public ready-made implementation was found for:

- a Tango device server for HPD-TA
- a Tango device server for Hamamatsu streak camera via RemoteEx
- a public Python package dedicated to HPD-TA RemoteEx control
- a public EPICS wrapper specifically for HPD-TA streak systems

Searches were performed across:

- web search
- public GitHub repository search
- Tango-related search terms
- HPD-TA / RemoteEx specific search terms

This does not prove that no such software exists anywhere, but it strongly suggests:

- if an implementation exists, it is likely lab-private
- or distributed directly by an institute rather than publicly maintained

## Recommended interpretation

The best public prior art is split across two categories:

1. Tango or LIMA wrappers for ordinary Hamamatsu DCAM cameras
2. Hamamatsu's own HPD-TA / TOKUSTREAK applications for streak systems

For this project, those two categories combine into one practical answer:

- keep HPD-TA as the hardware coordinator
- expose its RemoteEx functionality through a custom Tango server

## Public references used

- Hamamatsu software page:
  - https://www.hamamatsu.com/us/en/product/cameras/software.html
- Hamamatsu DCAM third-party plugins:
  - https://dcam-api.com/third-party-plugins/
- Hamamatsu support page mentioning streak-camera software and TOKUSTREAK:
  - https://www.hamamatsu.com/eu/en/support/service-and-support.html
- GitHub repository for Hamamatsu DCAM + LIMA/Tango integration:
  - https://github.com/tiagocoutinho/hamamatsu
