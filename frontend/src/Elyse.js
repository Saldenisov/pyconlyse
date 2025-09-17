// src/Elyse.js
import React, { useState } from 'react';
import Synchronization from './tabs/Synchronization';
import Modulator from './tabs/Modulator';
import HT from "./tabs/HT";
import Fluides from "./tabs/Fluides";
// Import other tab components as needed

const tabs = [
  "Vacuum",
  "Fluides",
  "Modulator",
  "HT",
  "HF",
  "Power_Supply",
  "Synchronization",
  "Radioprotection",
  "Monitoring",
  "Cameras",
  "Magnets",
  "Experiment"
];

const Elyse = () => {
  const [activeTab, setActiveTab] = useState(tabs[0]);

  const handleTabClick = (tab) => {
    setActiveTab(tab);
  };

  // Render the content for the active tab.
  // For "Modulator" and "Synchronization", render their dedicated components.
  const renderTabContent = (tab) => {
    switch (tab) {
      case "Modulator":
        return <Modulator />;
      case "Synchronization":
        return <Synchronization />;
      case "HT":
        return <HT />;
      case "Fluides":
        return <Fluides />;
      // Add additional cases for other tabs if you create dedicated components.
      default:
        return <div>Content for {tab}</div>;
    }
  };

  return (
    <div>
      <h1>ELYSE Control Panel</h1>
      <ul className="nav nav-tabs" id="elyseTabs" role="tablist">
        {tabs.map((tab) => {
          const lowerTab = tab.toLowerCase();
          return (
            <li className="nav-item" role="presentation" key={tab}>
              <a
                className={`nav-link ${activeTab === tab ? "active" : ""}`}
                id={`${lowerTab}-tab`}
                onClick={() => handleTabClick(tab)}
                role="tab"
                aria-controls={lowerTab}
                aria-selected={activeTab === tab ? "true" : "false"}
                style={{ cursor: "pointer" }}
              >
                {tab}
              </a>
            </li>
          );
        })}
      </ul>
      <div className="tab-content" id="elyseTabsContent">
        {tabs.map((tab) => {
          const lowerTab = tab.toLowerCase();
          return (
            <div
              key={tab}
              className={`tab-pane fade ${activeTab === tab ? "show active" : ""}`}
              id={lowerTab}
              role="tabpanel"
              aria-labelledby={`${lowerTab}-tab`}
            >
              {activeTab === tab && renderTabContent(tab)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Elyse;
