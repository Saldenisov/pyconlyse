import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import './css/PumpProbeV0.css';

const PIXELS = 512;
const STAGE_MIN_MM = -900;
const STAGE_MAX_MM = 100;
const SAMPLE_STAGE_MIN_MM = 0;
const SAMPLE_STAGE_MAX_MM = 78;
const SAMPLE_STAGE_SPEED_MM_PER_SEC = 1;
const DEFAULT_SAMPLE_POSITIONS_MM = Array.from({ length: 7 }, (_value, index) => index * 13);
const MM_PER_PS = 0.0749481145;
const API_BASE = '/api/pump-probe-v0';

async function pumpProbeRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    credentials: 'include',
    ...options,
  });
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
  let lastError = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(url, options);
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Request failed: ${response.status}`);
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (!isTransientTangoError(error.message) || attempt + 1 >= attempts) {
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

function PlotPanel({ title, children, className = '', actions = null }) {
  return (
    <section className={`pp-panel ${className}`.trim()}>
      <div className="pp-panel-title">
        <span>{title}</span>
        {actions ? <div className="pp-panel-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function SampleStageControl({
  positionMm,
  targetMm,
  positions,
  onMove,
  onStop,
  onMarkerMove,
  onOpenConfig,
}) {
  const [draftMm, setDraftMm] = useState(targetMm);
  const percent = ((positionMm - SAMPLE_STAGE_MIN_MM) / (SAMPLE_STAGE_MAX_MM - SAMPLE_STAGE_MIN_MM)) * 100;

  useEffect(() => {
    setDraftMm(targetMm);
  }, [targetMm]);

  const handleSetRealChange = (value) => {
    const setText = String(value).split('/')[0] || '';
    const parsed = Number(setText.replace(',', '.'));
    if (Number.isFinite(parsed)) {
      setDraftMm(clamp(parsed, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
    }
  };

  const moveTo = (value) => {
    const next = clamp(value, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM);
    setDraftMm(next);
    onMove(next);
  };

  return (
    <section
      className="pp-sample-stage"
      onContextMenu={(event) => {
        event.preventDefault();
        onOpenConfig('sampleStage');
      }}
    >
      <div
        className="pp-device-title"
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenConfig('sampleStage');
        }}
      >
        Sample translation stage
      </div>
      <div className="pp-sample-stage-row">
        <div className="pp-sample-rail">
          <div className="pp-sample-scale">
            <span>{SAMPLE_STAGE_MIN_MM}</span>
            <span>{SAMPLE_STAGE_MAX_MM} mm</span>
          </div>
          <div
            className="pp-sample-carriage"
            style={{ left: `${clamp(percent, 0, 100)}%` }}
          />
          {positions.map((marker, index) => (
            <button
              key={index}
              type="button"
              className="pp-sample-marker"
              style={{ left: `${((marker - SAMPLE_STAGE_MIN_MM) / (SAMPLE_STAGE_MAX_MM - SAMPLE_STAGE_MIN_MM)) * 100}%` }}
              title={`P${index + 1}: ${formatStageMm(marker)} mm`}
              onClick={() => moveTo(marker)}
              onContextMenu={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onMarkerMove(index, positionMm);
              }}
            />
          ))}
        </div>
        <label className="pp-sample-set">
          set/real mm
          <input
            type="text"
            value={`${formatStageMm(draftMm)}/${formatStageMm(positionMm)}`}
            onChange={(event) => handleSetRealChange(event.target.value)}
          />
        </label>
        <div className="pp-sample-move-stack">
          <button type="button" onClick={() => moveTo(draftMm)}>
            Move
          </button>
          <button type="button" onClick={onStop}>
            Stop
          </button>
        </div>
      </div>
      <div className="pp-sample-marker-row">
        {positions.map((marker, index) => (
          <button
            key={index}
            type="button"
            onClick={() => moveTo(marker)}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onMarkerMove(index, positionMm);
            }}
          >
            P{index + 1} {formatStageMm(marker)}
          </button>
        ))}
      </div>
    </section>
  );
}

function DeviceConfigModal({
  deviceKey,
  config,
  onChange,
  samplePositions,
  onSamplePositionsChange,
  onClose,
}) {
  if (!deviceKey) {
    return null;
  }
  const device = config[deviceKey];
  if (!device) {
    return null;
  }
  const setDeviceField = (field, value) => {
    onChange({
      ...config,
      [deviceKey]: {
        ...device,
        [field]: value,
      },
    });
  };

  return (
    <div className="pp-modal-backdrop" onClick={onClose}>
      <section className="pp-device-modal" onClick={(event) => event.stopPropagation()}>
        <div className="pp-device-modal-title">
          <span>{device.label}</span>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <div className="pp-device-status">
          <div><span>Tango server</span>{device.enabled ? 'EMULATOR ONLINE' : 'DISABLED'}</div>
          <div><span>Device state</span>{device.enabled ? 'ON / READY' : 'OFFLINE'}</div>
          {deviceKey === 'spectrometer' && (
            <div><span>Power</span>{device.powerOn ? 'NETIO ON' : 'NETIO OFF'}</div>
          )}
        </div>
        <label>
          {deviceKey === 'delayLine' || deviceKey === 'sampleStage' ? 'OWIS aggregator' : 'Tango device'}
          <input
            type="text"
            value={device.tangoDevice || ''}
            onChange={(event) => setDeviceField('tangoDevice', event.target.value)}
          />
        </label>
        {(deviceKey === 'delayLine' || deviceKey === 'sampleStage') && (
          <>
            <label>
              axis
              <input
                type="number"
                min="1"
                max="4"
                value={device.axis || 1}
                onChange={(event) => setDeviceField('axis', Number(event.target.value) || 1)}
              />
            </label>
            <label>
              axis device
              <input
                type="text"
                value={device.backendDeviceName || ''}
                onChange={(event) => setDeviceField('backendDeviceName', event.target.value)}
              />
            </label>
            <label>
              hardware label
              <input
                type="text"
                value={device.hardwareLabel || ''}
                onChange={(event) => setDeviceField('hardwareLabel', event.target.value)}
              />
            </label>
          </>
        )}
        {deviceKey === 'spectrometer' && (
          <label>
            NETIO power device
            <input
              type="text"
              value={device.netioDevice || ''}
              onChange={(event) => setDeviceField('netioDevice', event.target.value)}
            />
          </label>
        )}
        {deviceKey === 'sampleStage' && (
          <label>
            positions, mm
            <textarea
              value={samplePositions.join('\n')}
              onChange={(event) => {
                const nextPositions = parseDelayPointsText(event.target.value)
                  .map((value) => clamp(value, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
                if (nextPositions.length) {
                  onSamplePositionsChange(nextPositions);
                }
              }}
            />
          </label>
        )}
        <div className="pp-device-modal-actions">
          <button type="button" onClick={() => setDeviceField('enabled', !device.enabled)}>
            {device.enabled ? 'Disable' : 'Enable'}
          </button>
          {deviceKey === 'spectrometer' && (
            <button type="button" onClick={() => setDeviceField('powerOn', !device.powerOn)}>
              Power {device.powerOn ? 'off' : 'on'}
            </button>
          )}
          <button type="button">Reload config</button>
          <button type="button">Restart Tango</button>
        </div>
      </section>
    </div>
  );
}

function DataBrowserWindow({
  open,
  sampleName,
  root,
  path,
  parent,
  entries,
  loading,
  error,
  selectedPath,
  onClose,
  onRefresh,
  onOpenPath,
  onSelectPath,
  onLoadFile,
  onCreateFolder,
}) {
  if (!open) {
    return null;
  }

  return (
    <section className="pp-data-window">
      <div className="pp-device-modal-title">
        <span>Data</span>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      <div className="pp-data-paths">
        <div><span>root</span>{root || 'DATA_VD'}</div>
        <div><span>current</span>{path || root || 'DATA_VD'}</div>
        {selectedPath ? <div><span>selected</span>{selectedPath}</div> : null}
      </div>
      <div className="pp-data-actions">
        <button type="button" onClick={() => onOpenPath(root)} disabled={!root || loading}>Root</button>
        <button type="button" onClick={() => onOpenPath(parent)} disabled={!parent || loading}>Up</button>
        <button type="button" onClick={onRefresh} disabled={loading}>Refresh</button>
        <button
          type="button"
          onClick={() => onCreateFolder(sampleName)}
          disabled={!sampleName.trim() || loading}
        >
          New sample
        </button>
      </div>
      {error ? <div className="pp-hardware-error">{error}</div> : null}
      <div className="pp-data-list">
        {loading ? <div className="pp-data-empty">Loading...</div> : null}
        {!loading && entries.length === 0 ? <div className="pp-data-empty">Empty</div> : null}
        {!loading && entries.map((entry) => (
          <button
            type="button"
            key={entry.path}
            className={`pp-data-row ${entry.is_dir ? 'pp-data-row-dir' : ''}`}
            onDoubleClick={() => {
              if (entry.is_dir) {
                onOpenPath(entry.path);
              } else {
                onLoadFile(entry.path);
              }
            }}
            onClick={() => {
              onSelectPath(entry.path);
            }}
          >
            <strong>{entry.is_dir ? 'DIR' : 'FILE'}</strong>
            <span>{entry.name}</span>
            <small>{entry.is_file ? formatBytes(entry.size_bytes) : displayPathTail(entry.path)}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function HardwareModal({
  open,
  channels,
  devices,
  tangoServers,
  tangoStates,
  loading,
  tangoLoading,
  error,
  tangoError,
  onClose,
  onRefresh,
  onToggle,
  onBulkPower,
  onStartTango,
  onRestartTango,
}) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const channelState = (channel) => {
    const output = devices[channel.device]?.outputs?.find((item) => item.id === channel.outputId);
    return output ? Number(output.state) === 1 : null;
  };

  return (
    <div className="pp-modal-backdrop" onClick={onClose}>
      <section className="pp-hardware-modal" onClick={(event) => event.stopPropagation()}>
        <div className="pp-device-modal-title">
          <span>Hardware</span>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <div className="pp-hardware-content">
          <div className="pp-hardware-toolbar">
            <button type="button" onClick={() => onBulkPower(true)} disabled={loading}>
              Turn all necessary ON
            </button>
            <button type="button" onClick={() => onBulkPower(false)} disabled={loading}>
              Turn all OFF
            </button>
            <button type="button" onClick={onRefresh} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <div className="pp-hardware-error">{error}</div> : null}
          {tangoError ? <div className="pp-hardware-error">{tangoError}</div> : null}
          <div className="pp-hardware-columns">
          <div className="pp-hardware-column">
            <div className="pp-hardware-section-title">NETIO</div>
            <div className="pp-hardware-list">
              {channels.map((channel) => {
                const isOn = channelState(channel);
                return (
                  <button
                    key={channel.key}
                    type="button"
                    className={`pp-hardware-toggle ${isOn ? 'pp-hardware-toggle-on' : ''}`}
                    onClick={() => onToggle(channel, !isOn)}
                    disabled={loading || isOn === null}
                  >
                    <span>{channel.label}</span>
                    <small>{channel.device} / out {channel.outputId}</small>
                    <strong>{isOn === null ? 'UNKNOWN' : (isOn ? 'ON' : 'OFF')}</strong>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="pp-hardware-column">
            <div className="pp-hardware-section-title">Tango</div>
            <div className="pp-tango-list">
              {tangoServers.map((server) => {
                const status = server.device ? tangoStates[server.device] : { state: 'NOT CONFIGURED', ok: false };
                return (
                  <div key={server.key} className={`pp-tango-row ${status?.ok ? 'pp-tango-row-ok' : ''}`}>
                    <div>
                      <span>{server.label}</span>
                      <small>{server.device || server.note}</small>
                      {status?.error ? <em>{status.error}</em> : null}
                    </div>
                    <strong>{tangoLoading ? '...' : (status?.state || 'UNKNOWN')}</strong>
                    <button
                      type="button"
                      onClick={() => onStartTango(server)}
                      disabled={!server.device || tangoLoading}
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      onClick={() => onRestartTango(server)}
                      disabled={!server.device || tangoLoading}
                    >
                      Restart
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function PlotlyChart({
  data,
  layout,
  config,
  className,
  onInteraction,
  onSelected,
  onPointerEnter,
  onPointerLeave,
}) {
  const nodeRef = useRef(null);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }
    Plotly.react(node, data, layout, config).catch(() => undefined);
    return undefined;
  }, [data, layout, config]);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }

    const resize = () => {
      Plotly.Plots.resize(node);
    };
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      try {
        Plotly.purge(node);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, []);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node || !node.on) {
      return undefined;
    }
    const interactionEvents = [
      'plotly_hover',
      'plotly_unhover',
      'plotly_selecting',
      'plotly_selected',
      'plotly_relayouting',
      'plotly_relayout',
    ];
    if (onInteraction) {
      interactionEvents.forEach((eventName) => node.on(eventName, onInteraction));
    }
    if (onSelected) {
      node.on('plotly_selected', onSelected);
    }
    return () => {
      if (node.removeListener) {
        if (onInteraction) {
          interactionEvents.forEach((eventName) => {
            node.removeListener(eventName, onInteraction);
          });
        }
        if (onSelected) {
          node.removeListener('plotly_selected', onSelected);
        }
      }
    };
  }, [onInteraction, onSelected]);

  return (
    <div
      ref={nodeRef}
      className={className}
      onMouseEnter={onPointerEnter}
      onMouseLeave={onPointerLeave}
    />
  );
}

function HeatmapSelectorChart({
  data,
  layout,
  config,
  className,
  wavelengthRange,
  delayRange,
  onRangesChange,
  onInteraction,
  onPointerEnter,
  onPointerLeave,
}) {
  const nodeRef = useRef(null);
  const shellRef = useRef(null);
  const dragRef = useRef(null);
  const [metrics, setMetrics] = useState(null);

  const updateMetrics = useCallback(() => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    if (!shell || !node?._fullLayout) {
      return;
    }
    const rect = shell.getBoundingClientRect();
    const xAxis = node._fullLayout.xaxis;
    const yAxis = node._fullLayout.yaxis;
    setMetrics({
      xOffset: Number.isFinite(xAxis?._offset) ? xAxis._offset : 64,
      yOffset: Number.isFinite(yAxis?._offset) ? yAxis._offset : 20,
      innerWidth: Number.isFinite(xAxis?._length) ? xAxis._length : Math.max(1, rect.width - 142),
      innerHeight: Number.isFinite(yAxis?._length) ? yAxis._length : Math.max(1, rect.height - 68),
    });
  }, []);

  useEffect(() => {
    const node = nodeRef.current;
    if (!node) {
      return undefined;
    }
    Plotly.react(node, data, layout, config)
      .then(() => window.requestAnimationFrame(updateMetrics))
      .catch(() => undefined);
    return undefined;
  }, [data, layout, config, updateMetrics]);

  useEffect(() => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    if (!shell || !node) {
      return undefined;
    }
    const resize = () => {
      Plotly.Plots.resize(node);
      window.requestAnimationFrame(updateMetrics);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(shell);
    return () => {
      resizeObserver.disconnect();
      try {
        Plotly.purge(node);
      } catch (_error) {
        // Ignore Plotly teardown races.
      }
    };
  }, [updateMetrics]);

  const xToPixel = useCallback((value) => {
    const xAxis = nodeRef.current?._fullLayout?.xaxis;
    if (!metrics || !xAxis?.l2p) {
      return 0;
    }
    return metrics.xOffset + xAxis.l2p(value);
  }, [metrics]);

  const yToPixel = useCallback((value) => {
    const yAxis = nodeRef.current?._fullLayout?.yaxis;
    if (!metrics || !yAxis?.l2p) {
      return 0;
    }
    return metrics.yOffset + yAxis.l2p(value);
  }, [metrics]);

  const pointerToValues = useCallback((event) => {
    const shell = shellRef.current;
    const node = nodeRef.current;
    const xAxis = node?._fullLayout?.xaxis;
    const yAxis = node?._fullLayout?.yaxis;
    if (!shell || !metrics || !xAxis?.p2l || !yAxis?.p2l) {
      return null;
    }
    const rect = shell.getBoundingClientRect();
    const localX = clamp(event.clientX - rect.left, metrics.xOffset, metrics.xOffset + metrics.innerWidth);
    const localY = clamp(event.clientY - rect.top, metrics.yOffset, metrics.yOffset + metrics.innerHeight);
    return {
      x: xAxis.p2l(localX - metrics.xOffset),
      y: yAxis.p2l(localY - metrics.yOffset),
    };
  }, [metrics]);

  const normalizeAxisRange = useCallback((range, axis) => {
    const fullRange = nodeRef.current?._fullLayout?.[axis]?.range;
    const normalized = normalizeRange(range);
    if (!normalized || !Array.isArray(fullRange)) {
      return normalized;
    }
    const limits = normalizeRange(fullRange);
    const minWidth = Math.abs(limits[1] - limits[0]) / 200;
    let [start, end] = normalized;
    if (end - start < minWidth) {
      end = start + minWidth;
    }
    const width = end - start;
    if (start < limits[0]) {
      start = limits[0];
      end = start + width;
    }
    if (end > limits[1]) {
      end = limits[1];
      start = end - width;
    }
    return [clamp(start, limits[0], limits[1]), clamp(end, limits[0], limits[1])];
  }, []);

  const beginDrag = (event, axis, mode) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const point = pointerToValues(event);
    if (!point) {
      return;
    }
    dragRef.current = {
      axis,
      mode,
      point,
      wavelengthRange,
      delayRange,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    onInteraction?.();
  };

  const updateDrag = useCallback((event) => {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    const point = pointerToValues(event);
    if (!point) {
      return;
    }
    let nextWavelengthRange = wavelengthRange;
    let nextDelayRange = delayRange;
    if (drag.axis === 'x') {
      const delta = point.x - drag.point.x;
      if (drag.mode === 'start') {
        nextWavelengthRange = [point.x, drag.wavelengthRange[1]];
      } else if (drag.mode === 'end') {
        nextWavelengthRange = [drag.wavelengthRange[0], point.x];
      } else {
        nextWavelengthRange = [drag.wavelengthRange[0] + delta, drag.wavelengthRange[1] + delta];
      }
      nextWavelengthRange = normalizeAxisRange(nextWavelengthRange, 'xaxis');
    } else {
      const delta = point.y - drag.point.y;
      if (drag.mode === 'start') {
        nextDelayRange = [point.y, drag.delayRange[1]];
      } else if (drag.mode === 'end') {
        nextDelayRange = [drag.delayRange[0], point.y];
      } else {
        nextDelayRange = [drag.delayRange[0] + delta, drag.delayRange[1] + delta];
      }
      nextDelayRange = normalizeAxisRange(nextDelayRange, 'yaxis');
    }
    onRangesChange(nextWavelengthRange, nextDelayRange);
    onInteraction?.();
  }, [delayRange, normalizeAxisRange, onInteraction, onRangesChange, pointerToValues, wavelengthRange]);

  const finishDrag = useCallback(() => {
    dragRef.current = null;
  }, []);

  useEffect(() => {
    window.addEventListener('pointermove', updateDrag);
    window.addEventListener('pointerup', finishDrag);
    window.addEventListener('pointercancel', finishDrag);
    return () => {
      window.removeEventListener('pointermove', updateDrag);
      window.removeEventListener('pointerup', finishDrag);
      window.removeEventListener('pointercancel', finishDrag);
    };
  }, [finishDrag, updateDrag]);

  const regionStyle = useMemo(() => {
    if (!metrics || !wavelengthRange || !delayRange) {
      return null;
    }
    const x0 = xToPixel(wavelengthRange[0]);
    const x1 = xToPixel(wavelengthRange[1]);
    const y0 = yToPixel(delayRange[0]);
    const y1 = yToPixel(delayRange[1]);
    return {
      x: {
        left: Math.min(x0, x1),
        top: metrics.yOffset,
        width: Math.max(4, Math.abs(x1 - x0)),
        height: metrics.innerHeight,
      },
      y: {
        left: metrics.xOffset,
        top: Math.min(y0, y1),
        width: metrics.innerWidth,
        height: Math.max(4, Math.abs(y1 - y0)),
      },
    };
  }, [delayRange, metrics, wavelengthRange, xToPixel, yToPixel]);

  return (
    <div
      className={`pp-selector-shell ${className || ''}`.trim()}
      ref={shellRef}
      onMouseEnter={onPointerEnter}
      onMouseLeave={onPointerLeave}
    >
      <div ref={nodeRef} className="pp-selector-plot" />
      <div className="pp-selector-overlay">
        {regionStyle && (
          <>
            <div
              className="pp-selector-region pp-selector-region-x"
              style={{
                left: `${regionStyle.x.left}px`,
                top: `${regionStyle.x.top}px`,
                width: `${regionStyle.x.width}px`,
                height: `${regionStyle.x.height}px`,
              }}
              onPointerDown={(event) => beginDrag(event, 'x', 'move')}
            >
              <span
                className="pp-selector-handle pp-selector-handle-start"
                onPointerDown={(event) => beginDrag(event, 'x', 'start')}
              />
              <span
                className="pp-selector-handle pp-selector-handle-end"
                onPointerDown={(event) => beginDrag(event, 'x', 'end')}
              />
            </div>
            <div
              className="pp-selector-region pp-selector-region-y"
              style={{
                left: `${regionStyle.y.left}px`,
                top: `${regionStyle.y.top}px`,
                width: `${regionStyle.y.width}px`,
                height: `${regionStyle.y.height}px`,
              }}
              onPointerDown={(event) => beginDrag(event, 'y', 'move')}
            >
              <span
                className="pp-selector-handle pp-selector-handle-start"
                onPointerDown={(event) => beginDrag(event, 'y', 'start')}
              />
              <span
                className="pp-selector-handle pp-selector-handle-end"
                onPointerDown={(event) => beginDrag(event, 'y', 'end')}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StageControl({
  positionMm,
  setPositionMm,
  stepPs,
  zeroMm,
  onPositionChange,
  onStop,
  onStepChange,
  onZeroChange,
  onOpenConfig,
}) {
  const railRef = useRef(null);
  const [draftPositionMm, setDraftPositionMm] = useState(positionMm);
  const [hasPendingMove, setHasPendingMove] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const carriagePercent = ((STAGE_MAX_MM - draftPositionMm) / (STAGE_MAX_MM - STAGE_MIN_MM)) * 100;
  const stageMoving = Math.abs(setPositionMm - positionMm) > 0.005;

  useEffect(() => {
    if (!hasPendingMove && !isDragging) {
      setDraftPositionMm(setPositionMm);
    }
  }, [hasPendingMove, isDragging, setPositionMm]);

  const setDraftPosition = useCallback((value) => {
    setDraftPositionMm(clamp(value, STAGE_MIN_MM, STAGE_MAX_MM));
    setHasPendingMove(true);
  }, []);

  const moveByStep = (direction) => {
    const deltaMm = -Number(stepPs || 0) * MM_PER_PS * direction;
    setDraftPosition(draftPositionMm + deltaMm);
  };
  const pointerToPosition = (event) => {
    const rail = railRef.current;
    if (!rail) {
      return null;
    }
    const rect = rail.getBoundingClientRect();
    const ratio = clamp((event.clientY - rect.top) / Math.max(1, rect.height), 0, 1);
    return STAGE_MAX_MM - ratio * (STAGE_MAX_MM - STAGE_MIN_MM);
  };
  const beginDrag = (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const nextPosition = pointerToPosition(event);
    if (nextPosition !== null) {
      setDraftPosition(nextPosition);
      setIsDragging(true);
    }
  };
  const updateDrag = (event) => {
    if (!isDragging) {
      return;
    }
    const nextPosition = pointerToPosition(event);
    if (nextPosition !== null) {
      setDraftPosition(nextPosition);
    }
  };
  const finishDrag = () => {
    setIsDragging(false);
  };
  const handleDlFieldChange = (value) => {
    const setText = String(value).split('/')[0] || '';
    const parsed = Number(setText.replace(',', '.'));
    if (Number.isFinite(parsed)) {
      setDraftPosition(parsed);
    }
  };
  const acceptMove = () => {
    onPositionChange(draftPositionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };
  const rejectMove = () => {
    setDraftPositionMm(setPositionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };
  const stopMove = () => {
    onStop();
    setDraftPositionMm(positionMm);
    setHasPendingMove(false);
    setIsDragging(false);
  };

  return (
    <section
      className="pp-stage-panel"
      onContextMenu={(event) => {
        event.preventDefault();
        onOpenConfig('delayLine');
      }}
    >
      <div
        className="pp-panel-title pp-device-title"
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenConfig('delayLine');
        }}
      >
        Delay line
      </div>
      <div className="pp-stage-readouts">
        <label>
          DL, set/real mm
          <input
            type="text"
            value={`${formatStageMm(draftPositionMm)}/${formatStageMm(positionMm)}`}
            onChange={(event) => handleDlFieldChange(event.target.value)}
          />
        </label>
        <label>
          step, ps
          <input
            type="number"
            value={stepPs}
            step="0.1"
            onChange={(event) => onStepChange(Number(event.target.value) || 0)}
          />
        </label>
        <label>
          zero, mm
          <input
            type="number"
            value={zeroMm}
            step="0.1"
            onChange={(event) => onZeroChange(Number(event.target.value) || 0)}
          />
        </label>
      </div>
      <div className="pp-stage">
        <div
          className="pp-stage-rail"
          ref={railRef}
          onPointerMove={updateDrag}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          {Array.from({ length: 17 }, (_value, index) => (
            <span key={index} className="pp-stage-bolt" style={{ top: `${5 + index * 5.6}%` }} />
          ))}
          <div
            className={`pp-stage-carriage ${hasPendingMove ? 'pp-stage-carriage-pending' : ''}`.trim()}
            style={{ top: `${clamp(carriagePercent, 0, 100)}%` }}
            onPointerDown={beginDrag}
            onPointerMove={updateDrag}
            onPointerUp={finishDrag}
            onPointerCancel={finishDrag}
          >
            <div className="pp-stage-mirror pp-stage-mirror-left" />
            <div className="pp-stage-mirror pp-stage-mirror-right" />
            <div className="pp-stage-beam pp-stage-beam-a" />
            <div className="pp-stage-beam pp-stage-beam-b" />
          </div>
        </div>
      </div>
      <div className="pp-stage-actions">
        <button type="button" onClick={() => moveByStep(-1)}>Move -</button>
        <button type="button" onClick={() => moveByStep(1)}>Move +</button>
        <button
          type="button"
          className="pp-stage-accept"
          disabled={!hasPendingMove}
          onClick={acceptMove}
        >
          Accept
        </button>
        <button
          type="button"
          className="pp-stage-reject"
          disabled={!hasPendingMove}
          onClick={rejectMove}
        >
          Reject
        </button>
        <button
          type="button"
          className="pp-stage-stop"
          disabled={!hasPendingMove && !stageMoving}
          onClick={stopMove}
        >
          Stop DL
        </button>
      </div>
      <div className="pp-stage-scale">
        <span>{STAGE_MAX_MM} mm</span>
        <span>{STAGE_MIN_MM} mm</span>
      </div>
    </section>
  );
}

function SettingsPanel({
  settings,
  hardwareConfig,
  onSettingChange,
  onHardwareModeChange,
  delayStats,
  delayPreviewData,
  delayPreviewLayout,
  delayPreviewConfig,
  onDelayPointsLoad,
  onConfigLoad,
  onConfigSave,
}) {
  const delayFileInputRef = useRef(null);
  const configFileInputRef = useRef(null);

  const readTextFile = async (event, handler) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    const text = await file.text();
    handler(text);
  };

  return (
    <section className="pp-settings-panel">
      <div className="pp-panel-title">Scan settings</div>
      <div className="pp-settings-grid">
        <label>
          OZ, ps
          <input
            type="number"
            value={settings.scanStartPs}
            onChange={(event) => onSettingChange('scanStartPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          step, ps
          <input
            type="number"
            step="0.001"
            value={settings.delayStepPs}
            disabled={settings.delayMode === 'custom'}
            onChange={(event) => onSettingChange('delayStepPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          # points
          <input
            type="number"
            min="2"
            max="400"
            value={settings.pointCount}
            disabled={settings.delayMode === 'custom'}
            onChange={(event) => onSettingChange('pointCount', clamp(Number(event.target.value) || 2, 2, 400))}
          />
        </label>
        <label>
          Kinetic, ps
          <output>{delayStats.kineticPs.toFixed(3)}</output>
        </label>
        <label>
          Total, ps
          <output>{delayStats.totalPs.toFixed(3)}</output>
        </label>
        <label>
          Real zero, ps
          <input
            type="number"
            value={settings.realZeroPs}
            onChange={(event) => onSettingChange('realZeroPs', Number(event.target.value) || 0)}
          />
        </label>
        <label>
          Pulses / point
          <input
            type="number"
            min="1"
            value={settings.pulsesPerPoint}
            onChange={(event) => onSettingChange('pulsesPerPoint', Number(event.target.value) || 1)}
          />
        </label>
        <label>
          mode
          <output>{settings.delayMode}</output>
        </label>
        <label>
          control
          <select
            value={hardwareConfig.controlMode}
            onChange={(event) => onHardwareModeChange(event.target.value)}
          >
            <option value="emulator">emulator</option>
            <option value="tango">tango</option>
          </select>
        </label>
      </div>
      <div className="pp-settings-actions">
        <button type="button" onClick={() => delayFileInputRef.current?.click()}>
          Load delays TXT
        </button>
        <button
          type="button"
          onClick={() => onSettingChange('delayPointsPs', null)}
          disabled={settings.delayMode !== 'custom'}
        >
          Generated
        </button>
        <button type="button" onClick={() => configFileInputRef.current?.click()}>
          Load config
        </button>
        <button type="button" onClick={onConfigSave}>
          Save config
        </button>
        <input
          ref={delayFileInputRef}
          type="file"
          accept=".txt,.dat,.csv"
          className="pp-hidden-file"
          onChange={(event) => readTextFile(event, onDelayPointsLoad)}
        />
        <input
          ref={configFileInputRef}
          type="file"
          accept=".json,.txt"
          className="pp-hidden-file"
          onChange={(event) => readTextFile(event, onConfigLoad)}
        />
      </div>
      <div className="pp-delay-preview">
        <PlotlyChart
          className="pp-plot pp-plot-delay-preview"
          data={delayPreviewData}
          layout={delayPreviewLayout}
          config={delayPreviewConfig}
        />
      </div>
    </section>
  );
}

function PumpProbeV0() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [hardwareConfig, setHardwareConfig] = useState(DEFAULT_HARDWARE_CONFIG);
  const [deviceConfig, setDeviceConfig] = useState(DEFAULT_DEVICE_CONFIG);
  const [deviceConfigKey, setDeviceConfigKey] = useState(null);
  const [samplePositionMm, setSamplePositionMm] = useState(0);
  const [sampleTargetMm, setSampleTargetMm] = useState(0);
  const [samplePositionsMm, setSamplePositionsMm] = useState(DEFAULT_SAMPLE_POSITIONS_MM);
  const plannedDelays = useMemo(() => activeDelayPoints(settings), [settings]);
  const fallbackRun = useMemo(() => buildSyntheticRun(plannedDelays.length), [plannedDelays.length]);
  const [backendState, setBackendState] = useState(null);
  const [backendError, setBackendError] = useState('');
  const [localIndex, setLocalIndex] = useState(0);
  const localRunning = false;
  const [localPositionMm, setLocalPositionMm] = useState(0);
  const [stepPs, setStepPs] = useState(1);
  const [zeroMm, setZeroMm] = useState(0);
  const [localElectronState, setLocalElectronState] = useState('OFF');
  const [localFaradayClosed, setLocalFaradayClosed] = useState(true);
  const [selectedWavelengthRange, setSelectedWavelengthRange] = useState(null);
  const [selectedDelayRange, setSelectedDelayRange] = useState(null);
  const [plotRevision, setPlotRevision] = useState(0);
  const [netioOpen, setNetioOpen] = useState(false);
  const [netioDevices, setNetioDevices] = useState({});
  const [netioLoading, setNetioLoading] = useState(false);
  const [netioError, setNetioError] = useState('');
  const [tangoStates, setTangoStates] = useState({});
  const [tangoLoading, setTangoLoading] = useState(false);
  const [tangoError, setTangoError] = useState('');
  const [hardwareInitStatus, setHardwareInitStatus] = useState(null);
  const [hardwareInitLoading, setHardwareInitLoading] = useState(false);
  const [sampleName, setSampleName] = useState('');
  const [dataBrowserOpen, setDataBrowserOpen] = useState(false);
  const [dataRoot, setDataRoot] = useState('');
  const [dataPath, setDataPath] = useState('');
  const [dataParent, setDataParent] = useState('');
  const [dataEntries, setDataEntries] = useState([]);
  const [dataSelectedPath, setDataSelectedPath] = useState('');
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState('');
  const [loadedOdDataset, setLoadedOdDataset] = useState(null);
  const [rawDataset, setRawDataset] = useState(null);
  const [spectraViewMode, setSpectraViewMode] = useState('current');
  const [savedKinetics, setSavedKinetics] = useState([]);
  const [kineticCounter, setKineticCounter] = useState(1);
  const [savedOdSpectra, setSavedOdSpectra] = useState([]);
  const [odSpectrumCounter, setOdSpectrumCounter] = useState(1);
  const refreshRequestRef = useRef({ inFlight: false, controller: null });

  const closeHardwareModal = useCallback(() => {
    setNetioOpen(false);
    setNetioError('');
    setTangoError('');
  }, []);

  const refreshState = useCallback(async () => {
    if (refreshRequestRef.current.inFlight) {
      return;
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 2000);
    refreshRequestRef.current = { inFlight: true, controller };
    try {
      const state = await pumpProbeRequest('/state', { signal: controller.signal });
      setBackendState(state);
      setBackendError('');
    } catch (error) {
      if (error.name !== 'AbortError') {
        setBackendError(error.message);
      }
    } finally {
      window.clearTimeout(timeoutId);
      if (refreshRequestRef.current.controller === controller) {
        refreshRequestRef.current = { inFlight: false, controller: null };
      }
    }
  }, []);

  const postAndRefresh = useCallback(async (path, payload = {}) => {
    try {
      const state = await pumpProbeRequest(path, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setBackendState(state);
      setBackendError('');
      return state;
    } catch (error) {
      setBackendError(error.message);
      return null;
    }
  }, []);

  const runHardwareInitialization = useCallback(async (fix = true) => {
    setHardwareInitLoading(true);
    try {
      const status = await pumpProbeRequest(fix ? '/hardware/initialize' : '/hardware/preflight', {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setHardwareInitStatus(status);
      setBackendError(status.success ? '' : (status.recommendation || status.message || 'Hardware initialization failed'));
      await refreshState();
      return status;
    } catch (error) {
      setHardwareInitStatus({ success: false, message: error.message, checks: [] });
      setBackendError(error.message);
      return null;
    } finally {
      setHardwareInitLoading(false);
    }
  }, [refreshState]);

  const loadNetioOutputs = useCallback(async () => {
    const deviceNames = [...new Set(NETIO_POWER_CHANNELS.map((channel) => channel.device))];
    setNetioLoading(true);
    setNetioError('');
    const entries = [];
    const errors = [];
    await Promise.all(deviceNames.map(async (deviceName) => {
      try {
        const payload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });
        entries.push([deviceName, {
          state: payload.state,
          outputs: normalizeNetioOutputs(payload.outputs),
        }]);
      } catch (error) {
        errors.push(`${deviceName}: ${error.message}`);
      }
    }));
    if (entries.length) {
      setNetioDevices((current) => ({ ...current, ...Object.fromEntries(entries) }));
    }
    setNetioError(compactHardwareError(errors));
    setNetioLoading(false);
  }, []);

  const toggleNetioChannel = useCallback(async (channel, enabled) => {
    const currentDevice = netioDevices[channel.device];
    if (!currentDevice?.outputs?.length) {
      setNetioError(`No output table for ${channel.device}`);
      return;
    }

    const nextStates = currentDevice.outputs.map((output) => (
      output.id === channel.outputId ? (enabled ? 1 : 0) : output.state
    ));

    setNetioLoading(true);
    setNetioError('');
    try {
      await fetchJsonWithRetry(`/api/device/${devicePath(channel.device)}/command/set_channels_states`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ args: nextStates }),
      });

      const verifyPayload = await fetchJsonWithRetry(`/api/device/${devicePath(channel.device)}/pdu/outputs`, {
        credentials: 'include',
      });
      setNetioDevices((current) => ({
        ...current,
        [channel.device]: {
          state: verifyPayload.state,
          outputs: normalizeNetioOutputs(verifyPayload.outputs),
        },
      }));
    } catch (error) {
      setNetioError(error.message);
    } finally {
      setNetioLoading(false);
    }
  }, [netioDevices]);

  const setNecessaryHardwarePower = useCallback(async (enabled) => {
    const deviceNames = [...new Set(NETIO_POWER_CHANNELS.map((channel) => channel.device))];
    setNetioLoading(true);
    setNetioError('');
    const entries = [];
    const errors = [];
    await Promise.all(deviceNames.map(async (deviceName) => {
      try {
        const readPayload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });

        const targetOutputIds = new Set(
          NETIO_POWER_CHANNELS
            .filter((channel) => channel.device === deviceName)
            .map((channel) => channel.outputId)
        );
        const currentOutputs = normalizeNetioOutputs(readPayload.outputs);
        const nextStates = currentOutputs.map((output) => (
          targetOutputIds.has(output.id) ? (enabled ? 1 : 0) : output.state
        ));

        await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/command/set_channels_states`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ args: nextStates }),
        });

        const verifyPayload = await fetchJsonWithRetry(`/api/device/${devicePath(deviceName)}/pdu/outputs`, {
          credentials: 'include',
        });
        entries.push([deviceName, {
          state: verifyPayload.state,
          outputs: normalizeNetioOutputs(verifyPayload.outputs),
        }]);
      } catch (error) {
        errors.push(`${deviceName}: ${error.message}`);
      }
    }));
    if (entries.length) {
      setNetioDevices((current) => ({ ...current, ...Object.fromEntries(entries) }));
    }
    setNetioError(compactHardwareError(errors));
    setNetioLoading(false);
  }, []);

  const loadTangoStates = useCallback(async () => {
    const servers = HARDWARE_TANGO_SERVERS.filter((server) => server.device);
    setTangoLoading(true);
    setTangoError('');
    try {
      const entries = await Promise.all(servers.map(async (server) => {
        try {
          const payload = await fetchJsonWithRetry(`/api/device/${devicePath(server.device)}/state`, {
            credentials: 'include',
          });
          return [server.device, {
            ok: true,
            state: String(payload.state || 'UNKNOWN').replace(/^DevState\./, ''),
            status: payload.status || '',
          }];
        } catch (error) {
          return [server.device, {
            ok: false,
            state: 'OFFLINE',
            error: error.message,
          }];
        }
      }));
      setTangoStates(Object.fromEntries(entries));
    } catch (error) {
      setTangoError(error.message);
    } finally {
      setTangoLoading(false);
    }
  }, []);

  const controlTangoServer = useCallback(async (server, action) => {
    if (!server.device) {
      return;
    }
    setTangoLoading(true);
    setTangoError('');
    try {
      const response = await fetch('/api/server/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ action, device_name: server.device }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to ${action} ${server.label}`);
      }
      await loadTangoStates();
    } catch (error) {
      setTangoError(error.message);
    } finally {
      setTangoLoading(false);
    }
  }, [loadTangoStates]);

  const loadDataPath = useCallback(async (nextPath = '') => {
    setDataLoading(true);
    setDataError('');
    try {
      const query = nextPath ? `?path=${encodeURIComponent(nextPath)}` : '';
      const response = await fetch(`${API_BASE}/data/list${query}`, {
        credentials: 'include',
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to list data path (${response.status})`);
      }
      setDataRoot(payload.root || '');
      setDataPath(payload.path || payload.root || '');
      setDataParent(payload.parent || payload.root || '');
      setDataEntries(payload.entries || []);
      if (!dataSelectedPath && payload.path) {
        setDataSelectedPath(payload.path);
      }
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, [dataSelectedPath]);

  const createSampleFolder = useCallback(async (name) => {
    const folderName = String(name || '').trim();
    if (!folderName) {
      return;
    }
    setDataLoading(true);
    setDataError('');
    try {
      const response = await fetch(`${API_BASE}/data/folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ parent: dataPath || dataRoot, name: folderName }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to create folder (${response.status})`);
      }
      setDataSelectedPath(payload.path);
      await loadDataPath(payload.path);
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, [dataPath, dataRoot, loadDataPath]);

  const loadDataFile = useCallback(async (filePath) => {
    if (!filePath) {
      return;
    }
    setDataLoading(true);
    setDataError('');
    try {
      const response = await fetch(`${API_BASE}/data/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ path: filePath }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success === false) {
        throw new Error(payload.error || `Failed to load data file (${response.status})`);
      }
      setDataSelectedPath(payload.path || filePath);
      if (payload.kind === 'od') {
        setLoadedOdDataset(payload);
        setSelectedWavelengthRange(null);
        setSelectedDelayRange(null);
        setPlotRevision((value) => value + 1);
      } else if (payload.kind === 'raw') {
        setRawDataset(payload);
        setSpectraViewMode('raw');
      }
    } catch (error) {
      setDataError(error.message);
    } finally {
      setDataLoading(false);
    }
  }, []);

  const handleSettingChange = useCallback((key, value) => {
    setSettings((current) => {
      if (key === 'delayPointsPs') {
        if (!value?.length) {
          return {
            ...current,
            delayPointsPs: null,
            delayMode: 'generated',
          };
        }
        return {
          ...current,
          delayPointsPs: value,
          delayMode: 'custom',
          pointCount: value.length,
          scanStartPs: value[0],
          delayStepPs: value.length > 1 ? value[1] - value[0] : current.delayStepPs,
        };
      }
      const next = { ...current, [key]: value };
      if (key === 'pointCount') {
        next.pointCount = clamp(Number(value) || 2, 2, 400);
      }
      if (key === 'scanStartPs' || key === 'delayStepPs' || key === 'pointCount') {
        next.delayPointsPs = null;
        next.delayMode = 'generated';
      }
      return next;
    });
    if (key === 'pointCount') {
      setLocalIndex((index) => Math.min(index, Number(value) - 1));
    }
  }, []);

  const handleDelayPointsLoad = useCallback((text) => {
    const points = parseDelayPointsText(text).slice(0, 400);
    if (points.length >= 2) {
      handleSettingChange('delayPointsPs', points);
    } else {
      setBackendError('Delay TXT must contain at least 2 numeric rows.');
    }
  }, [handleSettingChange]);

  const handleHardwareModeChange = useCallback((mode) => {
    setHardwareConfig((current) => ({
      ...current,
      controlMode: mode === 'tango' ? 'tango' : 'emulator',
    }));
  }, []);

  const handleConfigLoad = useCallback((text) => {
    try {
      const parsed = JSON.parse(text);
      const loadedSettings = parsed.settings || parsed;
      setSettings((current) => ({
        ...current,
        ...loadedSettings,
        delayMode: loadedSettings.delayPointsPs?.length ? 'custom' : 'generated',
      }));
      if (parsed.devices) {
        setDeviceConfig((current) => ({ ...current, ...parsed.devices }));
      }
      if (parsed.hardwareConfig || parsed.hardware) {
        setHardwareConfig((current) => ({
          ...current,
          ...hardwareConfigFromApi(parsed.hardwareConfig || parsed.hardware),
        }));
      }
      if (parsed.sampleStage) {
        setSamplePositionMm(clamp(Number(parsed.sampleStage.positionMm) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
        setSampleTargetMm(clamp(Number(parsed.sampleStage.targetMm) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM));
        const loadedPositions = parsed.sampleStage.positionsMm || parsed.sampleStage.markersMm;
        if (Array.isArray(loadedPositions)) {
          setSamplePositionsMm(loadedPositions.map((value) => (
            clamp(Number(value) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM)
          )));
        }
      }
      if (parsed.data) {
        setSampleName(String(parsed.data.sampleName || ''));
        setDataSelectedPath(String(parsed.data.selectedPath || ''));
      }
      setBackendError('');
    } catch (error) {
      setBackendError(`Config load failed: ${error.message}`);
    }
  }, []);

  const handleConfigSave = useCallback(() => {
    const payload = {
      version: 1,
      experiment: 'pump-probe-v0',
      settings,
      hardwareConfig,
      hardware: hardwareConfigToApi(hardwareConfig, deviceConfig),
      devices: deviceConfig,
      sampleStage: {
        positionMm: samplePositionMm,
        targetMm: sampleTargetMm,
        positionsMm: samplePositionsMm,
      },
      data: {
        sampleName,
        root: dataRoot,
        selectedPath: dataSelectedPath,
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'pump-probe-v0-config.json';
    anchor.click();
    URL.revokeObjectURL(url);
  }, [dataRoot, dataSelectedPath, deviceConfig, hardwareConfig, sampleName, samplePositionMm, samplePositionsMm, sampleTargetMm, settings]);

  const moveSampleStage = useCallback((positionMmValue) => {
    const next = clamp(Number(positionMmValue) || 0, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM);
    setSampleTargetMm(next);
    if (hardwareConfig.controlMode === 'tango') {
      setBackendState((current) => (current ? {
        ...current,
        sample_set_position_mm: next,
        sample_stage_moving: true,
      } : current));
      postAndRefresh('/sample-stage/move', { position_mm: next });
    }
  }, [hardwareConfig.controlMode, postAndRefresh]);

  const setSampleMarker = useCallback((index, positionMmValue) => {
    setSamplePositionsMm((current) => current.map((marker, markerIndex) => (
      markerIndex === index ? clamp(positionMmValue, SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM) : marker
    )));
  }, []);

  const stopSampleStage = useCallback(() => {
    if (hardwareConfig.controlMode === 'tango') {
      postAndRefresh('/sample-stage/stop');
      return;
    }
    setSampleTargetMm(samplePositionMm);
  }, [hardwareConfig.controlMode, postAndRefresh, samplePositionMm]);

  useEffect(() => {
    if (hardwareConfig.controlMode === 'tango') {
      return undefined;
    }
    let lastTime = performance.now();
    const timerId = window.setInterval(() => {
      const now = performance.now();
      const elapsedSec = Math.max(0, (now - lastTime) / 1000);
      lastTime = now;
      setSamplePositionMm((current) => {
        const distance = sampleTargetMm - current;
        const maxStep = SAMPLE_STAGE_SPEED_MM_PER_SEC * elapsedSec;
        if (Math.abs(distance) <= maxStep) {
          return sampleTargetMm;
        }
        return current + Math.sign(distance) * maxStep;
      });
    }, 50);
    return () => window.clearInterval(timerId);
  }, [hardwareConfig.controlMode, sampleTargetMm]);

  useEffect(() => {
    refreshState();
    const timerId = window.setInterval(refreshState, 250);
    return () => {
      window.clearInterval(timerId);
      refreshRequestRef.current.controller?.abort();
    };
  }, [refreshState]);

  useEffect(() => {
    postAndRefresh('/config', {
      ...settingsToApi(settings),
      hardware_config: hardwareConfigToApi(hardwareConfig, deviceConfig),
    });
  }, [settings, hardwareConfig, deviceConfig, postAndRefresh]);

  useEffect(() => {
    if (netioOpen) {
      loadNetioOutputs();
      loadTangoStates();
    }
  }, [loadNetioOutputs, loadTangoStates, netioOpen]);

  useEffect(() => {
    if (dataBrowserOpen && !dataPath && !dataLoading) {
      loadDataPath(dataSelectedPath);
    }
  }, [dataBrowserOpen, dataLoading, dataPath, dataSelectedPath, loadDataPath]);

  const fileOdLoaded = loadedOdDataset?.kind === 'od';
  const wavelengths = fileOdLoaded ? loadedOdDataset.wavelengths : (backendState?.wavelengths || fallbackRun.wavelengths);
  const delays = fileOdLoaded ? loadedOdDataset.delays : (backendState?.delays || fallbackRun.delays);
  const heatmap = fileOdLoaded ? loadedOdDataset.heatmap : (backendState?.heatmap || fallbackRun.heatmap);
  const liveOd = backendState?.live_od || null;
  const currentIndex = backendState?.current_index ?? localIndex;
  const activeCurrentIndex = clamp(currentIndex, 0, Math.max(0, delays.length - 1));
  const running = backendState?.running ?? localRunning;
  const realTime = backendState?.real_time ?? false;
  const faradayClosed = backendState?.faraday_closed ?? localFaradayClosed;
  const electronState = backendState?.electron_state || localElectronState;
  const positionMm = backendState?.position_mm ?? localPositionMm;
  const setPositionMm = backendState?.set_position_mm ?? localPositionMm;
  const activeControlMode = hardwareConfig.controlMode || backendState?.control_mode || 'emulator';
  const daqCounter = backendState?.daq_counter || {};
  const counterActive = Boolean(daqCounter.active);
  const counterRateHz = Number(daqCounter.rate_hz || 0);
  const hardwareChecks = hardwareInitStatus?.checks || [];
  const failedHardwareChecks = hardwareChecks.filter((check) => !check.ok);
  const sampleDisplayPositionMm = activeControlMode === 'tango'
    ? (backendState?.sample_position_mm ?? samplePositionMm)
    : samplePositionMm;
  const sampleDisplayTargetMm = activeControlMode === 'tango'
    ? (backendState?.sample_set_position_mm ?? sampleTargetMm)
    : sampleTargetMm;
  const netioAnyOn = NETIO_POWER_CHANNELS.some((channel) => (
    netioDevices[channel.device]?.outputs?.some((output) => (
      output.id === channel.outputId && Number(output.state) === 1
    ))
  ));
  const delayStats = useMemo(() => {
    const finiteDelays = delays.filter((value) => Number.isFinite(value));
    if (!finiteDelays.length) {
      return { pointCount: 0, kineticPs: 0, totalPs: 0 };
    }
    const minDelay = Math.min(...finiteDelays);
    const maxDelay = Math.max(...finiteDelays);
    return {
      pointCount: finiteDelays.length,
      kineticPs: Math.max(0, maxDelay),
      totalPs: maxDelay - minDelay,
    };
  }, [delays]);

  useEffect(() => {
    if (backendState || !localRunning) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      setLocalIndex((value) => (value + 1) % delays.length);
      setLocalElectronState(localFaradayClosed ? 'OFF' : 'ON');
    }, 200);
    return () => window.clearInterval(timerId);
  }, [backendState, localRunning, localFaradayClosed, delays.length]);

  useEffect(() => {
    if (backendState) {
      return;
    }
    const delayPs = delays[currentIndex] || 0;
    setLocalPositionMm(clamp(-(delayPs + settings.realZeroPs) * MM_PER_PS, STAGE_MIN_MM, STAGE_MAX_MM));
  }, [backendState, currentIndex, delays, settings.realZeroPs]);

  const spectra = useMemo(
    () => backendState?.spectra || makeCurrentSpectra(wavelengths, activeCurrentIndex, electronState),
    [backendState, wavelengths, activeCurrentIndex, electronState]
  );

  const completedHeatmap = backendState || fileOdLoaded
    ? heatmap
    : heatmap.map((row, index) => (
      index <= activeCurrentIndex ? row : row.map(() => null)
    ));
  const kineticWavelength = 445;
  const kineticIndex = wavelengths.reduce((bestIndex, wavelength, index) => (
    Math.abs(wavelength - kineticWavelength) < Math.abs(wavelengths[bestIndex] - kineticWavelength)
      ? index
      : bestIndex
  ), 0);
  const delayStep = Math.abs((delays[1] ?? delays[0] + 1) - (delays[0] ?? 0)) || 1;
  const defaultWavelengthRange = rangeAround(wavelengths, wavelengths[kineticIndex], 10);
  const defaultDelayRange = rangeAround(delays, delays[activeCurrentIndex] || delays[0] || 0, delayStep);
  const activeWavelengthRange = selectedWavelengthRange || defaultWavelengthRange;
  const activeDelayRange = selectedDelayRange || defaultDelayRange;
  const selectedWavelengthIndexes = indexesInRange(wavelengths, activeWavelengthRange);
  const selectedDelayIndexes = indexesInRange(delays, activeDelayRange);
  const safeWavelengthIndexes = selectedWavelengthIndexes.length
    ? selectedWavelengthIndexes
    : [kineticIndex];
  const safeDelayIndexes = selectedDelayIndexes.length
    ? selectedDelayIndexes
    : [activeCurrentIndex];
  const selectedRowsOd = averageRows(heatmap, safeDelayIndexes);
  const selectedRowsHaveData = selectedRowsOd.some((value) => value !== null && value !== undefined);
  const selectedOd = (selectedRowsHaveData ? selectedRowsOd : (liveOd || selectedRowsOd))
    .map((value) => value ?? 0);
  const kineticTrace = averageColumns(heatmap, safeWavelengthIndexes);
  const selectedWavelengthLabel = `${activeWavelengthRange[0].toFixed(1)}-${activeWavelengthRange[1].toFixed(1)} nm`;
  const selectedDelayLabel = `${activeDelayRange[0].toFixed(2)}-${activeDelayRange[1].toFixed(2)} ps`;
  const rawDelayIndexes = rawDataset?.delays?.length
    ? indexesInRange(rawDataset.delays, activeDelayRange)
    : [];
  const rawSafeDelayIndexes = rawDelayIndexes.length
    ? rawDelayIndexes
    : (rawDataset?.delays?.length
      ? [nearestIndex(rawDataset.delays, (activeDelayRange[0] + activeDelayRange[1]) / 2)]
      : []);
  const showRawSpectra = spectraViewMode === 'raw' && rawDataset?.channels?.length;
  const rawColors = ['#f1c84b', '#33c5ff', '#f05d5e', '#c798ff', '#7ee787', '#ff9f43'];
  const savedKineticColors = ['#33c5ff', '#f1c84b', '#c798ff', '#ff9f43', '#7ee787', '#ff6b9a', '#9fb7ff'];
  const currentOdSource = fileOdLoaded
    ? (loadedOdDataset.file_name || 'OD file')
    : 'live';

  const addKineticTrace = () => {
    const nextIndex = kineticCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedKinetics((current) => ([
      ...current,
      {
        id: `kinetic-${Date.now()}-${nextIndex}`,
        label: `K${nextIndex}`,
        source: currentOdSource,
        wavelengthRange: [...activeWavelengthRange],
        wavelengthLabel: selectedWavelengthLabel,
        x: [...delays],
        y: kineticTrace.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setKineticCounter((value) => value + 1);
  };

  const removeKineticTrace = (id) => {
    setSavedKinetics((current) => current.filter((trace) => trace.id !== id));
  };

  const addOdSpectrumTrace = () => {
    const nextIndex = odSpectrumCounter;
    const nextColor = savedKineticColors[(nextIndex - 1) % savedKineticColors.length];
    setSavedOdSpectra((current) => ([
      ...current,
      {
        id: `od-spectrum-${Date.now()}-${nextIndex}`,
        label: `S${nextIndex}`,
        source: currentOdSource,
        delayRange: [...activeDelayRange],
        delayLabel: selectedDelayLabel,
        x: [...wavelengths],
        y: selectedOd.map((value) => (value ?? null)),
        color: nextColor,
      },
    ]));
    setOdSpectrumCounter((value) => value + 1);
  };

  const removeOdSpectrumTrace = (id) => {
    setSavedOdSpectra((current) => current.filter((trace) => trace.id !== id));
  };

  const plotTheme = {
    paper_bgcolor: '#11151b',
    plot_bgcolor: '#07090d',
    font: { color: '#d9dde4', family: 'Segoe UI, Arial, sans-serif' },
    margin: { l: 58, r: 18, t: 20, b: 48 },
    uirevision: `pump-probe-v0-${plotRevision}`,
    dragmode: 'zoom',
    xaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
      title: { text: 'Wavelength, nm' },
    },
    yaxis: {
      gridcolor: '#26313b',
      zerolinecolor: '#59636d',
    },
  };

  const spectraData = showRawSpectra
    ? rawDataset.channels.map((channel, index) => ({
      x: rawDataset.wavelengths,
      y: averageRows(channel.values || [], rawSafeDelayIndexes).map((value) => value ?? 0),
      type: 'scatter',
      mode: 'lines',
      name: channel.label || channel.key,
      line: { color: rawColors[index % rawColors.length], width: index < 3 ? 2 : 1.5 },
    }))
    : [
      {
        x: wavelengths,
        y: spectra.signal,
        type: 'scatter',
        mode: 'lines',
        name: 'Is',
        line: { color: '#f05d5e', width: 2 },
      },
      {
        x: wavelengths,
        y: spectra.reference,
        type: 'scatter',
        mode: 'lines',
        name: 'Ir',
        line: { color: '#33c5ff', width: 2 },
      },
      ...(spectra.background_available === false ? [] : [{
        x: wavelengths,
        y: spectra.background,
        type: 'scatter',
        mode: 'lines',
        name: 'BG',
        line: { color: '#f1c84b', width: 1.5 },
      }]),
    ];
  const spectraTitle = showRawSpectra
    ? `Raw spectrum (${rawDataset.file_name || 'ZIP'})`
    : 'Current spectra';

  const spectraLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'Amplitude' } },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const savedOdSpectrumData = savedOdSpectra.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.delayLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.1f} nm<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const odSpectrumData = [
    ...savedOdSpectrumData,
    {
      x: wavelengths,
      y: selectedOd,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedDelayLabel}`,
      line: { color: '#7ee787', width: 2.4 },
    },
  ];

  const odSpectrumLayout = {
    ...plotTheme,
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.006, 0.006], fixedrange: true },
  };

  const savedKineticsData = savedKinetics.map((trace) => ({
    x: trace.x,
    y: trace.y,
    type: 'scatter',
    mode: 'lines',
    name: `${trace.label} ${trace.wavelengthLabel}`,
    line: { color: trace.color, width: 1.8, dash: 'dot' },
    hovertemplate: `${trace.label}<br>%{x:.2f} ps<br>OD=%{y:.5f}<extra>${trace.source}</extra>`,
  }));
  const kineticsData = [
    ...savedKineticsData,
    {
      x: delays,
      y: kineticTrace,
      type: 'scatter',
      mode: 'lines',
      name: `selection ${selectedWavelengthLabel}`,
      line: { color: '#f05d5e', width: 2.4 },
    },
    {
      x: [delays[activeCurrentIndex]],
      y: [kineticTrace[activeCurrentIndex]],
      type: 'scatter',
      mode: 'markers',
      name: 'current',
      marker: { color: '#f1c84b', size: 9 },
    },
  ];

  const kineticsLayout = {
    ...plotTheme,
    xaxis: { ...plotTheme.xaxis, title: { text: 'Time delay, ps' } },
    yaxis: { ...plotTheme.yaxis, title: { text: 'delta O.D.' }, range: [-0.18, 0.28] },
    legend: { orientation: 'h', y: 1.16, x: 0 },
  };

  const heatmapData = [
    {
      x: wavelengths,
      y: delays,
      z: completedHeatmap,
      type: 'heatmap',
      colorscale: [
        [0, '#13294b'],
        [0.35, '#1f8f7a'],
        [0.55, '#f0d34f'],
        [1, '#e6462e'],
      ],
      zmin: -0.12,
      zmax: 0.25,
      colorbar: { title: 'delta O.D.' },
      hovertemplate: 'wl=%{x:.1f} nm<br>delay=%{y:.2f} ps<br>OD=%{z:.4f}<extra></extra>',
    },
  ];

  const heatmapLayout = {
    ...plotTheme,
    dragmode: false,
    margin: { l: 64, r: 78, t: 20, b: 48 },
    xaxis: {
      ...plotTheme.xaxis,
      range: [wavelengths[0], wavelengths[wavelengths.length - 1]],
      fixedrange: true,
    },
    yaxis: {
      ...plotTheme.yaxis,
      title: { text: 'Time delay, ps' },
      range: [delays[0], delays[delays.length - 1]],
      fixedrange: true,
    },
  };
  const heatmapConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    doubleClick: false,
    scrollZoom: false,
  }), []);
  const delayPreviewData = [
    {
      x: delays.map((_delay, index) => index + 1),
      y: delays,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'delay',
      line: { color: '#33c5ff', width: 1.5 },
      marker: { color: '#f1c84b', size: 3 },
      hovertemplate: 'point=%{x}<br>delay=%{y:.3f} ps<extra></extra>',
    },
  ];
  const delayPreviewLayout = {
    ...plotTheme,
    margin: { l: 48, r: 12, t: 8, b: 34 },
    xaxis: { ...plotTheme.xaxis, title: { text: 'Point' }, fixedrange: true },
    yaxis: { ...plotTheme.yaxis, title: { text: 'Delay, ps' }, fixedrange: true },
    showlegend: false,
  };
  const delayPreviewConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: false,
    scrollZoom: false,
  }), []);
  const chartConfig = useMemo(() => ({
    responsive: true,
    displaylogo: false,
    displayModeBar: true,
    modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d', 'resetScale2d'],
    scrollZoom: true,
  }), []);
  const plotInteractionProps = {
  };

  return (
    <main className="pp-page">
      <header className="pp-header">
        <div>
          <h1>V0 Pump-Probe</h1>
          <div className="pp-subtitle">DLIII-V0 / Andor CCD / pulse radiolysis</div>
        </div>
        <SampleStageControl
          positionMm={sampleDisplayPositionMm}
          targetMm={sampleDisplayTargetMm}
          positions={samplePositionsMm}
          onMove={moveSampleStage}
          onStop={stopSampleStage}
          onMarkerMove={setSampleMarker}
          onOpenConfig={setDeviceConfigKey}
        />
        <div className="pp-run-controls">
          <button
            type="button"
            className={`pp-device-pill ${netioAnyOn ? 'pp-device-powered' : ''}`}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setNetioOpen(true);
            }}
            onClick={() => setNetioOpen(true)}
          >
            Hardware
          </button>
          <button
            type="button"
            className={hardwareInitStatus?.success ? 'pp-action-ok' : ''}
            disabled={hardwareInitLoading}
            onClick={() => runHardwareInitialization(true)}
            title="Check Tango servers, NETIO power, OWIS axes, DG645 recall 8, and DAQmx counter"
          >
            {hardwareInitLoading ? 'Init...' : 'Initialize HW'}
          </button>
          <button
            type="button"
            onClick={() => {
              postAndRefresh('/run', { running: !running });
            }}
          >
            {running ? 'Stop' : 'Start'}
          </button>
          <button
            type="button"
            className={faradayClosed ? 'pp-action-ok' : 'pp-action-warn'}
            onClick={() => {
              const nextClosed = !faradayClosed;
              setLocalFaradayClosed(nextClosed);
              setLocalElectronState(nextClosed ? 'OFF' : 'ON');
              postAndRefresh('/faraday', { closed: nextClosed });
            }}
          >
            Faraday {faradayClosed ? 'closed' : 'open'}
          </button>
          <button type="button" onClick={() => postAndRefresh('/crystal/move')}>
            Move Crystal
          </button>
          <button
            type="button"
            className={realTime ? 'pp-action-warn' : ''}
            onClick={() => {
              postAndRefresh('/realtime', { enabled: !realTime });
            }}
          >
            Real time {realTime ? 'on' : 'off'}
          </button>
          <button
            type="button"
            onClick={() => {
              setLocalIndex(0);
              setLocalElectronState('OFF');
              postAndRefresh('/reset');
            }}
          >
            Reset
          </button>
          <div className="pp-data-strip">
            <input
              type="text"
              value={sampleName}
              onChange={(event) => setSampleName(event.target.value)}
              placeholder="sample name"
            />
            <button
              type="button"
              onClick={() => {
                setDataBrowserOpen(true);
                loadDataPath(dataSelectedPath || dataPath || dataRoot);
              }}
            >
              Files
            </button>
            <span title={dataSelectedPath || 'No data folder selected'}>
              {dataSelectedPath ? displayPathTail(dataSelectedPath) : 'no folder'}
            </span>
          </div>
        </div>
      </header>

      <section className="pp-status-strip">
        <div><span>control</span>{activeControlMode}</div>
        <div><span>delay</span>{(delays[activeCurrentIndex] || 0).toFixed(2)} ps</div>
        <div><span>position</span>{positionMm.toFixed(3)} mm</div>
        <div><span>state</span>electrons {electronState}</div>
        <div><span>point</span>{activeCurrentIndex + 1} / {delays.length}</div>
        <div><span>pulses</span>{backendState?.total_pulses ?? 0} @ {backendState?.accelerator_hz ?? 5} Hz</div>
        <div>
          <span>spectrometer</span>
          {backendState?.spectrometer_frames ?? 0} @ {backendState?.spectrometer_hz ?? 15} Hz
          / burst {backendState?.spectrometer_burst ?? 3}
        </div>
        <div className="pp-counter-status">
          <span>counter</span>
          <i className={`pp-counter-led ${counterActive ? 'pp-counter-led-active' : ''}`} />
          {daqCounter.value ?? '-'} @ {counterRateHz.toFixed(2)} Hz
        </div>
      </section>
      {backendError ? <div className="pp-api-error">{backendError}</div> : null}
      {backendState?.hardware_error ? <div className="pp-api-error">{backendState.hardware_error}</div> : null}
      {hardwareInitStatus ? (
        <section className={`pp-hw-init ${hardwareInitStatus.success ? 'pp-hw-init-ok' : 'pp-hw-init-fail'}`}>
          <div className="pp-hw-init-head">
            <strong>{hardwareInitStatus.message || (hardwareInitStatus.success ? 'Hardware initialized' : 'Hardware initialization failed')}</strong>
            <span>{failedHardwareChecks.length ? `${failedHardwareChecks.length} problem(s)` : 'all checks OK'}</span>
            {!hardwareInitStatus.success ? (
              <button type="button" disabled={hardwareInitLoading} onClick={() => runHardwareInitialization(true)}>
                Resolve automatically
              </button>
            ) : null}
          </div>
          <div className="pp-hw-init-list">
            {hardwareChecks.map((check) => (
              <div key={`${check.label}-${check.device || check.axis || check.output_id || ''}`} className={check.ok ? 'pp-hw-check-ok' : 'pp-hw-check-fail'}>
                <b>{check.ok ? 'OK' : 'ERR'}</b>
                <span>{check.label}</span>
                <small>{check.detail}</small>
              </div>
            ))}
          </div>
          {hardwareInitStatus.recommendation ? <p>{hardwareInitStatus.recommendation}</p> : null}
        </section>
      ) : null}
      <section className="pp-selection-strip">
        <div><span>wavelength range</span>{selectedWavelengthLabel}</div>
        <div><span>delay range</span>{selectedDelayLabel}</div>
        <button
          type="button"
          onClick={() => {
            setSelectedWavelengthRange(null);
            setSelectedDelayRange(null);
            setPlotRevision((value) => value + 1);
          }}
        >
          Clear ranges
        </button>
      </section>

      <section className="pp-layout">
        <div className="pp-left-column">
          <PlotPanel
            title={spectraTitle}
            className="pp-panel-fill"
            actions={(
              <div className="pp-panel-toggle">
                <button
                  type="button"
                  className={spectraViewMode === 'current' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('current')}
                >
                  Current
                </button>
                <button
                  type="button"
                  className={spectraViewMode === 'raw' ? 'pp-panel-toggle-active' : ''}
                  onClick={() => setSpectraViewMode('raw')}
                  disabled={!rawDataset}
                >
                  Raw
                </button>
              </div>
            )}
          >
            <PlotlyChart
              className="pp-plot pp-plot-spectra"
              data={spectraData}
              layout={spectraLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Current OD" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
          </PlotPanel>
        </div>

        <div className="pp-center-grid">
          <PlotPanel title="OD heatmap" className="pp-panel-fill">
            <HeatmapSelectorChart
              className="pp-plot pp-plot-heatmap"
              data={heatmapData}
              layout={heatmapLayout}
              config={heatmapConfig}
              wavelengthRange={activeWavelengthRange}
              delayRange={activeDelayRange}
              onRangesChange={(nextWavelengthRange, nextDelayRange) => {
                setSelectedWavelengthRange(nextWavelengthRange);
                setSelectedDelayRange(nextDelayRange);
              }}
              {...plotInteractionProps}
            />
          </PlotPanel>

          <PlotPanel title="Kinetics" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-kinetics"
              data={kineticsData}
              layout={kineticsLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-kinetics-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add kinetics: ${selectedWavelengthLabel}`}
                  onClick={addKineticTrace}
                >
                  + Kinetic
                </button>
                {savedKinetics.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved kinetics"
                    onClick={() => setSavedKinetics([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedKinetics.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.wavelengthLabel} / ${trace.source}`}
                      onClick={() => removeKineticTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <PlotPanel title="OD spectrum" className="pp-panel-fill">
            <PlotlyChart
              className="pp-plot pp-plot-od"
              data={odSpectrumData}
              layout={odSpectrumLayout}
              config={chartConfig}
              {...plotInteractionProps}
            />
            <div className="pp-spectrum-floating-actions">
              <div className="pp-kinetics-actions">
                <button
                  type="button"
                  className="pp-icon-button"
                  title={`Add OD spectrum: ${selectedDelayLabel}`}
                  onClick={addOdSpectrumTrace}
                >
                  + Spectrum
                </button>
                {savedOdSpectra.length ? (
                  <button
                    type="button"
                    className="pp-icon-button"
                    title="Clear saved OD spectra"
                    onClick={() => setSavedOdSpectra([])}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="pp-kinetic-chip-row">
                  {savedOdSpectra.map((trace) => (
                    <button
                      key={trace.id}
                      type="button"
                      className="pp-kinetic-chip"
                      title={`${trace.label}: ${trace.delayLabel} / ${trace.source}`}
                      onClick={() => removeOdSpectrumTrace(trace.id)}
                    >
                      <span style={{ background: trace.color }} />
                      {trace.label} x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </PlotPanel>

          <SettingsPanel
            settings={settings}
            hardwareConfig={hardwareConfig}
            onSettingChange={handleSettingChange}
            onHardwareModeChange={handleHardwareModeChange}
            delayStats={delayStats}
            delayPreviewData={delayPreviewData}
            delayPreviewLayout={delayPreviewLayout}
            delayPreviewConfig={delayPreviewConfig}
            onDelayPointsLoad={handleDelayPointsLoad}
            onConfigLoad={handleConfigLoad}
            onConfigSave={handleConfigSave}
          />
        </div>

        <aside className="pp-right-column">
          <StageControl
            positionMm={positionMm}
            setPositionMm={setPositionMm}
            stepPs={stepPs}
            zeroMm={zeroMm}
            onPositionChange={(value) => {
              setBackendState((current) => (current ? { ...current, set_position_mm: value, stage_moving: true } : current));
              postAndRefresh('/stage/move', { position_mm: value });
            }}
            onStop={() => {
              setBackendState((current) => (current ? {
                ...current,
                set_position_mm: current.position_mm,
                stage_moving: false,
              } : current));
              postAndRefresh('/stage/stop');
            }}
            onStepChange={setStepPs}
            onZeroChange={setZeroMm}
            onOpenConfig={setDeviceConfigKey}
          />
        </aside>
      </section>
      <DeviceConfigModal
        deviceKey={deviceConfigKey}
        config={deviceConfig}
        onChange={setDeviceConfig}
        samplePositions={samplePositionsMm}
        onSamplePositionsChange={setSamplePositionsMm}
        onClose={() => setDeviceConfigKey(null)}
      />
      <HardwareModal
        open={netioOpen}
        channels={NETIO_POWER_CHANNELS}
        devices={netioDevices}
        tangoServers={HARDWARE_TANGO_SERVERS}
        tangoStates={tangoStates}
        loading={netioLoading}
        tangoLoading={tangoLoading}
        error={netioError}
        tangoError={tangoError}
        onClose={closeHardwareModal}
        onRefresh={() => {
          loadNetioOutputs();
          loadTangoStates();
        }}
        onToggle={toggleNetioChannel}
        onBulkPower={setNecessaryHardwarePower}
        onStartTango={(server) => controlTangoServer(server, 'start')}
        onRestartTango={(server) => controlTangoServer(server, 'restart')}
      />
      <DataBrowserWindow
        open={dataBrowserOpen}
        sampleName={sampleName}
        root={dataRoot}
        path={dataPath}
        parent={dataParent}
        entries={dataEntries}
        loading={dataLoading}
        error={dataError}
        selectedPath={dataSelectedPath}
        onClose={() => setDataBrowserOpen(false)}
        onRefresh={() => loadDataPath(dataPath || dataRoot)}
        onOpenPath={(pathValue) => loadDataPath(pathValue || dataRoot)}
        onSelectPath={setDataSelectedPath}
        onLoadFile={loadDataFile}
        onCreateFolder={createSampleFolder}
      />
    </main>
  );
}

export default PumpProbeV0;
