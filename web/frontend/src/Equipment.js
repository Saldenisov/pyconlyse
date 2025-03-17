import React, { useState } from 'react';

const Equipment = () => {
  // State to track the selected equipment
  const [selectedEquipment, setSelectedEquipment] = useState(null);
  // State to hold the status message from the button click
  const [statusMessage, setStatusMessage] = useState("");

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
    setSelectedEquipment(equipmentId);
    setStatusMessage(""); // Reset the status message
  };

  // Handle button click within the widget
  const handleClick = (equipmentId) => {
    setStatusMessage(`Equipment ${equipmentId} button clicked!`);
  };

  return (
    <div>
      <h1>Equipment Page</h1>
      <div className="container">
        <div className="row">
          {/* Left Column: Equipment Images */}
          <div className="column column-left">
            <div className="grid-container">
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
