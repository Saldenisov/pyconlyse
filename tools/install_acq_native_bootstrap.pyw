"""Operator-opened cold source plus command-transport setup; never starts NI."""
import json
import os
import runpy


def main():
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    folder = os.path.dirname(os.path.abspath(__file__))
    result = dict(result="FAILED", hardware_commands_sent=False, cards_initialized=False)
    try:
        with open(os.path.join(folder, "command_transport.key"), "rb") as stream:
            key = stream.read().strip()
        if len(key) < 32:
            raise ValueError("Deployment command key missing or too short")
        updater = runpy.run_path(os.path.join(folder, "install_acq_matched_source.pyw"))
        transport = runpy.run_path(os.path.join(folder, "configure_acq_command_transport.py"))
        result = updater["install"](folder)
        result["source_installed"] = True
        result["transport"] = transport["configure"](updater["TARGET"], key)
        result["result"] = "INSTALLED"
        messagebox.showinfo("Update installed; no cards initialized",
            "Native bootstrap updated; XP command transport configured.\n"
            "Commissioning flags and ownership evidence preserved.\n"
            "Everest command transport requires matching configuration.\n"
            "Open START_SERVER shortcut. Initialize remains manual.", parent=root)
    except Exception as error:
        result.update(result="FAILED", error=type(error).__name__ + ": " + str(error))
        messagebox.showerror("Update incomplete; no Initialize", result["error"], parent=root)
    finally:
        with open(os.path.join(folder, "installation_result.json"), "w") as stream:
            json.dump(result, stream, indent=2)
        root.destroy()


if __name__ == "__main__":
    main()
