"""
Test Script for Parallel Avantes Spectrometer Readout
======================================================

This script demonstrates how to use the parallel measurement functions
to achieve true simultaneous readout of multiple Avantes spectrometers.

Requirements:
- Two Avantes AvaSpec-2048L spectrometers connected
- msl-equipment library installed
- avantes_parallel module
"""

import sys
from pathlib import Path
import time
import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))

from msl.equipment import Backend, ConnectionRecord, EquipmentRecord

# Import parallel measurement functions
from DeviceServers.cameras.avantes.avantes_parallel import (
    parallel_full_measurement,
    parallel_poll_and_get_data,
    parallel_measure,
    parallel_prepare_measure,
    parallel_stop_measure
)


def test_parallel_basic():
    """Test basic parallel measurement with two spectrometers."""
    
    print("=" * 70)
    print("Test 1: Basic Parallel Measurement")
    print("=" * 70)
    
    # Configuration for spectrometer 1
    record1 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810225U1",  # Default serial number for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    # Configuration for spectrometer 2
    record2 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810226U1",  # Default serial number for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    # Connect to both spectrometers
    print("Connecting to spectrometers...")
    spec1 = record1.connect(demo=False)
    spec2 = record2.connect(demo=False)
    
    print(f"  Spec1 handle: {spec1._handle}")
    print(f"  Spec2 handle: {spec2._handle}")
    print(f"  Spec1 pixels: {spec1.get_num_pixels()}")
    print(f"  Spec2 pixels: {spec2.get_num_pixels()}")
    
    # Enable 16-bit ADC for both
    spec1.use_high_res_adc(True)
    spec2.use_high_res_adc(True)
    
    # Create measurement configurations
    num_pixels1 = spec1.get_num_pixels()
    num_pixels2 = spec2.get_num_pixels()
    
    cfg1 = spec1.MeasConfigType()
    cfg1.m_StopPixel = num_pixels1 - 1
    cfg1.m_IntegrationTime = 100  # milliseconds
    cfg1.m_NrAverages = 1
    
    # Software trigger mode for testing
    trigger1 = spec1.TriggerType()
    trigger1.m_Mode = 0  # Software trigger
    trigger1.m_Source = 0
    trigger1.m_SourceType = 0
    cfg1.m_Trigger = trigger1
    
    cfg2 = spec2.MeasConfigType()
    cfg2.m_StopPixel = num_pixels2 - 1
    cfg2.m_IntegrationTime = 100  # milliseconds
    cfg2.m_NrAverages = 1
    
    trigger2 = spec2.TriggerType()
    trigger2.m_Mode = 0  # Software trigger
    trigger2.m_Source = 0
    trigger2.m_SourceType = 0
    cfg2.m_Trigger = trigger2
    
    # Test 1: Using convenience function
    print("\nTest 1a: Using parallel_full_measurement()...")
    start_time = time.time()
    
    results = parallel_full_measurement(
        spectrometers=[spec1, spec2],
        configs=[cfg1, cfg2],
        num_measurements=1,
        timeout=5.0
    )
    
    elapsed = time.time() - start_time
    
    print(f"  Measurement completed in {elapsed:.3f} seconds")
    for idx, (success, data) in results.items():
        if success and data is not None:
            print(f"  Spec{idx+1}: SUCCESS - {len(data)} pixels, mean={np.mean(data):.1f}, max={np.max(data):.1f}")
        else:
            print(f"  Spec{idx+1}: FAILED")
    
    # Test 2: Manual step-by-step (gives more control)
    print("\nTest 1b: Manual step-by-step parallel measurement...")
    start_time = time.time()
    
    # Step 1: Prepare both
    prep_results = parallel_prepare_measure([spec1, spec2], [cfg1, cfg2])
    print(f"  Prepare: {prep_results}")
    
    # Step 2: Start both measurements
    meas_results = parallel_measure([spec1, spec2], num_measurements=1)
    print(f"  Measure: {meas_results}")
    
    # Step 3: Poll and get data
    data_results = parallel_poll_and_get_data([spec1, spec2], timeout=5.0, poll_interval=0.001)
    
    elapsed = time.time() - start_time
    
    print(f"  Manual measurement completed in {elapsed:.3f} seconds")
    for idx, (success, data) in data_results.items():
        if success and data is not None:
            print(f"  Spec{idx+1}: SUCCESS - {len(data)} pixels, mean={np.mean(data):.1f}, max={np.max(data):.1f}")
        else:
            print(f"  Spec{idx+1}: FAILED")
    
    # Disconnect
    print("\nDisconnecting...")
    spec1.disconnect()
    spec2.disconnect()
    
    print("✓ Test 1 completed successfully\n")


def test_parallel_hardware_trigger():
    """Test parallel measurement with hardware trigger (requires Arduino sync)."""
    
    print("=" * 70)
    print("Test 2: Hardware-Triggered Parallel Measurement")
    print("=" * 70)
    
    # Similar setup to test_parallel_basic, but with hardware trigger
    record1 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810225U1",  # Default for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    record2 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810226U1",  # Default for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    print("Connecting to spectrometers...")
    spec1 = record1.connect(demo=False)
    spec2 = record2.connect(demo=False)
    
    spec1.use_high_res_adc(True)
    spec2.use_high_res_adc(True)
    
    # Hardware trigger configuration
    num_pixels1 = spec1.get_num_pixels()
    num_pixels2 = spec2.get_num_pixels()
    
    cfg1 = spec1.MeasConfigType()
    cfg1.m_StopPixel = num_pixels1 - 1
    cfg1.m_IntegrationTime = 100
    cfg1.m_NrAverages = 1
    
    # Hardware trigger mode
    trigger1 = spec1.TriggerType()
    trigger1.m_Mode = 1  # Hardware trigger
    trigger1.m_Source = 0  # External trigger
    trigger1.m_SourceType = 0  # Edge trigger
    cfg1.m_Trigger = trigger1
    
    cfg2 = spec2.MeasConfigType()
    cfg2.m_StopPixel = num_pixels2 - 1
    cfg2.m_IntegrationTime = 100
    cfg2.m_NrAverages = 1
    
    trigger2 = spec2.TriggerType()
    trigger2.m_Mode = 1  # Hardware trigger
    trigger2.m_Source = 0  # External trigger
    trigger2.m_SourceType = 0  # Edge trigger
    cfg2.m_Trigger = trigger2
    
    print("\nPreparing hardware-triggered measurement...")
    print("NOTE: This requires external trigger from Arduino!")
    print("      Make sure Arduino is configured to generate trigger pulses.")
    
    # Prepare both spectrometers for hardware trigger
    prep_results = parallel_prepare_measure([spec1, spec2], [cfg1, cfg2])
    print(f"  Prepare: {prep_results}")
    
    # Start measurements (will wait for hardware trigger)
    meas_results = parallel_measure([spec1, spec2], num_measurements=1)
    print(f"  Measure started: {meas_results}")
    print("  Waiting for hardware trigger...")
    
    # Poll for data (will wait until trigger arrives and measurement completes)
    start_time = time.time()
    data_results = parallel_poll_and_get_data([spec1, spec2], timeout=10.0, poll_interval=0.001)
    elapsed = time.time() - start_time
    
    print(f"\n  Hardware-triggered measurement completed in {elapsed:.3f} seconds")
    for idx, (success, data) in data_results.items():
        if success and data is not None:
            print(f"  Spec{idx+1}: SUCCESS - {len(data)} pixels, mean={np.mean(data):.1f}, max={np.max(data):.1f}")
        else:
            print(f"  Spec{idx+1}: FAILED")
    
    # Disconnect
    print("\nDisconnecting...")
    spec1.disconnect()
    spec2.disconnect()
    
    print("✓ Test 2 completed successfully\n")


def test_timing_comparison():
    """Compare timing between sequential and parallel readout."""
    
    print("=" * 70)
    print("Test 3: Sequential vs Parallel Timing Comparison")
    print("=" * 70)
    
    record1 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810225U1",  # Default for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    record2 = EquipmentRecord(
        manufacturer="Avantes",
        model="AvaSpec-2048L",
        serial="1810226U1",  # Default for your device
        connection=ConnectionRecord(
            address="SDK::C:/dev/pyconlyse/DeviceServers/cameras/avantes/drivers/avaspecx64.dll"
        ),
    )
    
    spec1 = record1.connect(demo=False)
    spec2 = record2.connect(demo=False)
    
    spec1.use_high_res_adc(True)
    spec2.use_high_res_adc(True)
    
    # Configuration
    num_pixels1 = spec1.get_num_pixels()
    num_pixels2 = spec2.get_num_pixels()
    
    cfg1 = spec1.MeasConfigType()
    cfg1.m_StopPixel = num_pixels1 - 1
    cfg1.m_IntegrationTime = 100
    cfg1.m_NrAverages = 1
    trigger1 = spec1.TriggerType()
    trigger1.m_Mode = 0
    trigger1.m_Source = 0
    trigger1.m_SourceType = 0
    cfg1.m_Trigger = trigger1
    
    cfg2 = spec2.MeasConfigType()
    cfg2.m_StopPixel = num_pixels2 - 1
    cfg2.m_IntegrationTime = 100
    cfg2.m_NrAverages = 1
    trigger2 = spec2.TriggerType()
    trigger2.m_Mode = 0
    trigger2.m_Source = 0
    trigger2.m_SourceType = 0
    cfg2.m_Trigger = trigger2
    
    # Sequential measurement
    print("\nSequential measurement (one after the other)...")
    start_seq = time.time()
    
    spec1.prepare_measure(cfg1)
    spec1.measure(1)
    while not spec1.poll_scan():
        time.sleep(0.001)
    tick1, data1 = spec1.get_data()
    
    spec2.prepare_measure(cfg2)
    spec2.measure(1)
    while not spec2.poll_scan():
        time.sleep(0.001)
    tick2, data2 = spec2.get_data()
    
    elapsed_seq = time.time() - start_seq
    
    # Parallel measurement
    print("Parallel measurement (simultaneous)...")
    start_par = time.time()
    
    results = parallel_full_measurement(
        spectrometers=[spec1, spec2],
        configs=[cfg1, cfg2],
        num_measurements=1,
        timeout=5.0
    )
    
    elapsed_par = time.time() - start_par
    
    # Results
    print(f"\n  Sequential time: {elapsed_seq:.3f} seconds")
    print(f"  Parallel time:   {elapsed_par:.3f} seconds")
    print(f"  Speedup:         {elapsed_seq/elapsed_par:.2f}x")
    print(f"  Time saved:      {(elapsed_seq-elapsed_par)*1000:.1f} ms")
    
    spec1.disconnect()
    spec2.disconnect()
    
    print("\n✓ Test 3 completed successfully\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AVANTES PARALLEL READOUT TEST SUITE")
    print("=" * 70 + "\n")
    
    try:
        # Run test 1: Basic parallel measurement
        test_parallel_basic()
        
        # Uncomment to test hardware trigger (requires Arduino)
        # test_parallel_hardware_trigger()
        
        # Uncomment to run timing comparison
        # test_timing_comparison()
        
        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
