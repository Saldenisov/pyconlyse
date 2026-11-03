"""Everest operator alarm. READS Tango only; never sends machine commands.

Interactive Windows process, independent of Flask/browser and database writer.
CANON/SECTION polarity follows SuperVision's saved Fluides panel. Only fresh
Chauffage ON and regulation/cooling ON together enable this alarm. Red inputs
outside that operating scope do not alarm. Unknown data cannot clear an
incident. This annunciator is not the hardware interlock or shutdown policy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import uuid

try:
    if __package__:
        from .elyse_cooling_temperature import TemperatureWatch
    else:
        from elyse_cooling_temperature import TemperatureWatch
except (ImportError, SyntaxError):
    TemperatureWatch = None  # report optional warning failure; keep 220V alarm

DEVICE = 'tango://10.20.30.202:10000/elyse/acquisition/telemetry'
CIRCUITS = {'CANON': 0, 'SECTION': 6}
POLICY_VERSION = 3
REGULATION_OK_INDEX = 2
CHAUFFAGE_OK_INDEX = 14
MAX_AGE = 2.0
RECOVERY_SECONDS = 2.0
DEFAULT_DIRECTORY = Path(r'F:\ELYSE_Telemetry_Server\cooling_alert')


def utc():
    return datetime.now(timezone.utc).isoformat()


class CoolingAlert:
    """Deterministic, independently testable transition detector."""
    def __init__(self, saved=None):
        saved = saved if isinstance(saved, dict) else {}
        self.general = saved.get('general') is True
        # Previous General-only arming cannot authorize a new-policy alarm.
        saved = saved if saved.get('policy_version') in (2, POLICY_VERSION) else {}
        self.chauffage = saved.get('chauffage') is True
        self.regulation = saved.get('regulation') is True
        self.operating = self.chauffage and self.regulation
        self.armed = set(saved.get('armed', [])) & set(CIRCUITS)
        self.faults = set(saved.get('faults', [])) & set(CIRCUITS)
        self.recovering = {}
        self.progress = {}
        self.episode = saved.get('episode', '') if self.faults else ''
        self.previous_reasons = ()
        self.temperature_error = ''
        try:
            self.temperature_watch = TemperatureWatch(saved=saved.get('temperature_alerts', []))
        except (OSError, ValueError, TypeError) as exc:
            # Optional warning configuration must not take down the 220V alarm.
            self.temperature_watch = None
            self.temperature_error = str(exc)

    def bank(self, publications, name, size, now, kind='boolean'):
        record = publications.get(name, {})
        age, values = record.get('age_seconds'), record.get('data')
        identity = (record.get('session_id'), record.get('sequence'))
        error = record.get('error', {})
        if (record.get('stale') is not False or type(age) not in (int, float)
                or not math.isfinite(age) or not 0 <= age < MAX_AGE
                or error.get('status') is not False or type(error.get('code')) is not int
                or error.get('code') != 0 or type(values) is not list or len(values) != size
                or any((type(value) is not bool if kind == 'boolean' else
                        type(value) not in (float, int) or not math.isfinite(value)) for value in values)
                or not isinstance(identity[0], str) or not identity[0]
                or type(identity[1]) is not int or identity[1] < 0):
            return None
        old_identity, changed = self.progress.get(name, (None, now))
        if old_identity != identity:
            changed = now
        self.progress[name] = identity, changed
        # Also reject frozen replies falsely advertising age=0 on every read.
        if now - changed >= MAX_AGE:
            return None
        return values

    def update(self, publications=None, *, now=None, error=''):
        now = time.monotonic() if now is None else now
        publications = publications if isinstance(publications, dict) else {}
        eps = self.bank(publications, 'EPS', 77, now) if not error else None
        c3 = self.bank(publications, 'C3_IN_DIO96', 56, now) if not error else None
        # Do not pair a previous owner session with the current owner.
        if (eps is not None and c3 is not None and publications['EPS']['session_id']
                != publications['C3_IN_DIO96']['session_id']):
            c3 = None
        if eps is not None:
            self.general = eps[8]
            self.chauffage = eps[CHAUFFAGE_OK_INDEX]
            self.regulation = eps[REGULATION_OK_INDEX]
            self.operating = self.chauffage and self.regulation
        unknown = eps is None or (self.operating and c3 is None)
        if eps is not None and not self.operating:
            self.armed.clear()
            self.faults.clear()
            self.recovering.clear()
        elif self.operating and c3 is not None and eps is not None:
            for name, index in CIRCUITS.items():
                self.armed.add(name)
                if c3[index] is False:
                    if name in self.faults:
                        since = self.recovering.setdefault(name, now)
                        if now - since >= RECOVERY_SECONDS:
                            self.faults.discard(name)
                            self.recovering.pop(name, None)
                else:
                    self.recovering.pop(name, None)
                    self.faults.add(name)
        if unknown:
            self.recovering.clear()
        readings = {}
        if eps is not None and self.operating:
            temperatures = self.bank(publications, 'C1NI6071E', 64, now, 'number')
            setpoints = self.bank(publications, 'C8NI6703', 10, now, 'number')
            if (temperatures is not None and setpoints is not None
                    and publications['C1NI6071E']['session_id'] == publications['C8NI6703']['session_id']
                    == publications['EPS']['session_id']):
                key = (publications['EPS']['session_id'], publications['C1NI6071E']['sequence'],
                       publications['C8NI6703']['sequence'])
                readings = {name: (temperatures[t], setpoints[s], key)
                            for name, t, s in (('CANON', 0, 1), ('SECTION', 8, 2))}
        thermal = (self.temperature_watch.update(self.operating if eps is not None else None, readings, now)
                   if self.temperature_watch is not None else dict(warnings=[], quality={}, policy={}))
        reasons = (tuple(sorted(self.faults)) + (('TELEMETRY',) if unknown and self.operating else ())
                   + tuple('TEMPERATURE:' + item['circuit'] for item in thermal['warnings']))
        # A new/escalated cause bypasses a previous silence interval.
        if reasons and (not self.episode or set(reasons) - set(self.previous_reasons)):
            self.episode = uuid.uuid4().hex
        elif not reasons:
            self.episode = ''
        self.previous_reasons = reasons
        return dict(schema_version=1, policy_version=POLICY_VERSION, observed_utc=utc(), general=self.general,
                    chauffage=self.chauffage, regulation=self.regulation, operating=self.operating,
                    armed=sorted(self.armed), faults=sorted(self.faults), reasons=list(reasons),
                    active=bool(reasons), episode=self.episode,
                    temperature_alerts=thermal['warnings'], temperature_quality=thermal['quality'],
                    temperature_policy=thermal['policy'], temperature_error=self.temperature_error,
                    severity='ALARM' if self.faults or unknown and self.operating else
                             'WARNING' if thermal['warnings'] else 'NORMAL',
                    quality='UNKNOWN' if unknown else 'FRESH', source_error=error,
                    cold_red=[name for name, index in CIRCUITS.items()
                              if not self.operating and c3 is not None and c3[index]])


def read_saved(path):
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        return result if result.get('schema_version') == 1 else {}
    except (OSError, ValueError, AttributeError):
        return {}


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def read_loop(output, stop, device):
    """One bounded synchronous read at a time; reconnect after any failure."""
    proxy = None
    while not stop.is_set():
        started = time.monotonic()
        try:
            if proxy is None:
                import tango
                proxy = tango.DeviceProxy(device)
                proxy.set_timeout_millis(1500)
            sample = json.loads(proxy.read_attribute('telemetry_json').value)
            item = (time.monotonic(), sample.get('publications', {}), '')
        except Exception as exc:
            proxy = None
            item = (time.monotonic(), {}, '%s: %s' % (type(exc).__name__, str(exc)[:350]))
        try:
            output.get_nowait()
        except queue.Empty:
            pass
        output.put_nowait(item)
        stop.wait(max(0.05, 0.5 - (time.monotonic() - started)))


def sound_loop(enabled, stop, audio_status):
    import winsound
    next_beep, last_kind = 0, None
    while not stop.is_set():
        kind, now = audio_status.get('kind', 'ALARM'), time.monotonic()
        if enabled.is_set() and (now >= next_beep or kind != last_kind):
            try:
                winsound.Beep(900 if kind == 'WARNING' else 1200, 200)
                if enabled.is_set() and kind != 'WARNING':
                    winsound.Beep(900, 200)
                audio_status['last_success_utc'] = utc()
                audio_status['error'] = ''
            except Exception as exc:
                audio_status['error'] = '%s: %s' % (type(exc).__name__, exc)
            next_beep, last_kind = now + (5 if kind == 'WARNING' else 1.6), kind
        if not enabled.is_set():
            last_kind = None
        stop.wait(0.1)


def run(directory, device, show=False):
    import msvcrt
    import tkinter as tk
    directory.mkdir(parents=True, exist_ok=True)
    # A second launch brings up the existing monitor instead of duplicating sound.
    lock = (directory / 'monitor.lock').open('a+b')
    # Do not read the byte: Windows denies even a read while another instance
    # owns its byte-range lock. File size is available without touching it.
    if os.fstat(lock.fileno()).st_size == 0:
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        if show:
            (directory / 'show.request').write_text(utc(), encoding='ascii')
        lock.close()
        return
    state_path = directory / 'status.json'
    policy = CoolingAlert(read_saved(state_path))
    root = tk.Tk()
    root.title('ELYSE — surveillance refroidissement')
    root.geometry('800x460')
    root.configure(bg='#163527')
    title = tk.StringVar(value='Surveillance refroidissement — démarrage')
    detail = tk.StringVar(value='Lecture seule Tango · aucune commande matérielle')
    sound_text = tk.StringVar(value='')
    tk.Label(root, textvariable=title, bg='#163527', fg='white', font=('Arial', 20, 'bold'),
             wraplength=700).pack(padx=18, pady=(22, 12))
    tk.Label(root, textvariable=detail, bg='#163527', fg='white', font=('Arial', 13),
             wraplength=700, justify='left').pack(padx=18, pady=8)
    tk.Label(root, textvariable=sound_text, bg='#163527', fg='white', font=('Arial', 12)).pack(pady=8)
    buttons = tk.Frame(root, bg='#163527')
    buttons.pack(pady=12)
    output, stop, audible = queue.Queue(maxsize=1), threading.Event(), threading.Event()
    audio_status = {'error': '', 'last_success_utc': None}
    threading.Thread(target=read_loop, args=(output, stop, device), daemon=True).start()
    threading.Thread(target=sound_loop, args=(audible, stop, audio_status), daemon=True).start()
    state = dict(started=time.monotonic(), silenced_until=0.0, test_until=0.0, last_item=None, last_episode='',
                 visible=show, last_saved=0.0, previous_event=None, was_sounding=False)

    def silence():
        state['silenced_until'] = time.monotonic() + 60
        audible.clear()

    def hide():
        # Closing does not terminate monitoring or permanently acknowledge a fault.
        if state['last_episode']:
            silence()
        root.withdraw()
        state['visible'] = False

    def test():
        state['test_until'] = time.monotonic() + 3

    tk.Button(buttons, text='Silence 60 s (alarme conservée)', command=silence).pack(side='left', padx=7)
    tk.Button(buttons, text='Test son (3 s)', command=test).pack(side='left', padx=7)
    tk.Button(buttons, text='Masquer la fenêtre', command=hide).pack(side='left', padx=7)
    root.protocol('WM_DELETE_WINDOW', hide)
    if not show:
        root.withdraw()

    def tick():
        now = time.monotonic()
        try:
            state['last_item'] = output.get_nowait()
        except queue.Empty:
            pass
        item = state['last_item']
        # Let the first bounded Tango read complete before diagnosing an outage.
        # Persisted real faults still announce immediately; no startup chirp for
        # an otherwise healthy monitor retaining its previous operating scope.
        if item is None and now - state['started'] < MAX_AGE and not policy.faults:
            root.after(200, tick)
            return
        if item is None or now - item[0] >= MAX_AGE:
            result = policy.update(now=now, error='Lecture Tango indisponible ou sans progression')
        else:
            result = policy.update(item[1], now=now, error=item[2])
        if result['episode'] != state['last_episode']:
            state['silenced_until'] = 0
        test_active = now < state['test_until']
        sounding = (result['active'] and now >= state['silenced_until']) or test_active
        audio_status['kind'] = 'ALARM' if test_active else result['severity']
        (audible.set if sounding else audible.clear)()
        show_request = directory / 'show.request'
        requested = show_request.exists()
        if requested:
            try:
                show_request.unlink()
            except OSError:
                pass
        if requested or (result['active'] and (result['episode'] != state['last_episode']
                                            or sounding and not state['was_sounding'])):
            root.deiconify()
            root.lift()
            state['visible'] = True
        state['was_sounding'] = sounding
        state['last_episode'] = result['episode']
        root.attributes('-topmost', result['active'])
        color = '#a5151a' if result['severity'] == 'ALARM' else '#795400' if result['active'] or result['quality'] != 'FRESH' or result['cold_red'] else '#163527'
        root.configure(bg=color)
        for widget in root.winfo_children():
            widget.configure(bg=color)
        if result['active']:
            circuits = ' + '.join(result['faults'])
            thermal_text = '\n'.join('%s : %.2f °C ; consigne %.2f °C ; écart +%.2f °C%s' %
                (t['circuit'], t['temperature_c'], t['setpoint_c'], t['deviation_c'],
                 ' (lecture périmée)' if t['quality'] != 'FRESH' else '') for t in result['temperature_alerts'])
            title.set(('AVERTISSEMENT TEMPÉRATURE' if result['severity'] == 'WARNING' else 'ALERTE REFROIDISSEMENT')
                      + (' — ' + circuits if circuits else ' — TÉLÉMÉTRIE PERDUE' if 'TELEMETRY' in result['reasons'] else ''))
            detail.set(('Retour Secteur 220 V rouge avec Chauffage et régulation activés.\n' if circuits else '')
                       + ('Surveillance perdue : circulation non confirmée.\n' if 'TELEMETRY' in result['reasons'] else '')
                       + (thermal_text + '\nRefroidissement dégradé possible : vérifier circulation et consignes.\n' if thermal_text else '')
                       + 'Vérifier immédiatement le moteur et la circulation d’eau ; rétablir le refroidissement ou arrêter la machine selon la procédure locale.\nAucune commande automatique envoyée par cette alerte.')
        else:
            title.set('Surveillance refroidissement — ' + ('active' if result['operating'] else 'hors fonctionnement / attente'))
            detail.set('Tango → alerte Windows · navigateur indépendant\n'
                       + 'Chauffage : ' + ('ON' if result['chauffage'] else 'OFF')
                       + ' · Régulation : ' + ('ON' if result['regulation'] else 'OFF') + '\n'
                       + ('Armés : ' + ', '.join(result['armed']) if result['armed'] else 'Alarme désarmée : Chauffage ET régulation requis')
                       + ('\nSignaux rouges initiaux : ' + ', '.join(result['cold_red']) if result['cold_red'] else '')
                       + ('\nLecture indisponible : ' + result['source_error'] if result['quality'] != 'FRESH' else ''))
            if result['operating'] and (result['temperature_error'] or 'UNKNOWN' in result['temperature_quality'].values()):
                detail.set(detail.get() + '\nSurveillance température indisponible : ' + result['temperature_error'])
        remaining = max(0, math.ceil(state['silenced_until'] - now))
        sound_text.set('ERREUR AUDIO : ' + audio_status['error'] if audio_status['error'] else
                       'TEST SON — 3 s' if test_active else 'Son coupé encore %s s ; alarme conservée' % remaining
                       if result['active'] and remaining else 'Signal sonore actif' if sounding else 'Signal sonore prêt')
        result.update(pid=os.getpid(), device=device, sounding=sounding,
                      silence_remaining_seconds=remaining, audio=dict(audio_status), test_active=test_active)
        event = (result['general'], tuple(result['armed']), tuple(result['faults']), result['episode'],
                 result['quality'], bool(remaining), test_active)
        try:
            if event != state['previous_event']:
                with (directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            if event != state['previous_event'] or now - state['last_saved'] >= 1:
                write_json(state_path, result)
                state['last_saved'] = now
            state['previous_event'] = event
        except OSError as exc:
            # A journal/disk fault must NEVER block sound, popup or fresh reads.
            sound_text.set(sound_text.get() + ' · Enregistrement indisponible : ' + str(exc))
        root.after(200, tick)

    def callback_failed(exception_type, value, traceback):
        # A UI callback failure must be visible/audible rather than silently
        # stopping all future polling callbacks in a hidden pythonw process.
        (audible.set if policy.operating else audible.clear)()
        root.deiconify()
        root.attributes('-topmost', True)
        title.set('ERREUR DU MONITEUR REFROIDISSEMENT')
        detail.set('%s: %s\nSurveillance non confirmée. Vérifier localement la machine.'
                   % (exception_type.__name__, value))
        try:
            with (directory / 'monitor_errors.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(utc=utc(), error=str(value))) + '\n')
        except OSError:
            pass
        root.after(1000, tick)

    root.report_callback_exception = callback_failed
    try:
        tick()
        root.mainloop()
    finally:
        stop.set()
        audible.clear()
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument('--device', default=DEVICE)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    run(args.directory, args.device, args.show)


if __name__ == '__main__':
    main()
