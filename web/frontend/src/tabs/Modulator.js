// src/tabs/Modulator.js
import React from 'react';
import './Modulator.css';

const Modulator = () => {
  return (
    <div className="modulateur-container">
      <div className="modulateur-title">Modulateur</div>

      {/* Row 1 */}
      <div className="control-row">
        <div className="diode-label">Diode</div>
        <div className="diode-indicator"></div>
        <button className="mode-btn" title="Marche">M</button>
        <div className="mode-label">General</div>
        <button className="mode-btn" title="Arrêt">A</button>
      </div>

      {/* Row 2 */}
      <div className="control-row">
        <div className="diode-label">Diode</div>
        <div className="diode-indicator"></div>
        <button className="mode-btn" title="Marche">M</button>
        <div className="mode-label">Chauffage</div>
        <button className="mode-btn" title="Arrêt">A</button>
      </div>

      {/* Row 3 */}
      <div className="control-row">
        <div className="diode-label">Diode</div>
        <div className="diode-indicator"></div>
        <button className="mode-btn" title="Marche">M</button>
        <div className="mode-label">Prema</div>
        <button className="mode-btn" title="Arrêt">A</button>
      </div>

      {/* Row 4 */}
      <div className="control-row">
        <div className="diode-label">Diode</div>
        <div className="diode-indicator"></div>
        <button className="mode-btn" title="Marche">M</button>
        <div className="mode-label">Focales</div>
        <button className="mode-btn" title="Arrêt">A</button>
      </div>

      {/* Row 5 */}
      <div className="control-row">
        <div className="diode-label">Diode</div>
        <div className="diode-indicator"></div>
        <button className="mode-btn" title="Marche">M</button>
        <div className="mode-label">Relais HT</div>
        <button className="mode-btn" title="Arrêt">A</button>
      </div>

      {/* RESET button */}
      <button className="reset-btn">Reset</button>
    </div>
  );
};

export default Modulator;
