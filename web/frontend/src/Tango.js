import React, { useEffect, useState } from 'react';

const HEALTHY_STATES = new Set(['ON', 'MOVING', 'STANDBY']);

const Tango = () => {
  const [tangoData, setTangoData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let disposed = false;

    const fetchStatuses = async () => {
      try {
        const response = await fetch('/api/tango_status');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        if (!disposed) {
          setTangoData(data);
          setError('');
        }
      } catch (err) {
        if (!disposed) {
          setError(err.message);
          setTangoData({
            mysql_status: false,
            mysql_downtime_seconds: 0,
            tango_statuses: [],
          });
        }
      }
    };

    fetchStatuses();
    const intervalId = setInterval(fetchStatuses, 2000);

    return () => {
      disposed = true;
      clearInterval(intervalId);
    };
  }, []);

  const tangoDbHealthy = Boolean(tangoData && tangoData.mysql_status);
  const starters = tangoData?.tango_statuses || [];

  return (
    <div>
      <h1>Tango Page</h1>
      <p>This page displays the status of the Tango Database and Tango starter devices.</p>
      {error && (
        <div className="error-alert">
          <strong>Connection error:</strong> {error}
        </div>
      )}
      <div className="container">
        <div className="row">
          <div className="column">
            <h2>Tango Database Status</h2>
            <div
              id="tango-db-status"
              className={`lamp ${tangoDbHealthy ? 'green' : 'red'}`}
            ></div>
            <p id="tango-db-downtime">
              {tangoData
                ? tangoDbHealthy
                  ? 'Tango DB is running'
                  : `Down for ${tangoData.mysql_downtime_seconds} seconds`
                : 'Loading...'}
            </p>
          </div>
          <div className="column">
            <h2>Tango Starter Device Statuses</h2>
            <div id="tango-statuses">
              {starters.length === 0 && <p>No starter devices reported.</p>}
              {starters.map((starter, index) => {
                const state = String(starter[2] || '');
                const healthy = HEALTHY_STATES.has(state);
                return (
                  <div key={`${starter[0]}-${index}`}>
                    <span>{starter[0]} ({starter[1]})</span>
                    <div className={`lamp ${healthy ? 'green' : 'red'}`}></div>
                    <p>{healthy ? state : `Down for ${starter[3]} seconds (${state || 'DOWN'})`}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Tango;
