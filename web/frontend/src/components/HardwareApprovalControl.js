import React, { useEffect, useState } from 'react';
import {
  clearHardwareApprovalNonce,
  getHardwareApprovalNonce,
  setHardwareApprovalNonce,
  subscribeHardwareApprovalStatus,
} from '../api/csrfRequest';

const statusMessage = (status) => {
  if (status === 'armed') {
    return 'Hardware approval armed for one mutation attempt.';
  }
  if (status === 'consumed') {
    return 'Hardware approval consumed by a mutation attempt.';
  }
  if (status === 'cleared') {
    return 'Hardware approval cleared.';
  }
  return '';
};

const HardwareApprovalControl = () => {
  const [nonce, setNonce] = useState('');
  const [status, setStatus] = useState(() => (
    getHardwareApprovalNonce() ? statusMessage('armed') : ''
  ));

  useEffect(() => subscribeHardwareApprovalStatus((nextStatus) => {
    setStatus(statusMessage(nextStatus));
  }), []);

  const armApproval = (event) => {
    event.preventDefault();
    if (!setHardwareApprovalNonce(nonce)) {
      setStatus('Invalid approval nonce. Enter exactly 64 lowercase hexadecimal characters.');
      return;
    }
    setNonce('');
  };

  const clearApproval = () => {
    clearHardwareApprovalNonce();
    setNonce('');
  };

  return (
    <form onSubmit={armApproval} aria-label="Hardware approval">
      <label htmlFor="hardware-approval-nonce">Hardware approval nonce</label>
      <input
        id="hardware-approval-nonce"
        value={nonce}
        onChange={(event) => setNonce(event.target.value)}
        autoComplete="off"
        spellCheck="false"
        aria-describedby="hardware-approval-status"
      />
      <button type="submit">Arm one mutation</button>
      <button type="button" onClick={clearApproval}>Clear approval</button>
      <output id="hardware-approval-status" aria-live="polite">{status}</output>
    </form>
  );
};

export default HardwareApprovalControl;
