import React from 'react';
import ITestPSUClient from './ITestPSUClient';
import './ITestBeamLinePanel.css';

export default function ITestBeamLinePanel({ tab, deviceName = 'elyse/pdu/itest', readOnly = false }) {
  return <ITestPSUClient key={`${deviceName.toLowerCase()}:${tab}`} deviceName={deviceName}
    fixedTab={tab} compact readOnly={readOnly} beamline />;
}
