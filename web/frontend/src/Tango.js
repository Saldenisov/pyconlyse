import React, { useState, useEffect } from 'react';

const Tango = () => {
  // State to hold the status data
  const [tangoData, setTangoData] = useState(null);

  // Fetch the status data every 500ms
  useEffect(() => {
    const fetchStatuses = () => {
      // Adjust the endpoint as needed (e.g. '/tango_status' or '/api/tango_status')
      fetch('/tango_status')
        .then(response => response.json())
        .then(data => {
          setTangoData(data);
        })
        .catch(error => {
          console.error("Error fetching Tango status:", error);
          // In case of error, assume the DB is down and clear statuses
          setTangoData({
            mysql_status: false,
            mysql_downtime_seconds: 0,
            tango_statuses: []
          });
        });
    };

    // Initial fetch and then poll every 500ms
    fetchStatuses();
    const intervalId = setInterval(fetchStatuses, 500);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div>
      <h1>Tango Page</h1>
      <p>This page displays the status of the Tango Database and Tango starter devices.</p>
      <div className="container">
        <div className="row">
          {/* Tango Database Status */}
          <div className="column">
            <h2>Tango Database Status</h2>
            <div
              id="tango-db-status"
              className={`lamp ${tangoData && tangoData.mysql_status ? 'green' : 'red'}`}
            ></div>
            <p id="tango-db-downtime">
              {tangoData
                ? (tangoData.mysql_status
                    ? 'Tango DB is running'
                    : `Down for ${tangoData.mysql_downtime_seconds} seconds`)
                : ''}
            </p>
          </div>
          {/* Tango Starter Device Statuses */}
          <div className="column">
            <h2>Tango Starter Device Statuses</h2>
            <div id="tango-statuses">
              {tangoData && tangoData.tango_statuses && tangoData.tango_statuses.map((starter, index) => (
                <div key={index}>
                  <span>{starter[0]} ({starter[1]})</span>
                  <div className={`lamp ${starter[2] ? 'green' : 'red'}`}></div>
                  {!starter[2] && <p>Down for {starter[3]} seconds</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Tango;
