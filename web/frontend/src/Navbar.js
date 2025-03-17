// src/Navbar.js
import React from 'react';
import { Link } from 'react-router-dom';

const Navbar = () => (
  <header>
    <img src="/images/pyconlyse_logo.png" alt="Pyconlyse Logo" className="logo" />
    <nav>
      <ul>
        <li><Link to="/">Home</Link></li>
        <li><Link to="/pyconlyse">Pyconlyse</Link></li>
        <li><Link to="/equipment">Equipment</Link></li>
        <li><Link to="/elyse">ELYSE</Link></li>
        <li><Link to="/tango">Tango</Link></li>
        <li><Link to="/datatreatment">Data Treatment</Link></li>
        <li><Link to="/dashboard">Dashboard</Link></li>
        <li><Link to="/settings">Settings</Link></li>
      </ul>
    </nav>
  </header>
);

export default Navbar;
