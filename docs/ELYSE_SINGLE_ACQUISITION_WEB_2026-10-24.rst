One Acquisition application and one telemetry/control device
==========================================================

Architecture decision
---------------------

ELYSE hardware control uses one application on ``10.20.30.10`` and one Tango
device, ``elyse/acquisition/telemetry``, on Everest. Telemetry and commands are
two directions of that device, not separate telemetry and control servers::

    Pyconlyse web -> web facade -> elyse/acquisition/telemetry -> XP application
    Pyconlyse web <- web facade <- elyse/acquisition/telemetry <- XP application

The XP application has two source modes. Without local NI initialization it
relays the VI stream. After explicit local initialization it publishes its own
NI observations. Absence of VI traffic alone must not initialize cards or
start equipment. Its internal listener, publisher and isolated NI owner are
not separately launched telemetry applications. The web never addresses XP,
NI or PSP directly.

``/api/elyse/acquisition/telemetry`` and ``/api/elyse/acquisition/control`` are
two web routes to that same device, not two Device Servers. The first reads
``telemetry_json``; the second reads ``runtime_json`` and sends named intents
through ``ExecuteCommand``.

``web/backend/acq_contract.py`` now supplies the fixed host/device identity to
both web blueprints. Telemetry, runtime metadata, cooling observations and
``ExecuteCommand`` use the same device. The cooling route defaults to
``unified``. Old ``labview``/``xp_control`` configuration labels are aliases for
that route; the observed producer determines the returned source label.
``xp_runtime`` is explicitly rejected without contacting another device. No
fallback to ``elyse/acquisition/runtime`` or a separate control DS remains in
these live web routes. Historical archives can still use the existing local
read-only PostgreSQL reader; this is not a second live Acquisition transport.

Source selection and command boundaries
---------------------------------------

The public control view includes the XP-reported ``source_mode`` and the
configured topology. ``LABVIEW_BRIDGE`` is read-only. Only ``PYTHON_NATIVE``
can expose admitted named commands, with all existing capability, ownership,
freshness and commissioning gates. ``TRANSITION_OR_FAULT`` and unknown/missing
mode metadata cannot grant actuation. POST rechecks the mode after the browser
confirmation; a former native observation cannot authorize a later VI-mode
operation. These fields describe software routing, not physical acknowledgement.

The existing 27-bank envelope is unchanged. Native unsupported banks remain
explicitly unavailable, not zero-filled. Receiver ON and bank count alone do
not establish fresh measurements, valid interlocks or physical readiness.
Metadata and bank reads are separate observations, not an atomic transaction;
the Device Server and XP admission fences remain authoritative at execution.

Web client and transitional panels
----------------------------------

``acqTelemetryClient`` is the canonical telemetry/control/cooling client. GET
deadlines are 5 s, including JSON decoding. Cancellation propagates without
consuming an armed hardware approval. An unsettled read cannot pin the polling
loop forever: reads can recover independently, without process restart or
command replay. Command acceptance retains its separate 10 s deadline,
one-use approval and at-most-once/UNKNOWN handling.

The candidate Elyse page keeps one persistent bank poller across tabs. The
connection panel and raw-bank view consume that same observation. The panel
distinguishes XP application state, source mode, receiver quality and the
fixed read/write device. Local Initialize/Deinitialize/Stop server and remote
initialization policy are unchanged.

``elyseSupervisionClient`` is a compatibility adapter for the existing rich
panels: its telemetry, controlState, command and coolingSafety methods are
the canonical client functions themselves. It no longer contains a second
command HTTP implementation without one-use approval. Legacy intent staging
and submission fail locally without a request. Inert replay, model, history
and local draft methods remain transitional. Removing the Supervision UI/model
namespace later must not require a new Acquisition application or Tango device.

A correlated first-attempt preflight refusal now reports REJECTED with
``dispatch_attempted=False`` and code ``acquisition_pre_dispatch_rejected``.
It is emitted only after the existing-ID checks and before reservation or
ExecuteCommand. This covers source/session/capability changes and read-only
preflight failure. The client accepts only the exact status/code and receipt
proof, not generic 409/5xx replies. Older/reloaded uncertainty and unknown
post-dispatch outcomes cannot be cleared by this response; no operation is
automatically resent. One-use authorization refusals keep the existing narrow
status/code proof as well.

Validation and deployment boundary
-----------------------------------

The nine new single-device web tests use one fake Tango proxy for reads,
cooling and named writes; requesting any other device fails the fixture.
Cases cover the native-to-VI transition between confirmation and POST,
untrusted enabled capabilities in non-native modes, missing/unknown source
metadata and old cooling labels. All I/O remains fake or private loopback.

The focused web API subset passed 84 tests. The frontend passed all 21 Jest
suites, 231 tests, in 14.263 s. Nine changed/new JavaScript files passed strict
ESLint with zero source warnings. Tests include a 5 s hung read/body, read
recovery, cancellation, one shared poller, invalidated confirmation and a
metadata outage without XP restart or command replay.

The combined Python 3.12 regression passed 659 tests in 51.78 s with
``--deny-network``. Two platform/optional tests were skipped; the same two
Windows symlink-creation cases remain deselected because this account lacks
the required privilege (``WinError 1314``). The 24 existing deprecation/import
warnings remain. The counts overlap the focused subset; no live PostgreSQL
integration was enabled. XP source and Device Server source are unchanged.
The source/test commit is ``ded2317a``.

The optimized build completed with the existing seven hook warnings in six
unchanged components, old toolchain notices and the existing large-bundle
warning. No source warning was reported by the separate strict lint check.
Build output:
``C:\Users\elyse\AppData\Local\Temp\elyse-single-ds-web-final-7747da9cbf444d23a785e72e052da74c``.
``static/js/main.13011d01.js`` SHA256 is
``3DECB87B32F537EEACBB581B140695FF06ECA00904E84478430FFD7FB3D0F7D3``;
``asset-manifest.json`` SHA256 is
``3E5F0BF11CDBF362BB8BDFC2C7A8EDA78A18AE5F82BA67A3B580568462EA303C``.
The bundle contains the single-connection panel, both source-mode labels,
same-device topology and strict pre-dispatch refusal code.

The routing fixture synchronizes only its fake lease-issuance scheduling point
and advances its virtual lease clock between operator decisions. Otherwise an
intentional nonblocking refusal under concurrent fake-owner lock contention
can make a routing assertion nondeterministic. Production lease issuance,
expiry, lifecycle and no-wait policy were not changed; dedicated application
view, priority-admission and nonblocking suites remain separate checks.

The build and source changes are development artifacts only. No XP application,
LabVIEW VI, card, Device Server, live web process, recorder or database was
restarted, initialized, commanded or migrated. The dirty production checkout
and its rich UI remain untouched. A later coordinated release must preserve
that layout, install the canonical adapter/provider with the existing panels,
and include the new backend ``acq_contract.py``; copying only a JS bundle is
not a complete backend update.

The release conditions in ``ELYSE_EXPERIMENT_COMMANDS_2026-10-24.rst`` still
apply: trusted direct-Tango authorization, coordinated rollback and physical
commissioning are not established by these web tests. Commands remain disabled
by default. No second XP service or Tango device should be introduced to bypass
those conditions.
