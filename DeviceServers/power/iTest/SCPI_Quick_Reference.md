# BILT / iTest SCPI Quick Reference (for Device Server Development)

Scope
- Target: iTest BILT mainframes with current-source modules like BE2819 (15A/10V) and BE2811
- Transport: TCP/IP over port 5025, ASCII SCPI, EOL = LF ("\n")
- This cheatsheet merges official BILT programming model with commands validated on rack 10.20.30.24

Connection basics
- Host: <rack_ip> (e.g. 10.20.30.24)
- Port: 5025
- Line terminator: LF only ("\n")
- Encoding: ASCII

Recommended discovery flow (validated)
1) Identify rack
   - *IDN? → returns model, serial, versions
   - SYST:VERS? → returns firmware (e.g. "VM 4.6.05 ARM I")

2) Discover installed modules / slots
   - INST:LIST? → returns semicolon-separated pairs: "slot,model;slot,model;..."
     Example observed: 1,2819;3,2819;5,2811;6,2811;7,2819;9,2819;11,2811;12,2811
   - INST:NSEL? → number of instruments
   Notes: INST:CAT? timed out on our rack; prefer INST:LIST?

3) Select a module (slot)
   - I <slot>  (alias of INST <slot>)
     Example: I 7  selects slot 7
   - IMC? → 1 if module is IMC (independent channels), 0 otherwise
   - For IMC modules with multiple channels: C <chan> selects channel

4) Basic PSU operations (on selected slot/channel)
   - Output
     - OUTP ON | OFF
     - OUTP? → 1 or 0 (observed OK)
   - Measurements (observed OK)
     - MEAS:VOLT? → measured voltage (V)
     - MEAS:CURR? → measured current (A)
   - Setpoints (write works; readback varies by module)
     - VOLT <V>
     - CURR <A>
     - SOUR:CURR <A> (alternative set syntax)
     - SOUR:CURR? → readback: timed out on our rack; not all modules support reading setpoint via this node
       Fallback strategies:
       - Try CURR? (legacy short form) if available on your module
       - Cache last written setpoint in software if no readback is available

5) Optional: Protection thresholds (per-module)
   - FUNC CV|CC → selects which quantity is regulated; the non-regulated is monitored by limits
   - LIM:LOW <val>; LIM:UPP <val>
   - LIM:DELay <ms>
   - LIM:STATe ON|OFF
   - LIM:FAIL? → returns reason token (e.g., HIGH/LOW)

6) Grouping (optional, for synchronized start/stop)
   - P <n>                select group
   - P:DEF / P:CLEAR:DEF define/delete group
   - P:INST:LIST <list>  attach modules/channels to group (e.g., 2,3,4-2,4-3)
   - P:STATe ON|OFF      start/stop group (honors per-module start/stop delays)
   - P:LIMit ON|OFF      enable group-level threshold stop
   - P:STATe:CLEAR       acknowledge/clear alarms

What worked vs. didn’t on 10.20.30.24
- Worked:
  - *IDN?
  - INST:LIST?
  - INST:NSEL?
  - MEAS:VOLT?, MEAS:CURR?
  - OUTP?, OUTP ON/OFF
  - SYST:VERS?
- Timeouts/Not supported on this rack:
  - INST:CAT? / OUTP:CAT?
  - INST:SEL?  (use I <slot> / INST <slot> instead)
  - SYST:CHAN:COUNT?, SYST:CARD:COUNT?, etc.
  - SOUR:CURR? setpoint readback (use cache or alternate query)

Slot model mapping (observed)
- Model 2819: 15A / 10V current source (slots observed: 1, 3, 7, 9)
- Model 2811: current source (slots observed: 5, 6, 11, 12)

Examples (SCPI sequences)
- Discover installed slots:
  *IDN?
  INST:LIST?

- Read measurements from slot 7:
  I 7
  MEAS:CURR?
  MEAS:VOLT?

- Turn output ON for slot 7, set current to 0.5 A (if supported):
  I 7
  CURR 0.5
  OUTP ON

- Configure upper current limit and arm it:
  I 7
  FUNC CV              ; monitor current in CV mode
  LIM:LOW -999         ; unused
  LIM:UPP 2.0          ; 2 A upper limit
  LIM:DEL 1000         ; 1 s stabilization delay
  LIM:STAT ON

- Minimal grouping of slots 1 and 7:
  P 1
  P:DEF
  P:INST:LIST 1,7
  P:STAT ON

Driver guidance for DS_itest_psu
- Selection:
  - Use I <slot> to target a module
  - If IMC?, select C <chan> for multi-channel modules (if present)
- Measurement path:
  - Prefer MEAS:CURR? and MEAS:VOLT? for live values
- Setpoints:
  - Use CURR <A> / VOLT <V> to set; readback of current setpoint via SOUR:CURR? may not be available → cache
- Output state:
  - OUTP ON/OFF, OUTP? (returns 1 or 0)
- Discovery:
  - Parse INST:LIST? into [(slot, model), ...]
  - Build friendly names, e.g., slot_7_model_2819
- Error handling:
  - Query SYST:ERR? on failures; consider SYST:VERBose OFF for machine parsing
- Networking:
  - Verify LF line termination ("\n"); timeouts ~3–5 s are reasonable defaults

Notes from the BILT manual
- Addressing model:
  - Rack → Instruments (I <slot>) → Channels (C <n>) → Groups (P <n>)
- Groups provide synchronized start/stop, logging, memories, cycling, thresholds
- Many commands support short/long SCPI forms and chaining with ";" and ";:"
- All SCPI is case-insensitive

Appendix: Quick command table
- Rack: *RST, SYST:VERS?, SYST:ERR?, SYST:ETH:ADDR/ROUT/MASK, SYST:VERBose
- Instrument select: INST <slot> | I <slot>, IMC?, C <chan>
- Discovery: INST:LIST?, INST:NSEL?
- PSU core: VOLT <V>, CURR <A>, MEAS:VOLT?, MEAS:CURR?, OUTP ON/OFF, OUTP?
- Limits: FUNC CV|CC, LIM:LOW <v>, LIM:UPP <v>, LIM:DEL <ms>, LIM:STAT ON/OFF, LIM:FAIL?
- Groups: P <n>, P:DEF, P:INST:LIST <...>, P:STAT ON/OFF, P:STAT:CLEAR, P:LIMit ON/OFF

Caveats
- Not all documented commands are present on all firmware/module revisions; implement feature-detection:
  - Try a command once; on SCPIError or timeout, mark unsupported and avoid spamming the device
- Prefer vendor-validated paths (INST:LIST? + I <slot> + MEAS:*) over catalog-like queries that timed out on our rack
