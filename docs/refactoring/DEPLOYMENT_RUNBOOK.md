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
   the repository.

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
device, treatment, VD2, and V0 APIs, including device debug-monitor GET because
it starts monitoring work. `treatmentClient`, VD2 callers, and shared V0
helpers attach CSRF headers.

Protected `PumpProbeV0.js` direct unsafe POSTs remain outside T10 and currently
include `/api/server/control` (line 283), `/api/pump-probe-v0/data/folder`
(lines 338 and 366), and `/api/pump-probe-v0/data/load` (line 387). Production
workflows remain deploy-blocked until an explicit V0 owner migrates them.

T11 deployment blocker: hardware mutations require roles, strict device,
command, and argument allowlists, plus one-shot human approval bound to user,
action, device, arguments, and expiry. JWT authentication alone is
insufficient. Eventlet/threading mode selection remains a separate blocker.

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

Exact T9 software-only gate:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config \
  tests/web/test_auth_security.py tests/web/test_websocket_handler_contracts.py
conda run -n pyconlyse39 python scripts/refactor/verify_refactor.py --apply --full
```

These commands must not start Tango, connect to devices, issue WebSocket
hardware commands, or deploy/restart services.

The verification tool has no SSH, Tango, PDU, motion, shutter, or power code.

T10 focused checks:

```bash
conda run -n pyconlyse39 python -m pytest --strict-config \
  tests/web/test_auth_security.py \
  tests/web/test_login_rate_limit.py \
  tests/web/test_production_startup_security.py \
  tests/web/test_production_mutation_auth.py
```

Coverage gate also requires `.coveragerc`, `scripts/refactor/verify_coverage.py`,
and `tests/unit/test_refactor_coverage.py`; current T10 measurements/floors
are app 55.0/50.0%, auth 87.0/80.0%, mutation_auth 100.0/90.0%, and
start_production 58.7/50.0%.

WebSocket command allowlists and CI dependency changes are deferred; these
checks do not validate either item. The remaining protected V0 direct POSTs
also remain outside this focused command.

Current production blocker: `web/backend/websocket_handler.py` forces
`async_mode='threading'`, while `start_production.py` claims eventlet mode;
`eventlet` is not a direct project dependency. Do not deploy T10 until one
server mode is selected, pinned, and covered by software-only tests.

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
3. Create a revert commit on Mac:

   ```bash
   git revert <bad-commit>
   git push origin develop
   ```

4. Deploy the revert through `deploy_everest.py`.
5. Restart only affected servers through `restart_tango_servers.py`, with a
   new human-created approval TOML.

## Required Manual Gate

Do not create an approval TOML unless an operator has verified:

- No acquisition is running.
- Stages and delay lines are stationary.
- No user is working at moving or powered hardware.
- Required shutters are closed.
- Restart list contains only servers changed by the deployed commit.
