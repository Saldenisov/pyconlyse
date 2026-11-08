# ELYSE Supervision: local frame and loop audit (2026-09-29)

## Scope and result

The copied `SUPERVISION.llb` is byte-identical to the copy read from the live
Supervision computer: SHA-256
`D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4`.
No Supervision or Acquisition VI was run, saved, or used to command hardware.

The [reproducible local audit](../Supervision/analysis/build_all_frame_static_audit.py)
walks every parser-exposed frame and loop body of the 39-VI application scope.
It verifies each source VI hash, creates a stable key from source hash, VI,
structure UID, ancestor path, frame index and frame label/value, and compares
the complete key sets with the existing selector and loop ledgers. The result is
**732/732 selector frames and 41/41 loop bodies statically extracted**, with no
duplicate or unmatched key. This is complete *relative to the lvkit
descriptions*, not a claim that each native diagram branch or runtime behavior
has been visually verified.

| Static structure | Frames / bodies |
|---|---:|
| Case | 417 |
| Sequence | 264 |
| Event | 43 |
| Diagram Disable | 8 |
| While Loop | 24 |
| For Loop | 17 |
| **Total** | **773** |

The [full JSONL](../Supervision/analysis/all_frame_static_audit.jsonl) preserves
direct nodes, instance inputs/outputs, operation names, selector source,
structure tunnels, child scope UIDs, and ancestor frame path for each row. The
[compact CSV](../Supervision/analysis/all_frame_static_audit.csv) is filterable
by VI, frame, operation, PSP access, or wait. The
[loop-control CSV](../Supervision/analysis/all_loop_control_inventory.csv)
separately lists all 41 loop bodies with parsed selector source, iteration-bound
and shift-register tunnel presence, direct waits, and operations.

Across the 773 bodies, the parser found 2,608 direct operation instances,
25 direct PSP-read nodes, 64 direct PSP-write nodes, and 66 direct `Wait (ms)`
nodes. All direct PSP accesses in this application scope are in
`0_SUP_ELYSE.vi`. There are 163 bodies with zero *direct* nodes (148 Case,
11 Sequence, 4 Diagram Disable); this does **not** prove a no-op because tunnel
values and enclosing dataflow still matter.

## Main VI layout and loop evidence

`0_SUP_ELYSE.vi` contributes 554 selector frames and 23 loop bodies. Its
five-frame outer Sequence (`UID 988`) is not the only top-level structure in
the parser description: ten other top-level structures contribute a nine-frame
Sequence, five two-frame Cases, and four two-frame Sequences. Their dataflow
relative to the outer Sequence must not be guessed from list order.

| Outer frame | Parsed descendant selector frames | Parsed descendant loop bodies | Observed role |
|---:|---:|---:|---|
| 0 | 0 | 0 | No direct nodes in the parsed frame; tunnel/dataflow meaning unverified. |
| 1 | 15 | 2 | Initialization and connection/setup branches. |
| 2 | 491 | 19 | Main runtime, event handlers, nested commands and monitoring loops. |
| 3 | 0 | 2 | Cleanup operations, including variable connection and image disposal loops. |
| 4 | 0 | 0 | Fifteen Formula Node instances in the parsed frame. |

The 41 loops span 12 application VIs. All 17 For Loops have an `lMax` tunnel in
the parser description. All 24 While Loops have a parsed selector source;
17 loops have a shift-register tunnel. **Neither the numerical For-loop bound
nor the While-loop stop/continue polarity is proven by these descriptions.**
For example, main-VI While `UID 80242` has a parsed `Or.result` selector and a
direct `Wait (ms)` input of `100`, but native diagram confirmation is required
before translating its termination logic. The exact loop paths and operation
sets are in the loop-control CSV.

## What remains unverified

1. The LabVIEW Print corpus has 701 application diagram PNGs, but no reliable
   UID/frame-to-PNG join key. The current [completeness audit](../Supervision/analysis/COMPLETENESS_AUDIT.md)
   therefore remains **0/732 native frame mappings and 0/41 native loop-body
   mappings**, despite complete static extraction. The earlier ordinal mapping
   was independently disproved; it is not used here.
2. Native diagram review must verify selector values, Boolean polarity, all
   frame-specific wire producers/tunnels, timing, error paths, and PSP payloads.
   In particular, the `Page HF` coarse-increase branch currently parses as
   `+1`, identical to fine increase; this may be source behavior or a parser
   resolution error. Do not translate it as `+5` without native confirmation.
3. `Error Code Database.vi` is password-protected. It has no selector frames,
   but its behavior is not established by this audit.
4. The 39-VI scope excludes 88 additional VI sections in the dependency Print
   export. Standard NI/library behavior can be an explicit adapter boundary;
   any project-specific dependency requires its own semantic review.
5. Attempting to open the copied root VI in local 32-bit LabVIEW 2020 produced
   `Hierarchy Conflicts with Project`: `General Error Handler.vi` and
   `DialogTypeEnum.ctl` conflict with open `TRANCON.lvproj`. LabVIEW offers
   `Open in New Project`, which leaves `TRANCON.lvproj` unchanged. The modal was
   not targetable by the available UI control, so **no native VI inspection
   was completed in this pass**. A user click on `Open in New Project` would
   allow passive diagram review without running or saving the VI.

## Verification command

```powershell
py -3.11 Supervision\analysis\build_all_frame_static_audit.py
```

Observed result: `Audited 39 source VIs, 732 selector frames, 41 loop bodies`.
The script also compiles with Python 3.11. All artifacts were produced from the
local copy; the Supervision computer was not contacted in this pass.
