#!/usr/bin/env python3
"""Utility launchers for DeviceServer GUI widgets (NETIO, OWIS, LaserPointing, etc.).

Usage examples:

- Start NETIO widget
    from main_app.ui.widget_launchers import start_netio_widget
    w = start_netio_widget("manip/sd1/pdu_sd1")

- Start OWIS widget (axes auto-detected)
    from main_app.ui.widget_launchers import start_owis_widget
    w = start_owis_widget("elyse/motion/owis_ps90_v0")

- Start LaserPointing widget
    from main_app.ui.widget_launchers import start_laser_pointing_widget
    w = start_laser_pointing_widget("elyse/control/laser_pointing_v0")

- Generic launcher (best-effort mapping)
    from main_app.ui.widget_launchers import start_widget_for_device
    w = start_widget_for_device("manip/sd1/pdu_sd1")

Notes:
- These functions expect a running Qt application (e.g., inside your main GUI).
- They return the created widget so you can keep a reference (to prevent GC).

"""

from __future__ import annotations

import ast
from typing import List, Optional

from DeviceServers.shared.DS_Widget import VisType
from main_app.core.config import OFFLINE_MODE
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


def _to_vis(vis: str | VisType) -> VisType:
    if isinstance(vis, VisType):
        return vis
    s = (vis or "").strip().lower()
    return VisType.FULL if s == "full" else VisType.MIN


def _offline_placeholder(title: str, text: str, parent=None):
    w = QWidget(parent)
    w.setWindowTitle(title)
    layout = QVBoxLayout(w)
    label = QLabel(text)
    label.setWordWrap(True)
    layout.addWidget(label)
    try:
        w.resize(420, 120)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_netio_widget(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Start NETIO (PDU) widget for a given Tango device name.

    Example: start_netio_widget("manip/sd1/pdu_sd1")
    """
    if OFFLINE_MODE:
        return _offline_placeholder(
            "NETIO (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu

    v = _to_vis(vis)
    w = Netio_pdu(device_name, parent, v)
    try:
        w.setWindowTitle(f"NETIO - {device_name}")
    except Exception:
        pass
    try:
        w.resize(900, 400)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_netio_client(instance="V0", parent=None, vis: str | VisType = "FULL"):
    """Start NETIO client with device selection (V0, VD2, all).

    This is the new approach that launches a client panel with multiple devices
    instead of individual device widgets.

    Example: start_netio_client("V0")
    """
    if OFFLINE_MODE:
        return _offline_placeholder(
            "NETIO Client (offline)",
            f"Offline mode is enabled. NETIO client would show instance: {instance}.",
            parent,
        )

    try:
        from DeviceServers.power.netio.DS_NETIO_client import (
            start_netio_client as _start_client,
        )

        v = _to_vis(vis)
        # Start as non-standalone (returns the panel)
        panel = _start_client(instance=instance, vis_type=v, standalone=False)

        if panel:
            try:
                panel.setParent(parent)
            except Exception:
                pass

        return panel

    except Exception as e:
        return _offline_placeholder(
            "NETIO Client (error)", f"Failed to start NETIO client: {e}", parent
        )


def _derive_owis_axes(device_name: str) -> List[int]:
    """Best-effort axes detection for OWIS controller.

    Strategy:
    - Try reading ds.friendly_names (list-like string) and use its length
    - Fallback: parse ds.states keys (dict-like string)
    - Final fallback: [0, 1]
    """
    try:
        from taurus import Device

        ds = Device(device_name)
        try:
            # Friendly names is expected to be a stringified list
            names_raw = ds.friendly_names
            names = ast.literal_eval(str(names_raw))
            if isinstance(names, (list, tuple)) and names:
                return list(range(len(names)))
        except Exception:
            pass
        try:
            states_raw = ds.states
            states = ast.literal_eval(str(states_raw))
            if isinstance(states, dict) and states:
                return sorted([int(k) for k in states.keys()])
        except Exception:
            pass
    except Exception:
        pass
    return [0, 1]


def start_owis_widget(
    device_name: str,
    axes: Optional[List[int]] = None,
    parent=None,
    vis: str | VisType = "FULL",
):
    """Start OWIS (PS90) widget.

    If axes is not provided, attempts to auto-detect from device attributes.
    """
    if OFFLINE_MODE:
        return _offline_placeholder(
            "OWIS (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor

    v = _to_vis(vis)
    if axes is None:
        axes = _derive_owis_axes(device_name)
    w = OWIS_motor(device_name, axes, parent, v)
    try:
        w.setWindowTitle(f"OWIS - {device_name}")
    except Exception:
        pass
    try:
        w.resize(1000, 500)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_laser_pointing_widget(
    device_name: str, parent=None, vis: str | VisType = "FULL"
):
    """Start LaserPointing composite widget."""
    if OFFLINE_MODE:
        return _offline_placeholder(
            "LaserPointing (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.control.laser_pointing.DS_LaserPointing_Widget import (
        LaserPointing,
    )

    v = _to_vis(vis)
    w = LaserPointing(device_name, parent, v)
    try:
        w.setWindowTitle(f"Laser Pointing - {device_name}")
    except Exception:
        pass
    try:
        w.resize(1200, 800)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_basler_widget(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Start Basler camera widget."""
    if OFFLINE_MODE:
        return _offline_placeholder(
            "Basler (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.cameras.basler.DS_BASLER_Widget import Basler_camera

    v = _to_vis(vis)
    w = Basler_camera(device_name, parent, v)
    try:
        w.setWindowTitle(f"Basler - {device_name}")
    except Exception:
        pass
    try:
        w.resize(1000, 700)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_standa_widget(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Start STANDA motor widget."""
    if OFFLINE_MODE:
        return _offline_placeholder(
            "STANDA (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.motion.standa.DS_STANDA_Widget import Standa_motor

    v = _to_vis(vis)
    w = Standa_motor(device_name, parent, v)
    try:
        w.setWindowTitle(f"STANDA - {device_name}")
    except Exception:
        pass
    try:
        w.resize(900, 500)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_topdirect_widget(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Start TopDirect motor widget."""
    if OFFLINE_MODE:
        return _offline_placeholder(
            "TopDirect (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.motion.topdirect.DS_TOPDIRECT_Widget import TopDirect_Motor

    v = _to_vis(vis)
    w = TopDirect_Motor(device_name, parent, v)
    try:
        w.setWindowTitle(f"TopDirect - {device_name}")
    except Exception:
        pass
    try:
        w.resize(900, 500)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_keysight_widget(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Start Keysight 33509B widget."""
    if OFFLINE_MODE:
        return _offline_placeholder(
            "Keysight 33509B (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    from DeviceServers.instruments.keysight.DS_KEYSIGHT_33509B_Widget import (
        Keysight_33509B,
    )

    v = _to_vis(vis)
    w = Keysight_33509B(device_name, parent, v)
    try:
        w.setWindowTitle(f"Keysight 33509B - {device_name}")
    except Exception:
        pass
    try:
        w.resize(700, 400)
    except Exception:
        pass
    try:
        w.show()
    except Exception:
        pass
    return w


def start_widget_for_device(device_name: str, parent=None, vis: str | VisType = "FULL"):
    """Best-effort launcher based on device name keywords.

    Known keywords -> widget:
    - 'netio' -> Netio_pdu
    - 'owis' or 'delay' -> OWIS_motor (axes auto-detected)
    - 'laser' -> LaserPointing
    - 'basler' or 'camera' -> Basler_camera
    - 'standa' -> Standa_motor
    - 'topdirect' -> TopDirect_Motor
    - 'keysight' or 'awg' or '33509' -> Keysight_33509B
    """
    name = (device_name or "").lower()

    if "netio" in name:
        return start_netio_widget(device_name, parent, vis)
    if "owis" in name or "delay" in name:
        return start_owis_widget(device_name, None, parent, vis)
    if "laser" in name:
        return start_laser_pointing_widget(device_name, parent, vis)
    if "basler" in name or "camera" in name:
        return start_basler_widget(device_name, parent, vis)
    if "standa" in name:
        return start_standa_widget(device_name, parent, vis)
    if "topdirect" in name:
        return start_topdirect_widget(device_name, parent, vis)
    if "keysight" in name or "awg" in name or "33509" in name:
        return start_keysight_widget(device_name, parent, vis)

    # Fallback: determine by server name via Database.get_device_info (no DeviceProxy)
    if OFFLINE_MODE:
        return _offline_placeholder(
            "Widget (offline)",
            f"Offline mode is enabled. Not connecting to {device_name}.",
            parent,
        )
    try:
        from tango import Database

        db = Database()
        info = db.get_device_info(device_name)
        srv = str(
            getattr(info, "server_name", "")
            or getattr(info, "server_id", "")
            or getattr(info, "server", "")
        )
        s = srv.lower()
        if "ds_netio_pdu" in s or "netio" in s:
            return start_netio_widget(device_name, parent, vis)
        if "ds_owis_ps90" in s or "owis" in s:
            return start_owis_widget(device_name, None, parent, vis)
        if "ds_laserpointing" in s or "laser" in s:
            return start_laser_pointing_widget(device_name, parent, vis)
        if "ds_basler_camera" in s or "basler" in s:
            return start_basler_widget(device_name, parent, vis)
        if "ds_standa_motor" in s or "standa" in s:
            return start_standa_widget(device_name, parent, vis)
        if "ds_topdirect_motor" in s or "topdirect" in s:
            return start_topdirect_widget(device_name, parent, vis)
        if "ds_keysight_33509b" in s or "keysight" in s or "awg" in s:
            return start_keysight_widget(device_name, parent, vis)
    except Exception:
        pass

    raise RuntimeError(f"Could not determine widget for device: {device_name}")
