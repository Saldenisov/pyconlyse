import React, { useEffect, useRef, useState } from 'react';
import { acqVideoClient } from '../api/acqVideoClient';
import { decodeSupervisionVideo, grayscaleRgba, VIDEO_STALE_SECONDS } from './acquisitionVideoU8';
import './AcquisitionVideo.css';

const initial = () => ({ state: 'WAITING', frame: null, age: null, at: null, error: '' });
const LABELS = { WAITING: 'En attente d’image', CURRENT: 'Image récente',
  STALE: 'Image périmée', UNAVAILABLE: 'Vidéo indisponible' };

export default function AcquisitionVideo({ client = acqVideoClient, enabled = true }) {
  const [view, setView] = useState(initial);
  const [now, setNow] = useState(() => performance.now());
  const canvas = useRef(null);
  useEffect(() => {
    setView(initial());
    if (!enabled) return undefined;
    if (typeof client?.video !== 'function') {
      setView({ ...initial(), state: 'UNAVAILABLE', error: 'Client vidéo indisponible.' });
      return undefined;
    }
    const abort = new AbortController();
    let timer;
    let previous = null;
    const poll = async () => {
      const started = performance.now();
      try {
        const payload = await client.video(abort.signal);
        if (abort.signal.aborted) return;
        const decoded = decodeSupervisionVideo(payload);
        const completed = performance.now();
        let age = decoded.age === null ? null : decoded.age + Math.max(0, completed - started) / 1000;
        if (decoded.frame) {
          if (previous?.stream === decoded.stream && decoded.frame.sequence < previous.sequence) {
            throw new Error('Séquence vidéo antérieure dans la même session.');
          }
          // An unchanged frame cannot obtain a new freshness window merely
          // because HTTP/owner heartbeats delivered the same pixels again.
          if (previous?.identity === decoded.identity) {
            age = Math.max(age, previous.age + Math.max(0, completed - previous.at) / 1000);
          }
          previous = { stream: decoded.stream, identity: decoded.identity,
            sequence: decoded.frame.sequence, age, at: completed };
        }
        setNow(completed);
        setView({ ...decoded, age, at: completed, error: '' });
      } catch (error) {
        if (!abort.signal.aborted) {
          setView({ ...initial(), state: 'UNAVAILABLE', error: error.message || 'Lecture vidéo indisponible.' });
        }
      } finally {
        // Serial latest-only polling: at most one request, >=1 second between
        // completion and the next request. No queued or overlapping reads.
        if (!abort.signal.aborted) timer = setTimeout(poll, 1000);
      }
    };
    poll();
    const clock = setInterval(() => setNow(performance.now()), 250);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client, enabled]);

  const age = view.age === null ? null : view.age + Math.max(0, now - view.at) / 1000;
  const state = !enabled ? 'UNAVAILABLE' : view.state === 'CURRENT'
    && age >= VIDEO_STALE_SECONDS ? 'STALE' : view.state;
  const current = state === 'CURRENT' && view.frame !== null;
  useEffect(() => {
    if (!current || !canvas.current) return;
    try {
      const context = canvas.current.getContext('2d');
      if (!context) throw new Error('Affichage Canvas indisponible.');
      const image = context.createImageData(view.frame.width, view.frame.height);
      image.data.set(grayscaleRgba(view.frame.pixels));
      context.putImageData(image, 0, 0);
    } catch (error) {
      setView({ ...initial(), state: 'UNAVAILABLE', error: error.message || 'Affichage de l’image impossible.' });
    }
  }, [current, view.frame]);

  return <section className="acquisition-video" aria-label="Caméra SuperVision">
    <header><h2>Caméra SuperVision</h2><span>Lecture seule · NI1409</span></header>
    <p className={`acquisition-video__status acquisition-video__status--${state.toLowerCase()}`}
      role="status" aria-label="État vidéo SuperVision">{LABELS[state]}</p>
    {view.error && <p role="alert" className="acquisition-video__error">{view.error}</p>}
    {current ? <figure>
      <canvas ref={canvas} width={view.frame.width} height={view.frame.height}
        role="img" aria-label="Image caméra SuperVision actuelle" />
      <figcaption>{view.frame.width} × {view.frame.height} · U8 brut · canal {view.frame.channel}
        {' · '}observation {view.frame.sequence} · âge {age.toFixed(2)} s
        {' · '}{view.frame.source === 'labview_supervision_ni1409' ? 'LabVIEW' : 'Python'}</figcaption>
    </figure> : <div className="acquisition-video__empty">
      {state === 'STALE' ? 'Aucune image actuelle : la dernière observation a expiré.'
        : 'Aucune image actuelle disponible.'}
    </div>}
  </section>;
}
