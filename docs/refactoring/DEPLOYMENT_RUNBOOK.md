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
for request/classification contracts. Manual probes, legacy, integration,
main-app, and utilities suites remain opt-in and are not silently deleted or
treated as software-only verification.

The verification tool has no SSH, Tango, PDU, motion, shutter, or power code.

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
