import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Equipment.css';

const Equipment = () => {
  const navigate = useNavigate();

  const [selectedEquipment, setSelectedEquipment] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [showPDUModal, setShowPDUModal] = useState(false);
  const [showMagnetsModal, setShowMagnetsModal] = useState(false);
  const [showMotorizedModal, setShowMotorizedModal] = useState(false);
  // State to control Cameras modal
  const [showCamerasModal, setShowCamerasModal] = useState(false);
  const [showDAQmxModal, setShowDAQmxModal] = useState(false);
  const [showVacuumModal, setShowVacuumModal] = useState(false);

  const openRoute = (path) => {
    navigate(path);
    setShowPDUModal(false);
    setShowMotorizedModal(false);
    setShowCamerasModal(false);
    setShowMagnetsModal(false);
    setShowDAQmxModal(false);
    setShowVacuumModal(false);
  };

  const openBackendPage = (path) => {
    const backendUrl = `${window.location.protocol}//${window.location.hostname}:5000${path}`;
    window.open(backendUrl, '_blank', 'noopener,noreferrer');
    setShowPDUModal(false);
    setShowMotorizedModal(false);
    setShowCamerasModal(false);
    setShowMagnetsModal(false);
    setShowDAQmxModal(false);
    setShowVacuumModal(false);
  };

  const equipmentItems = [
    { id: 1, label: "PDU", img: "/images/pdu.png" },
    { id: 2, label: "Motorized Stages", img: "/images/motorized_stages2.png" },
    { id: 3, label: "Cameras", img: "/images/cameras.png" },
    { id: 4, label: "Magnets", img: "/images/magnets.png" },
    { id: 5, label: "DAQmx", img: "/images/pumps.png" },
    { id: 6, label: "Vacuum", img: "/images/vacuum.png" },
    { id: 7, label: "Pumps", img: "/images/pumps.png" }
  ];

  const updateWidget = (equipmentId) => {
    const equipment = equipmentItems.find((item) => item.id === equipmentId);
    setSelectedEquipment(equipmentId);

    if (equipmentId === 1) {
      setStatusMessage("Open the NETIO web client in a dedicated tab.");
      setShowPDUModal(true);
    } else if (equipmentId === 2) {
      setStatusMessage("Open the motorized stages clients in dedicated tabs.");
      setShowMotorizedModal(true);
    } else if (equipmentId === 3) {
      // For Cameras, open camera control interface
      setShowCamerasModal(true);
    } else if (equipmentId === 4) {
      setStatusMessage("Open the iTest client in a dedicated tab.");
      setShowMagnetsModal(true);
    } else if (equipmentId === 5) {
      setStatusMessage("Open DAQmx / Supervision client in a dedicated tab.");
      setShowDAQmxModal(true);
    } else if (equipmentId === 6) {
      setStatusMessage("Open the Vacuum real-time monitor in a dedicated tab.");
      setShowVacuumModal(true);
    } else {
      setStatusMessage(
        `${equipment?.label || 'This equipment'} page is not wired yet.`
      );
    }
  };

  return (
    <div className="equipment-page">
      <div className="equipment-header">
        <h1>Equipment Control Center</h1>
        <p>Select equipment to access control interfaces</p>
      </div>

      {statusMessage && (
        <div className="equipment-status">
          <strong>Status:</strong> {statusMessage}
        </div>
      )}

      {/* DAQmx Modal */}
      {showDAQmxModal && (
        <div className="modal-overlay" onClick={() => setShowDAQmxModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>DAQmx - Supervision</h2>
            <div className="modal-links">
              <button type="button" className="modal-link" onClick={() => openRoute("/daqmx-clients")}>
                Open DAQmx Clients
              </button>
            </div>
            <button onClick={() => setShowDAQmxModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}

      {/* Vacuum Modal */}
      {showVacuumModal && (
        <div className="modal-overlay" onClick={() => setShowVacuumModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Vacuum Monitoring</h2>
            <div className="modal-links">
              <button type="button" className="modal-link" onClick={() => openRoute("/vacuum-clients")}>
                Open Vacuum Clients
              </button>
            </div>
            <button onClick={() => setShowVacuumModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}
      
      {/* PDU Modal */}
      {showPDUModal && (
        <div className="modal-overlay" onClick={() => setShowPDUModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>PDU - NETIO Clients</h2>
            <div className="modal-links">
              <button type="button" className="modal-link" onClick={() => openRoute("/pdu-clients")}>
                Open PDU Clients
              </button>
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
              <button type="button" className="modal-link" onClick={() => openRoute("/standa-motors")}>
                Standa Motors Control
              </button>
              <button type="button" className="modal-link" onClick={() => openBackendPage("/owis_ps90.html")}>
                OWIS PS90 Control
              </button>
            </div>
            <button onClick={() => setShowMotorizedModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}

      {/* Cameras Modal */}
      {showCamerasModal && (
        <div className="modal-overlay" onClick={() => setShowCamerasModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Cameras - Camera Controllers</h2>
            <div className="modal-links">
              <button type="button" className="modal-link" onClick={() => openRoute("/cameras-clients")}>
                Open Basler Cameras
              </button>
              <button type="button" className="modal-link" onClick={() => openRoute("/spectroscopy-clients")}>
                Open Spectroscopy
              </button>
            </div>
            <button onClick={() => setShowCamerasModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}

      {/* Magnets Modal */}
      {showMagnetsModal && (
        <div className="modal-overlay" onClick={() => setShowMagnetsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Magnets - Itest</h2>
            <div className="modal-links">
              <button type="button" className="modal-link" onClick={() => openRoute("/magnets-clients")}>
                Open Magnets Clients
              </button>
            </div>
            <button onClick={() => setShowMagnetsModal(false)} className="modal-close">Close</button>
          </div>
        </div>
      )}
      
      <div className="equipment-grid">
        {equipmentItems.map(item => (
          <div 
            className={`equipment-card ${selectedEquipment === item.id ? 'selected' : ''}`}
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
