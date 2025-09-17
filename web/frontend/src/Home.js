import React from 'react';
import { Helmet } from 'react-helmet'; // Optional for managing the page title

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
    </div>
  );
};

export default Home;
