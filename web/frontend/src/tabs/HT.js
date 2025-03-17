// web/frontend/src/tabs/HT.js
import React from 'react';
import './HT.css';

const HT = () => {
  return (
    <div className="container">
      {/* Left Column */}
      <div className="left-column">
        <div className="block red">
          ALIMENTATION HT EN MARCHE
        </div>
        <div className="block gray">
          <p>Alimentation HT</p>
          <p>Mesure VHF: 0.0 kV</p>
          <p>Mesure IHF: 0.0 A</p>
        </div>
        <div className="block">
          <button>Démarrage alimentation HT</button>
          <div style={{ marginTop: "10px" }}>
            <button>MARCHE</button>
            <button>ARRET</button>
          </div>
        </div>
      </div>

      {/* Middle Column */}
      <div className="middle-column">
        <div className="block">
          <h3>Préamplificateur HF</h3>
          <p>240 g / 400 W</p>
          <div className="controls">
            <button>&laquo;</button>
            <span>360 W</span>
            <button>&raquo;</button>
          </div>
        </div>

        <div className="block">
          <h3>Consigne HV</h3>
          <div className="controls">
            <button>&laquo;</button>
            <span>6.5 kV</span>
            <button>&raquo;</button>
          </div>
        </div>
      </div>

      {/* Right Column */}
      <div className="right-column">
        <div className="block">
          <h3>Radioprotection coupure HT</h3>
          <p style={{ marginTop: "10px" }}>Coupure active</p>
        </div>

        <div className="block green">
          <p>SECTION</p>
          <p>-6.36e+10 μA</p>
        </div>

        {/* "Impulsions modulateur" moved here */}
        <div className="block">
          <h3>Impulsions modulateur</h3>
          <button>MARCHE</button>
          <button>ARRET</button>
        </div>
      </div>
    </div>
  );
};

export default HT;
