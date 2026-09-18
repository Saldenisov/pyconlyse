# LaserPointing optical-point calibration — 2026-09-18

The six optical point presets for Cam1 and Cam2 were recalibrated from live
camera statistics in a dark room. The old 40/20/10 presets and 60%/30% inactive
diaphragm positions were historical choices; sweeps showed that several of
them occupied the same transmission plateau and therefore did not produce six
meaningfully different beam profiles.

## Conditions

- Laser repetition rate: 10 Hz.
- Cam1: threshold 20, exposure 80,000 us.
- Cam2: threshold 50, exposure 50,000 us.
- Exposure was kept below the 100 ms pulse-period limit.
- Keysight 33509B was not initialized or modified.
- Standa alignment positions were not moved during this calibration.
- Measurements used repeated frames and contour roundness, illuminated area,
  integrated signal, centroid stability, and valid-frame rate.

## Calibrated presets

| Controller | Points | Plane / active diaphragm | Wide | Medium | Fine | Inactive diaphragm |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Cam1 | 1–3 | Near / DV01 | 10 | 6.5 | 5 | DV02 = 20 |
| Cam1 | 4–6 | Far / DV02 | 15 | 10 | 7.5 | DV01 = 20 |
| Cam2 | 1–3 | Near / DV03 | 15 | 10 | 5 | DV02 = 20 |
| Cam2 | 4–6 | Far / DV03 | 15 | 10 | 5 | DV02 = 20 |

Cam2 points 1–3 retain translation position 0; points 4–6 retain translation
position -700. All other routing, shutter, main-diaphragm, and half-wave-plate
settings are unchanged.

## Representative observations

- Cam1 DV01 6.5 / DV02 20 was explicitly validated over eight frames: median
  centroid area 4,182 pixels, illuminated area 4,281 pixels, and 6.03%
  contour-roundness error.
- Cam1 near-plane open behavior plateaued around DV01 10–12.5; settings above
  that added little useful signal. The 10/6.5/5 triplet samples the plateau,
  transition, and tight stable profile.
- Cam1 far-plane behavior with DV01 fixed at 20 gave distinct stable profiles
  at DV02 15/10/7.5. DV02 values around 20–60 were largely redundant.
- Cam2 DV02 had its best useful open plateau around 20. With DV02 fixed at 20,
  DV03 15/10/5 remained valid at both translation positions and produced
  distinct wide, medium, and fine illuminated areas.

## Live verification

After updating the Tango properties and restarting both LaserPointing
controllers, point 3 was applied and checked on each camera:

- Cam1 reached DV01 5 / DV02 20 and returned valid centroids in 8/8 frames.
- Cam2 reached DV02 20 / DV03 5 with OWIS axis 3 at 0 and returned valid
  centroids in 8/8 frames.
- All eight Standa alignment-axis readbacks were identical before and after
  point verification.
- The controller now retries transient OWIS status-read timeouts during a long
  translation move and publishes the point only after final readback.

These values describe the present optical and camera conditions. Repeat the
same sweep after material optical changes, camera replacement, or a substantial
change in beam energy/profile; do not infer new presets only from the nominal
diaphragm percentages.
