# Centering-first laser alignment: offline validation — 2026-10-21

Status: source implementation and offline tests complete. Not deployed or enabled
on equipment. No Tango connection, equipment command, acquisition, process
restart or production frontend replacement was performed for this work.

## Algorithm

- Explicit `alignment_objective="centering"` selects the new path. The existing
  `roundness` default and its public diagnostic fields remain compatible.
- Independent ellipse-fit centers determine within-frame center spread in pixels;
  ellipticity remains a separate percentage. An elliptical but concentric beam can
  pass centering without passing the shape diagnostic.
- Open/closed aperture endpoints are also checked by default. Disabling a full
  aperture sweep does not silently disable that endpoint check. Missing pair
  evidence cannot pass pair verification. Apertures return to the closed target.
- Each position receives 3 independent measurement batches by default (range 3–5).
  A promising candidate must pass a fresh reference measurement and a return to
  the candidate. Median improvement must exceed both the configured minimum and
  twice the larger robust scatter estimate (`1.4826 × MAD`); at least two-thirds
  of candidate repeats must improve. This is a noise guard, not a confidence interval.
- A rejected candidate cannot enter the optimizer's best-position bookkeeping.
  Cached minima from earlier passes do not select the new path's retained position.
  Final fresh repeats must all satisfy centering tolerance.
- Duplicate camera transfers are rejected as repeat-confirmation evidence.
  Cancellation restores only the last confirmed position for keep-current mode;
  the existing explicit cancel-and-restore behavior remains available.

Initial offline settings: `centering_tolerance_px=1.0`,
`centering_minimum_improvement_px=0.1`, `confirmation_noise_multiplier=2.0`,
`measurement_repetitions=3`, `centering_check_aperture_pair=true`.
The separate ellipticity diagnostic tolerance is 7%. These values are configurable;
the 1 px criterion has not been commissioned on live equipment.

## Archived-frame replay

63 distinct frames from 9 archived bursts were partitioned into three disjoint
batches per burst (3, 2 and 2 frames). Camera thresholds/exposure in the archive
were retained; comparisons reject changed camera settings or reused frames.

| Archived measurement | Center spread, median (px) | Ellipticity, median (%) |
| --- | ---: | ---: |
| P4 before coarse correction | 3.955 | 23.147 |
| P4 after coarse correction | 3.277 | 12.806 |
| P3 after coarse correction | 0.227 | 11.582 |
| Earlier P6, 100 ms exposure | 0.294 | 15.245 |

The P4 centering gain of 0.678 px exceeds its repeatability guard of 0.229 px;
all three candidate batches improve. A nominally unchanged P6 comparison gives
only 0.046 px gain and is rejected by the 0.1 px minimum.

The P3/P6 records pass the *within-frame* center criterion while failing the
separate ellipse diagnostic. They do not establish full P3/P6 alignment: no
complete matched open/closed-pair dataset exists, the P6 record precedes later
corrections, and saved bursts cannot test actual motor response or backlash.
Physical return and cancellation behavior are covered with fake-controller tests.

Reproduce offline only:

```powershell
& 'C:\Users\elyse\miniconda3\envs\pyconlyse312\python.exe' bin/diagnostics/replay_laser_centering.py --input-dir .tmp/pointing-cam2-20261021 --output-dir .tmp/pointing-centering-offline-20261021
```

Generated evidence: `.tmp/pointing-centering-offline-20261021/report.json` and
`centering-vs-ellipticity.png`. Automated checks: 136 Python tests and 22 web UI
tests passed. The replay test forbids socket connections and verifies that source
archives remain unchanged.
