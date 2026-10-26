Canonical SuperVision backup: source comparison
================================================

The backed-up canonical ``SUPERVISION.llb`` contains byte-identical copies of
the three original VIs used by the Python synchronization reconstruction.
Its saved camera settings also match the Python source defaults. This supports
using the saved default profile rather than the conflicting Acquisition mirror
as an automatic takeover profile. It does not establish physical pulse timing
or prove which dependency paths were resolved in the previous loaded VI.

Evidence
----------

The parent supplied the backup receipt:
``C:\Users\elyse\AppData\Local\Temp\elyse-supervision-takeover-eb67a984ecd04a62a3cc5ae8725deccb\supervision_source_backup_flat_receipt.json``.
All58 files in its sibling ``live_supervision_source_backup_flat`` were checked
against their recorded sizes and SHA256 values: 2,973,581bytes, zero mismatches.
The backup finished at2026-10-26T16:43:30.250000Z.

Canonical container SHA256:
``d427b2ba8544e4ffd6868f4e2ef74762363c7c713e30b2ff151e5f5ad168bcf4``.
Canonical project SHA256:
``f93b9043c87853e69f7663a699aa52917c5a3968bf52bd5f97ada2e2d6dd97d1``.
The project uses LabVIEW2012 format ``12008004``.

The existing local pylabview/lvkit reader extracted raw UCRF member bytes while
the original backup filesystem stream remained open. It found43 named members.
No VI was opened or run in LabVIEW, and no NI driver or camera was accessed.
The archive parser warned that complex CONP/CPC2 section1 forms are not
implemented; the raw member reads below independently match all three original
hash pins. No whole-archive semantic parse coverage is inferred from that match.

Compared members:

* ``0_SUP_ELYSE.vi``: UCRF section44, 1,142,015bytes,
  ``B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B``.
* ``1_SUP_INIT_NI6602.vi``: section39, 74,437bytes,
  ``CE8BCA30E727C9B8C1EE9681263FBCE1D60247C2DBECDD0B73A37A385C88104F``.
* ``1_SUP_WRITE_NI6602.vi``: section27, 24,010bytes,
  ``81F29F2C56C22DB6FB37CC8893D360362B2610B6488F9D95C8AFCE0CB21E0DCE``.

Each is byte-identical to the pinned source receipts00/01/03. Consequently the
already audited source diagrams/types/defaults apply to these exact embedded
members; a new behavioral interpretation of different VI bytes is unnecessary.

Default settings comparison
----------------------------

NI6602 counter0--7 nominal delay/width pairs are:

::

    0: 0.35 / 0.35
    1: 2176 / 100
    2: 2008.30 / 10
    3: 2175 / 10
    4: 2175 / 100
    5: 500 / 500
    6: 0.30 / 10
    7: 2175 / 100

All have source InitialDelay=0, rising PFI10 start trigger, rising external
PFI11 timebase, low idle, retriggering and finite one-sample timing; all eight
source tasks are started. The numerical conversion is20ticks per nominal
microsecond. No external clock frequency or electrical waveform was measured
by this audit.

The main's saved NI1409 initialization is ``img0``, channel2, white reference
0.9V and black reference0.1V. These match the current Python source defaults.
Python raw capture still excludes the original rotate/interlace/BCG/profile
processing pipeline; matching initialization defaults is not full image
processing equivalence.

Project/dependency binding limit
---------------------------------

The saved project has274 URL-bearing items. Its main entry is
``../SUPERVISION.llb/0_SUP_ELYSE.vi``. However, its initializer and writer item
URLs name ``/G/PILOTAGE_ELYSE_SUP_moteurs/SUPERVISIONAudrey.llb/``. That Audrey
container is not present in this58-file folder backup. These are saved project
URLs, not a readback of the previously loaded dependency resolution.

The positive conclusion is exact identity of the embedded canonical members.
The stronger claim that every previously loaded initializer resolved to those
members remains unproved. The canonical folder backup also does not include
the complete installed NI/Vision/system dependency closure. No G-drive access
or live dependency query was performed to fill that gap.

Normal stop source inventory
-----------------------------

The byte-identical root's outer sequence988 frame3, diagram14127, contains
independent resource/error chains:

* PSP: close indexed references,13 visible references, then error handling.
* IMAQ: Dispose22899 for nine buffers, then IMAQ Close22923 and error handling.
* CmdLib: addressed AbortMotion177515, then Shutdown192398 and error handling.

No direct DAQmx Stop Task or Clear Task call is present in the root main's
call inventory. Therefore normal completion of that main alone is not source
proof that all eight NI6602 tasks were explicitly cleared. Closing the LabVIEW
process is additional context-release evidence, but this audit does not query
the driver or certify successful cleanup, absence of retained native ownership,
reachability of cleanup from every stop path, or a physical safe state.
No task reset, stop, clear or competing initialization was issued here.

Machine-readable audit
------------------------

``docs/evidence/ELYSE_SUPERVISION_CANONICAL_SOURCE_AUDIT_2026-10-26.json`` records
all58 file checks, original/canonical hashes, extracted member inventory,
critical project URLs, settings and the cleanup/binding limits. Its SHA256 is
``61b5e81e6b76a486c6ea415513e6270d466ee98c6ccbb50bb17673be81d6790b``.
The temporary extraction and inventory path is
``C:\Users\elyse\AppData\Local\Temp\elyse-supervision-live-llb-offline-audit-akxqli5u``.
The backed-up files were read only and remain unchanged.
