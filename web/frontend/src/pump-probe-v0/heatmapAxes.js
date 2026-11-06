// Keep acquisition/merge order when physical coordinates do not identify cells.
export function heatmapAxis(values) {
  const direction = Math.sign(values[1] - values[0]);
  const positional = values.length < 2 || !direction
    || values.some((value, index) => index > 0 && Math.sign(value - values[index - 1]) !== direction);
  const coordinates = positional ? values.map((_value, index) => index) : values;
  const last = coordinates.length - 1;
  const range = positional ? [-0.5, last + 0.5]
    : [coordinates[0] - (coordinates[1] - coordinates[0]) / 2,
      coordinates[last] + (coordinates[last] - coordinates[last - 1]) / 2];
  const step = Math.max(1, Math.ceil(values.length / 12));
  const ticks = values.map((_value, index) => index).filter((index) => index % step === 0 || index === last);
  return { positional, coordinates, range,
    ticks: positional ? { tickmode: 'array', tickvals: ticks, ticktext: ticks.map((index) => `${values[index]} [${index}]`) } : {} };
}

export function selectionAround(axis, index, halfWidth) {
  const center = axis.coordinates[index] ?? 0;
  const limits = [Math.min(...axis.range), Math.max(...axis.range)];
  return [Math.max(limits[0], center - halfWidth), Math.min(limits[1], center + halfWidth)];
}

export function physicalSelection(values, indexes) {
  const selected = indexes.map((index) => values[index]);
  return [Math.min(...selected), Math.max(...selected)];
}
