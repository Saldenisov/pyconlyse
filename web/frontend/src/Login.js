// Login.js
import React, { useState } from 'react';
import { Helmet } from 'react-helmet';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password })
      });
      if (response.ok) {
        // Instead of using navigate, force a full page reload to home page
        window.location.href = '/';
      } else {
        const data = await response.json();
        setError(data.msg || 'Login failed');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    }
  };

  return (
    <div>
      <Helmet>
        <title>Login - Pyconlyse Project</title>
      </Helmet>
      <h1>Login</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label>Username:</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Password:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button type="submit">Login</button>
      </form>
    </div>
  );
};

export default Login;
