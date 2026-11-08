# XP NI eleven-card audit, 2026-09-28

## Evidence and result

Source: `tools/xp_acq_input_probe_v1/input_probe.jsonl`, copied from
`10.20.30.10` after the 07:46:07 UTC inventory. NI-DAQmx 9.6.2 reported
11 non-simulated devices. All six physical-channel collection queries
(AI, AO, DI, DO, CI, CO) succeeded for each device, without creating a task,
reading a line, or writing hardware. Channel counts are capabilities; DI and
DO on a bidirectional line are **not** separate simultaneously usable pins.

| Card | Device | Serial | AI | AO | DI/DO | CI/CO | Live Python signal test |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | PCI-6071E | 18955553 | 64 | 2 | 8/8 | 2/3 | 64/64 AI voltages read |
| 2 | PCI-6071E | 18023031 | 64 | 2 | 8/8 | 2/3 | 64/64 AI voltages read |
| 3 | PCI-DIO-96 | 11099079 | 0 | 0 | 96/96 | 0/0 | None; metadata only |
| 4 | PCI-DIO-96 | 18235561 | 0 | 0 | 96/96 | 0/0 | None; metadata only |
| 5 | PCI-DIO-96 | 11164926 | 0 | 0 | 96/96 | 0/0 | None; metadata only |
| 6 | PCI-6703 | 13355601 | 0 | 16 | 8/8 | 0/0 | None; metadata only |
| 7 | PCI-6703 | 13355581 | 0 | 16 | 8/8 | 0/0 | None; metadata only |
| 8 | PCI-6703 | 13355875 | 0 | 16 | 8/8 | 0/0 | None; metadata only |
| 9 | PCI-6703 | 13355612 | 0 | 16 | 8/8 | 0/0 | None; metadata only |
| 10 | PCI-6602 | 18293888 | 0 | 0 | 32/32 | 8/8 | None; metadata only |
| 11 | PCI-6220 | 19464152 | 16 | 0 | 24/24 | 2/3 | 16/16 AI voltages read |

The analog reads were software-timed diagnostics, using DIFFERENTIAL on
`ai0:7` and RSE on `ai8+`. Total: 144/144 successful in the final whole-card
passes. No task has validated legacy hardware triggering, calibration, signal
meaning, channel wiring, or output electrical state.

Fresh pre-start analog baseline: card 11 completed 16/16 at 08:09:33 UTC,
card 1 completed 64/64 at 08:09:42 UTC, and card 2 completed 64/64 at
08:09:53 UTC. The pre-start copied journal was 57,563 bytes, SHA-256
`FD9E9E22A80BE05316874F511499456450B7F1091D184F943BA865CC6EB7DF08`.
No LabVIEW process was visible in the XP desktop/taskbar while these three
measurements were made. The log records `hardware_writes: false` for each.

## Before/after Acquisition experiment

The useful comparison has three distinct layers:

1. **Before:** preserve the card/serial inventory; sample the 144 analog
   inputs with exact task configuration and timestamps; record the machine's
   safe operating state and independent equipment readbacks. Do not claim
   an AO/DO/CO pin-state baseline from DAQmx capability metadata.
2. **During one controlled LabVIEW run:** document which VI is launched,
   whether initialization completes, every visible error, the run duration,
   and PSP command/readback snapshots. Confirm independent interlocks and
   operator supervision before allowing startup. LabVIEW startup can write
   analog/digital outputs and start counter pulses.
3. **After normal VI stop:** repeat inventory and the same analog reads;
   compare values with timestamps and PSP snapshots. This measures changes
   in observed AI signals, **not** direct electrical state of AO/DO/CO pins.
   Verify physical safe state independently after stop; task release does not
   prove that outputs reverted.

Do not create DI tasks on cards 3–5 solely for this comparison: PCI-DIO-96
uses 8255 port-direction groups. The recovered DI ranges include port 6 on
cards 3/5 and port 7 on card 4; their sibling groups include output ports.
Creating an input task can reset neighboring outputs even without an explicit
write. Cards 6–9 are predominantly AO; card 10 counters can drive PFI pins.
True output comparison requires independent measurement/loopback on selected
wired pins, with polarity and safe-state limits agreed per channel.

## Controlled LabVIEW run and stop

The XP desktop `ACQ ELYSE` shortcut launched LabVIEW 2012 32-bit and the
`0_ACQ_ELYSE.vi` front panel. During the run, the panel showed
`Défaut de communication TCP/IP avec le SVE`; both displayed HT command and
readback were `0,0 kV`. The left-hand loop counters advanced, confirming
that the VI was running. These panel observations are not a full trace of
NI output values or a physical interlock check.

After the operator explicitly confirmed the machine was safe to stop, one
click on the front-panel `STOP` button returned the VI to LabVIEW edit mode.
The displayed loop counters then stayed constant across a five-second
observation. This supports normal VI stop; LabVIEW itself remained open.

Post-stop analog reads completed: card 11, 16/16 at 08:32:33 UTC; card 1,
64/64 at 08:32:56 UTC; card 2, 64/64 at 08:33:06 UTC. All reports recorded
`hardware_writes: false`. The before and after values are in the same copied
JSONL journal (SHA-256
`3F117C34AAF9C58FA86EB94E3A0934993785068D6D98D2070B15F855BD1F1302`).

| Card | Channels changing by >0.1 V | Largest absolute change |
|---|---:|---:|
| 1 | 38/64 | 6.01 V |
| 2 | 32/64 | 7.32 V |
| 11 | 7/16 | 5.67 V |

These are raw, non-simultaneous software-timed voltage readings separated by
about 23 minutes; they do **not** isolate a causal effect of LabVIEW startup.
Many of the largest changes on cards 1 and 2 are channels labeled `Libre ?`
in the recovered map, so floating/unwired behavior is a plausible competing
explanation. The acquisition run was not timed to exactly one minute, and no
PSP snapshot or independent AO-pin measurement was recorded during the run.

## Python output and TCP readiness

The XP offline bundle pins `nidaqmx==0.5.7`. Its Python 3.4 API exposes
`AOChannelCollection.add_ao_voltage_chan` and `Task.write`; the real XP
driver enumerated `/6/ao0:15` through `/9/ao0:15`. This establishes a
plausible software path for voltage output, **not** a successful physical AO
write or a verified voltage on a terminal. The recovered LabVIEW mapping
uses `/6/ao0:9` through `/9/ao0:9` (40 logical outputs).

The TCP/JSON server and simulator command contract are implemented, but
`10.20.30.10:8765` did not accept a connection during this audit. In
`simulation` mode, output commands mutate memory only. In `discover_only`
mode, they are rejected, and `allow_hardware_writes: true` fails startup.
The current XP agent therefore cannot change real NI output states over TCP.
Exact LabVIEW startup AO values and output retention after stop have not yet
been established; simulator zero defaults are not evidence for either.
