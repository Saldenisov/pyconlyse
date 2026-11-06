const TIME_IN_SECONDS = new Map([['s', 1], ['ms', 1e-3], ['us', 1e-6], ['ns', 1e-9], ['ps', 1e-12], ['fs', 1e-15]]);

export function previewCurve(selection) {
  const { active_data_type: dataType, file_info: file, map_index: mapIndex, cursors } = selection;
  const { x1, x2, y1, y2 } = cursors;
  const path = file.file_path;
  const filename = path.split(/[\\/]/).pop();
  const range = (first, last) => [first, last].map((value) => Number(value).toPrecision(5)).join('–');
  return {
    id: JSON.stringify([path, dataType, mapIndex, x1, x2, y1, y2]),
    path,
    label: `${filename} · ${dataType} · Map ${mapIndex}`,
    ranges: `${range(cursors.x1_value, cursors.x2_value)} nm · ${range(cursors.y1_value, cursors.y2_value)} ${selection.kinetics.time_scale || ''}`,
    unit: dataType === 'OD' || dataType === 'DAT' ? 'OD' : 'Intensity',
    kinetics: selection.kinetics,
    spectrum: selection.spectrum,
  };
}

function normalizeTimeUnit(unit) {
  return String(unit || '').trim().toLowerCase().replace(/[µμ]/g, 'u').replace(/^\?+$/, '');
}

export function convertPreviewTime(values, from, to) {
  const source = normalizeTimeUnit(from);
  const target = normalizeTimeUnit(to);
  // Legacy DAT files may contain delay coordinates without unit metadata.
  // Keep their original axes together and label them as file units in Preview.
  if (source === target) return values;
  const sourceFactor = TIME_IN_SECONDS.get(source);
  const targetFactor = TIME_IN_SECONDS.get(target);
  if (!sourceFactor || !targetFactor) return null;
  return values.map((value) => value * (sourceFactor / targetFactor));
}
