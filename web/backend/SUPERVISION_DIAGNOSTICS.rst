SuperVision image diagnostics on Everest
======================================

Only U8 image observations from the existing receiver are analysed. A camera
ID is ``ni1409:<actual unsigned channel>``; this module does not select camera
inputs or claim that separate MUX inputs are acquired simultaneously.

Analysis uses the current single raw frame, median edge background and a
four-MAD noise floor with a minimum3-count offset. Intensity-weighted centroid
and marginal profiles are returned in raw top-left pixel coordinates. No time
averaging is introduced. A uniform/broad field is not accepted as a separated
beam. This is a defined raw-frame estimator, not a reproduction of native
SuperVision's rotated/BCG/interlaced/thresholded/particle-filtered centroid.
Ellipse/ROI/SOI fitting is deferred.

Integration
-----------

``DiagnosticsService(read_video, store, camera_ids=...)`` performs no I/O during
construction. ``observe(camera_id,envelope)`` returns the diagnostic row for
that exact source frame and queues a scalar observation without SQL. The caller
can attach that row to its existing video envelope. ``start(poll=False)`` starts
only the independent PostgreSQL worker, avoiding a second camera reader when a
frame broker already supplies observations. Optional ``start()`` also starts a
separate analysis poll. ``close(timeout=5)`` reports whether workers ended.

``PostgresDiagnosticsStore(config_path)`` uses the existing local archive
PostgreSQL configuration on F:. Its constructor reads configuration/imports
the driver but does not connect. SQL initialization happens in the writer.
``UnavailableDiagnosticsStore`` retains image analysis with explicit degraded
reference/archive status; it never claims that an in-memory centre is durable.

The async numeric queue is bounded to512 observations by default. It drains
batches of32. ``pending``, ``rejected``, ``oldest_pending_age_seconds`` and writer
errors remain visible. A full/offline archive never blocks image observation;
excess new numeric records are explicitly counted. The queue is RAM-only and
does not guarantee history across process crashes. Saved centre/mode changes,
in contrast, complete a PostgreSQL transaction before success is returned.

Separate PostgreSQL tables contain centroid scalars, source/capture/frame IDs,
channel, geometry, processing provenance, quality and times. They contain no
image pixels, base64 strings, image blobs or profile arrays. Observation identity
deduplicates retries. Reference and mode changes append history rows and update
a per-camera revision under ``SELECT ... FOR UPDATE``. Latest committed revision
wins; a stale browser revision receives409 rather than overwriting a newer one.

Reference and automatic-mode API
--------------------------------

Register ``create_diagnostics_api(service)`` on the existing Flask application.
The normal mutation authentication/CSRF guard is installed, and diagnostic GETs
are also authenticated in production. Responses use ``Cache-Control:no-store``.

* ``GET /api/elyse/supervision/diagnostics?camera_id=ni1409:2`` returns one camera;
  omitting the query returns all known/configured channels independently.
* ``POST .../reference`` accepts exactly ``camera_id``, ``frame_identity``,
  ``expected_revision`` and ``radius_px``. It freezes the centroid computed by
  the server for that observed image. Browser pixels or arbitrary x/y are not
  accepted. At25Hz, a bounded64-observation numeric cache permits a recent click
  without requiring that a newer frame stop arriving. The selected observation
  must still be less than2 seconds old, valid, and from the current capture.
* ``POST .../mode`` accepts exactly ``camera_id``, ``mode`` and
  ``expected_revision``. Modes are ``manual`` and ``auto``; mode revision is
  separate from reference revision. Both begin at revision0.

Each camera row includes ``current``, ``profiles``, ``reference``, ``offset``,
``planner`` and archive status. Current x/y become null for invalid, absent,
no-beam or expired observations. Repeated frames never refresh their source age.
The offset and target-circle membership are calculated only when reference
camera, geometry, source kind and processing coordinates match.

Automatic preference does not mean a motor is moving. Default planner output
has ``execution_allowed:false``. It blocks without a commissioned, nonsingular
pixel-to-step matrix bound to this camera/geometry/source/processing space. A
valid proposal is bounded, carries an idempotent source/reference/mode identity,
and is labelled preview-only. Manual motor controls remain unavailable until
their actual route and calibration are commissioned.

``CorrectionController`` defines an optional actuator protocol for later
integration. Default ``live_enabled=False`` performs no moves, even with an
adapter present. Tests use only a fake adapter. Explicit live execution requires
an adapter marked commissioned and must run outside the camera ingress worker.
Repeated/regressed/retired frames and stale observations cannot trigger another
correction. An uncertain adapter result fences automatic retry. This module
imports no concrete Tango, serial, NI or picomotor driver.

Validation
----------

From repository root::

  python -B -m pytest tests/web/test_supervision_diagnostics.py tests/web/test_supervision_diagnostics_api.py -q

Fixtures cover measured centroid/profile geometry, no-beam and stale quality,
frame identity/replay rejection, bounded recent clicks, revision conflicts,
source-coordinate changes, numeric-only archival, a deliberately blocked
database, explicit overflow, production auth and dry-run/fake-actuator behavior.
No XP, NI, physical camera or motor operation is performed by these tests.
