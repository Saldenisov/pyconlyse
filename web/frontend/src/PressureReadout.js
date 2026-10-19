import React from 'react';

// Display-only rounding. Never clamp signed calibrated values or round a
// small pressure to a decimal zero; keep the scientific exponent explicit.
export function pressureParts(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  if (value === 0) return { mantissa: '0,0', exponent: null };
  const [mantissa, exponent] = value.toExponential(1).split('e');
  return { mantissa: mantissa.replace('.', ','), exponent: String(Number(exponent)).replace('-', '−') };
}

export default function PressureReadout({ value, label }) {
  const parts = pressureParts(value);
  return <div className="elyse-pressure__reading">
    <output aria-label={label} title={parts ? `Valeur avant arrondi : ${value} mbar` : 'Mesure indisponible'}>
      {parts ? <><span className="elyse-pressure__mantissa">{parts.mantissa}</span>
        {parts.exponent !== null && <span className="elyse-pressure__power"> × 10<sup>{parts.exponent}</sup></span>}</> : '—'}
    </output><span className="elyse-pressure__unit">mbar</span>
  </div>;
}
