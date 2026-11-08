import { clampSampleIndex } from "./TopSection.HEATMAP_MARGIN";
import { mean } from "./TopSection.HEATMAP_MARGIN";

function buildPreviewCurves(selection, selectedRange) {
  const z = selection?.heatmap?.z || [];
  const wavelengths = selection?.heatmap?.wavelengths || [];
  const timedelays = selection?.heatmap?.timedelays || [];
  const xLength = selection?.file_info?.wavelengths_length || wavelengths.length;
  const yLength = selection?.file_info?.timedelays_length || timedelays.length;

  if (!selectedRange || z.length === 0 || wavelengths.length === 0 || timedelays.length === 0) {
    return null;
  }

  const x1 = clampSampleIndex(selectedRange.x1, xLength, wavelengths.length);
  const x2 = clampSampleIndex(selectedRange.x2, xLength, wavelengths.length);
  const y1 = clampSampleIndex(selectedRange.y1, yLength, timedelays.length);
  const y2 = clampSampleIndex(selectedRange.y2, yLength, timedelays.length);
  const xStart = Math.min(x1, x2);
  const xEnd = Math.max(x1, x2);
  const yStart = Math.min(y1, y2);
  const yEnd = Math.max(y1, y2);

  const kinetics = z.map((row) => mean((row || []).slice(xStart, xEnd + 1)) ?? 0);
  const spectrum = wavelengths.map((_, colIndex) => {
    const values = [];
    for (let rowIndex = yStart; rowIndex <= yEnd; rowIndex += 1) {
      values.push(z[rowIndex]?.[colIndex]);
    }
    return mean(values) ?? 0;
  });

  return {
    kinetics: {
      x: timedelays,
      y: kinetics,
      time_scale: selection.kinetics?.time_scale || '',
    },
    spectrum: {
      x: wavelengths,
      y: spectrum,
    },
  };
}

export {
  buildPreviewCurves,
};
