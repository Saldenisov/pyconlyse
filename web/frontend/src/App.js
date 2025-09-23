// App.js
import React, { useEffect, useState } from 'react';
import './css/styles.css'; // Import your CSS file
import Navbar from './Navbar';  // Import the Navbar component
import Home from './Home';
import Dashboard from './Dashboard';
import Settings from './Settings';
import Equipment from './Equipment';
import Tango from './Tango';
import Elyse from "./Elyse";
import DataTreatment from "./DataTreatment";
import Login from "./Login";  // Ensure Login.js is created
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    // Check authentication status by calling a protected endpoint
    fetch('/api/status', { credentials: 'include' })
      .then((res) => {
        if (res.ok) {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
        }
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  // While checking auth, show loading.
  if (isAuthenticated === null) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      <div>
        {/* Show Navbar only when authenticated, passing the setIsAuthenticated function */}
        {isAuthenticated && <Navbar setIsAuthenticated={setIsAuthenticated} />}
        <Routes>
          <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/" />} />
          <Route path="/" element={isAuthenticated ? <Home /> : <Navigate to="/login" />} />
          <Route path="/equipment" element={isAuthenticated ? <Equipment /> : <Navigate to="/login" />} />
          <Route path="/elyse" element={isAuthenticated ? <Elyse /> : <Navigate to="/login" />} />
          <Route path="/tango" element={isAuthenticated ? <Tango /> : <Navigate to="/login" />} />
          <Route path="/datatreatment" element={isAuthenticated ? <DataTreatment /> : <Navigate to="/login" />} />
          <Route path="/dashboard" element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" />} />
          <Route path="/settings" element={isAuthenticated ? <Settings /> : <Navigate to="/login" />} />
          {/* Fallback route */}
          <Route path="*" element={<Navigate to={isAuthenticated ? "/" : "/login"} />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
