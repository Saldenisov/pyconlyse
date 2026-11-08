import { useEffect, useRef, useState } from 'react';
import Plotly from 'plotly.js-dist';
import { SAMPLE_STAGE_MIN_MM, SAMPLE_STAGE_MAX_MM, clamp, formatStageMm, formatBytes, displayPathTail, parseSamplePositionsText } from './shared';

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
                const nextPositions = parseSamplePositionsText(event.target.value)
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
  topPath,
  onClose,
  onRefresh,
  onOpenPath,
  onSelectPath,
  onSetTopFolder,
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
        <div><span>top folder</span>{topPath || 'not selected'}</div>
        {selectedPath ? <div><span>selected</span>{selectedPath}</div> : null}
      </div>
      <div className="pp-data-actions">
        <button type="button" onClick={() => onOpenPath(root)} disabled={!root || loading}>Root</button>
        <button type="button" onClick={() => onOpenPath(parent)} disabled={!parent || loading}>Up</button>
        <button type="button" onClick={onRefresh} disabled={loading}>Refresh</button>
        <button
          type="button"
          onClick={() => onSetTopFolder(path || root)}
          disabled={!(path || root) || loading}
        >
          Set top folder
        </button>
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

export {
  PlotPanel, SampleStageControl, DeviceConfigModal, DataBrowserWindow, HardwareModal,
  PlotlyChart,
};
