import React from 'react';
import './FrameDisplayRate.css';

export default function FrameDisplayRate({ hz }) {
  return <span className="frame-display-rate" aria-label="Frame display rate"
    title="New frames drawn in this view per second; independent of camera trigger rate">
    Display {Number.isFinite(hz) && hz > 0 ? hz.toFixed(1) : '0.0'} Hz
  </span>;
}
