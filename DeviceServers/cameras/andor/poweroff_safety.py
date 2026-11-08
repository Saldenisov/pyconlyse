"""Fresh SDK2 reads for camera power-off; never discover or open a camera."""

import math


def read_poweroff_safety(camera):
    if camera is None:
        raise RuntimeError("Andor SDK handle is absent; temperature cannot be verified")
    temperature = float(camera.get_temperature())
    if not math.isfinite(temperature):
        raise RuntimeError("Andor temperature readback is not finite")
    return {"temperature_c": temperature, "cooler_on": bool(camera.is_cooler_on()),
            "acquisition_active": bool(camera.acquisition_in_progress()),
            "temperature_status": str(camera.get_temperature_status()), "fresh_sdk_readback": True}


def begin_safe_poweroff(camera):
    if camera is None:
        raise RuntimeError("Andor SDK handle is absent; safe warm-up cannot be started")
    camera.stop_acquisition()
    if camera.acquisition_in_progress():
        raise RuntimeError("Andor acquisition did not stop; cooler/power retained")
    # CoolerOFF allows controlled warming while camera/fan power stays present.
    # No fan-off, temperature setpoint, acquisition start, or SDK reset.
    camera.set_cooler(False)
    return read_poweroff_safety(camera)
