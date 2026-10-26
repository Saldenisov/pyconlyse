One Device Server: legacy Acquisition plus read-only SuperVision
==============================================================

This explicit, optional migration mode permits the existing Acquisition r16
publisher to keep its selected 27-bank wire while a separate SuperVision owner
publishes counter metadata and raw camera frames. Both streams enter the same
Everest Device Server application and the same existing TCP listener, normally
``10.20.30.202:8767``. It creates no second telemetry server application.

Default behavior is unchanged. Full two-owner federation and this migration
mode are mutually exclusive. Migration never selects a replacement Acquisition
source because another stream becomes fresh, stale, silent or unavailable.

Configuration
-------------

The new Tango device property ``supervision_migration_config_file`` defaults to
empty/disabled. Configure it with the absolute path of a local JSON file using
``DeviceServers/control/elyse_acq/supervision_migration.example.json``::

  {
    "schema_version": 1,
    "migration_mode": "acquisition_legacy_supervision_read_only",
    "supervision": {
      "host": "10.20.30.2",
      "port": 8772,
      "read_key_file": "supervision.read.key"
    }
  }

Keep ``federation_config_file`` empty. Existing ``key_file`` remains the
Acquisition credential; ``producer_kind_filter`` keeps its existing explicit
source policy (currently ``unified_acquisition``). Existing Acquisition HTTP
port, command key and command-enable properties keep their meaning.

``supervision.read.key`` resolves relative to the configuration directory and
must hold the same private read/telemetry key configured on the SuperVision
publisher. It must differ from the Acquisition key. No key is included in the
example. The SuperVision host/port are fixed to ``10.20.30.2:8772``; only
``10.20.30.10`` and ``10.20.30.2`` are admitted by the shared listener. Peer IP
is an allowlist, not authentication; the two wire paths verify distinct keys.

Authority and public attributes
-------------------------------

* Existing signed Acquisition packets go only to ``TelemetrySinkStore`` under
  its configured source policy. The current 27-bank values, source identity,
  freshness, receiver counters and cooling view remain selected from that store.
* Only signed ``owner=supervision`` frames go to the independent sidecar
  ``FederatedTelemetryStore``. Acquisition owner frames are rejected in this
  mode; no cross-wire fallback is attempted.
* ``telemetry_json`` preserves Acquisition's 27 banks, including its existing
  ``C1011NI6602`` and opaque ``C12NI1409``. SuperVision data never replaces them.
  Additive fields identify ``migration_mode``, ``supervision_owner``,
  ``video_metadata``, ``sidecar_read_only``, ``migration_received_total`` and
  ``atomic_across_sources=false``. Legacy ``received_this_process`` still counts
  Acquisition receipts only.
* ``video_json`` exposes the sidecar's independently current U8 frame, or null
  when unavailable/stale. A healthy image does not freshen Acquisition banks;
  healthy Acquisition packets do not freshen an old image. Raw pixels remain
  outside the 27-bank JSON.
* ``orchestrators_json`` reports both available runtime views, with
  ``federated=false`` and the explicit migration mode. The SuperVision HTTP
  metadata client is constructed with ``enabled=false`` and no command key.

Every SuperVision command capability is disabled with
``MIGRATION_SUPERVISION_READ_ONLY``. ``ExecuteOwnerCommand`` rejects all
SuperVision intents even if a faulty or future runtime advertises enabled
capabilities. Existing Acquisition command routing and its current-source gates
are unchanged. This migration mode does not commission SuperVision control.

Verification boundary
---------------------

``tests/unit/test_acq_hybrid_telemetry.py`` uses RAM fixtures, temporary local
configuration files, a fake listener and fake Tango runtime views. It checks both
start orders, key/wire isolation, source/session independence, legacy-bank and
age preservation, bounded image delegation, hard read-only command behavior,
and one-listener construction. It opens no socket and performs no NI operation.

Deploying this source/configuration and restarting the live Device Server remain
separate operational actions. No such action is performed by these tests or by
loading the example file.
