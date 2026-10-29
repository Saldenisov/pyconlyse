import React, { useEffect, useRef, useState } from 'react';
import { acqVideoClient } from '../api/acqVideoClient';
import { decodeSupervisionVideo, grayscaleRgba, VIDEO_STALE_SECONDS } from './acquisitionVideoU8';
import './AcquisitionVideo.css';

const initial = () => ({ state: 'WAITING', frame: null, age: null, at: null, error: '' });
const LABELS = { WAITING: 'En attente d’image', CURRENT: 'Image récente',
  STALE: 'Image périmée', UNAVAILABLE: 'Vidéo indisponible' };

const finitePoint = (point) => Number.isFinite(point?.x) && Number.isFinite(point?.y);
const sameCameraFrame = (row, frame) => row && frame && row.channel === frame.channel
  && row.capture_session_id === frame.captureSessionId
  && row.source_session_id === (frame.sourceSessionId || frame.ownerSessionId)
  && row.source_kind === frame.source && row.processing === frame.processing
  && row.sequence === frame.sequence;

export default function AcquisitionVideo({ client = acqVideoClient, enabled = true, channel,
  targetFps = 25, title = 'Caméra SuperVision', diagnostics, onObservation,
  onSaveReference, savingReference = false, radiusPx = 10, onRadiusChange }) {
  const [view, setView] = useState(initial);
  const [now, setNow] = useState(() => performance.now());
  const canvas = useRef(null);
  const notify = useRef(onObservation);
  notify.current = onObservation;
  useEffect(() => {
    setView(initial());
    if (!enabled) return undefined;
    if (typeof client?.video !== 'function' && typeof client?.subscribe !== 'function') {
      setView({ ...initial(), state: 'UNAVAILABLE', error: 'Client vidéo indisponible.' });
      return undefined;
    }
    const abort = new AbortController();
    let timer;
    let previous = null;
    let arrivals = [];
    const fps = targetFps === 12.5 ? 12.5 : 25;
    const accept = (payload, started = performance.now()) => {
      if (abort.signal.aborted) return;
      const decoded = decodeSupervisionVideo(payload);
      const completed = performance.now();
      let age = decoded.age === null ? null : decoded.age + Math.max(0, completed - started) / 1000;
      if (decoded.frame) {
        if (Number.isInteger(channel) && decoded.frame.channel !== channel) {
          throw new Error('La source reçue ne correspond pas au canal caméra demandé.');
        }
        if (previous?.stream === decoded.stream && decoded.frame.sequence < previous.sequence) {
          throw new Error('Séquence vidéo antérieure dans la même session.');
        }
        if (previous?.identity === decoded.identity) {
          age = Math.max(age, previous.age + Math.max(0, completed - previous.at) / 1000);
        } else {
          arrivals = [...arrivals.filter((at) => completed - at <= 2000), completed];
        }
        const frame = previous?.identity === decoded.identity ? previous.frame
          : { ...decoded.frame, ownerSessionId: payload.session_id, processing: payload.frame.processing };
        previous = { stream: decoded.stream, identity: decoded.identity,
          sequence: decoded.frame.sequence, frame, age, at: completed };
      }
      const receivedFps = arrivals.length > 1 && arrivals.at(-1) > arrivals[0]
        ? (arrivals.length - 1) * 1000 / (arrivals.at(-1) - arrivals[0]) : null;
      setNow(completed);
      // Source status and displayed pixels have separate lifetimes.
      setView({ ...decoded, frame: previous?.frame || null,
        age: previous?.age ?? age, at: previous?.at ?? completed, error: '',
        diagnostics: payload.diagnostics || null, receivedFps });
      notify.current?.({ payload, frame: previous?.frame || null,
        identity: decoded.identity, state: decoded.state, at: completed });
    };
    const reject = (error) => {
      if (!abort.signal.aborted) {
        setNow(performance.now());
        setView((retained) => ({ ...retained, state: 'UNAVAILABLE',
          error: error.message || 'Lecture vidéo indisponible.' }));
      }
    };
    const poll = async () => {
      const started = performance.now();
      let failed = false;
      try {
        accept(await client.video(abort.signal, { channel }), started);
      } catch (error) {
        failed = true;
        reject(error);
      } finally {
        // No overlap; a successful read does not add a one-second delay.
        if (!abort.signal.aborted) timer = setTimeout(poll,
          failed ? 250 : Math.max(0, 1000 / fps - (performance.now() - started)));
      }
    };
    let unsubscribe;
    if (typeof client.subscribe === 'function') {
      try {
        unsubscribe = client.subscribe({ signal: abort.signal, channel, targetFps: fps,
          onFrame: (payload) => { try { accept(payload); } catch (error) { reject(error); } },
          onError: reject });
      } catch (error) { if (typeof client.video === 'function') poll(); else reject(error); }
    } else poll();
    const clock = setInterval(() => setNow(performance.now()), 250);
    return () => { abort.abort(); if (typeof unsubscribe === 'function') unsubscribe(); clearTimeout(timer); clearInterval(clock); };
  }, [client, enabled, channel, targetFps]);

  const age = view.age === null ? null : view.age + Math.max(0, now - view.at) / 1000;
  const state = !enabled ? 'UNAVAILABLE' : view.state === 'CURRENT'
    && age >= VIDEO_STALE_SECONDS ? 'STALE' : view.state;
  const retainedFrame = enabled ? view.frame : null;
  const frameDiagnostics = sameCameraFrame(view.diagnostics, retainedFrame) ? view.diagnostics
    : sameCameraFrame(diagnostics, retainedFrame) ? diagnostics : null;
  const currentPoint = state === 'CURRENT' && frameDiagnostics?.current?.valid === true
    && frameDiagnostics.current.quality === 'CURRENT' && finitePoint(frameDiagnostics.current)
    && frameDiagnostics.current.age_seconds < VIDEO_STALE_SECONDS
    && frameDiagnostics.current.x >= 0 && frameDiagnostics.current.x < retainedFrame.width
    && frameDiagnostics.current.y >= 0 && frameDiagnostics.current.y < retainedFrame.height
    ? frameDiagnostics.current : null;
  const referenceCandidates = [view.diagnostics, diagnostics]
    .filter((row) => row && retainedFrame && row.channel === retainedFrame.channel)
    .map((row) => row.reference)
    .filter((item) => retainedFrame && finitePoint(item) && item.width === retainedFrame.width
      && item.height === retainedFrame.height && Number.isFinite(item.radius_px) && item.radius_px > 0);
  const boundReferences = referenceCandidates.filter((item) => item.source_kind === retainedFrame.source
    && item.processing === retainedFrame.processing);
  const reference = boundReferences.sort((a, b) => b.revision - a.revision)[0] || null;
  const storedReference = [view.diagnostics?.reference, diagnostics?.reference]
    .filter((item) => finitePoint(item)).sort((a, b) => b.revision - a.revision)[0] || null;
  const distance = currentPoint && reference
    ? Math.hypot(currentPoint.x - reference.x, currentPoint.y - reference.y) : null;
  const inside = distance !== null && distance <= reference.radius_px;
  useEffect(() => {
    if (!retainedFrame || !canvas.current) return;
    try {
      const context = canvas.current.getContext('2d');
      if (!context) throw new Error('Affichage Canvas indisponible.');
      const image = context.createImageData(retainedFrame.width, retainedFrame.height);
      image.data.set(grayscaleRgba(retainedFrame.pixels));
      context.putImageData(image, 0, 0);
    } catch (error) {
      setView({ ...initial(), state: 'UNAVAILABLE', error: error.message || 'Affichage de l’image impossible.' });
    }
  }, [retainedFrame]);

  return <section className="acquisition-video" aria-label={title}>
    <header><h2>{title}</h2><span>NI1409 · pixels bruts</span></header>
    <p className={`acquisition-video__status acquisition-video__status--${state.toLowerCase()}`}
      role="status" aria-label="État vidéo SuperVision">{LABELS[state]}
      {retainedFrame && state !== 'CURRENT' && ' · dernière image conservée'}</p>
    {view.error && <p role="alert" className="acquisition-video__error">{view.error}</p>}
    {retainedFrame ? <figure>
      <div className="acquisition-video__image">
        <canvas ref={canvas} width={view.frame.width} height={view.frame.height}
          role="img" aria-label={`Dernière image ${title === 'Caméra SuperVision' ? 'caméra SuperVision' : title}`} />
        {(reference || currentPoint) && <svg className="acquisition-video__overlay"
          viewBox={`0 0 ${retainedFrame.width} ${retainedFrame.height}`} aria-hidden="true">
          {reference && <g className={`acquisition-video__reference${inside ? ' acquisition-video__reference--inside' : ''}`}>
            <circle data-testid="reference-tolerance" cx={reference.x} cy={reference.y}
              r={reference.radius_px} data-inside={inside ? 'true' : 'false'} />
            <path data-testid="reference-cross" d={`M ${reference.x - 7} ${reference.y} H ${reference.x + 7} M ${reference.x} ${reference.y - 7} V ${reference.y + 7}`} />
          </g>}
          {currentPoint && <circle className="acquisition-video__centroid" data-testid="current-centroid"
            cx={currentPoint.x} cy={currentPoint.y} r="3" />}
        </svg>}
      </div>
      <figcaption>{view.frame.width} × {view.frame.height} · U8 brut · canal {view.frame.channel}
        {' · '}observation {view.frame.sequence} · âge {age.toFixed(2)} s
        {' · '}{view.frame.source === 'labview_supervision_ni1409' ? 'LabVIEW' : 'Python'}
        {' · '}reçu {state === 'CURRENT' && Number.isFinite(view.receivedFps) ? view.receivedFps.toFixed(1) : '—'} image/s</figcaption>
    </figure> : <div className="acquisition-video__empty">
      {state === 'STALE' ? 'Aucune image actuelle : la dernière observation a expiré.'
        : 'Aucune image actuelle disponible.'}
    </div>}
    {typeof onSaveReference === 'function' && <div className="acquisition-video__reference-controls">
      <p>Repère de l’image affichée · pixels. Point cyan : centroïde courant.
        Croix jaune : centre enregistré. Cercle : tolérance.</p>
      <label>Rayon de tolérance (pixels)<input type="number" min="1" max="512" step="1"
        value={radiusPx} onChange={(event) => onRadiusChange?.(event.target.value)} /></label>
      <button type="button" disabled={!currentPoint || savingReference || !Number.isFinite(Number(radiusPx))
        || Number(radiusPx) < 1 || Number(radiusPx) > 512}
        onClick={() => onSaveReference(frameDiagnostics)}>Enregistrer le centre</button>
      <output aria-label="Position du centroïde">{currentPoint
        ? `x ${currentPoint.x.toFixed(2)} · y ${currentPoint.y.toFixed(2)} px${distance === null ? '' : ` · écart ${distance.toFixed(2)} px · ${inside ? 'dans la cible' : 'hors cible'}`}`
        : 'Centroïde actuel indisponible pour cette image.'}</output>
      {storedReference && <small>Centre enregistré : x {storedReference.x.toFixed(2)}, y {storedReference.y.toFixed(2)} px · révision {storedReference.revision}</small>}
      {storedReference && retainedFrame && !reference && <small>
        Centre enregistré incompatible avec la géométrie ou le traitement de cette image.</small>}
    </div>}
  </section>;
}
