# Tango Restart Performance: Everest and Elysium 2

`scripts/refactor/benchmark_tango_restarts.py` measures an explicitly approved
Tango server restart. It is not an unattended restart tool. Default mode is a
local dry run and opens no SSH connection.

The benchmark supports only fixed, reviewable endpoints:

| Target | SSH endpoint | Repository | Starter |
| --- | --- | --- | --- |
| `everest` | `elyse@10.20.30.202` | `C:\dev\pyconlyse` | `tango/admin/everest` |
| `elysium2` | `elysium2` | `C:\dev\pyconlyse` | `tango/admin/elysium2` |

## What is measured

Each named server runs sequentially. Remote timestamps use
`time.monotonic_ns()`, so durations do not depend on clock synchronization with
the workstation. One JSON record is printed and retained for every attempted
server, including failures.

| Measurement | Meaning |
| --- | --- |
| `precheck` | Time for both Starter server-list queries before action. |
| `stop_request` | RPC time until Starter accepts `DevStop`. |
| `stop_confirmation` | Time to observe target absent from running and present in stopped lists. |
| `start_request` | RPC time until Starter accepts `DevStart`; this is process-launch request latency, not proof of a running process. |
| `start_registration` | Time until Starter lists target as running. |
| `admin_readiness` | Time until read-only `dserver/<server>.ping()` succeeds. |
| `device_readiness` | Optional read-only `--readiness-device SERVER=device` ping. Use for the relevant non-actuating device only. |
| `recovery_start` | Recorded only if a failed run had already stopped a server; one safe recovery start is attempted. |

`outcome`, `error`, `recovery`, poll count, cumulative Starter poll RPC time,
and total per-server duration are included. A nonzero SSH/PowerShell exit is
also retained in the report. No success result is inferred from a `DevStart`
acknowledgement alone: registration and admin ping must both succeed.

The first failed server stops the run after its bounded recovery attempt; later
requested servers remain untouched. Reports therefore distinguish
`requested_server_count` from `server_count`: a transport failure can occur
before any per-server record is emitted.

## Passive baseline — 2026-08-27

The following checks were read-only. No `DevStop`, `DevStart`, hardware
command, PDU action, or restart was issued; these are not restart-time results.

| Check | Everest | Elysium 2 | Interpretation |
| --- | ---: | ---: | --- |
| Tango DB/Starter list RPC | 0–21 ms | 0–21 ms | Database/list transport is not a multi-second bottleneck in this sample. |
| Tango import | 195 ms | 524 ms | Elysium 2 import path is slower by 329 ms. |
| Direct Python process | 302 ms | 676 ms | Baseline process launch differs by 374 ms. |
| Warm direct device import: Netio | 438–478 ms; process 562–632 ms | — | Everest warm-path sample. |
| Direct device import: Basler | 392–400 ms warm; 870 ms cold | — | Everest cold import remains materially slower. |
| Direct device import: Standa | — | 596–618 ms warm; 771 ms cold | Elysium 2 warm/cold sample. |
| Warm direct device import: Keysight 33509B | — | 576–586 ms; process about 719–724 ms | Elysium 2 live Keysight sample. |
| `conda run` total | 3,319.5 ms | Not separately reported | Conda wrapper is material on Everest. |
| Conda activation per server | 1.41 s | 0.50–0.58 s | Avoid per-server activation; batch one interpreter where approval allows. |
| Direct Python pass | 0.07–0.13 s | 0.07–0.13 s | Interpreter reuse/direct execution has much lower wrapper overhead. |
| Process timestamp span | Normal batch: 4–5 s/server | 26 processes: 16:05:04–16:07:21 (137 s) | Span is observational; it does not identify an individual server's restart latency. |
| Starter configuration | `EnableParallelStartup=false`; inter-server waits 0 | Same observed policy | Sequential policy, rather than an added inter-server delay, is active. |

The sample supports one bounded implementation hypothesis: remove repeated
Conda activation from the restart hot path and retain one approved remote
Python process for the ordered server batch. It does **not** prove a restart
speedup, because no restart was performed. Measure the phases above on a
future approved restart before changing production behaviour.

## Safety gate

Do not run the apply command until experiment is stopped and the operator has
approved the exact target, commit, and ordered server list. The approval file
must be absolute and outside the repository. New approvals must use the
existing restart fields plus an explicit target binding:

```toml
commit = "<40-character-deployed-SHA>"
servers = ["DS_KEYSIGHT_33509B/MAIN"]
approver = "First Last"
hardware_safe = true
expires_at_utc = "2026-08-27T18:00:00Z"
target = "elysium2"
```

`target` is mandatory for Elysium 2. The canonical restart approval loader
maps an omitted legacy target to Everest; do not rely on that compatibility
path for a new benchmark approval.

The remote script refuses a dirty worktree or a `HEAD` different from
`--expected-commit`. It uses only `DevStop`, `DevStart`, Starter list reads,
and Tango `ping`; it never invokes `HardKillServer`, `taskkill`, PDU, motion,
shutter, or power control.

## Runbook

1. Deploy and validate the exact commit using the approved deployment path.
2. Confirm a quiet, hardware-safe laboratory state and create the external
   approval file above. Use only affected server instances.
3. Inspect a dry run. It is safe offline and makes no remote call:

```bash
python scripts/refactor/benchmark_tango_restarts.py \
  --target elysium2 \
  --server DS_KEYSIGHT_33509B/MAIN \
  --readiness-device DS_KEYSIGHT_33509B/MAIN=manip/awg/keysight33509b_laser \
  --expected-commit <40-character-deployed-SHA>
```

4. With explicit operator approval, measure one normal planned restart and
   retain an external report. Choose a real, read-only readiness device only
   when it is known to be safe to ping:

```bash
python scripts/refactor/benchmark_tango_restarts.py \
  --apply \
  --target elysium2 \
  --server DS_KEYSIGHT_33509B/MAIN \
  --readiness-device DS_KEYSIGHT_33509B/MAIN=manip/awg/keysight33509b_laser \
  --expected-commit <40-character-deployed-SHA> \
  --approval-file /absolute/path/restart-benchmark-approval.toml \
  --output /absolute/path/elysium2-restart-20260827.json
```

5. Review `outcome`, each phase, `polls`, `poll_rpc_ms`, remote stderr, and
   the bounded post-restart observation specified by `TEST_MATRIX.md`. Stop
   investigation on an error; preserve the report and terminal output. Do not
   issue an unapproved retry, hard kill, or power cycle.

The generated remote payload applies this blocker before importing Tango or
issuing any Starter command:

```powershell
Set-Location -LiteralPath 'C:\dev\pyconlyse'
$status = & git status --porcelain
if ($LASTEXITCODE -ne 0) { throw 'git status failed.' }
if ($status) { throw 'Refusing benchmark: remote worktree is dirty.' }
$headCommit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'git rev-parse HEAD failed.' }
if ($headCommit -ne '<40-character-deployed-SHA>') {
    throw "Refusing benchmark: HEAD is $headCommit, expected <40-character-deployed-SHA>."
}
```

The no-network dry-run command is the safe command to validate server and
target spelling before requesting approval:

```bash
python scripts/refactor/benchmark_tango_restarts.py \
  --target everest \
  --server DS_DG645/main \
  --expected-commit <40-character-deployed-SHA>
```

## Performance interpretation and improvement range

### Applied Starter 200 ms transition polling — 2026-08-27

The Windows Starter build was changed and rebuilt on Everest from
`C:\dev\pyconlyse-runtime\starter-9.1-tango103-src`. The change replaces the
hard-coded four-second startup detection guard with a monotonic 200 ms first
check, polls startup status and the Windows process snapshot every 200 ms, and
sets Starter state/list polling to 200 ms. A missing launcher process is allowed
two seconds to appear before it is classified as failed; this does not delay a
successful process.

The identical binary is active on Everest and Elysium 2:

```text
SHA-256 924F4C08AFD74B3BC9F16DBCD391414B354B59568F8FA695FDCE6027425E9B6F
```

Elysium 2 Astor-equivalent `DevStop`/`DevStart` measurements used direct Starter
commands and 20 ms observation polling:

| Server | Phase | Before | After | Change |
| --- | --- | ---: | ---: | ---: |
| `DS_Standa_Motor/11_S1` | stop confirmation | 4.613 s | 0.696 s | -84.9% |
| `DS_Standa_Motor/11_S1` | start registration | 6.006 s | 5.038 s | -16.1% |
| `DS_Standa_Motor/11_S1` | complete stop/start | 10.647 s | 5.744 s | -46.1% |
| `DS_KEYSIGHT_33509B/MAIN` | stop confirmation | 3.715 s | 0.924 s | -75.1% |
| `DS_KEYSIGHT_33509B/MAIN` | start registration | 13.960 s | 13.999 s | no material change |
| `DS_KEYSIGHT_33509B/MAIN` | complete stop/start | 17.686 s | 14.935 s | -15.6% |

This separates Starter observation latency from server initialization. The
remaining approximately five-second Standa start and fourteen-second Keysight
start occur after the process-launch request and are dominated by the configured
CMD/Conda/Python/Tango/device initialization path, not the removed Starter guard.

The generated 200 ms defaults did not initially replace polling periods already
stored in the Tango database. Those retained values were 1,000 ms for
`Servers`, `RunningServers`, `StoppedServers`, `HostState`, and `State` on both
hosts. They were explicitly changed to 200 ms on Everest and Elysium 2. A second
Elysium 2 phase profile for `DS_Standa_Motor/11_S1` then measured:

| Milestone after `DevStart` | Elapsed |
| --- | ---: |
| `DevStart` returned | 0.012 s |
| new `cmd.exe` observed | 0.014 s |
| new `python.exe` observed | 1.454 s |
| Tango database export appeared | 3.356 s |
| Starter running list updated | 3.818 s |
| admin device ping succeeded | 3.848 s |

Starter state propagation therefore contributed about 0.46 s in this sample.
The preceding 3.36 s was in the configured launcher and device server: about
1.44 s before Python started and about 1.90 s from Python creation through
imports, Standa USB discovery, and Tango export.

### Direct Python launch deployment

On 2026-08-27, all reviewed `DS_*.bat` Astor entrypoints on Everest and
Elysium 2 were changed to resolve and invoke an absolute `PYCONLYSE_PYTHON`.
Their process-local `PATH` still includes the environment root, `Library\bin`,
and `Scripts`, so native DLL discovery does not depend on `activate.bat`.
There is no Conda activation fallback: an unresolved interpreter fails with a
clear launcher error. Conflicting legacy wrapper EXEs were moved into the
dated rollback directory; `DS_DAQmx_ZMQ.exe` remains because it is the actual
DAQmx ZMQ server and has no conflicting root BAT entrypoint.

The first direct-interpreter deployment still kept Python behind a PowerShell
output-mirroring process. Its intermediate measurements were:

| Host/server | Stop confirmation | Start registration | Admin ping after registration |
| --- | ---: | ---: | ---: |
| Elysium 2 `DS_Standa_Motor/11_S1` | 0.641 s | 3.000 s | 0.031 s |
| Everest `DS_DG645/1_DG645` | 0.500 s | 2.969 s | 0.015 s |

For the Elysium 2 Standa sample, start registration decreased from 3.818 s to
3.000 s (0.818 s, 21.4%). Logs on both hosts recorded the intended absolute
interpreter with `source=PYCONLYSE_PYTHON`, and active launchers contained no
`activate.bat`.

High-resolution launcher tracing then isolated two additional synchronous
waits:

- cold `powershell.exe` startup for output mirroring took about 2.6 s;
- Standa passive discovery could wait 1.0 s for the shared XIMC mutex and then
  continue without discovering hardware.

The final launcher starts the absolute Python interpreter with CMD redirection
before asynchronously creating a Windows Terminal log-tail tab. It sets
`PYTHONUNBUFFERED=1`, keeps the script and instance tokens compatible with
Starter's legacy process parser, and does not put PowerShell or Windows Terminal
on the Tango registration path. Standa passive discovery now waits at most
0.1 s for the shared transport; normal commands retain their configured lock
timeout.

Final Astor-equivalent start measurements were:

| Host/server | `DevStart` return | Starter running list | Admin ping |
| --- | ---: | ---: | ---: |
| Elysium 2 `DS_Standa_Motor/11_S1` | 0.002 s | 1.862 s | 2.039 s |
| Everest `DS_DG645/1_DG645` | 0.001 s | 1.450 s | 1.010 s |

The Standa startup trace measured 0.767 s for imports/PyTango setup, 0.029 s
for the base/Netio phase before discovery, and 1.016 s in the former shared-lock
wait. The shortened passive wait removed approximately 0.9 s without issuing a
motor command or changing operational command timeouts. Final post-checks were
`ON`, 26 running/0 stopped on Elysium 2 and `ON`, 18 running/5 intentionally
stopped on Everest.

Elysium 2 Starter idle CPU rose from 1.56% to 11.25% of one logical core
(0.078% to 0.562% of the whole machine in the five-second samples). Working set
remained effectively unchanged: 15.9 MB before and 16.3 MB after. Both hosts
retained rollback binaries beside the active executable.

The preceding restart script polled Starter at 0.5 s after both stop and start
transitions. It therefore introduced a sampling delay of 0--500 ms for each
transition: 0--1,000 ms total per restart, 500 ms expected when transition
completion is uncorrelated with the poll schedule. This is a design-bound
latency, not an observed laboratory result.

The benchmark defaults to a bounded 0.10 s polling interval. Its corresponding
sampling bound is 0--200 ms total, 100 ms expected. Relative to 0.5 s polling,
the available observability improvement is therefore up to 800 ms per restart
(about 400 ms expected), before accounting for actual process initialization,
Starter/DB RPC latency, network latency, or readiness time. The 50 ms minimum
prevents an experiment from turning diagnostic polling into Starter load.

Use measurements to classify slow restarts before changing production timing:

| Dominant phase | Likely bottleneck | Safe next investigation |
| --- | --- | --- |
| `stop_confirmation` | Server shutdown or Starter/DB list propagation. | Inspect server and Starter logs; compare `poll_rpc_ms` with elapsed wait. |
| `start_request` | Starter RPC, remote host load, or process spawn request. | Inspect Starter log, CPU, memory, antivirus, and conda executable startup. |
| `start_registration` | Python import, dependency initialization, DB registration, or port binding. | Compare startup logs and imports; reduce only verified startup work. |
| `admin_readiness` | Server initialization after registration or Tango transport availability. | Inspect initialization logs and Tango DB/ORB connectivity. |
| `device_readiness` | Device-specific initialization or external controller connection. | Inspect that controller's logs and network path; do not mask it by reducing waits. |

Do not claim an improvement from one sample. Compare equivalent planned,
hardware-safe restarts of the same server and version, retain raw JSON, and
report phase medians plus failures. Changes to the production poll interval
require review after measurements show that polling, rather than process or
device initialization, is material.

## Software verification

The benchmark is regression-tested without Tango, SSH, or network access:

```bash
python -m pytest --strict-config --deny-network \
  tests/unit/test_tango_restart_benchmark.py
```
