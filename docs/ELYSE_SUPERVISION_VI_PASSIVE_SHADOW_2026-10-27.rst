Original SuperVision VI passive shadow
=====================================

The optional local ``config.supervision.control.json`` flag pins a process to
the original-VI shadow policy::

    "vi_passive_shadow": true

Every deployment used alongside the original SuperVision VI must explicitly
set this flag to true in the installed local configuration before starting the
orchestrator. The packaged default is false; an IDLE window, zero Python NI
resources, disabled remote commands or an absence of incoming telemetry does
not by itself pin passive shadow operation. Confirm the running snapshot says
``vi_passive_shadow=true`` and ``owner_mode="VI_PASSIVE_SHADOW"``.

The runtime reports ``owner_mode="VI_PASSIVE_SHADOW"`` and
``native_initialization_allowed=false``. Initialize remains one of the three
GUI labels, but its button is disabled. Direct, queued and private native
initialization paths reject the request before card construction. The command
broker and all command capabilities remain disabled even if command permission
or counter commissioning flags are otherwise true.

The original VI retains synchronization/camera ownership. Only its observed
exports enter the orchestrator's passive ingress and then the common Everest
Device Server. Missing exports remain missing. Silence, an expired frame,
elapsed time or a quiet VI do not enable native initialization.

The flag cannot be changed through the runtime property or an HTTP command.
Changing ownership policy requires a cold restart with explicitly changed local
configuration. Omitted or false retains the existing native-capable behavior;
neither setting automatically initializes cards. The cold installer preserves
the optional flag and rejects non-Boolean values. Its existing uncommissioned
site-profile restrictions remain unchanged.

Offline regressions use the production authenticated HTTP handler and the typed
8768 ingress handler at newly allocated loopback ports. They verify disabled
leases/commands and preserved counter/image payloads without starting a native
card owner or an outbound relay. Synthetic exports do not qualify the original
VI export producer or prove its live camera/timing correspondence.
