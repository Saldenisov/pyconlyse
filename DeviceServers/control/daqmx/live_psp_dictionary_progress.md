# Live PSP Dictionary Progress

- Source dictionary: `/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/live_psp_raw_dictionary.after_clear.json`
- Clean live dump: `/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/live_psp_latest_raw_after_clear.json`
- Seed mappings: `/Users/sad/dev/pyconlyse/DeviceServers/control/daqmx/raw_to_canonical_seed_dictionary.after_clear.json`

## Coverage

- Total channels: `677`
- Channels with canonical_name: `104`
- Channels with functional_group: `380`
- Channels with direction: `475`

## By Group

- `cooling`: `20`
- `ht_hf`: `49`
- `magnets`: `92`
- `modulator`: `37`
- `placeholder`: `66`
- `sync`: `33`
- `vacuum`: `83`

## By Direction

- `ignore`: `66`
- `read`: `339`
- `write`: `70`

## Known Conflicts

- `34 ACH34 b71 Mes I Guidage V5` -> `elyse/magnets/Cor_V5/value` for now; also conflicts with `elyse/magnets/Cor_H5/value`
