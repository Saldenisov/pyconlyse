import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import LaserPointingController, {
  CameraPreview,
  ConvergenceChart,
  DeltaVectorChart,
  alignmentActivityText,
  actuatorGroupForPoint,
  actuatorGroupForRole,
  actuatorVisualState,
  formatOpticalStatusValue,
  laserSnapshotErrorMessage,
  pointAperture,
  pointNumber,
  roundnessError,
} from './LaserPointingController';

describe('LaserPointing optical point presentation', () => {
  test('extracts numeric point names without treating working as a plane point', () => {
    expect(pointNumber('point1')).toBe(1);
    expect(pointNumber('POINT6')).toBe(6);
    expect(pointNumber('working')).toBeNull();
  });

  test('selects the active 40/20/10 diaphragm aperture from each preset', () => {
    expect(pointAperture({ CrimpingDiaphragm1: 40, CrimpingDiaphragm2: 60 })).toBe(40);
    expect(pointAperture({ CrimpingDiaphragm1: 30, CrimpingDiaphragm2: 10 })).toBe(10);
    expect(pointAperture({ TranslationStage1: [3, -700] })).toBeNull();
  });

  test('maps optical points and roles to the protected Standa pair', () => {
    const groups = {
      'Actuators 1': ['ActuatorX1', 'ActuatorY1'],
      'Actuators 2': ['ActuatorX2', 'ActuatorY2'],
    };

    expect(actuatorGroupForPoint('point1')).toBe(1);
    expect(actuatorGroupForPoint('point3')).toBe(1);
    expect(actuatorGroupForPoint('point4')).toBe(2);
    expect(actuatorGroupForPoint('point6')).toBe(2);
    expect(actuatorGroupForPoint('working')).toBe(0);
    expect(actuatorGroupForRole('ActuatorY1', groups)).toBe(1);
    expect(actuatorGroupForRole('ActuatorX2', groups)).toBe(2);
  });

  test('physical disconnection overrides passive STANDBY presentation', () => {
    expect(actuatorVisualState({
      state: 'STANDBY',
      hardware_connection_state: 'DISCONNECTED',
      initialization_state: 'NOT_REQUESTED',
    })).toBe('disconnected');
    expect(actuatorVisualState({
      state: 'STANDBY',
      hardware_connection_state: 'CONNECTED',
      initialization_state: 'NOT_REQUESTED',
    })).toBe('standby');
    expect(actuatorVisualState({
      state: 'ON',
      hardware_connection_state: 'READY',
      initialization_state: 'SUCCEEDED',
    })).toBe('ready');
  });

  test('presents Tango serialization timeouts as an automatic retry', () => {
    expect(laserSnapshotErrorMessage(new Error(
      'API_CommandTimedOut: Not able to acquire serialization monitor'
    ))).toBe('LaserPointing controller is busy; retrying automatically…');
  });

  test('uses beam roundness for automatic convergence while retaining legacy history', () => {
    expect(roundnessError({ roundness_error_pct: 6.5, error_px: 99 })).toBe(6.5);
    expect(roundnessError({ error_px: 4.25 })).toBe(4.25);

    render(
      <ConvergenceChart
        tolerance={7}
        history={[
          { elapsed_s: 0, roundness_error_pct: 12, error_px: 88, actuator_group: 1 },
          { elapsed_s: 4.5, roundness_error_pct: 5.5, error_px: 77, actuator_group: 2 },
        ]}
      />
    );

    expect(screen.getByRole('img', {
      name: /beam roundness error convergence over elapsed time/i,
    })).toBeInTheDocument();
    expect(screen.getByText('Roundness error (%)')).toBeInTheDocument();
    expect(screen.getByText('Roundness tolerance')).toBeInTheDocument();
    expect(screen.getAllByText(/Diaphragm 1 · Standa pair 1/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Diaphragm 2 · Standa pair 2/i).length).toBeGreaterThan(0);
  });

  test('describes point changes, actuator corrections and profile calculations for the operator', () => {
    expect(alignmentActivityText({
      phase: 'applying_point', point: 'point3', optical_role: 'CrimpingDiaphragm1', optical_target: 10,
    })).toEqual({ title: 'Moving optics to point 3', detail: 'CrimpingDiaphragm1 → 10' });
    expect(alignmentActivityText({
      phase: 'moving_actuators', group: 'group1',
      actuator_roles: ['ActuatorX3', 'ActuatorY3'], move_delta: [5, 0],
    })).toEqual({ title: 'Adjusting group1', detail: 'ActuatorX3 +5.00 · ActuatorY3 +0.00' });
    expect(alignmentActivityText({
      phase: 'calculating_profiles', point: 'point6',
    })).toEqual({
      title: 'Calculating profiles at point 6',
      detail: 'Fitting nine iso-intensity contours from the outer beam to the core',
    });
  });

  test('formats the desktop-equivalent passive optical readback', () => {
    expect(formatOpticalStatusValue('Shutter2', -1)).toBe('−1');
    expect(formatOpticalStatusValue('Shutter2', 1)).toBe('+1');
    expect(formatOpticalStatusValue('Shutter2', 0)).toBe('UNKNOWN');
    expect(formatOpticalStatusValue('Shutter2', 'UP_BLOCKED')).toBe('UP · BLOCKED');
    expect(formatOpticalStatusValue('Shutter2', 'DOWN_CLEAR')).toBe('DOWN · CLEAR');
    expect(formatOpticalStatusValue('Shutter2', 'LEFT')).toBe('UP · BLOCKED');
    expect(formatOpticalStatusValue('Shutter2', 'RIGHT')).toBe('DOWN');
    expect(formatOpticalStatusValue('CrimpingDiaphragm1', 40)).toBe('40%');
    expect(formatOpticalStatusValue('HalfWavePlate1', 20.5)).toBe('20.5%');
  });

  test('renders signed XY delta values and a true centred vector view', () => {
    render(
      <DeltaVectorChart
        tolerance={2}
        history={[
          { delta_px: [7, -4], error_px: 8.06, actuator_group: 1 },
          { delta_px: [1.25, -0.5], error_px: 99, actuator_group: 2 },
        ]}
      />
    );

    expect(screen.getByRole('img', {
      name: /xy delta vector and trajectory centred on zero/i,
    })).toBeInTheDocument();
    expect(screen.getByText('+1.25 px')).toBeInTheDocument();
    expect(screen.getByText('-0.50 px')).toBeInTheDocument();
    expect(screen.getByText('1.35 px')).toBeInTheDocument();
  });

  test('lets the operator start an off camera from the preview', async () => {
    const originalFetch = global.fetch;
    const onRefresh = jest.fn().mockResolvedValue(undefined);
    global.fetch = jest.fn().mockImplementation((url, options = {}) => {
      if (url.endsWith('/info')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            camera_info: {
              exposure_time: 1500,
              gain: 2,
              gain_min: 0,
              gain_max: 3,
              width: 1280,
              height: 1024,
              offsetX: 16,
              offsetY: 24,
              center_gravity_threshold: 120,
              trigger_mode: 0,
              format_pixel: 'Mono8',
            },
          }),
        });
      }
      if (url.endsWith('/parameters')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            results: { offsetX: { success: true, value: 32 } },
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, grabbing: true, state_confirmed: true }),
      });
    });

    const view = render(
      <CameraPreview
        camera="manip/V0/Cam1_V0"
        enabled={false}
        state="OFF"
        onRefresh={onRefresh}
      />
    );

    expect(screen.queryByLabelText('Offset X')).not.toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/info',
      expect.anything()
    );

    fireEvent.click(screen.getByRole('button', { name: 'Start camera' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/grabbing',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'start' }),
      })
    ));
    await waitFor(() => expect(onRefresh).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByText('Camera controls'));
    const threshold = await screen.findByLabelText('Threshold CG');
    const offsetX = await screen.findByLabelText('Offset X');
    expect(threshold).toHaveValue(120);
    expect(offsetX).toHaveValue(16);
    expect(screen.getAllByRole('spinbutton')).toHaveLength(7);
    expect(screen.queryByLabelText('Trigger mode')).not.toBeInTheDocument();
    const gain = screen.getByLabelText('Gain');
    fireEvent.change(gain, { target: { value: '10' } });
    fireEvent.blur(gain);
    expect(await screen.findByText('Gain must be at most 3.')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/parameters',
      expect.objectContaining({ body: JSON.stringify({ gain: 10 }) })
    );
    fireEvent.change(threshold, { target: { value: '125' } });
    fireEvent.blur(threshold);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/parameters',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ center_gravity_threshold: 125 }),
      })
    ));
    fireEvent.change(offsetX, { target: { value: '32' } });
    fireEvent.blur(offsetX);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/parameters',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ offsetX: 32 }),
      })
    ));

    view.unmount();
    global.fetch = originalFetch;
  });

  test('keeps preview reads suspended after the operator stops the camera', async () => {
    const originalFetch = global.fetch;
    const onRefresh = jest.fn().mockResolvedValue(undefined);
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url.endsWith('/info')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, camera_info: {} }),
        });
      }
      if (url.endsWith('/image')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, image: [] }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, grabbing: false, state_confirmed: true }),
      });
    });

    const view = render(
      <CameraPreview
        camera="manip/V0/Cam1_V0"
        enabled
        state="ON"
        onRefresh={onRefresh}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Stop camera' }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/camera/manip%2FV0%2FCam1_V0/grabbing',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'stop' }),
      })
    ));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start camera' })).toBeInTheDocument());

    view.unmount();
    global.fetch = originalFetch;
  });

  test('separates automatic visualization from manual Standa and OWIS controls', async () => {
    const snapshot = {
      device: 'manip/V0/LaserPointing-Cam2',
      state: 'ON',
      rules: {
        point3: { CrimpingDiaphragm1: 10, TranslationStage1: [3, 0] },
        point6: { CrimpingDiaphragm2: 10, TranslationStage1: [3, -700] },
      },
      groups: {
        'Actuators 1': ['ActuatorX1', 'ActuatorY1'],
        'Actuators 2': ['ActuatorX2', 'ActuatorY2'],
      },
      capabilities: {
        automatic_search: true,
        apply_point: true,
        manual_point_selection: true,
        initialize_active_pair: true,
        interlocked_motion: true,
      },
      automatic_search: {
        status: 'idle',
        progress: {
          phase: 'measuring',
          reference_roundness_pct: 96,
          test_roundness_pct: 91,
          roundness_error_pct: 9,
        },
        history: [{ elapsed_s: 1, roundness_error_pct: 9, error_px: 9, actuator_group: 1 }],
        config: {
          mode: 'sensitive',
          step_schedule: [10, 6, 2],
          radius: 30,
          tolerance_px: 2,
          roundness_tolerance_pct: 7,
          max_evaluations: 16,
          samples: 3,
        },
      },
      pair_initialization: { phase: 'idle', message: 'Select a point' },
      active_point: '',
      camera: { device: 'manip/V0/Cam2', state: 'OFF', centroid_valid: false },
      actuators: [
        {
          role: 'ActuatorX1', device: 'manip/V0/x1', state: 'ON', position: 1.5, ready: true, move_supported: true,
        },
        {
          role: 'ActuatorY1', device: 'manip/V0/y1', state: 'ON', position: -2, ready: true, move_supported: true,
        },
      ],
      manual_devices: [{
        role: 'TranslationStage1',
        device: 'manip/general/DS_OWIS_Aggregator',
        state: 'ON',
        ready: true,
        move_supported: true,
        axes: [{ axis: 3, position: -700 }],
      }],
      other_devices: [
        {
          role: 'CrimpingDiaphragm1',
          control_type: 'diaphragm',
          friendly_name: 'IrisExp_1',
          device: 'manip/V0/dv01',
          state: 'ON',
          position: 40,
          preset_positions: [0, 5, 10, 15, 25, 40, 100],
          unit: '%',
          ready: true,
          move_supported: true,
          stop_supported: true,
        },
        {
          role: 'HalfWavePlate1',
          control_type: 'half_wave_plate',
          friendly_name: 'Lambda_2_Exp',
          device: 'manip/V0/L-2_1',
          state: 'ON',
          position: 100,
          preset_positions: [0, 5, 10, 15, 20, 50, 100],
          unit: '%',
          ready: true,
          move_supported: true,
          stop_supported: true,
        },
        {
          role: 'Shutter1',
          control_type: 'flipper',
          friendly_name: 'ShutterExp_1',
          device: 'manip/V0/s1',
          state: 'ON',
          position: 0,
          commanded_flipper_state: 'UP_BLOCKED',
          unit: 'state',
          ready: true,
          move_supported: true,
          stop_supported: true,
        },
        {
          role: 'Shutter2',
          control_type: 'flipper',
          friendly_name: 'ShutterExp_2',
          device: 'manip/V0/s2',
          state: 'ON',
          position: -1,
          commanded_flipper_state: 'UP_BLOCKED',
          preset_positions: [-1, 1],
          unit: 'state',
          ready: true,
          move_supported: true,
          stop_supported: true,
        },
      ],
    };
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, snapshot }),
    });

    const view = render(<LaserPointingController deviceName={snapshot.device} />);
    expect(await screen.findByRole('tab', { name: 'Automatic' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Convergence over time')).toBeInTheDocument();
    expect(screen.getByLabelText('Roundness error (%)')).toHaveValue(7);
    expect(screen.getByRole('img', { name: /beam roundness error convergence/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Current beam roundness metrics')).toHaveTextContent('Reference 96.00%');
    expect(screen.queryByText('Standa alignment mounts')).not.toBeInTheDocument();
    expect(screen.getByText('Optical points')).toBeInTheDocument();
    const componentStatus = screen.getByRole('region', { name: 'Main components live status' });
    expect(within(componentStatus).getByText('Camera')).toBeInTheDocument();
    expect(within(componentStatus).getByText('Standa 1')).toBeInTheDocument();
    expect(within(componentStatus).getByText('40%')).toBeInTheDocument();
    expect(within(componentStatus).getAllByText('UP · BLOCKED')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: /Point 3 Fine 10%/i }));
    expect(screen.getByLabelText('point3 optical state')).toBeInTheDocument();
    expect(screen.getByLabelText('CrimpingDiaphragm1 target aperture 10% open')).toBeInTheDocument();
    expect(screen.getByText('40% → 10%')).toBeInTheDocument();
    expect(screen.getByText('DL position')).toBeInTheDocument();
    expect(screen.getByText('-700 → 0')).toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/manip%2FV0%2FLaserPointing-Cam2/command/apply_controller_point',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ args: 'point3' }),
      })
    ));

    fireEvent.click(screen.getByRole('tab', { name: 'Manual' }));
    expect(screen.getByText('Standa alignment mounts')).toBeInTheDocument();
    expect(screen.getAllByText('TranslationStage1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Axis 3')).toBeInTheDocument();
    expect(screen.getByText('Basler preview')).toBeInTheDocument();
    expect(screen.getByText('Centroid diagnostic')).toBeInTheDocument();
    expect(screen.getByText(/automatic alignment minimizes beam roundness error/i)).toBeInTheDocument();
    expect(screen.getByText('Optical points')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Point 3 Fine 10%/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Point 6 Fine 10%/i })).toBeInTheDocument();
    expect(screen.queryByText('Active Standa pair')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Initialize active pair/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Convergence over time')).not.toBeInTheDocument();

    const standaStep = screen.getByLabelText('ActuatorX1 step size');
    expect(standaStep).toBeEnabled();
    fireEvent.change(standaStep, { target: { value: '0.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Increase ActuatorX1 by 0.5' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/manip%2FV0%2Fx1/command/move_axis_abs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ args: 2 }),
      })
    ));

    fireEvent.click(screen.getByRole('tab', { name: 'Other' }));
    expect(screen.getByRole('tabpanel', { name: 'Other optical controls' })).toBeInTheDocument();
    expect(screen.getByText('Optical points')).toBeInTheDocument();
    expect(screen.getByLabelText('point3 optical state')).toBeInTheDocument();
    expect(screen.getByText('Basler preview')).toBeInTheDocument();
    expect(screen.getByText(/controller-owned flippers/i)).toBeInTheDocument();
    expect(screen.getAllByText('CrimpingDiaphragm1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('λ/2 plate · HalfWavePlate1')).toBeInTheDocument();
    expect(screen.getByText('Camera flipper · Shutter1')).toBeInTheDocument();
    expect(screen.getByText('Camera flipper · Shutter2')).toBeInTheDocument();
    expect(screen.getAllByText('Last completed command')).toHaveLength(2);
    const firstFlipper = screen.getByText('Camera flipper · Shutter1').closest('section');
    fireEvent.click(within(firstFlipper).getByRole('button', { name: '+1 · Lower / clear' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/manip%2FV0%2Fs1/command/move_axis_abs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ args: 1 }),
      })
    ));
    const secondFlipper = screen.getByText('Camera flipper · Shutter2').closest('section');
    const secondFlipperButton = within(secondFlipper).getByRole('button', { name: '+1 · Lower / clear' });
    await waitFor(() => expect(secondFlipperButton).toBeEnabled());
    fireEvent.click(secondFlipperButton);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/manip%2FV0%2Fs2/command/move_axis_abs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ args: 1 }),
      })
    ));
    expect(screen.getByText('40.00 %')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set CrimpingDiaphragm1 to 25 %' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Set HalfWavePlate1 to 50 %' })).toBeInTheDocument();
    const target = screen.getByLabelText('CrimpingDiaphragm1 target');
    fireEvent.change(target, { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Move CrimpingDiaphragm1 to target' }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/api/device/manip%2FV0%2Fdv01/command/move_axis_abs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ args: 20 }),
      })
    ));

    view.unmount();
    global.fetch = originalFetch;
  });
});
