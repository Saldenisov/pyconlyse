// Navbar.js
import React from 'react';
import { Link } from 'react-router-dom';

const Navbar = () => {
  return (
    <nav className="navbar-container"> {/* Use your original container class */}
      <ul className="navbar-list"> {/* If you previously used an unordered list for styling */}
        <li><Link to="/">Home</Link></li>
        <li><Link to="/equipment">Equipment</Link></li>
        <li><Link to="/dashboard">Dashboard</Link></li>
        <li><Link to="/settings">Settings</Link></li>
        <li><Link to="/elyse">Elyse</Link></li>
        <li><Link to="/datatreatment">Data Treatment</Link></li>
        <li><Link to="/pump-probe-v0">Pump-Probe V0</Link></li>
        <li><Link to="/device-clients">Device Clients</Link></li>
        <li><Link to="/login">Login</Link></li>
      </ul>
    </nav>
  );
};

export default Navbar;
