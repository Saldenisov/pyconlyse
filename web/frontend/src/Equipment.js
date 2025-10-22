import React, { useState } from 'react';
import ITestPSUClient from './components/ITestPSUClient';
import './Equipment.css';

const Equipment = () => {
  // State to track the selected equipment
  const [selectedEquipment, setSelectedEquipment] = useState(null);
  // State to hold the status message from the button click
  const [statusMessage, setStatusMessage] = useState("");
  // State to control PDU modal
  const [showPDUModal, setShowPDUModal] = useState(false);
  // State to control Magnets modal
  const [showMagnetsModal, setShowMagnetsModal] = useState(false);
  // State to control Motorized Stages modal
  const [showMotorizedModal, setShowMotorizedModal] = useState(false);

  // Array of equipment items with id, label, and image path
  const equipmentItems = [
    { id: 1, label: "PDU", img: "/images/pdu.png" },
    { id: 2, label: "Motorized Stages", img: "/images/motorized_stages2.png" },
    { id: 3, label: "Cameras", img: "/images/cameras.png" },
    { id: 4, label: "Magnets", img: "/images/magnets.png" },
    { id: 5, label: "Vacuum", img: "/images/vacuum.png" },
    { id: 6, label: "Pumps", img: "/images/pumps.png" }
  ];

  // Update the widget based on the selected equipment
  const updateWidget = (equipmentId) => {
    if (equipmentId === 1) {
      // For PDU, open modal with NETIO link
      setShowPDUModal(true);
    } else if (equipmentId === 2) {
      // For Motorized Stages, open modal with OWIS link
      setShowMotorizedModal(true);
    } else if (equipmentId === 4) {
      // For Magnets, open modal with Itest link
      setShowMagnetsModal(true);
    } else {
      setSelectedEquipment(equipmentId);
      setStatusMessage(""); // Reset the status message
    }
  };

  // Handle button click within the widget
  const handleClick = (equipmentId) => {
    setStatusMessage(`Equipment ${equipmentId} button clicked!`);
  };

  return (
    <div className="equipment-page">
      <div className="equipment-header">
        <h1>Equipment Control Center</h1>
        <p>Select equipment to access control interfaces</p>
      </div>
      
      {/* PDU Modal */}
      {showPDUModal && (
        <div className="modal-overlay" onClick={() => setShowPDUModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>PDU - NETIO Clients</h2>
            <div className="modal-links">
              <a href="/test_netio_pdu.html" target="_blank" rel="noopener noreferrer" className="modal-link">
                NETIO Web Client
              </a>
            </div>
            <button onClick={() => setShowPDUModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}

      {/* Motorized Stages Modal */}
      {showMotorizedModal && (
        <div className="modal-overlay" onClick={() => setShowMotorizedModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Motorized Stages</h2>
            <div className="modal-links">
              <a href="/test_standa_motors.html" target="_blank" rel="noopener noreferrer" className="modal-link">
                Standa Motors Client
              </a>
              <a href="/test_owis_ps90.html" target="_blank" rel="noopener noreferrer" className="modal-link">
                OWIS PS90 Controller
              </a>
            </div>
            <button onClick={() => setShowMotorizedModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}

      {/* Magnets Modal */}
      {showMagnetsModal && (
        <div className="modal-overlay" onClick={() => setShowMagnetsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Magnets - Itest</h2>
            <div className="modal-links">
              <a href="/test_ds_itest_psu.html" target="_blank" rel="noopener noreferrer" className="modal-link">
                Itest
              </a>
            </div>
            <button onClick={() => setShowMagnetsModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}
      
      <div className="equipment-grid">
        {equipmentItems.map(item => (
          <div 
            className="equipment-card" 
            key={item.id}
            onClick={() => updateWidget(item.id)}
          >
            <div className="card-image-wrapper">
              <img src={item.img} alt={item.label} className="card-image" />
              <div className="card-overlay">
                <span className="card-icon">🔧</span>
              </div>
            </div>
            <div className="card-content">
              <h3>{item.label}</h3>
              <p>Click to access controls</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Equipment;
