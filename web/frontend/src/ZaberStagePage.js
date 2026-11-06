import React from 'react';
import VD2TranslationStages from './components/VD2TranslationStages';

export default function ZaberStagePage() {
  return (
    <main className="vd2-stage-page" style={{ maxWidth: 1100, margin: '2rem auto', padding: '0 1rem' }}>
      <h1>Zaber stage control</h1>
      <p>VD2 source-selection mirror on Elysium2. Commands and positions use millimetres.</p>
      <VD2TranslationStages showOwis={false} />
    </main>
  );
}
