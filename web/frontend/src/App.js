// App.js
import React from 'react';
import './css/styles.css'; // Import your CSS file
import Navbar from './Navbar';  // Import the Navbar component
import Home from './Home';
import Dashboard from './Dashboard';
import Settings from './Settings';
import Equipment from './Equipment';
import Elyse from "./Elyse";
import DataTreatment from "./DataTreatment";
import StandaMotorsExample from './StandaMotorsExample';
import DeviceClients from './DeviceClients';
import PDUClients from './PDUClients';
import MagnetsClients from './MagnetsClients';
import CamerasClients from './CamerasClients';
import SpectroscopyClients from './SpectroscopyClients';
import DAQmxClients from './DAQmxClients';
import VacuumClients from './VacuumClients';
import Login from './Login';
import PumpProbeV0 from './PumpProbeV0';
import PumpProbeVD2 from './PumpProbeVD2';
import HardwareApprovalControl from './components/HardwareApprovalControl';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  return (
    <Router>
      <div>
        <Navbar />
        <HardwareApprovalControl />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/equipment" element={<Equipment />} />
          <Route path="/elyse" element={<Elyse />} />
          <Route path="/datatreatment" element={<DataTreatment />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/standa-motors" element={<StandaMotorsExample />} />
          <Route path="/device-clients" element={<DeviceClients />} />
          <Route path="/pdu-clients" element={<PDUClients />} />
          <Route path="/magnets-clients" element={<MagnetsClients />} />
          <Route path="/cameras-clients" element={<CamerasClients />} />
          <Route path="/spectroscopy-clients" element={<SpectroscopyClients />} />
          <Route path="/daqmx-clients" element={<DAQmxClients />} />
          <Route path="/vacuum-clients" element={<VacuumClients />} />
          <Route path="/pump-probe-v0" element={<PumpProbeV0 />} />
          <Route path="/pump-probe-vd2" element={<PumpProbeVD2 />} />
          <Route path="/login" element={<Login />} />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
