import React from 'react';
import { Helmet } from 'react-helmet';

const Home = () => {
  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '3rem 2rem',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
    }}>
      <Helmet>
        <title>Home - Pyconlyse Project</title>
      </Helmet>
      
      <header style={{
        textAlign: 'center',
        marginBottom: '3rem'
      }}>
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: '700',
          color: '#1a202c',
          marginBottom: '1rem'
        }}>
          Welcome to PYCONLYSE
        </h1>
        <p style={{
          fontSize: '1.25rem',
          color: '#4a5568',
          maxWidth: '800px',
          margin: '0 auto',
          lineHeight: '1.6'
        }}>
          A comprehensive distributed control system for scientific instrumentation in the ELYSE experiment
        </p>
      </header>

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '2rem'
      }}>
        <img
          src="/images/hero_background.png"
          alt="PYCONLYSE System"
          style={{
            width: '100%',
            maxWidth: '600px',
            height: 'auto',
            borderRadius: '8px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}
        />

        <section style={{
          backgroundColor: '#f7fafc',
          padding: '2rem',
          borderRadius: '8px',
          width: '100%',
          maxWidth: '900px'
        }}>
          <h2 style={{
            fontSize: '1.75rem',
            fontWeight: '600',
            color: '#2d3748',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}>
            System Overview
          </h2>
          
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '1.5rem',
            marginBottom: '2rem'
          }}>
            <div style={{
              backgroundColor: 'white',
              padding: '1.5rem',
              borderRadius: '6px',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
            }}>
              <h3 style={{
                fontSize: '1.125rem',
                fontWeight: '600',
                color: '#2b6cb0',
                marginBottom: '0.75rem'
              }}>
                🎯 Distributed Architecture
              </h3>
              <p style={{
                color: '#4a5568',
                fontSize: '0.95rem',
                lineHeight: '1.5'
              }}>
                PyTango-based framework providing robust, scalable control of scientific instruments across the network
              </p>
            </div>

            <div style={{
              backgroundColor: 'white',
              padding: '1.5rem',
              borderRadius: '6px',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
            }}>
              <h3 style={{
                fontSize: '1.125rem',
                fontWeight: '600',
                color: '#2b6cb0',
                marginBottom: '0.75rem'
              }}>
                🔬 Multi-Device Support
              </h3>
              <p style={{
                color: '#4a5568',
                fontSize: '0.95rem',
                lineHeight: '1.5'
              }}>
                Control cameras (ANDOR, Basler, Avantes), motion systems (OWIS, Standa), power management, and data acquisition devices
              </p>
            </div>

            <div style={{
              backgroundColor: 'white',
              padding: '1.5rem',
              borderRadius: '6px',
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
            }}>
              <h3 style={{
                fontSize: '1.125rem',
                fontWeight: '600',
                color: '#2b6cb0',
                marginBottom: '0.75rem'
              }}>
                🌐 Real-Time Monitoring
              </h3>
              <p style={{
                color: '#4a5568',
                fontSize: '0.95rem',
                lineHeight: '1.5'
              }}>
                WebSocket-enabled interface for live device status updates, measurements, and remote control capabilities
              </p>
            </div>
          </div>

          <div style={{
            textAlign: 'center',
            padding: '1.5rem',
            backgroundColor: 'white',
            borderRadius: '6px',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)'
          }}>
            <p style={{
              color: '#2d3748',
              fontSize: '1rem',
              lineHeight: '1.6',
              marginBottom: '1rem'
            }}>
              <strong>PYCONLYSE</strong> provides a complete solution for controlling and monitoring scientific instruments 
              in the ELYSE experiment. Built with Python, PyTango, Flask, and React, it offers both desktop and web-based 
              interfaces for seamless experiment control, data acquisition, and real-time analysis.
            </p>
            <p style={{
              color: '#4a5568',
              fontSize: '0.9rem',
              fontStyle: 'italic'
            }}>
              Designed for researchers, by researchers
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Home;
