"""Python 3.4 lifecycle stubs. No NI, serial, PSP, shell or hardware calls.

Native frame order/constants are pinned in a builder-checked inert bundle.
Same-frame effects use a chosen serial simulation schedule, not native timing.
"""
import copy
import os

from .supervision_wire import strict_json

STATES = ("UNMANAGED", "INITIALIZING", "RUNNING", "STOPPING", "STOPPED", "FAULT", "UNKNOWN")
CATALOG = (
    dict(page="Cycle ACQ", control="Initialiser ACQ", kind="PROCEDURE", procedure="acq.initialize",
         blocked_reason="", hardware_blocked_reason="Synthetic lifecycle only; no physical initialization"),
    dict(page="Cycle ACQ", control="Arrêt général ACQ", kind="PROCEDURE", procedure="acq.stop",
         blocked_reason="", hardware_blocked_reason="Synthetic controlled stop; not hardware safe shutdown"),
)
BANKS = {9: ("analog", "C6NI6703"), 10: ("analog", "C7NI6703"),
         11: ("analog", "C8NI6703"), 12: ("analog", "C9NI6703"),
         17: ("digital", "C3_OUT_DIO96"), 15: ("digital", "C4_OUT_DIO96"),
         13: ("digital", "C5_OUT_DIO96")}


def load_bundle():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "supervision_lifecycle.json")
    with open(path, "rb") as stream:
        result = strict_json(stream.read())
    if result.get("schema_version") != 1 or result.get("simulation_only") is not True:
        raise ValueError("Simulation-only lifecycle bundle required")
    return result


def plans():
    bundle = load_bundle()
    def step(operation, label, **metadata):
        return dict(operation=operation, label=label, metadata=metadata)
    start = [step("lifecycle_open", "Initialiseur simulé " + name, resource="card." + name)
             for name in ("NI6602", "NI6071E", "DIO96", "NI6703")]
    start.insert(1, step("lifecycle_counters", "Compteurs initiaux simulés", counters=bundle["counters_started"]))
    start += [step("lifecycle_stub", "Lecture pilote simulée, pas une mesure", frame="pilot_read"),
              step("lifecycle_stub", "Découverte PSP simulée", frame="discovery"),
              step("lifecycle_startup_image", "Commandes initiales natives · 152 champs", commands=bundle["startup_commands"])]
    start += [step("lifecycle_open", "Publication simulée " + name, resource="psp." + name)
              for unused, bank, name in bundle["command_publications"]]
    start += [step("lifecycle_stub", "Premier échange AI/DIO/AO simulé", frame="25990"),
              step("lifecycle_open", "Initialiseur simulé NI6220", resource="card.NI6220")]
    start += [step("lifecycle_open", "Session TPG simulée " + port, resource="tpg." + port)
              for unused, port, bank, handler in bundle["tpg_branches"]]
    start += [step("lifecycle_resets", "Réinitialisation logicielle DPS/EPS/TCP/Emergency", resets=bundle["postinit_resets"])]
    published = {row[2] for row in bundle["command_publications"]}
    start += [step("lifecycle_open", "Référence PSP simulée " + name, resource="psp." + name)
              for name in bundle["cleanup_variables"] if name not in published]
    start += [step("lifecycle_wait", "Attente de publication simulée · 100 ms", seconds=0.1),
              step("lifecycle_loops", "Entrée des cinq boucles · simulation", loops=bundle["runtime_loops"], running=True)]
    stop = [step("lifecycle_loops", "Jonction des cinq boucles · retour synthétique", loops=bundle["runtime_loops"], running=False)]
    def flatten(phase):
        frame, effects = phase
        for effect in effects:
            operation = effect[0]
            if operation == "subsequence":
                for child in effect[1]:
                    flatten(child)
            elif operation == "write":
                stop.append(step("lifecycle_write", "Écriture logique · frame " + frame,
                                 frame=frame, bank=effect[1], fields=effect[2]))
            elif operation == "wait":
                stop.append(step("lifecycle_wait", "Attente simulée · frame " + frame,
                                 frame=frame, seconds=effect[1] / 1000.0))
            elif operation == "ht_ramp":
                stop.append(step("lifecycle_ht_ramp", "Rampe HT native : commande < 6.6", frame=frame))
            elif operation == "counter_poll_stop_clear":
                stop.append(step("lifecycle_counter_stop", "Done/Stop/Clear simulé · compteur " + str(effect[2]),
                                 frame=frame, counter=effect[2], max_iteration=effect[4], period_ms=effect[5]))
            else:
                raise ValueError("Unsupported lifecycle effect")
    for phase in bundle["controlled_stop"]:
        flatten(phase)
    stop += [step("lifecycle_close", "Fermer référence PSP simulée " + name, resource="psp." + name)
             for name in bundle["cleanup_variables"]]
    stop += [step("lifecycle_close", "Fermer session TPG simulée " + port, resource="tpg." + port)
             for unused, port, bank, handler in bundle["tpg_branches"]]
    stop += [step("lifecycle_write", "Cleanup : stop30=False, aucun zéro de sortie", frame="246", bank=30, fields=[[-1, False]])]
    return dict((name, dict(name=name, kind="LIFECYCLE", dps_index=None, blocked_reason="", steps=steps))
                for name, steps in (("acq.initialize", start), ("acq.stop", stop)))


def write_bank(image, bank, fields):
    if bank in BANKS:
        kind, name = BANKS[bank]
        for field, value in fields:
            image[kind][name + "." + str(field).zfill(2)] = value
    elif bank == 36:
        for field, value in fields:
            image.setdefault("lifecycle_dps", [False] * 29)[field] = value
    elif bank == 44:
        for field, value in fields:
            image.setdefault("eps", [False] * 77)[field] = value
    else:
        image.setdefault("native_locals", {})[str(bank)] = fields[0][1]


def execute(outputs, step, wait):
    operation, meta = step["operation"], step["metadata"]
    detail = dict(label=step["label"], simulated=True, frame=meta.get("frame"))
    if operation == "lifecycle_wait":
        wait(meta["seconds"])
        return dict(detail, seconds=meta["seconds"], native_within_frame_order=False)
    if operation == "lifecycle_ht_ramp":
        with outputs._lock:
            current = outputs.image["analog"].get("C9NI6703.00")
        if current is None:
            raise ValueError("HT command unknown; no implicit zero or physical readback")
        iterations = 0
        while True:
            wait(0)
            with outputs._lock:
                outputs.image.setdefault("native_locals", {}).update({"50": 6.0, "48": current})
                if current < 6.6:
                    break
                if iterations >= 256:
                    raise ValueError("Simulation ramp bound exceeded; not a native shutdown deadline")
                current -= 0.1
                outputs.image["analog"]["C9NI6703.00"] = current
            iterations += 1
            wait(0.5)
        return dict(detail, iterations=iterations, value=current, strict_threshold=6.6)
    with outputs._lock:
        image = outputs.image
        if operation in ("lifecycle_open", "lifecycle_close"):
            image.setdefault("resources", {})[meta["resource"]] = "OPEN" if operation.endswith("open") else "CLOSED"
            detail.update(resource=meta["resource"], fixture_return=True)
        elif operation == "lifecycle_startup_image":
            for bank, values in meta["commands"]:
                write_bank(image, bank, list(enumerate(values)))
            detail["logical_fields"] = 152
        elif operation == "lifecycle_counters":
            for counter in meta["counters"]:
                image["counters"]["ctr" + str(counter)] = "RUNNING"
        elif operation == "lifecycle_loops":
            image["runtime_loops"] = dict((loop, meta["running"]) for loop in meta["loops"])
            detail["synthetic_join"] = not meta["running"]
        elif operation == "lifecycle_resets":
            for bank, values in meta["resets"]:
                if isinstance(values, list):
                    write_bank(image, bank, list(enumerate(values)))
                else:
                    write_bank(image, bank, [[-1, values]])
        elif operation == "lifecycle_write":
            write_bank(image, meta["bank"], meta["fields"])
            detail.update(bank=meta["bank"], fields=copy.deepcopy(meta["fields"]))
        elif operation == "lifecycle_counter_stop":
            image["counters"]["ctr" + str(meta["counter"])] = "STOPPED"
            detail.update(done_fixture=True, polls=1, native_predicate="Done OR i>40", clear_errors_fixture=True)
        elif operation != "lifecycle_stub":
            raise ValueError("Unknown lifecycle simulation operation")
    return detail
