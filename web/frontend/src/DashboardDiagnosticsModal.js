import React from 'react';

const panelStyle = {
  position: 'fixed',
  inset: 0,
  zIndex: 1100,
  background: 'rgba(15, 23, 42, 0.55)',
  display: 'grid',
  placeItems: 'center',
  padding: '24px',
};

const preStyle = {
  margin: 0,
  maxHeight: '260px',
  overflow: 'auto',
  padding: '12px',
  border: '1px solid #d0d5dd',
  background: '#101828',
  color: '#f9fafb',
  fontSize: '0.8rem',
  lineHeight: 1.45,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

const renderValue = (value) => {
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value, null, 2);
};

const lifecycleAttributeNames = new Set([
  'hardware_connection_state',
  'initialization_state',
  'hardware_lifecycle_status',
  'power_dependency_status',
  'controller_connection_status',
]);

const DashboardDiagnosticsModal = ({ diagnostics, loading, error, onClose }) => {
  const copyDiagnostics = async () => {
    if (!diagnostics || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2));
  };

  const device = diagnostics?.device;
  const errorAttributes = Object.entries(device?.error_attributes || {});
  const lifecycleAttributes = errorAttributes.filter(([name]) => lifecycleAttributeNames.has(name));
  const serverErrorAttributes = errorAttributes.filter(([name]) => !lifecycleAttributeNames.has(name));
  const lifecycleValue = (name, fallback = 'NOT INSTRUMENTED') => {
    const attribute = lifecycleAttributes.find(([attributeName]) => attributeName === name);
    return attribute ? renderValue(attribute[1]) : fallback;
  };
  const serverLog = diagnostics?.server_log;
  const starterLog = diagnostics?.starter_log;

  return (
    <div style={panelStyle} role="presentation" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Tango server diagnostics"
        onMouseDown={(event) => event.stopPropagation()}
        style={{
          width: 'min(960px, 100%)',
          maxHeight: 'calc(100vh - 48px)',
          overflow: 'auto',
          padding: '20px',
          border: '1px solid #d0d5dd',
          borderRadius: '8px',
          background: '#ffffff',
          boxShadow: '0 24px 56px rgba(15, 23, 42, 0.28)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
          <div>
            <h2 style={{ margin: 0 }}>Server diagnostics</h2>
            <div style={{ marginTop: '6px', color: '#475467', wordBreak: 'break-word' }}>
              {diagnostics?.server_name || 'Loading server data...'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'start' }}>
            <button type="button" onClick={copyDiagnostics} disabled={!diagnostics}>Copy</button>
            <button type="button" onClick={onClose}>Close</button>
          </div>
        </div>

        {loading && <p>Reading Tango state and Starter logs...</p>}
        {error && <p style={{ color: '#b42318' }}>{error}</p>}
        {diagnostics && (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
                gap: '12px',
                marginTop: '18px',
              }}
            >
              <div><strong>Starter</strong><br />{diagnostics.starter}</div>
              <div><strong>Server process</strong><br />{diagnostics.running ? 'RUNNING' : diagnostics.stopped ? 'STOPPED' : 'UNKNOWN'}</div>
              <div><strong>Tango proxy</strong><br />{device?.available ? 'REACHABLE' : 'UNREACHABLE'}</div>
              <div><strong>Tango state</strong><br />{device?.state || 'UNREACHABLE'}</div>
              <div><strong>Hardware connection</strong><br />{lifecycleValue('hardware_connection_state')}</div>
              <div><strong>Initialisation</strong><br />{lifecycleValue('initialization_state')}</div>
              <div><strong>Captured</strong><br />{diagnostics.timestamp || ''}</div>
            </div>

            <h3>Hardware lifecycle</h3>
            <pre style={preStyle}>{lifecycleValue('hardware_lifecycle_status', 'This device does not yet expose the shared lifecycle contract.')}</pre>

            {lifecycleAttributes
              .filter(([name]) => !['hardware_connection_state', 'initialization_state', 'hardware_lifecycle_status'].includes(name))
              .map(([name, value]) => (
                <div key={name} style={{ marginBottom: '10px' }}>
                  <strong>{name}</strong>
                  <pre style={preStyle}>{renderValue(value)}</pre>
                </div>
              ))}

            <h3>Device status</h3>
            <pre style={preStyle}>{device?.status || device?.error || 'No status returned.'}</pre>

            {serverErrorAttributes.length > 0 && (
              <>
                <h3>Server error details</h3>
                {serverErrorAttributes.map(([name, value]) => (
                  <div key={name} style={{ marginBottom: '10px' }}>
                    <strong>{name}</strong>
                    <pre style={preStyle}>{renderValue(value)}</pre>
                  </div>
                ))}
              </>
            )}

            {diagnostics.capture_note && (
              <p style={{ padding: '10px', background: '#fff8e6', color: '#7a4e00' }}>
                {diagnostics.capture_note}
              </p>
            )}

            <h3>Server log</h3>
            <pre style={preStyle}>
              {serverLog?.available ? serverLog.text || 'Log is empty.' : serverLog?.error || 'No captured server log.'}
            </pre>

            <h3>Starter log</h3>
            <pre style={preStyle}>
              {starterLog?.available ? starterLog.text || 'Log is empty.' : starterLog?.error || 'No Starter log.'}
            </pre>
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardDiagnosticsModal;
