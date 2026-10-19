"""XP GUI for one analog card at a time, without output or DIO tasks."""

from __future__ import print_function

import json
import os
import threading

try:
    import queue
except ImportError:
    import Queue as queue

import tkinter as tk
from tkinter import scrolledtext

from elyse_agent.input_probe import INPUT_CARDS, discover_inventory, probe_card


ROOT = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(ROOT, "runtime", "input_probe.jsonl")


class ProbeWindow(object):
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.buttons = []
        root.title("ELYSE NI analog input probe - read only")
        root.geometry("820x580")
        self.status = tk.StringVar(value="Choose discovery or one input card.")

        controls = tk.Frame(root)
        controls.pack(fill="x", padx=8, pady=8)
        self._button(controls, "Audit all NI devices (no tasks)", self._discover, 0, 0, 2)
        for row, task_name in enumerate(sorted(INPUT_CARDS), 1):
            tk.Label(controls, text=task_name, anchor="w", width=21).grid(
                row=row, column=0, sticky="w"
            )
            self._button(
                controls, "Read first input",
                lambda name=task_name: self._probe(name, "first"), row, 1
            )
            self._button(
                controls, "Read whole card (raw)",
                lambda name=task_name: self._probe(name, "all"), row, 2
            )
            self._button(
                controls, "Read ai8 RSE",
                lambda name=task_name: self._probe(name, "ai8_rse"), row, 3
            )
            self._button(
                controls, "Read ai8+ RSE",
                lambda name=task_name: self._probe(name, "ai8_plus_rse"), row, 4
            )

        tk.Label(root, textvariable=self.status, anchor="w").pack(
            fill="x", padx=8
        )
        self.text = scrolledtext.ScrolledText(root, wrap="none", font=("Courier", 9))
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self._append("Reports: " + REPORT_PATH)
        self._append("DIO-96 input tasks are excluded: 8255 reconfiguration can reset outputs.")
        root.after(100, self._drain_events)

    def _button(self, parent, label, action, row, column, span=1):
        button = tk.Button(parent, text=label, command=action)
        button.grid(row=row, column=column, columnspan=span, padx=3, pady=2, sticky="ew")
        self.buttons.append(button)

    def _append(self, message):
        self.text.insert("end", message + "\n")
        self.text.see("end")

    def _run(self, label, action):
        for button in self.buttons:
            button.configure(state="disabled")
        self.status.set("Reading " + label + " ...")

        def worker():
            try:
                result = action()
                if not os.path.isdir(os.path.dirname(REPORT_PATH)):
                    os.makedirs(os.path.dirname(REPORT_PATH))
                with open(REPORT_PATH, "a") as stream:
                    stream.write(json.dumps(result, ensure_ascii=True, sort_keys=True) + "\n")
                self.events.put((label, result, None))
            except Exception as error:
                self.events.put((label, None, "{0}: {1}".format(type(error).__name__, error)))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _discover(self):
        self._run("NI devices", discover_inventory)

    def _probe(self, task_name, scope):
        self._run(task_name + " (" + scope + ")", lambda: probe_card(task_name, scope))

    def _drain_events(self):
        try:
            while True:
                label, result, error = self.events.get_nowait()
                if error:
                    self.status.set(label + ": " + error)
                    self._append(label + ": " + error)
                else:
                    self.status.set(label + ": " + result.get("status", "discovered"))
                    self._append(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
                for button in self.buttons:
                    button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)


def main():
    root = tk.Tk()
    ProbeWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
