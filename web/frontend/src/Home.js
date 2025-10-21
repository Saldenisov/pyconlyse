import React from 'react';
import { Helmet } from 'react-helmet'; // Optional for managing the page title
import { Link } from 'react-router-dom';

const Home = () => {
  return (
    <div>
      <Helmet>
        <title>Home - Pyconlyse Project</title>
      </Helmet>
      <h1>Welcome to Pyconlyse Project</h1>
      <h2>We work to bring food closer to you...</h2>
      <img
        src="/images/hero_background.png"
        alt="Hero Background"
        style={{ width: "8cm" }}
      />
      <div style={{ marginTop: '2rem' }}>
        <Link to="/equipment" style={{ 
          display: 'inline-block', 
          padding: '10px 20px', 
          backgroundColor: '#007bff', 
          color: 'white', 
          textDecoration: 'none', 
          borderRadius: '5px',
          marginRight: '10px'
        }}>
          Go to Equipment
        </Link>
        <a href="/test_ds_itest_psu.html" style={{ 
          display: 'inline-block', 
          padding: '10px 20px', 
          backgroundColor: '#28a745', 
          color: 'white', 
          textDecoration: 'none', 
          borderRadius: '5px'
        }}>
          Go to Itest Client
        </a>
      </div>
    </div>
  );
};

export default Home;
