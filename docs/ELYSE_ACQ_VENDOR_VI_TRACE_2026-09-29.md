# Acquisition vendor-VI trace: CHROMA and TPG300 (2026-09-29)

## Decision boundary

The question is what the saved Acquisition program commands and how it handles communication failures. This note examines LabVIEW source and vendor-VI dataflow, not measured instrument output, NI-card electrical behavior, or the current deployed binary. The saved `ACQUISITION.llb` has SHA-256 `EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A`; the copied `chr62000.llb` has SHA-256 `613571F23CBD2C19899C73806431E1D91EC26ABFDD1857EA507E63E577E218D7`. No VI was executed or saved and no hardware command was sent.

## Source integrity and extraction

The original Acquisition LLB contains 17 members. An independent extraction with the source file held open recovered all 17, byte-identical to the previously extracted set. The CHROMA LLB has 70 sections, seven `UCRF` and 63 `CPRF`; all 70 were extracted with the same method. The `lvkit` convenience extractor recovered only two because its lazy reader had already closed the LLB file (`ValueError: seek of closed file` for the remaining sections). The complete CHROMA extraction is in `C:\dev\ELYSE-ACQ-analysis\offline\extracted\chr62000_VIs\`, with per-member hashes in `extraction_manifest.json`. This is source preservation, not behavioral validation.

## Focal power supplies: observed command chain

The raw `1_Focales ON.vi` and `1_Focales OFF.vi` members reference `<instrlib>\chr62000\chr62000.llb` and six exact vendor members: `Initialize`, `Set Voltage`, `Set Current Slew`, `Set Current`, `Set Output`, and `Close`. The earlier `chr6200d` spelling in the native-frame ledger was a transcription error. The three parallel focal branches target default front-panel resources COM10/COM11/COM12 for Focale 3/2/1; source constants are 70/0.02/15.1, 80/0.02/20.9, and 80/0.02/13.73 for voltage/current-slew/current inputs, respectively. `ON` supplies `True` to each `Set Output`; `OFF` supplies `False`. Each branch closes its session; the parent merges errors. These are requested values, not measured outputs. The `Current Slew` terminal type is DBL, but its physical units are not encoded in the inspected connector pane.

The copied `chr62000 Set Output.vi` converts the Boolean input to 0/1 before its external-function call. `chr62000 Set Current Slew.vi` passes the DBL current-slew input to an external-function call. Both contain a two-arm error-in Case: the `No Error` arm calls the external function and an IVI error converter; the `Error` arm bypasses the call and propagates the incoming error. This describes the LabVIEW wrapper. The DLL implementation, serial device response, and runtime binary identity are outside the verified boundary.

## TPG300 vacuum controller: observed protocol path

The two root initialization calls supply distinct COM1/COM2 VISA resources and numeric baud selector **4** to `TPG 300.lvlib:Initialize.vi`. `TPG300-Serial Init.vi` indexes `[300, 1200, 2400, 4800, 9600, 19200, 38400]`; selector 4 therefore configures **9600 baud**. The initializer is a five-state While-loop machine (`Init & Test`, `Next Baud Rate`, `Set Default`, `Communication OK`, `Error Box`). Its initial test uses command `PNR` through `TPG300-Driver Core.vi` with a wired **700 ms** timeout. A serial-init error selects `Error Box`; the other state-transition predicates and total attempt bound still require wire-level confirmation.

`TPG300-Get Pressure-Status.vi` passes a sensor-dependent command to `TPG300-Driver Core.vi`, then splits the returned text at a comma. The pre-comma substring is parsed as an integer `Status`; the post-comma substring is parsed as floating-point `Pressure`. The VI exposes distinct VISA, pressure, status, and error outputs. Its source contains sensor tokens `A1`, `A2`, `B1`, `B2` and a `P` string input to the command-building primitive; the exact emitted command string remains to be confirmed natively. The pressure/status parser establishes output **types and field order**, not valid ranges or error-state semantics.

`TPG300-Driver Core.vi` exposes default timeout **600 ms** and a `Retry (3)` control. Its visible sequence appends carriage return to commands, uses VISA serial-byte counts/read/write, waits **50 ms** in the exchange loops, compares incoming bytes with ACK (`0x06`) and NAK (`0x15`), sends ENQ (`0x05`) in the response phase, and searches for a carriage-return terminator. The exact retry count as *attempts* versus *additional retries*, all timeout branches, and error propagation need native terminal tracing; the normalized netlist alone is not sufficient to reimplement this state machine.

## Consequence for Python transfer

The source now supports a precise interface model for focal commands and vacuum readbacks. It does **not** yet support a safe claim that Python reproduces the vendor protocols, interlock decisions, or all failure paths. The next discriminating review is a native wire trace of the TPG300 driver loops and of every caller's error handling, followed by read-only replay tests against recorded serial responses. Direct live device commands are not justified by this static audit.

The current `tools/xp_acq_agent_simulator_v4/elyse_agent/simulator.py` exposes two scalar `TPG300_*_mbar` environment values but no TPG status or error fields. The source pressure reader returns both numeric pressure and integer status, and the root loop contains three pressure-reader call sites (two in its first ordered frame, one in the second). The simulator therefore does not yet reproduce the source data shape. The parent-to-sensor/output mapping and configured pressure unit must be established before changing this contract.
