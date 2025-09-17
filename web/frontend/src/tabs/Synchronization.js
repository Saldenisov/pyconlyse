// src/tabs/Synchronization.js
import React from 'react';
import './Synchronization.css';  // Ensure you create and include this CSS file

const Synchronization = () => {
  return (
    <div className="container">
      {/* Left Column */}
      <div className="column">
        <h2>Synchronisation Carte (Gauche)</h2>

        <div className="control-row highlight">
          <label htmlFor="delai-ni6071e">Délais NI6071E:</label>
          <input type="text" id="delai-ni6071e" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row highlight">
          <label htmlFor="largeur-ni6071e">Largeur NI6071E:</label>
          <input type="text" id="largeur-ni6071e" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="freq-elyse1">Fréquence ELYSE:</label>
          <input type="text" id="freq-elyse1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="freq-elyse2">Fréquence ELYSE:</label>
          <input type="text" id="freq-elyse2" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-faraday">Délais Faraday:</label>
          <input type="text" id="delai-faraday" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-faraday">Largeur Faraday:</label>
          <input type="text" id="largeur-faraday" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-wcm">Délais WCM:</label>
          <input type="text" id="delai-wcm" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-wcm">Largeur WCM:</label>
          <input type="text" id="largeur-wcm" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row highlight">
          <label htmlFor="delai-modulateur">Délais Modulateur:</label>
          <input type="text" id="delai-modulateur" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row highlight">
          <label htmlFor="largeur-modulateur">Largeur Modulateur:</label>
          <input type="text" id="largeur-modulateur" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="synchro-left1">Synchro 50Hz@20MHz:</label>
          <input type="text" id="synchro-left1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="synchro-left2">Synchro 50Hz@20MHz:</label>
          <input type="text" id="synchro-left2" placeholder="0.0" />
          <span>µs</span>
        </div>
      </div>

      {/* Right Column */}
      <div className="column">
        <h2>Synchronisation Carte (Droite)</h2>

        <div className="control-row">
          <label htmlFor="delai-laser-hf">Délais LASER/HF:</label>
          <input type="text" id="delai-laser-hf" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-laser-hf">Largeur LASER/HF:</label>
          <input type="text" id="largeur-laser-hf" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-imac">Délais IMAC:</label>
          <input type="text" id="delai-imac" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-imac">Largeur IMAC:</label>
          <input type="text" id="largeur-imac" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-osc1">Délais Oscilloscope 1:</label>
          <input type="text" id="delai-osc1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-osc1">Largeur Oscilloscope 1:</label>
          <input type="text" id="largeur-osc1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-osc2">Délais Oscilloscope 2:</label>
          <input type="text" id="delai-osc2" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-osc2">Largeur Oscilloscope 2:</label>
          <input type="text" id="largeur-osc2" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-detection1">Délais Détection 1:</label>
          <input type="text" id="delai-detection1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-detection1">Largeur Détection 1:</label>
          <input type="text" id="largeur-detection1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="delai-machine">Délais Machine:</label>
          <input type="text" id="delai-machine" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="largeur-machine">Largeur Machine:</label>
          <input type="text" id="largeur-machine" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="synchro-right1">Synchro 50Hz@20MHz:</label>
          <input type="text" id="synchro-right1" placeholder="0.0" />
          <span>µs</span>
        </div>

        <div className="control-row">
          <label htmlFor="synchro-right2">Synchro 50Hz@20MHz:</label>
          <input type="text" id="synchro-right2" placeholder="0.0" />
          <span>µs</span>
        </div>
      </div>
    </div>
  );
};

export default Synchronization;
