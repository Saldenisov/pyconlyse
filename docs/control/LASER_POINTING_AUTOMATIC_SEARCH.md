# Automatic laser-pointing search

## Purpose

The controller aligns one laser beam through separated diaphragm planes. The
Elyse entry diaphragm is closed near 10% to make the beam small, and downstream
diaphragms (or a translated propagation plane) constrain beam position and
angle. Basler centroid measurements provide the objective; the camera centre is
not assumed to be the physical diaphragm centre.

The algorithm has been developed without access to the laser or motion
hardware. The first run must therefore be supervised.

## Optical configurations

Point values remain owned by
`DeviceServers/control/laser_pointing/add_ds_LaserPointing.py`. The automatic
controller executes those rules rather than duplicating hardware positions.

### LaserPointing1 / Basler1

Device: `manip/V0/LaserPointing-Cam1`; camera: `manip/V0/Cam1_V0`.

- The Elyse entry diaphragm (`MainLaserDiaphragm1`) stays at 9.2 for points
  1-6.
- Points 1, 2, and 3 close the first downstream diaphragm to 40, 20, and 10.
  `ActuatorX1` and `ActuatorY1` align this plane.
- Points 4, 5, and 6 close the second downstream diaphragm to 40, 20, and 10.
  `ActuatorX2` and `ActuatorY2` align this plane.

### LaserPointing2 / Basler2

Device: `manip/V0/LaserPointing-Cam2`; camera: `manip/V0/Cam2_V0`.

- The Elyse entry diaphragm again stays at 9.2.
- Points 1-3 use translation-stage position 0 and diaphragm settings 40, 20,
  and 10. `ActuatorX3` and `ActuatorY3` are adjusted.
- Points 4-6 use translation-stage position -700 and diaphragm settings 40,
  20, and 10. The extra propagation distance increases angular sensitivity;
  `ActuatorX4` and `ActuatorY4` are adjusted.

The translation stage is moved only through these point rules. It is not an
optimisation variable.

## Optical and motor sequence

For each X/Y actuator pair the controller measures a wider reference setting
and a closed setting, then minimises:

`error = sqrt((X_reference - X_closed)^2 + (Y_reference - Y_closed)^2)`

Optical modes:

| Mode | First plane | Second plane | Intended use |
|---|---|---|---|
| Sensitive (default) | 1 vs 3 | 4 vs 6 | Normal workflow using points 3 and 6 |
| Medium | 1 vs 2 | 4 vs 5 | Engineering test using the 20 setting |
| Staged | 1 vs 2, then 1 vs 3 | 4 vs 5, then 4 vs 6 | Optional optical coarse-to-fine run |

The default motor schedule is 10, 6, then 2 units. At each step size the first
plane (point 3 in Sensitive mode) and then the second plane (point 6) are
aligned. This repeats at the next smaller step. A second complete cycle is
available because the two separated-plane adjustments can interact. The run
ends early when both errors are within the pixel tolerance.

## Mechanical stiction handling

The optical mounts sometimes stick: a motor readback changes but the mirror
does not respond, then several accumulated movements release it in a jump. The
search therefore distinguishes motor motion from optical response.

- A direction is first tested with one scheduled step.
- If the measured optical error is effectively unchanged, another step is
  added in the same direction, up to `probe_repetitions` (default 3).
- Repeated additions stop immediately when an optical change is observed.
- The best measured position is retained; a worse jump is not accepted as the
  new centre.
- All candidates remain inside the configured radius and motor limits.

This reproduces the manual add/add/jump behaviour while bounding the total
movement. The default 10-unit step, three probes, and radius 30 allow at most
three coarse additions in one direction.

## Motion completion and camera timing

Motion settling is based on real controller readings, not a fixed 1.5-second
delay.

- `DS_Standa_Motor.move_axis_abs` already blocks on the controller's
  `command_wait_for_stop`, reads the physical motor position, and rejects a
  target/readback mismatch. The laser controller performs a final published
  position and state check.
- The OWIS aggregator starts movement asynchronously. The laser controller
  repeatedly calls `get_status_axis` and `read_position_axis` until the axis is
  non-moving and stable at its target for two reads.
- Both paths use a 180-second maximum motion timeout, 0.2-second polling, and a
  0.05-unit position tolerance by default.
- After confirmed motion completion, a 0.25-second delay allows Basler to
  publish a frame acquired at the new position. Three centroid samples are
  then combined by their median.

These defaults come from the registered hardware settings. OWIS axis 3 is
configured at speed 15 and must travel 700 units between the two propagation
planes, so its nominal full move is about 47 seconds; 180 seconds allows ample
margin without guessing that it completed. Basler1 and Basler2 are configured
at 10 frames/s with 20 ms exposure, so 0.25 seconds spans more than two normal
frame periods after motion completion.

## Laser-loss and stop behaviour

Basler publishes `cg_valid`. If it is false at any required point, the
controller reports **laser not visible**, stops the procedure immediately, and
does not issue a recovery scan or an automatic return movement. The operator
must verify that the laser is present before restarting.

Manual Stop is cooperative. It interrupts polling, camera waits, and sampling
as soon as the current blocking controller command returns. No new search or
restoration move is issued after cancellation.

Other device exceptions, rejected commands, readback timeouts, or invalid
configuration also stop the run and are shown in the UI status.

The Basler tracker selects the largest contour by physical area rather than the
contour with the most vertices. It also publishes `cg_area`, which can support
a hardware-derived minimum spot-area threshold later.

## Operator controls

The **Automatic alignment** panel exposes:

- optical sequence: sensitive, medium, or staged;
- coarse, middle, and fine motor steps;
- maximum radius from each starting motor position;
- final centroid-displacement tolerance in pixels;
- maximum evaluations per group and step size;
- camera samples per point;
- start, stop, active group, motor step, and current error.

Repeated interaction passes remain a DS default rather than an operator
control. The operator selects an optical sequence and the controller performs
the required diaphragm changes and Standa corrections.

### XY delta and convergence over time

Both clients place a centred **ΔX versus ΔY** view immediately below the
Basler camera image. It shows the current signed ΔX and ΔY values, the vector
from the zero target to the latest mismatch, the trajectory of previous
measurements, and a circular tolerance boundary. The centre `(0, 0)` means the
two measured optical configurations have the same centroid. This view answers
which direction remains to be corrected.

The automatic-alignment controls retain the scalar error against elapsed
seconds:

`delta centroid = sqrt(delta_x^2 + delta_y^2)`

Absolute camera X and Y are not plotted in the LaserPointing composite because
they are coordinates in two different optical configurations and therefore
jump when the diaphragm or propagation plane changes. Each convergence sample
is coloured as **Diaphragm 1 · Standa pair 1** or **Diaphragm 2 · Standa pair
2**. The operator does not select a graph pair or cycle; a sample is added
automatically after the controller changes the optical point, moves the active
Standa pair, and measures both centroids. The time chart answers whether the
sequence is converging and how mechanical stick-slip affected it. Its tolerance
is drawn as a horizontal reference line.

### Diaphragm-to-mount interlock

Manual alignment starts with both mount pairs locked:

- a successfully applied point 1, 2, or 3 selects only Standa pair 1;
- a successfully applied point 4, 5, or 6 selects only Standa pair 2;
- the selected pair remains movement-locked until the operator presses
  **Initialize Standa pair**;
- initialisation is deterministic and sequential: X completes before Y starts;
- the pair unlocks only after both axes report successful initialisation;
- Working/open and an unknown point lock both pairs;
- applying a point, initialising a pair, and running automatic alignment lock
  all manual mount movement until the operation completes.

The controller publishes the last point only after every point-rule device has
reached its readback. The web client sends manual moves through the controller's
interlocked command instead of commanding a child Standa DS directly. Qt keeps
the inactive buttons disabled while leaving state and recovery controls
available.

#### Standa power and passive startup

All eight alignment axes share NETIO `manip/V0/PDU_VO` output 3:

- `elyse/motorized_devices/mm1_x`, `mm1_y`, `mm2_x`, and `mm2_y`;
- `manip/V0/mm3_x`, `mm3_y`, `mm4_x`, and `mm4_y`.

Each device is registered with `power_dependency_auto_turn_on=0`. Startup and
power restoration only perform passive discovery: they may enumerate and close
a probe handle, but they do not open the operational transport, stop an axis,
or initialise a motor. Operational initialisation occurs only through the
explicit active-pair command after point selection.

The compact Qt and web rows use the hardware lifecycle attributes rather than
Tango STANDBY alone. A passively discovered axis is amber, an initialised axis
is green, and `DISCONNECTED`, `POWER_OFF`, or an unreachable/FAULT axis is red.

### Qt layout

The composite Qt client is organised for two controllers side by side:

- all generic `Update param` buttons are hidden because Taurus attributes
  already refresh continuously;
- points 1-3 and 4-6 are shown as two explicit optical planes, with Wide 40%,
  Medium 20%, and Fine 10% sensitivity labels;
- LaserPointing2 labels the planes as translation-stage positions 0 and -700;
- the raw Basler absolute X/Y traces are replaced by signed **ΔX/ΔY** values
  and a centred XY vector/trajectory directly below the camera;
- the camera and signed XY view remain visible in both modes;
- the shared **Optical points** selector remains visible above both tabs,
  preserving the old point1–point6 workflow and selecting the active mount
  pair for manual alignment;
- the **Automatic** tab contains active-pair initialisation, search settings,
  and **Convergence over time**;
- the **Manual** tab replaces only the right-hand control column with Standa
  mount widgets and, for LaserPointing2, the required OWIS translation-stage
  widget. It does not show the convergence graph;
- Standa controls use one row per device: state LED, friendly name, position,
  decrement, relative step, and increment. Optical-device widgets are omitted
  from Manual because point presets remain in the shared selector above the
  tabs and are applied by the controller.

Right-click the relative-step value in a Qt Standa row to select another step.

#### Qt device recovery

Right-click a device state LED, friendly name, unavailable-device placeholder,
or empty device-widget area to open recovery actions:

- **Restart Tango DS** resolves the registered server and controlling Tango
  Starter from the database, requests `DevStop`, confirms that it stopped, then
  requests `DevStart` and confirms registration. It never calls
  `HardKillServer` and does not remove hardware power.
- **Power cycle PDU output** is shown only when the device has an explicit
  `power_dependency_device` and `power_dependency_output_id`. The GUI confirms
  the exact PDU/output, warns that an output can be shared, switches only that
  output OFF, verifies it, waits three seconds, restores it, verifies it, and
  waits for the configured power-settle interval. Other PDU outputs are read
  again before restoration and are not overwritten from a stale state.

Both operations require a confirmation dialog and run outside the Qt UI
thread. If an output is already OFF, the recovery action refuses to turn it ON
automatically; use the PDU controller after checking why it is off. The OWIS
axis-3 widget obtains its power mapping from the configured three-axis backend.
No PDU action is offered for a camera or device without a registered mapping.

Compact Standa rows keep a fixed height throughout a Tango DS restart. Restart
progress is shown in place with a blue LED/border and tooltip; a temporary
disconnect or failed recovery is red. Recovery banners are intentionally not
inserted above the row, so restarting one axis cannot collapse its controls or
shift the remaining manual hardware view.

### Web controller

The React control centre exposes Laser Pointing as a dedicated equipment
family at `/laser-pointing-clients` and as a specialised client in the generic
Device Browser. Each controller panel contains:

- a compact desktop layout: the page title and DS selector occupy single rows,
  controller chrome uses reduced spacing, and camera/chart heights are bounded
  so the operating controls enter the first screen; narrow screens still stack
  the camera and controls vertically;

- a Basler preview and signed XY delta view that stay visible in both modes;
- an **Automatic** tab with the two-plane point visualisation, sequential
  **Initialize Standa pair**, search configuration, progress, Start/Stop, and
  the time-based convergence plot;
- a **Manual** tab with compact readback-driven Standa controls plus the
  configured OWIS translation-stage axis when present, but no convergence plot;
- the same diaphragm/mount interlock as Qt. Selecting Manual never changes the
  active optical point or bypasses the pair-initialisation requirement.

Read-only state is returned by
`GET /api/laser-pointing/<device>/snapshot`. Mutations use the existing generic
Tango command endpoint and therefore retain the website's hardware-approval
policy. The browser never coordinates child devices itself: the
`apply_controller_point` controller command applies a complete point rule and
`initialize_active_pair` activates only its selected X/Y pair in sequence.
`move_active_actuator` validates both the active diaphragm and initialised pair
before moving one axis.

During a rolling deployment, a controller still running the previous DS code
returns a read-only compatibility snapshot. New point and automatic-search
buttons remain disabled and the page reports **server restart required**. Plan
the restart for a safe maintenance window; do not restart an active optical
alignment only to refresh the page.

## Device-server interface

Commands:

- `apply_controller_point(point_name)` applies one complete manual optical
  preset and waits for child-device readback;
- `move_active_actuator(json)` moves one axis only if its role belongs to the
  pair unlocked by the active point;
- `start_automatic_search(json_config)` starts the worker and returns
  immediately (`0` accepted, `-1` rejected).
- `stop_automatic_search()` requests cancellation.
- `start_cgc` and `stop_cgc` remain compatibility aliases.

Attributes:

- `automatic_search_config`: readable/writable JSON;
- `automatic_search_status`: idle, running, stopping, completed, cancelled,
  laser-not-visible, or an error message;
- `automatic_search_progress`: JSON with cycle, step, group, point pair,
  actuator positions, centroids, delta, error, and failure details.
- `automatic_search_history`: chronological JSON observations with elapsed
  seconds, centroid error, diaphragm, active pair, and actuator position;
- `active_point` and `active_actuator_group`: authoritative manual-interlock
  state shared by Qt and web.

Default configuration:

```json
{
  "mode": "sensitive",
  "initial_step": 10.0,
  "minimum_step": 2.0,
  "step_schedule": [10.0, 6.0, 2.0],
  "radius": 30.0,
  "tolerance_px": 2.0,
  "minimum_improvement_px": 0.1,
  "unchanged_response_tolerance_px": 0.25,
  "probe_repetitions": 3,
  "max_evaluations": 16,
  "max_cycles": 2,
  "samples": 3,
  "sample_interval_s": 0.2,
  "camera_frame_wait_s": 0.25,
  "motion_timeout_s": 180.0,
  "motion_poll_s": 0.2,
  "position_tolerance": 0.05,
  "position_stable_reads": 2,
  "groups": [],
  "point_pairs": {},
  "restore_point": ""
}
```

`groups` can restrict a diagnostic run to `group1` or `group2`. `point_pairs`
can override comparison pairs for an engineering test. Motion/readback and
stiction parameters remain DS-only advanced options.

## First hardware-test procedure

1. Verify Basler1 is displayed in LaserPointing1 and Basler2 in LaserPointing2.
2. Confirm the manual points produce the intended diaphragm, shutter, and
   LaserPointing2 translation-stage positions.
3. With laser present, confirm `cg_valid` is true. Block or switch off the laser
   and confirm it becomes false and an automatic run stops with **laser not
   visible**.
4. Record all four actuator positions and verify motor limits cover the proposed
   radius.
5. Restrict the DS configuration to `group1`, use Sensitive mode, and supervise
   the 10, 6, 2 schedule at point 3.
6. Inspect the progress data to see whether unchanged-error probes correctly
   identify stick/add/jump behaviour without accepting a worse jump.
7. Test `group2` at point 6 and confirm that LaserPointing2 waits for real OWIS
   position -700 rather than merely waiting a fixed time.
8. Run both groups for one cycle, then enable the second interaction cycle.
9. Decide whether the last measurement point should remain for verification or
   whether both controllers need an agreed `working` restore rule.

## Remaining commissioning measurements

- Measure typical Basler frame latency and increase `camera_frame_wait_s` if
  0.25 seconds can return a frame from before motion completion.
- Record the optical error noise while stationary. It should set
  `unchanged_response_tolerance_px`; 0.25 px is only a software default.
- Measure the real OWIS final-position repeatability to confirm the 0.05-unit
  tolerance.
- Determine a reliable minimum `cg_area` from real laser images if rejecting
  small noise spots is necessary.
