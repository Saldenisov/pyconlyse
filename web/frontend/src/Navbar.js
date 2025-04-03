// Navbar.js
import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Navbar = ({ setIsAuthenticated }) => {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      const response = await fetch('/api/logout', {
        method: 'POST',
        credentials: 'include'
      });
      if (response.ok) {
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        console.error('Failed to logout');
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return (
    <nav className="navbar-container"> {/* Use your original container class */}
      <ul className="navbar-list"> {/* If you previously used an unordered list for styling */}
        <li><Link to="/">Home</Link></li>
        <li><Link to="/equipment">Equipment</Link></li>
        <li><Link to="/dashboard">Dashboard</Link></li>
        <li><Link to="/settings">Settings</Link></li>
        <li><Link to="/tango">Tango</Link></li>
        <li><Link to="/elyse">Elyse</Link></li>
        <li><Link to="/datatreatment">Data Treatment</Link></li>
        <li><button onClick={handleLogout}>Logout</button></li>
      </ul>
    </nav>
  );
};

export default Navbar;
