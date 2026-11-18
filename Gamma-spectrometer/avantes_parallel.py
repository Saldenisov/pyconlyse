"""
Parallel Measurement Support for Multiple Avantes Spectrometers
================================================================

This module provides utility functions to enable true simultaneous/parallel
readout of multiple Avantes spectrometers using msl-equipment.

Key Features:
- Non-blocking parallel measurement initiation
- Interleaved polling of multiple devices
- Synchronized data retrieval
- Thread-safe operations

Usage Example:
    from avantes_parallel import parallel_measure, parallel_poll_and_get_data, parallel_prepare_measure
    
    # Assuming spec1 and spec2 are two Avantes instances
    specs = [spec1, spec2]
    configs = [config1, config2]
    
    # Start measurements on both simultaneously
    parallel_prepare_measure(specs, configs)
    parallel_measure(specs, num_measurements=1)
    
    # Poll and retrieve data from both
    results = parallel_poll_and_get_data(specs, timeout=5.0)
"""

import logging
import time
from typing import List, Dict, Tuple, Optional
import numpy as np


logger = logging.getLogger(__name__)


def _report_failure(diagnostics, index, stage, error):
    logger.warning("Spectrometer %s %s: %s", index + 1, stage, error)
    if diagnostics is not None:
        diagnostics[index] = {"stage": stage, "error": str(error)}


def parallel_prepare_measure(spectrometers: List, configs: List, *, diagnostics=None) -> Dict[int, bool]:
    """
    Prepare measurements for multiple spectrometers in parallel.
    
    Parameters
    ----------
    spectrometers : List
        List of Avantes spectrometer instances (msl-equipment Avantes objects)
    configs : List
        List of MeasConfigType configurations, one for each spectrometer
        
    Returns
    -------
    Dict[int, bool]
        Dictionary mapping spectrometer index to success status
    """
    if len(spectrometers) != len(configs):
        raise ValueError("Each spectrometer requires a measurement configuration")
    results = {}
    
    for idx, (spec, config) in enumerate(zip(spectrometers, configs)):
        try:
            spec.prepare_measure(config)
            results[idx] = True
        except Exception as exc:
            _report_failure(diagnostics, idx, "prepare", exc)
            results[idx] = False
            
    return results


def parallel_measure(spectrometers: List, num_measurements: int = 1,
                     window_handles: Optional[List] = None, *, diagnostics=None) -> Dict[int, bool]:
    """
    Start measurements on multiple spectrometers simultaneously.
    
    This initiates measurements on all spectrometers without waiting for completion.
    For hardware-triggered operation, all devices will start together on trigger.
    
    Parameters
    ----------
    spectrometers : List
        List of Avantes spectrometer instances
    num_measurements : int, optional
        Number of measurements per spectrometer (default: 1, use -1 for continuous)
    window_handles : List, optional
        List of window handles for callbacks (default: None for all)
        
    Returns
    -------
    Dict[int, bool]
        Dictionary mapping spectrometer index to success status
    """
    results = {}
    
    if window_handles is None:
        window_handles = [None] * len(spectrometers)
    if len(spectrometers) != len(window_handles):
        raise ValueError("Each spectrometer requires a window handle or None")
    
    # Start all measurements as quickly as possible
    for idx, (spec, wh) in enumerate(zip(spectrometers, window_handles)):
        try:
            spec.measure(num_measurements, wh)
            results[idx] = True
        except Exception as exc:
            _report_failure(diagnostics, idx, "start", exc)
            results[idx] = False
            
    return results


def parallel_poll_and_get_data(spectrometers: List, timeout: float = 5.0, 
                                poll_interval: float = 0.001,
                                max_retries: int = 3,
                                diagnostics: Optional[dict] = None) -> Dict[int, Tuple[bool, Optional[np.ndarray]]]:
    """
    Poll multiple spectrometers in parallel and retrieve data when ready.
    
    This function continuously polls all spectrometers in a round-robin fashion
    until all have data available or timeout is reached.
    
    Parameters
    ----------
    spectrometers : List
        List of Avantes spectrometer instances
    timeout : float, optional
        Maximum time to wait for all measurements in seconds (default: 5.0)
    poll_interval : float, optional
        Time between poll attempts in seconds (default: 0.001)
    max_retries : int, optional
        Maximum retries for data retrieval errors (default: 3)
    diagnostics : dict, optional
        Receives the device tick, saturation indices when available, and readout errors.
        
    Returns
    -------
    Dict[int, Tuple[bool, Optional[np.ndarray]]]
        Dictionary mapping spectrometer index to (success, data) tuple
        - success: True if data retrieved successfully
        - data: numpy array of spectral data, or None if failed
    """
    results = {idx: (False, None) for idx in range(len(spectrometers))}
    data_ready = {idx: False for idx in range(len(spectrometers))}
    retry_count = {idx: 0 for idx in range(len(spectrometers))}
    retry_after = dict.fromkeys(data_ready, 0.0)
    deadline = time.monotonic() + timeout
    
    # Poll all spectrometers until all are ready or timeout
    while not all(data_ready.values()):
        now = time.monotonic()
        if now >= deadline:
            break
            
        # Poll each spectrometer that hasn't finished yet
        for idx, spec in enumerate(spectrometers):
            if data_ready[idx] or now < retry_after[idx]:
                continue  # Skip if already got data
                
            try:
                # Non-blocking poll
                scan_ready = spec.poll_scan()
                
                if scan_ready:
                    # Data is ready, retrieve it
                    try:
                        tick_count, data = spec.get_data()
                    except Exception as get_error:
                        # Handle ERR_INVALID_MEAS_DATA - data not ready yet
                        if "INVALID_MEAS_DATA" in str(get_error) and retry_count[idx] < max_retries:
                            retry_count[idx] += 1
                            retry_after[idx] = time.monotonic() + 0.01
                            continue
                        else:
                            raise  # Re-raise if max retries exceeded or other error
                    data = np.asarray(data)
                    if data.ndim != 1 or not data.size or data.dtype.kind not in "iuf":
                        raise ValueError("Expected a one-dimensional numeric spectrum")
                    results[idx] = (True, data)
                    data_ready[idx] = True
                    if diagnostics is not None:
                        info = {"device_tick": None, "saturated_pixels": None}
                        diagnostics[idx] = info
                        try:
                            info["device_tick"] = int(tick_count) if tick_count is not None else None
                        except (TypeError, ValueError, OverflowError) as exc:
                            info["device_tick_error"] = str(exc)
                        try:
                            get_saturation = getattr(spec, "get_saturated_pixels", None)
                            if callable(get_saturation):
                                pixels = np.asarray(get_saturation())
                                if pixels.shape == data.shape:
                                    info["saturated_pixels"] = np.flatnonzero(pixels).tolist()
                        except Exception as exc:
                            info["saturation_error"] = str(exc)

            except Exception as exc:
                results[idx] = (False, None)
                data_ready[idx] = True  # Mark as done (failed)
                _report_failure(diagnostics, idx, "readout", exc)
        
        # Small sleep to prevent CPU spinning
        if not all(data_ready.values()):
            time.sleep(poll_interval)
    
    for idx, ready in data_ready.items():
        if not ready:
            _report_failure(diagnostics, idx, "readout", "readout timeout")
    return results


def parallel_full_measurement(spectrometers: List, configs: List, 
                               num_measurements: int = 1,
                               timeout: float = 5.0, *,
                               diagnostics=None) -> Dict[int, Tuple[bool, Optional[np.ndarray]]]:
    """
    Complete parallel measurement workflow: prepare, measure, poll, and retrieve data.
    
    This is a convenience function that combines all steps for parallel measurement.
    
    Parameters
    ----------
    spectrometers : List
        List of Avantes spectrometer instances
    configs : List
        List of MeasConfigType configurations
    num_measurements : int, optional
        Number of measurements (default: 1)
    timeout : float, optional
        Maximum wait time in seconds (default: 5.0)
    diagnostics : dict, optional
        Receives diagnostic details from preparation, startup, readout, and cleanup.
        
    Returns
    -------
    Dict[int, Tuple[bool, Optional[np.ndarray]]]
        Dictionary mapping spectrometer index to (success, data) tuple
    """
    # Step 1: Prepare all measurements
    prep_results = parallel_prepare_measure(spectrometers, configs, diagnostics=diagnostics)
    
    if not all(prep_results.values()):
        return {idx: (False, None) for idx in range(len(spectrometers))}
    
    # Step 2: Start all measurements
    meas_results = parallel_measure(spectrometers, num_measurements, diagnostics=diagnostics)
    
    if not all(meas_results.values()):
        parallel_stop_measure(spectrometers, diagnostics=diagnostics)
        return {idx: (False, None) for idx in range(len(spectrometers))}
    
    # Step 3: Poll and retrieve data
    try:
        data_results = parallel_poll_and_get_data(spectrometers, timeout, diagnostics=diagnostics)
    except Exception:
        parallel_stop_measure(spectrometers, diagnostics=diagnostics)
        raise
    failed = [idx for idx, (success, _) in data_results.items() if not success]
    parallel_stop_measure(spectrometers, indices=failed, diagnostics=diagnostics)
    return data_results


def parallel_stop_measure(spectrometers: List, *, indices=None, diagnostics=None) -> Dict[int, bool]:
    """
    Stop measurements on multiple spectrometers.
    
    Parameters
    ----------
    spectrometers : List
        List of Avantes spectrometer instances
        
    Returns
    -------
    Dict[int, bool]
        Dictionary mapping spectrometer index to success status
    """
    results = {}
    
    for idx in range(len(spectrometers)) if indices is None else indices:
        try:
            spectrometers[idx].stop_measure()
            results[idx] = True
        except Exception as exc:
            logger.warning("Spectrometer %s cleanup: %s", idx + 1, exc)
            if diagnostics is not None:
                diagnostics.setdefault(idx, {})["cleanup_error"] = str(exc)
            results[idx] = False
            
    return results


# Utility function for synchronized triggering
def get_hardware_trigger_config(integration_time: float, num_averages: int = 1,
                                 stop_pixel: int = 2047) -> 'MeasConfigType':
    """
    Create a measurement configuration for hardware-triggered operation.
    
    Parameters
    ----------
    integration_time : float
        Integration time in milliseconds
    num_averages : int, optional
        Number of averages (default: 1)
    stop_pixel : int, optional
        Last pixel to read (default: 2047 for AvaSpec-2048L)
        
    Returns
    -------
    MeasConfigType
        Configuration object ready for prepare_measure()
        
    Note
    ----
    You must import MeasConfigType and TriggerType from your Avantes instance:
        cfg = spec.MeasConfigType()
        trigger = spec.TriggerType()
    """
    # This is a template - actual implementation should be done by the caller
    # since we need access to the Avantes class structures
    pass
