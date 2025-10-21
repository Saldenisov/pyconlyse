// App.js
import React from 'react';
import './css/styles.css'; // Import your CSS file
import Navbar from './Navbar';  // Import the Navbar component
import Home from './Home';
import Dashboard from './Dashboard';
import Settings from './Settings';
import Equipment from './Equipment';
import Tango from './Tango';
import Elyse from "./Elyse";
import DataTreatment from "./DataTreatment";
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  return (
    <Router>
      <div>
        <Navbar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/equipment" element={<Equipment />} />
          <Route path="/elyse" element={<Elyse />} />
          <Route path="/tango" element={<Tango />} />
          <Route path="/datatreatment" element={<DataTreatment />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
