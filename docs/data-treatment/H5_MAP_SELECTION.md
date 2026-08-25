# H5 map-selection contract

Treatment H5 files are the structured working representation of a measurement.
Hamamatsu HIS input is converted to H5 before cleaning or OD calculation.

## Canonical schema (H5 schema version 2)

```
/raw_data                  float[map, wavelength, timedelay]
/wavelengths               float[wavelength]
/timedelays                float[timedelay]
/metadata                  provenance and conversion attributes
/map_selection/included    bool[map]
```

`/raw_data` is the complete acquisition in original map order. Cleaning must
never delete, move, reorder, or overwrite a raw map.

`/map_selection/included` is the authoritative decision for downstream map
averages and OD calculations. `True` selects a map; `False` excludes it. The
group attributes record the selection method, SAM thresholds, and JSON records
with the reason for every excluded map.

## Lifecycle

1. HIS conversion writes every source map to `/raw_data` and an all-`True`
   selection.
2. SAM cleaning writes a complete H5 archive and changes only the selection
   mask plus its audit metadata.
3. OD/noise averages use selected maps only.
4. Cleaning preview reads all raw maps, including excluded maps, so a decision
   can be inspected or recomputed.
5. Restore sets every selection value to `True`; it does not rewrite
   `/raw_data`.

Legacy files that used `/deleted/data` remain readable. Saving or restoring
such a file migrates its maps into `raw_data` and writes the version-2
selection contract.

Retention or deletion of the original HIS source is a separate acquisition
storage policy. It is not implied by this H5 contract.
