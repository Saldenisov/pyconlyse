# Pyconlyse web W0 diagnosis and corrections

The failed baseline combined test-environment gaps, omitted static fixtures and
React effect problems. The follow-up fixes the reproducible web problems and
qualifies them in the isolated worktree. It does not establish recovery of the
acquisition server or any native driver.

Local source target: `C:\dev\pyconlyse`. Source hashes, backups and application
status are recorded in `application-verification.json` and `applied.json` in the
evidence directory below. The historical baseline report and its original
results remain unchanged.

## Causes and changes

| Observation | Cause established from code and focused tests | Correction |
| --- | --- | --- |
| Strict CI frontend build failed | Seven hook warnings across five components; unstable read callbacks and array dependencies | Stable callbacks and device/motor selections; explicit effect dependencies; strict CI retained |
| PDU faults could disappear after initial reads | Socket handler captured the initial empty device dictionary | Match configured devices and current socket; regression test asserts fault visibility |
| Loading device attributes did not enable later receipt refreshes | Socket handler captured initial `attributesLoaded=false` | Read current loaded state through a ref; regression test verifies refresh without reconnect or command replay |
| Rendering equivalent PDU selections reconnected the socket | Parent created a new array with the same names | Stable selection by array contents; regression test verifies one connection and one initial read |
| Frontend default test discovery found zero tests | Default root-expanded patterns did not match this Windows worktree path | Portable source globs in package Jest configuration; normal `npm test` discovers the suite |
| Three fake-device test modules could not import | Collection still required MSL, NI and easy-SCPI packages although transports were fake | Scoped import-only stand-ins; unexpected SDK transport construction raises; native packages remain absent |
| Native Tango and external converter tests broke default collection | Those tests require a real standalone Tango context or separate pinned converter checkout | Preserve tests in explicit integration directories outside the default software lane; native Tango integration bypasses fake protocol imports |
| Coverage tooling failed before evaluating results | Three new data readers had no configured floors or inclusion | Add explicit 80% floors and coverage inclusion; retain all existing floors |
| Windows symlink tests failed before policy checks | This process lacks symlink creation privilege | Split malformed-input tests; run metadata rejection tests without that privilege; report real symlink tests as explicit skips |
| Local startup test attempted an E-drive probe | Fixture supplied no treatment root | Give the test a temporary root; retain the filesystem guard and application behavior |
| Two treatment queue tests attempted to parse fake HDF5 text | Mock targeted the old shared service; cleaner now constructs its own worker service | Mock the worker class boundary and assert it differs from the shared service |
| Reader coverage was below its retained floor | No disposable binary HIS fixtures covered frame decoding | Add signed 8/16/32-bit, map-selection and orientation cases using temporary synthetic files |
| Ruff reported 46 findings | Unused imports/locals, placeholder-free f-strings, implicit re-exports and an unnecessary wildcard import | Clean test imports, make compatibility/test-suite exports explicit, and preserve evaluated expressions and public bindings |
| Verification selected a missing Python 3.9 environment | Legacy verification default differed from the Python 3.12 lock | Change only the verification default; deployment and restart interpreter profiles retain their existing settings |

Explicit test-class exports remain collected. No imported unittest suite was
removed merely to clear a lint warning. Python runtime bodies in the nine
affected backend/DeviceServer modules match their captured versions after
normalizing imports, three unused local names and two literal f-strings. Static
AST comparison also confirms that all 13 frontend handlers containing hardware
approval requests retain their previous bodies.

## Verification

| Check | Result |
| --- | --- |
| Normal frontend tests | 591 passed in 51 suites |
| Strict frontend CI build | Passed; no lint suppression or disabled CI checks |
| Guard/tooling tests | 45 passed |
| Focused fixture/queue/HIS repairs | 38 passed |
| Web software verification | 3,881 passed, 104 skipped; 3,985 cases, zero failures |
| Named Python coverage floors | All 30 pass; 73.04% combined statement coverage; no existing floor lowered |
| Changed-file Ruff F check | Passed with zero findings |
| Compile and whitespace checks | Passed |

The web software command includes all `tests/web` and `tests/device_servers`
tests plus explicitly listed security/tooling, import-isolation, data-reader,
numerical correction and treatment unit tests. Its exact paths and command are
stored in `web-software.result.json`; it is not the full historical test suite.

Expected skips retain their reasons: original Python 3.4 is unavailable, native
Windows symlink creation lacks privilege, and a POSIX directory-fsync case is
separate from Windows durability tests. Synthetic metadata tests exercise
policy/approval rejection without claiming that native filesystem symlinks were
qualified.

The unrestricted historical run exposed hundreds of omitted corpus inputs and
was interrupted as a diagnostic, not reported as a completed pass. In particular,
Supervision source-audit tests require hash-pinned parser receipts such as
`Supervision/analysis/lvkit_eval/parser_release_20261003/00.json` and their source
corpus. Those inputs belong to separate historical qualification. Native Tango
and converter integration also remain unqualified in this environment.

Eight closed, copied ACQ source-export ZIPs and two static CSV expectations were
added to the isolated test inputs with source/destination SHA-256 checks. They
were only read as static files. No VI, source converter, hardware, live service
or active HDF5 file was executed or accessed.

The HIS fixtures cover the current reader's uncalibrated Other mode. They
qualify signed values, map selection and `(wavelengths, timedelays)` orientation;
they do not qualify vendor calibration or repair numerical algorithms.

## Local evidence and preservation

Worktree: `C:\Users\elyse\.codex\worktrees\web-stability-w0\pyconlyse`.
Evidence: `.tmp/w0-followup-20261025/` inside that worktree.

| Evidence | Purpose |
| --- | --- |
| `changes.json` and `before/` | Exact before hashes and source copies for this follow-up only |
| `review-changes.json` and `changes.patch` | Reviewable delta, excluding inherited unrelated work |
| `web-software.xml`, `frontend.log`, per-check `*.result.json` | Outcomes, skips and exact commands |
| `coverage.json`, `coverage-floor.log` | Measured coverage and retained-floor gate |
| `mutation-handlers.json`, `python-runtime-proof.json` | Static checks bounding changes to command/runtime behavior |
| `closed-fixtures.json`, `csv-fixtures.json` | Hashes of copied static test inputs |
| `python.diagnostic-missing-fixtures.log` | Interrupted historical diagnostic; not a passing full-suite result |
| `original-backup/`, `applied.json`, `application-verification.json` | Source application and preservation checks |
| `application-selftest.json` | Successful synthetic application, conflict refusal and rollback cases |

Application is limited to the captured follow-up delta. Before each replacement,
the original must still match its captured hash. Files are backed up and replaced
atomically; a conflict prevents overwrite. Git HEAD and index are preserved.
Inherited changes are neither reset nor stashed. Build output, test environments,
runtime databases and source-corpus archives are not deployed to the original
checkout. No service restart or deployment is part of this change.
