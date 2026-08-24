
import {
  fetchWithCsrfToken,
  fetchWithHardwareApproval,
  isHardwareApprovalConcurrencyError,
} from '../api/csrfRequest';

// Shared V0 domain constants, API helpers, and selection math.
const PIXELS = 512;
const STAGE_MIN_MM = -900;
const STAGE_MAX_MM = 100;
const SAMPLE_STAGE_MIN_MM = 0;
const SAMPLE_STAGE_MAX_MM = 78;
const SAMPLE_STAGE_SPEED_MM_PER_SEC = 1;
const DEFAULT_SAMPLE_POSITIONS_MM = Array.from({ length: 7 }, (_value, index) => index * 13);
const MM_PER_PS = 0.0749481145;
const API_BASE = '/api/pump-probe-v0';

function isUnsafeRequest(options) {
  return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(String(options.method || 'GET').toUpperCase());
}

function hasExplicitlyDisabledJsonAction(options, field) {
  if (typeof options.body !== 'string') {
    return false;
  }

  try {
    const payload = JSON.parse(options.body);
    return payload !== null
      && typeof payload === 'object'
      && !Array.isArray(payload)
      && payload[field] === false;
  } catch (_error) {
    return false;
  }
}

function requiresPumpProbeHardwareApproval(path, options) {
  if (!isUnsafeRequest(options)) {
    return false;
  }

  if (path === '/hardware/initialize'
    || path === '/stage/move'
    || path === '/stage/stop'
    || path === '/sample-stage/move'
    || path === '/sample-stage/stop') {
    return true;
  }

  if (path === '/run') {
    return !hasExplicitlyDisabledJsonAction(options, 'running');
  }
  if (path === '/realtime') {
    return !hasExplicitlyDisabledJsonAction(options, 'enabled');
  }
  return false;
}

function requiresDeviceHardwareApproval(url, options) {
  return isUnsafeRequest(options)
    && typeof url === 'string'
    && (url === '/api/device' || url.startsWith('/api/device/'));
}

function fetchV0Request(url, options, requiresHardwareApproval) {
  return requiresHardwareApproval
    ? fetchWithHardwareApproval(url, options)
    : fetchWithCsrfToken(url, options);
}

async function pumpProbeRequest(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const requestOptions = {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    credentials: 'include',
    ...options,
  };
  const response = await fetchV0Request(
    url,
    requestOptions,
    requiresPumpProbeHardwareApproval(path, requestOptions)
  );
  if (!response.ok) {
    let message = `Pump-probe V0 API failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.error || payload.msg || message;
    } catch (_error) {
      // Keep HTTP status fallback for non-JSON failures.
    }
    throw new Error(message);
  }
  return response.json();
}

function isTransientTangoError(message) {
  const text = String(message || '').toLowerCase();
  return text.includes('connection request was delayed')
    || text.includes('api_cantconnecttodevice')
    || text.includes('last connection request was done less than');
}

function compactHardwareError(errors) {
  if (!errors.length) {
    return '';
  }

  const details = errors.join('\n');
  if (details.includes('API_CantConnectToDatabase')) {
    return 'Tango Database unavailable: 10.20.30.202:10000. Check ELYSE Ethernet connection and the Windows Tango host.';
  }

  return errors.length === 1 ? errors[0] : `${errors.length} hardware requests failed. ${errors[0]}`;
}

async function fetchJsonWithRetry(url, options = {}, attempts = 3) {
  const requiresHardwareApproval = requiresDeviceHardwareApproval(url, options);
  let lastError = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetchV0Request(url, options, requiresHardwareApproval);
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Request failed: ${response.status}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (requiresHardwareApproval
        || isHardwareApprovalConcurrencyError(error)
        || !isTransientTangoError(error.message)
        || attempt + 1 >= attempts) {
        throw error;
      }
      await new Promise((resolve) => { window.setTimeout(resolve, 1100); });
    }
  }
  throw lastError;
}

function linspace(start, stop, count) {
  if (count <= 1) {
    return [start];
  }
  const step = (stop - start) / (count - 1);
  return Array.from({ length: count }, (_value, index) => start + step * index);
}

function gaussian(x, center, width) {
  const scaled = (x - center) / width;
  return Math.exp(-0.5 * scaled * scaled);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeRange(range) {
  if (!range || range.length !== 2) {
    return null;
  }
  const first = Number(range[0]);
  const second = Number(range[1]);
  if (!Number.isFinite(first) || !Number.isFinite(second)) {
    return null;
  }
  return [Math.min(first, second), Math.max(first, second)];
}

function indexesInRange(values, range) {
  const normalized = normalizeRange(range);
  if (!normalized) {
    return values.map((_value, index) => index);
  }
  return values
    .map((value, index) => ({ value, index }))
    .filter(({ value }) => value >= normalized[0] && value <= normalized[1])
    .map(({ index }) => index);
}

function averageRows(rows, indexes) {
  if (!rows.length) {
    return [];
  }
  const width = rows[0]?.length || 0;
  return Array.from({ length: width }, (_value, colIndex) => {
    let sum = 0;
    let count = 0;
    indexes.forEach((rowIndex) => {
      const value = rows[rowIndex]?.[colIndex];
      if (value !== null && value !== undefined && Number.isFinite(Number(value))) {
        sum += Number(value);
        count += 1;
      }
    });
    return count ? sum / count : null;
  });
}

function averageColumns(rows, indexes) {
  return rows.map((row) => {
    let sum = 0;
    let count = 0;
    indexes.forEach((colIndex) => {
      const value = row?.[colIndex];
      if (value !== null && value !== undefined && Number.isFinite(Number(value))) {
        sum += Number(value);
        count += 1;
      }
    });
    return count ? sum / count : null;
  });
}

function nearestIndex(values, target) {
  if (!values.length) {
    return 0;
  }
  return values.reduce((bestIndex, value, index) => (
    Math.abs(value - target) < Math.abs(values[bestIndex] - target) ? index : bestIndex
  ), 0);
}

function rangeAround(values, center, halfWidth) {
  if (!values.length) {
    return [0, 1];
  }
  const minValue = values[0];
  const maxValue = values[values.length - 1];
  return [
    clamp(center - halfWidth, minValue, maxValue),
    clamp(center + halfWidth, minValue, maxValue),
  ];
}

function formatStageMm(value) {
  return Number(value).toFixed(2).replace('.', ',');
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} kB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function displayPathTail(path) {
  const text = String(path || '').replace(/\/+$/, '');
  const parts = text.split('/').filter(Boolean);
  return parts[parts.length - 1] || text || 'root';
}

function buildSyntheticRun(pointCount = 100) {
  const wavelengths = linspace(253.2375, 826.3287, PIXELS);
  const delays = linspace(-25, 95, pointCount);

  const heatmap = delays.map((delay, rowIndex) => (
    wavelengths.map((wavelength, colIndex) => {
      const bandA = gaussian(wavelength, 445, 42);
      const bandB = gaussian(wavelength, 650, 68);
      const kinetics = 0.18 * (1 - Math.exp(-(delay + 30) / 42));
      const ripple = 0.012 * Math.sin(colIndex / 13 + rowIndex / 7);
      return Number((kinetics * bandA - 0.07 * bandB + ripple).toFixed(5));
    })
  ));

  return { wavelengths, delays, heatmap };
}

function makeCurrentSpectra(wavelengths, index, electronState) {
  const phase = index * 0.31;
  const electronScale = electronState === 'ON' ? 0.92 : 1.0;
  const signal = wavelengths.map((wavelength, pixel) => {
    const lamp = 22000 * gaussian(wavelength, 525, 230) + 4200;
    const absorbance = 1 - 0.11 * gaussian(wavelength, 458 + 6 * Math.sin(phase), 38);
    const noise = 260 * Math.sin(pixel / 9 + phase);
    return Math.round(lamp * absorbance * electronScale + noise);
  });
  const reference = wavelengths.map((wavelength, pixel) => {
    const lamp = 21000 * gaussian(wavelength, 535, 250) + 4600;
    const noise = 190 * Math.cos(pixel / 11 + phase * 0.7);
    return Math.round(lamp + noise);
  });
  const background = wavelengths.map((wavelength, pixel) => (
    Math.round(520 + 45 * Math.sin(pixel / 17 + phase) + 8 * gaussian(wavelength, 400, 180))
  ));
  return { signal, reference, background };
}

const DEFAULT_SETTINGS = {
  pointCount: 100,
  scanStartPs: -25,
  delayStepPs: 1,
  realZeroPs: 465,
  pulsesPerPoint: 10,
  delayPointsPs: null,
  delayMode: 'generated',
};

const DEFAULT_HARDWARE_CONFIG = {
  controlMode: 'emulator',
};

const DEFAULT_DEVICE_CONFIG = {
  delayLine: {
    label: 'Delay line',
    tangoDevice: 'manip/general/DS_OWIS_Aggregator',
    axis: 3,
    backendDeviceName: 'manip/V0/DLl1_V0',
    hardwareLabel: 'Delay line long',
    enabled: true,
  },
  sampleStage: {
    label: 'Sample translation stage',
    tangoDevice: 'manip/general/DS_OWIS_Aggregator',
    axis: 1,
    backendDeviceName: 'manip/V0/DLs_V0',
    hardwareLabel: 'Sample holder V0',
    positionsMm: DEFAULT_SAMPLE_POSITIONS_MM,
    enabled: true,
  },
  spectrometer: {
    label: 'Spectrometer',
    tangoDevice: 'manip/CR/ANDOR_CCD1',
    netioDevice: 'tango://localhost:10000/v0/netio/spectrometer',
    powerOn: false,
    enabled: true,
  },
};

const NETIO_POWER_CHANNELS = [
  {
    key: 'delayLineController',
    label: 'DL controller',
    device: 'manip/V0/PDU_VO',
    outputId: 2,
  },
  {
    key: 'standaStepMotors',
    label: 'Standa StpMtr',
    device: 'manip/V0/PDU_VO',
    outputId: 3,
  },
  {
    key: 'uvVis',
    label: 'UV-vis',
    device: 'manip/SD1/PDU_SD1',
    outputId: 1,
  },
  {
    key: 'ir',
    label: 'IR',
    device: 'manip/SD1/PDU_SD1',
    outputId: 2,
  },
  {
    key: 'dg645',
    label: 'DG645',
    device: 'manip/SD2/PDU_SD2',
    outputId: 2,
  },
  {
    key: 'powerControl',
    label: 'Power control',
    device: 'manip/SD2/PDU_SD2',
    outputId: 3,
  },
  {
    key: 'powerCurrent',
    label: 'Power current',
    device: 'manip/SD2/PDU_SD2',
    outputId: 4,
  },
];

const HARDWARE_TANGO_SERVERS = [
  {
    key: 'owisAggregator',
    label: 'DSOWIS aggregator',
    device: 'manip/general/DS_OWIS_Aggregator',
  },
  {
    key: 'andorCcd',
    label: 'Andor CCD / UVIS',
    device: 'manip/CR/ANDOR_CCD1',
  },
  {
    key: 'dg645',
    label: 'DG645 digital generator',
    device: 'manip/sync/DG645',
  },
];

function devicePath(deviceName) {
  return deviceName;
}

function normalizeNetioOutputs(outputs = []) {
  return outputs.map((output, index) => ({
    id: Number(output.id ?? index + 1),
    name: output.name || `Output ${index + 1}`,
    state: Number(output.state) ? 1 : 0,
  }));
}

function generatedDelayPoints(settings) {
  return Array.from({ length: settings.pointCount }, (_value, index) => (
    settings.scanStartPs + index * settings.delayStepPs
  ));
}

function activeDelayPoints(settings) {
  return settings.delayPointsPs?.length ? settings.delayPointsPs : generatedDelayPoints(settings);
}

function parseDelayPointsText(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/[-+]?\d+(?:[.,]\d+)?/);
      return match ? Number(match[0].replace(',', '.')) : NaN;
    })
    .filter((value) => Number.isFinite(value));
}

function settingsToApi(settings) {
  const delayPoints = settings.delayPointsPs?.length ? settings.delayPointsPs : null;
  return {
    point_count: delayPoints ? delayPoints.length : settings.pointCount,
    scan_start_ps: settings.scanStartPs,
    delay_step_ps: settings.delayStepPs,
    scan_span_ps: delayPoints
      ? delayPoints[delayPoints.length - 1] - delayPoints[0]
      : (settings.pointCount - 1) * settings.delayStepPs,
    pulses_per_point: settings.pulsesPerPoint,
    real_zero_ps: settings.realZeroPs,
    delay_points_ps: delayPoints,
  };
}

function hardwareConfigToApi(hardwareConfig, deviceConfig) {
  return {
    control_mode: hardwareConfig.controlMode || 'emulator',
    owis_aggregator_device: deviceConfig.delayLine.tangoDevice || 'manip/general/DS_OWIS_Aggregator',
    owis_backend_device: 'manip/general/DS_OWIS_PS90_IP',
    delay_line_axis: Number(deviceConfig.delayLine.axis) || 3,
    delay_line_label: deviceConfig.delayLine.hardwareLabel || 'Delay line long',
    delay_line_device_name: deviceConfig.delayLine.backendDeviceName || 'manip/V0/DLl1_V0',
    sample_stage_axis: Number(deviceConfig.sampleStage.axis) || 1,
    sample_stage_label: deviceConfig.sampleStage.hardwareLabel || 'Sample holder V0',
    sample_stage_device_name: deviceConfig.sampleStage.backendDeviceName || 'manip/V0/DLs_V0',
    andor_device: deviceConfig.spectrometer.tangoDevice || 'manip/CR/ANDOR_CCD1',
    dg645_device: 'manip/sync/DG645',
    daqmx_device: 'control/DAQ/DAQMX_1',
    daqmx_counter_channel: 'ELYSE Pulse Counter',
  };
}

function hardwareConfigFromApi(value) {
  const config = value || {};
  return {
    controlMode: config.controlMode || config.control_mode || 'emulator',
  };
}


export {
  PIXELS, STAGE_MIN_MM, STAGE_MAX_MM, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM,
  SAMPLE_STAGE_SPEED_MM_PER_SEC, DEFAULT_SAMPLE_POSITIONS_MM, MM_PER_PS, API_BASE,
  pumpProbeRequest, isTransientTangoError, compactHardwareError, fetchJsonWithRetry,
  linspace, gaussian, clamp, normalizeRange, indexesInRange, averageRows, averageColumns,
  nearestIndex, rangeAround, formatStageMm, formatBytes, displayPathTail, buildSyntheticRun,
  makeCurrentSpectra, DEFAULT_SETTINGS, DEFAULT_HARDWARE_CONFIG, DEFAULT_DEVICE_CONFIG,
  NETIO_POWER_CHANNELS, HARDWARE_TANGO_SERVERS, devicePath, normalizeNetioOutputs,
  generatedDelayPoints, activeDelayPoints, parseDelayPointsText, settingsToApi,
  hardwareConfigToApi, hardwareConfigFromApi,
};
