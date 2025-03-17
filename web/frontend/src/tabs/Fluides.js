// web/frontend/src/tabs/Fluides.js
import React from 'react';
import './Fluides.css';

const Fluides = () => {
  return (
    <div>
      <h1>Régulation de température du CANON et de la SECTION</h1>

      {/* Top row: Colored status blocks */}
      <div className="status-container">
        {/* Left block */}
        <div className="status-block">
          <div className="status-line red">CANON Secteur 220V</div>
          <div className="status-line green">CANON AUCUN DEFAUT</div>
          <div className="status-line orange">RESISTIVITE</div>
        </div>

        {/* Middle block */}
        <div className="status-block">
          <div className="status-line red">SECTION Secteur 220V</div>
          <div className="status-line green">SECTION PRESSOSTAT</div>
          <div className="status-line orange">SECTION DEBITMETRE</div>
        </div>

        {/* Right block */}
        <div className="status-block">
          <div className="status-line red">SECTION Secteur 220V</div>
          <div className="status-line green">SECTION AUCUN DEFAUT</div>
          <div className="status-line orange">VANNE SECTION FERMEE</div>
        </div>
      </div>

      {/* Middle row: Temperature controls */}
      <div className="temperature-controls">
        <button>&laquo;</button>
        <button>&raquo;</button>
        <span>T° CANON: 21,0 °C, 10,0 °C</span>
        <button>&laquo;</button>
        <button>&raquo;</button>
        <span>T° SECTION: 27,9 °C, 9,9 °C</span>
      </div>

      {/* Bottom row: MARCHE / ARRET buttons */}
      <div className="buttons">
        <button>MARCHE</button>
        <button>ARRET</button>
      </div>
    </div>
  );
};

export default Fluides;
