// NetioExample.js - Example usage of DSNetioPDUClient
import React from 'react';
import DSNetioPDUClient from './DSNetioPDUClient';

const NetioExample = () => {
  // Define your 5 NETIO device names here
  // Replace these with actual Tango device names from your system
  const netioDevices = [
    'elyse/pdu/netio1',
    'elyse/pdu/netio2',
    'elyse/pdu/netio3',
    'elyse/pdu/netio4',
    'elyse/pdu/netio5'
  ];

  return (
    <div style={{ padding: '20px' }}>
      <DSNetioPDUClient deviceNames={netioDevices} />
    </div>
  );
};

export default NetioExample;
