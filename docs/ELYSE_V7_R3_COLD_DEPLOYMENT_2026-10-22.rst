v7-r3 cold XP deployment and live bridge acceptance
==================================================

Deployment boundary
-------------------

After explicit action-time approval, v7-r2 was closed through its Stop server
button with IDLE, zero NI tasks, revision zero and commands disabled confirmed
immediately beforehand. Port 8772 was then confirmed closed. The new package
was copied into a separate directory, ``C:\ACQ_Python_Control_20261022_v7_r3``,
and only ``acquisition_control_server.pyw`` was launched. The old installation
was preserved; Windows startup configuration was not changed.

The new boot was verified at 11:31:19 Europe/Paris on 22 October 2026. Its
installed-source fingerprint matched the checked artifact::

    session  9481cfbec8e3441ea095deffd2361e54
    build_id 4da741d6ab733645fc309131c6327c39a1ec1863fda13a06fe05e973a7166708
    zip_sha  848B4F5105D81857C6F154A6865FAD1429D3E005065C6E3CCEFB96BCD7E1CBE8

The site-specific configuration differs from the generic manifest only in the
existing XP read-key path. No key bytes were transferred or printed. Initialize
was not pressed; native sequence, state revision and NI task count remained
zero. Automatic/remote initialization and remote commands remained disabled.
Acquisition and its existing passive VI transport were not stopped, restarted
or saved. Everest's receiver, web process and recorder were not restarted, and
the live HDF5 file was not opened.

Finite live acceptance
----------------------

Between 11:32:48.986 and 11:34:49.056 Europe/Paris, a read-only check sampled
Tango ``telemetry_json`` and the web telemetry GET endpoint once per second.
Signed XP snapshot GETs before and after the interval confirmed the same boot,
IDLE, zero NI resources, native sequence/revision zero and disabled commands.

Both sides contained exactly the expected 27 bank names in all 120 checks.
Every bank on each side had 120 distinct publication sequences. All web samples
were FRESH; no sampled bank was null, stale, from another boot, or marked with
a bank error. No read failed. Maximum observed bank age was 0.797 s at Tango
and 0.515 s at the web. In 104 checks the two independently read sides exposed
the same sequence; differing sequences during the remaining reads do not by
themselves imply loss because publication continued between the GETs.

VI acceptances increased from 1580 to 3085, and signed Everest acknowledgements
from 635 to 1174. The existing receiver session remained unchanged. The rendered
web page also showed the connected watchdog, Python IDLE, and current Canon and
Section readings. The previously observed OWNER_STATE_BUSY null substitution
did not recur in the sampled interval despite 373 additional busy projection
reads.

The ingress still rejects promptly when the lifecycle lock cannot be acquired;
that counter increased from 79 to 169. The ownership fence was not relaxed.
The bounded latest-only outbox also replaces pending images, so this acceptance
does not establish lossless source-frame delivery or indefinite availability.
The 27 controls are sequential snapshots, not proven atomic physical samples;
freshness does not establish electrical safety or calibrated hardware readiness.

Evidence is retained outside the repository at::

    C:\dev\ELYSE-ACQ-telemetry\2026-10-22\v7-r3-live-deployment\deployment.json

The earlier recovery report describes the preceding v7-r2 state. This acceptance
supersedes its pending-deployment status, not its recorded historical evidence.
