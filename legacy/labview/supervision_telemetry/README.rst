Native camera observer proof bundle
===================================

Status: ``NOT_RUNTIME_QUALIFIED``.

The observer passed cold Open and native Save in LabVIEW 2020 32-bit, followed
by the user's native Save for Previous Version export to LabVIEW 12.0.0,
release build 4. The two included VIs are authored helpers; NI Vision libraries
and the original SuperVision main library are excluded.

The exported source retains 17 front-panel controls at their original root,
the 12-port interface, a 95-byte camera header, original image/error identity,
and separate copy/queue errors. Offline evaluation of the reparsed native graph
passed 13,450 dimension/error cases. Only accepted copies reach serialization
and the capacity-one latest queue. The existing worker must perform transport.

The native export cleared the observer's current DSInit cache
(``nDCOs=0``, ``fpdcoTableTMI=-1``), retaining all 17 source interface fields.
Native LabVIEW 2012 Open/Save cache reconstruction, physical camera execution,
copy-before-Rotate integration, clock agreement, and worker cleanup remain
unqualified. The modified main also returned ``Memory Full`` during local
32-bit cold Open; main integration remains unresolved. This bundle must not
replace the running acquisition program.

Preserve the ``observer_v3`` subdirectory. The system dependencies are the
installed ``<vilib>/vision/Basics.llb/IMAQ ImageToArray`` and
``<vilib>/vision/Image Controls.llb/IMAQ Image.ctl``.

Read-only verification, using Python 3.4 or later::

    python tools/verify_supervision_observer_bundle.py
    python -m unittest tests.unit.test_supervision_observer_bundle

Verification checks pinned bytes, bounded RSRC version/execution flags, receipt
integrity, and dependency closure. It neither loads nor executes a VI. The JSON
proof records source audits; it does not establish hardware runtime behavior.

The separately pinned ``individual_helpers`` subpacket is explicitly registered
in ``manifest.json`` and validated through its own native-provenance guard.
Registration does not change the original observer/queue bytes or runtime limits.
