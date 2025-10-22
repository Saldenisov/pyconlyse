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
    <div>
      <h1>Equipment Page</h1>
      
      {/* PDU Modal */}
      {showPDUModal && (
        <div className="modal-overlay" onClick={() => setShowPDUModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>PDU - NETIO Clients</h2>
            <div className="modal-links">
              <a href="/test_netio_pdu.html" target="_blank" rel="noopener noreferrer" className="modal-link">
                NETIO Web Client
              </a>
              <a href="http://10.20.30.202" target="_blank" rel="noopener noreferrer" className="modal-link">
                NETIO Direct Access
              </a>
            </div>
            <button onClick={() => setShowPDUModal(false)} className="modal-close">Close</button>
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
      
      <div className="container">
        <div className="row">
          {/* Left Column: Equipment Images */}
          <div className="column column-left">
            <div
              className="grid-container"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)", // Three columns per row
                gridTemplateRows: "repeat(2, auto)",   // Two rows
                gap: "10px"
              }}
            >
              {equipmentItems.map(item => (
                <div className="grid-item" key={item.id}>
                  <div
                    className="image-container"
                    onClick={() => updateWidget(item.id)}
                  >
                    <span className="image-label">{item.label}</span>
                    <img src={item.img} alt={item.label} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          {/* Right Column: Widget */}
          <div className="column column-right">
            <div id="widget-container">
              {selectedEquipment ? (
                <>
                  <h2>Control Equipment {selectedEquipment}</h2>
                  <button onClick={() => handleClick(selectedEquipment)}>Click Me</button>
                  <p>{statusMessage}</p>
                </>
              ) : (
                <h2>Select equipment to control</h2>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Equipment;
