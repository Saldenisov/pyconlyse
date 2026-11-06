import React from 'react';

export default function TreatmentError({ message }) {
  if (!message) return null;
  return (
    <p className="treatment-error" role="alert">
      {message}
    </p>
  );
}
