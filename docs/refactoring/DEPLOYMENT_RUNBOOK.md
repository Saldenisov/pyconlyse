# Refactor Deployment Runbook

## Scope

This prototype deploys a reviewed Git commit from Mac to Everest and can
request a restart of explicitly named Tango servers through Tango Starter.

It does not control PDU outputs, motion, shutters, power, HPD-TA, RemoteEx,
or laboratory hardware. It never uses `git reset --hard`, `taskkill`, or
`HardKillServer`.

## Preconditions

1. Refactor phase has a dedicated commit on the intended branch.
2. Mac worktree is clean. The deploy tool refuses a dirty tree.
3. Local checks passed:

   ```bash
   python scripts/refactor/verify_refactor.py --apply --full
   ```

4. Everest repository is `C:\dev\pyconlyse`, on the same branch, with a clean
   worktree.
5. SSH key access to `elyse@10.20.30.202` works.
6. `pyconlyse39` exists on Everest.
7. Before any Tango restart: experiment stopped, stages stationary, shutters
   closed, and an operator has created a time-limited approval TOML outside
   the repository. This restart approval is separate from T11 web mutation
   approvals, which are external JSON files.

## Web security provisioning

Production must set `PYCONLYSE_PRODUCTION=true`,
`PYCONLYSE_ENFORCE_DEVICE_AUTH=true`, `PYCONLYSE_JWT_COOKIE_SECURE=true`,
and `PYCONLYSE_JWT_COOKIE_CSRF_PROTECT=true`, plus non-empty `JWT_SECRET_KEY`
and `PYCONLYSE_AUTH_USERS`. The users value is a JSON object whose values are
Werkzeug password hashes (`scrypt` or `pbkdf2`, never plaintext). Generate a
hash without contacting equipment:

```bash
conda run -n pyconlyse39 python -c \
  "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Password: '), method='scrypt'))"
```

Set the resulting JSON, for example:

```powershell
$env:PYCONLYSE_AUTH_USERS = '{"operator":"<paste-generated-scrypt-or-pbkdf2-hash>"}'
$env:JWT_SECRET_KEY = '<long-random-production-secret>'
```

Generate `JWT_SECRET_KEY` offline; do not handcraft, reuse, or leave a default
secret:

```bash
conda run -n pyconlyse39 python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Validator currently checks minimum UTF-8 length only; it does not prove secret
entropy.

Production also keeps device authentication, secure cookies, and CSRF enabled.
CORS remains same-origin unless an explicit allowlist is configured. For local
development only, the local launcher may explicitly set the applicable
enforcement variables to `false`; never copy those opt-outs into production.
An optional CORS allowlist does not make cookie-plus-CSRF authentication valid
cross-origin; the authenticated production UI remains same-origin.

`JWT_SECRET_KEY` must contain at least 32 UTF-8 bytes. Startup validates the
configured TCP bind before starting the device snapshot monitor. An occupied,
invalid, unresolved, or otherwise unbindable `PYCONLYSE_WEB_HOST` /
`PYCONLYSE_WEB_PORT` stops startup and never kills or terminates an existing
process.

Login throttling defaults to 5 failed attempts per IP in 900 seconds, with a
maximum of 10,000 process-local IP keys. Exhausted limits return HTTP 429 and a
`Retry-After` header. Override only with bounded values:

- `PYCONLYSE_LOGIN_RATE_LIMIT_ATTEMPTS`: 1–1000.
- `PYCONLYSE_LOGIN_RATE_LIMIT_WINDOW_SECONDS`: 1–86400.
- `PYCONLYSE_LOGIN_RATE_LIMIT_MAX_KEYS`: 1–100000.

Limiter state is single-process: restart clears it, multiple workers do not
share it, NAT may combine users under one address, and `request.remote_addr`
must only be trusted behind a separately reviewed proxy configuration.

Production and explicit local auth enforcement cover all non-safe methods in
device, treatment, VD2, and V0 APIs. Device debug-monitor GET is passive; the
explicit monitor-start POST is authenticated and mutation-protected.
`treatmentClient`, VD2 callers, and shared V0 helpers attach CSRF headers.
Treatment mutations use CSRF-only transport and preserve an armed hardware
nonce.

Frontend hardware approval is operator-pasted lowercase 64-hex input.
`fetchWithHardwareApproval` composes CSRF and
`X-PYCONLYSE-HARDWARE-APPROVAL`, strips caller-supplied approval headers, and
consumes the nonce before one same-origin unsafe fetch attempt, including
rejected or synchronously thrown attempts. Safe/cross-origin requests do not
consume it; the browser never generates one. UI status is visible. Login POST
intentionally excludes this header. Protected `PumpProbeV0.js` direct
server/data mutation fetches remain a deployment blocker.

VD2 automatic, button, and post-action refreshes are passive GET loaders; only
explicit Read hardware invokes Refresh Status POST. Same-turn bulk maps fail
closed before any fetch when fan-out would reuse one nonce; stale approval is
consumed, fresh approval works later, and requests do not retry after dispatch
ambiguity/failure. Shared-helper Promise.all fan-out is covered by this
zero-fetch rejection. Protected `PumpProbeV0.js` raw direct mutations reach the
backend without an approval header and rely on backend fail-closed rejection;
they remain deploy-blocked. Future WebSocket
`execute_command` needs separate `approval_nonce` transport because HTTP
approval headers do not cross WebSocket messages.

Shared V0 nonhardware POSTs (`/config`, `/hardware-config`,
`/hardware/preflight`, `/faraday`, `/crystal/move`, `/reset`, `/run=false`, and
`/realtime=false`) are CSRF-only. Approval paths are `/hardware/initialize`, `/run=true`,
`/realtime=true`, and stage/sample move/stop.

T11 deployment blocker: hardware mutations require roles, strict device,
command, and argument allowlists, plus one-shot human approval bound to user,
action, device, arguments, and expiry. JWT authentication alone is
insufficient. Supported-server selection and Windows-target load validation
remain deployment blockers.

Package B selects constant
`async_mode='threading'` and adds direct `simple-websocket==1.1.0`; direct
development pins are `pytest==8.4.2` and `coverage==7.10.7`. The lock already
contained simple-websocket; the update adds direct pins, their transitive
packages, coverage, pytest, `iniconfig`, and resolver metadata without
upgrading existing package versions.
The launcher still uses a controlled single-process Werkzeug runner: it applies
production security but is not a supported production deployment. Flask-SocketIO
guidance treats Werkzeug as development-only; the supported threaded example
uses Gunicorn one worker plus threads and simple-websocket. Gunicorn is
Unix-only, so Windows needs supported-server selection and load validation.
Deployment remains blocked pending that validation.

No CI workflow is added yet. Native/proprietary PyTango, PyQt, pypylon, and
Windows dependencies, named conda assumptions, and Mac-only `sandbox-exec`
network denial require a reproducible hosted bootstrap and equivalent OS-level
network isolation before CI can be trusted.

T11 authorization provisioning is software-only and fail-closed. Policy JSON,
approval JSON, and consumed-marker directories must be outside the repository
with restrictive ACLs. The server derives JWT subject and role; callers cannot
select either. Each approval binds explicit route ID, action, ordered targets,
device, command, canonical args, UTC expiry, and a lowercase 256-bit hex nonce.
Unknown, duplicate, missing, wildcard, or non-finite fields are rejected.
Approval consumption creates a marker before any proxy/Tango operation. POSIX
uses atomic `O_EXCL` plus marker and parent-directory `fsync`; Windows uses
atomic `CreateFileW(CREATE_NEW)` with write-through, `WriteFile`, and
`FlushFileBuffers` (no portable Windows directory-`fsync` equivalent). Any
marker I/O error fails closed. There is no approval-generation API or tool.
Expected HTTP errors
are 401 (authentication), 403 (policy), 428 (missing approval), and 409
(invalid/replayed approval). Existing explicit local opt-outs do not weaken
production fail-closed validation. Protected V0 UI mutations remain
deploy-blocked.

Import-safety incident (fixed in T11): an earlier check showed that
`web/backend/routes.py` could construct a Tango database at import time after
applying a remote default host. The route now performs lazy lookup only; it
does not set a remote default or construct Tango objects during import.
Explicit `PYCONLYSE_TANGO_HOST` mapping to `TANGO_HOST` remains compatible.
The regression test and network-denied collection audit are mandatory.

## Local Verification

Dry run prints commands only:

```bash
python scripts/refactor/verify_refactor.py
```

Run backend syntax and unit tooling checks:

```bash
python scripts/refactor/verify_refactor.py --apply
```

Include frontend test and production build:

```bash
python scripts/refactor/verify_refactor.py --apply --frontend
```

Run the complete software-only pytest suite plus frontend tests/build:

```bash
python scripts/refactor/verify_refactor.py --apply --full
```

`--full` runs `npm ci --legacy-peer-deps` from the committed frontend lockfile,
then the default automated pytest lane, named DeviceServer/backend coverage
with `.coveragerc` and `verify_coverage.py`, and focused frontend Jest coverage
for `src/api/csrfRequest.js`, `src/api/treatmentClient.js`, and
`src/utils/deviceFamily.js`. Manual probes, legacy, integration,
main-app, and utilities suites remain opt-in and are not silently deleted or
treated as software-only verification.

The Python lane enables `--deny-network` before collection and propagates
`PYCONLYSE_DENY_NETWORK=1` to nested pytest processes. External Python-socket
DNS/TCP/UDP is blocked; literal loopback and AF_UNIX remain available for
deterministic local tests. This is not an OS firewall for npm or native C
transports; none of the latter are default-collected.

Host-data opener characterization remains explicit and is not run during
deployment verification:

```bash
conda run -n pyconlyse39 python -m pytest -o addopts='' tests/integration/data
```

This lane may scan mounted experiment data. It reports real characterization
failures but cannot gate an exact-SHA software-only checkout update.

Exact T9 software-only gate:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_auth_security.py tests/web/test_websocket_handler_contracts.py
conda run -n pyconlyse39 python scripts/refactor/verify_refactor.py --apply --full
```

These commands must not start Tango, connect to devices, issue WebSocket
hardware commands, or deploy/restart services.

The verification tool has no SSH, Tango, PDU, motion, shutter, or power code.

T10 focused checks:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_auth_security.py \
  tests/web/test_login_rate_limit.py \
  tests/web/test_production_startup_security.py \
  tests/web/test_production_mutation_auth.py
```

Coverage gate also requires `.coveragerc`, `scripts/refactor/verify_coverage.py`,
and `tests/unit/test_refactor_coverage.py`; current T10 measurements/floors
are app 55.0/50.0%, auth 87.0/80.0%, mutation_auth 100.0/90.0%, and
start_production 58.7/50.0%.

T11 focused checks (software-only):

```bash
/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  conda run --no-capture-output -n pyconlyse39 python -m pytest --strict-config --deny-network \
  tests/web/test_hardware_authorization.py \
  tests/web/test_hardware_authorization_routes.py \
  tests/web/test_hardware_authorization_websocket.py \
  tests/web/test_hardware_authorization_device_mutations.py \
  tests/web/test_hardware_authorization_vd2.py \
  tests/web/test_routes_import_safety.py \
  tests/unit/test_pytest_module_isolation.py
```

The focused T11 suite collected and passed 159 tests in both forward and
reverse order, with one warning, under OS-level network denial. Current full
Python deny-network gate passed tooling 39; Python 586 passed, 1 skipped,
with 68.4% named-module coverage;
frontend 10 suites/83 tests with 96.66% statements, 90.08% branches, 97.87%
functions, and 96.61% lines; production build passed with existing hook/bundle
warnings. Existing named-module coverage remains recorded below.

T11 covers HTTP, WebSocket, device, VD2, and backend V0 mutation gates. The
protected V0 UI files remain unchanged and cannot yet attach approval nonces;
production V0 UI workflows therefore remain deploy-blocked. Background
monitoring and VD2 preview are read-only polling paths; V0 active polling is
available only for an already-authorized run/realtime sequence. Supported
server selection and Windows load validation remain deployment blockers.

Fail-closed workflow blockers: enforced iTest increment/decrement derived-value
actions return 403 until exact ordered plans are represented; iTest set remains
behind its existing gate. Enforced VD2 initialize/deinitialize return 403
because conditional recovery/PDU plans are not exact. Enforced V0 Tango
run/realtime start returns 403 because repeated cycles and complete argument
plans are not fully bound. Local opt-out preserves legacy behavior. Do not
treat these high-level workflows as authorized until UI and policy migrations
are reviewed and deployed.

Enforced fallback routes require policy migration when their exact
`command_variant` changes. Parameter-batch approvals bind the full ordered
write plan. Restart approval never authorizes an implicit `HardKillServer`;
server action and trusted Starter target must match explicitly. VD2 preview is
a passive read-frame operation.

Current production blocker: Socket.IO threading mode is selected and pinned,
but the controlled Werkzeug runner is not supported production deployment.
Select and load-validate a supported server/runtime for the Windows target.

## Deploy Exact Commit

Deployment first fetches `origin/<branch>` on Mac and requires local `HEAD` to
equal its exact 40-digit commit. It then checks that Everest has the same
`origin/<branch>` commit. Before the production checkout changes, Everest
creates a temporary detached Git worktree at that exact SHA and runs the full
software-only verification there. The temporary worktree is removed with
`git worktree remove --force`, never `git reset --hard`. Only then does the
production checkout use `git merge --ff-only <commit>`.

Dry run:

```bash
python scripts/refactor/deploy_everest.py --branch develop
```

Apply deployment:

```bash
python scripts/refactor/deploy_everest.py --branch develop --apply
```

On the temporary Everest worktree the tool runs:

```powershell
conda run -n pyconlyse39 python scripts/refactor/verify_refactor.py --apply --full
```

No services are restarted during deployment.

## Restart Explicit Tango Servers

Restart is a separate operation. It requires all three conditions:

1. At least one exact `--server` value.
2. `--apply`.
3. `--approval-file` pointing to a human-created TOML file outside the Git
   repository.

The tool never creates approval files. The approval must bind the exact
deployed SHA and ordered server list, identify the approver, set
`hardware_safe = true`, and contain a non-expired UTC timestamp:

```toml
commit = "<40-character-deployed-SHA>"
servers = ["DS_DG645/main", "DS_HAMAMATSU_STREAK/main"]
approver = "First Last"
hardware_safe = true
expires_at_utc = "2026-07-27T18:00:00Z"
```

Example:

```bash
python scripts/refactor/restart_tango_servers.py \
  --server DS_DG645/main \
  --server DS_HAMAMATSU_STREAK/main \
  --expected-commit <40-character-deployed-SHA> \
  --apply \
  --approval-file /absolute/path/outside/pyconlyse/restart-approval.toml
```

The script checks that Everest `HEAD` is exactly `--expected-commit`, then
restarts one server at a time. It polls both `DevGetRunningServers` and
`DevGetStopServers` after each `DevStop` and `DevStart`; a failed initial
start receives exactly one recovery `DevStart`. It does not restart Tango DB,
Starter, Netio, web, or all servers.

## Web Restart

This prototype does not restart the web application. A future web restart must
name an existing Windows Scheduled Task explicitly and use only:

```powershell
Start-ScheduledTask -TaskName '<approved-existing-task-name>'
```

It must first verify that the scheduled task exists. Process termination is
prohibited.

## Failure and Rollback

1. Stop at the failed step and preserve terminal output.
2. Do not use `git reset --hard`, `taskkill`, or `HardKillServer`.
3. Disable hardware mutation access first, or isolate the web service, without
   issuing equipment commands. Preserve authorization policy, approval, and
   consumed-marker evidence for review.
4. Through the operator-approved safety process, confirm that the service is
   not issuing hardware mutations and that the laboratory state is safe. This
   runbook prescribes no Tango, PDU, motion, shutter, power, deploy, or restart
   commands.
5. Only after steps 1–4, deploy a previously secure release or replacement
   authorization gate through the separately approved deployment procedure.
   A T11 revert must never restore JWT-only hardware mutation access.

## Required Manual Gate

Do not create an approval TOML unless an operator has verified:

- No acquisition is running.
- Stages and delay lines are stationary.
- No user is working at moving or powered hardware.
- Required shutters are closed.
- Restart list contains only servers changed by the deployed commit.
