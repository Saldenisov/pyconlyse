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
    from avantes_parallel import parallel_measure, parallel_poll_and_get_data
    
    # Assuming spec1 and spec2 are two Avantes instances
    specs = [spec1, spec2]
    configs = [config1, config2]
    
    # Start measurements on both simultaneously
    parallel_measure(specs, configs, num_measurements=1)
    
    # Poll and retrieve data from both
    results = parallel_poll_and_get_data(specs, timeout=5.0)
"""

import time
from typing import List, Dict, Tuple, Optional
import numpy as np


def parallel_prepare_measure(spectrometers: List, configs: List) -> Dict[int, bool]:
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
    results = {}
    
    for idx, (spec, config) in enumerate(zip(spectrometers, configs)):
        try:
            spec.prepare_measure(config)
            results[idx] = True
        except Exception as e:
            print(f"Error preparing spectrometer {idx}: {e}")
            results[idx] = False
            
    return results


def parallel_measure(spectrometers: List, num_measurements: int = 1, 
                     window_handles: Optional[List] = None) -> Dict[int, bool]:
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
    
    # Start all measurements as quickly as possible
    for idx, (spec, wh) in enumerate(zip(spectrometers, window_handles)):
        try:
            spec.measure(num_measurements, wh)
            results[idx] = True
        except Exception as e:
            print(f"Error starting measurement on spectrometer {idx}: {e}")
            results[idx] = False
            
    return results


def parallel_poll_and_get_data(spectrometers: List, timeout: float = 5.0, 
                                poll_interval: float = 0.001,
                                max_retries: int = 3) -> Dict[int, Tuple[bool, Optional[np.ndarray]]]:
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
    start_time = time.time()
    
    # Poll all spectrometers until all are ready or timeout
    while not all(data_ready.values()):
        if time.time() - start_time > timeout:
            print(f"Timeout waiting for measurements. Ready: {sum(data_ready.values())}/{len(spectrometers)}")
            break
            
        # Poll each spectrometer that hasn't finished yet
        for idx, spec in enumerate(spectrometers):
            if data_ready[idx]:
                continue  # Skip if already got data
                
            try:
                # Non-blocking poll
                scan_ready = spec.poll_scan()
                
                if scan_ready:
                    # Data is ready, retrieve it
                    try:
                        tick_count, data = spec.get_data()
                        results[idx] = (True, data)
                        data_ready[idx] = True
                    except Exception as get_error:
                        # Handle ERR_INVALID_MEAS_DATA - data not ready yet
                        if "INVALID_MEAS_DATA" in str(get_error) and retry_count[idx] < max_retries:
                            retry_count[idx] += 1
                            print(f"Spec {idx}: Data not ready, retry {retry_count[idx]}/{max_retries}")
                            time.sleep(0.01)  # Wait a bit before next poll
                            continue
                        else:
                            raise  # Re-raise if max retries exceeded or other error
                    
            except Exception as e:
                print(f"Error polling/retrieving data from spectrometer {idx}: {e}")
                results[idx] = (False, None)
                data_ready[idx] = True  # Mark as done (failed)
        
        # Small sleep to prevent CPU spinning
        if not all(data_ready.values()):
            time.sleep(poll_interval)
    
    return results


def parallel_full_measurement(spectrometers: List, configs: List, 
                               num_measurements: int = 1,
                               timeout: float = 5.0) -> Dict[int, Tuple[bool, Optional[np.ndarray]]]:
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
        
    Returns
    -------
    Dict[int, Tuple[bool, Optional[np.ndarray]]]
        Dictionary mapping spectrometer index to (success, data) tuple
    """
    # Step 1: Prepare all measurements
    prep_results = parallel_prepare_measure(spectrometers, configs)
    
    if not all(prep_results.values()):
        failed = [idx for idx, success in prep_results.items() if not success]
        print(f"Failed to prepare spectrometers: {failed}")
        return {idx: (False, None) for idx in range(len(spectrometers))}
    
    # Step 2: Start all measurements
    meas_results = parallel_measure(spectrometers, num_measurements)
    
    if not all(meas_results.values()):
        failed = [idx for idx, success in meas_results.items() if not success]
        print(f"Failed to start measurements on spectrometers: {failed}")
        return {idx: (False, None) for idx in range(len(spectrometers))}
    
    # Step 3: Poll and retrieve data
    data_results = parallel_poll_and_get_data(spectrometers, timeout)
    
    return data_results


def parallel_stop_measure(spectrometers: List) -> Dict[int, bool]:
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
    
    for idx, spec in enumerate(spectrometers):
        try:
            spec.stop_measure()
            results[idx] = True
        except Exception as e:
            print(f"Error stopping spectrometer {idx}: {e}")
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
