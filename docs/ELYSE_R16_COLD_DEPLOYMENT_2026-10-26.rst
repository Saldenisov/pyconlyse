Verified r16 cold deployment
===========================

Two independent applications are installed and running on their respective XP
hosts. Both authenticated APIs report IDLE, zero native resources and no
automatic initialization:

* Acquisition: ``10.20.30.10:8772``, installation
  ``C:\ELYSE_Orchestrator_Acquisition_r16``.
* SuperVision: ``10.20.30.2:8772``, installation
  ``C:\ELYSE_Orchestrator_Supervision_r16``.

Each host has its own verified portable CPython3.4.4 x86 runtime at
``C:\Python34_ELYSE`` with NumPy 1.15.4, nidaqmx 0.5.7, six 1.16.0 and Tk.
Source closure build identity on both installations is
``567ed17539439c9e91e881c2da0a09193c8316de5cab4236d677950b6405c6fc``;
application variants, sessions, keys, configuration and ownership are separate.
The Acquisition site retains its operator-supervised profile and enabled
command transport. Current VI ownership still disables native command admission.

Only the previous cold Python Acquisition application was stopped normally.
The new application's signed API session matches every received bank's session.
Two consecutive receiver observations increased from 11499 to 11504, and all 27
bank sequences advanced. Maximum bank age in that verification was 0.25 seconds.
The web facade returned FRESH with all 27 banks from the new session. This
demonstrates reception of updated snapshots; it does not imply that every
physical value changed or that the banks were sampled atomically.

The one existing Everest Tango Device Server was updated and restarted with
its previous legacy source configuration. Its PID after restart was 32304.
Source rollback backup:
``F:\ELYSE_Telemetry_Server\postgres_v3\rollbacks\orchestrators_r16_20261026T144616Z``.
The new Acquisition executable initially had outgoing telemetry but blocked
incoming HTTP. After the Windows permission window was handled, signed API
reads and the existing Tango runtime bridge both worked.

Live verification and source/runtime receipts are saved under
``F:\ELYSE_Orchestrators\r16_20261026``. The detailed file is
``cold_deployment_verification.json``. No Python NI card was initialized, no
device command was sent, and neither running VI was stopped or modified.

SuperVision's r16 publisher remains disabled. Its running VI has not yet been
instrumented with the new telemetry producer. DS federation remains disabled
so the current complete Acquisition VI stream continues. The r17 candidate
contains the additional SuperVision VI ingress and camera viewer; those are
prepared source, not live LabVIEW/camera qualification.
