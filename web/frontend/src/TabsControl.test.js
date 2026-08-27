import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import TabsControl, { summarizeFolderSetProgress } from './TabsControl';
import { TreatmentContext } from './DataWindowVD2';
import {
  enqueueStandardFolderTreatment,
  enqueueTreatmentRecipe,
  fetchFolderListing,
  fetchTreatmentQueue,
  fetchTreatmentSession,
  postTreatment,
  updateSelectionConfig,
} from './api/treatmentClient';

jest.mock('./api/treatmentClient', () => ({
  fetchCleaningView: jest.fn().mockResolvedValue({ success: true, cleaning_view: null }),
  fetchCompressionJob: jest.fn(),
  fetchFileSummary: jest.fn(),
  fetchFolderListing: jest.fn().mockResolvedValue({ success: true, folders: [], files: [] }),
  fetchTreatmentQueue: jest.fn().mockResolvedValue({
    success: true,
    queue: { running: false, active_job_id: null, pending_count: 0, jobs: [] },
  }),
  fetchTreatmentSession: jest.fn(),
  enqueueStandardFolderTreatment: jest.fn(),
  enqueueTreatmentRecipe: jest.fn(),
  postTreatment: jest.fn(),
  removeTreatmentQueueJob: jest.fn(),
  startCompressionJob: jest.fn(),
  updateSelectionConfig: jest.fn(),
}));

const sessionPayload = {
  success: true,
  allowed_root: '',
  allowed_root_exists: false,
  exp_types: ['ABS+BASE+NOISE'],
  data_types: ['ABS', 'BASE', 'NOISE'],
  calc_modes: ['averaged'],
  session: {
    exp_type: 'ABS+BASE+NOISE',
    selected_data_type: 'ABS',
    calc_mode: 'averaged',
    first_map_with_electrons: true,
    folder_path: '',
    paths: {},
    path_sources: {},
    required_data_types: ['ABS', 'BASE', 'NOISE'],
    active_data_type: '',
    ready_for_calc: false,
    result_ready: false,
    save_folder: '',
    save_file_name: '',
  },
};

function renderStudioTabs() {
  return render(
    <TreatmentContext.Provider
      value={{
        treatmentSessionId: 'test-session',
        treatmentProfile: 'VD2',
        treatmentLayoutMode: 'studio',
        requestSelectionRefresh: jest.fn(),
      }}
    >
      <TabsControl />
    </TreatmentContext.Provider>
  );
}

test('summarizes folder progress in one compact line', () => {
  expect(summarizeFolderSetProgress({
    phase: 'converting',
    current_items: 0,
    total_items: 3,
    message: 'BASE: Compressing map 36/200 with gzip level 4',
    files: {
      ABS: { status: 'running', phase: 'convert', current: 38, total: 200 },
      BASE: { status: 'running', phase: 'convert', current: 36, total: 200 },
    },
  }, '/runs/12890-water_600_1us-x0')).toBe('12890-water_600_1us-x0 · BASE 36/200 · 0/3');
});

const readySessionPayload = {
  ...sessionPayload,
  session: {
    ...sessionPayload.session,
    folder_path: '/runs/run-001',
    save_folder: '/runs/run-001',
    save_file_name: 'od.dat',
    paths: {
      ABS: '/runs/run-001/abs.h5',
      BASE: '/runs/run-001/base.h5',
      NOISE: '/runs/run-001/noise.h5',
    },
    path_sources: {
      ABS: '/runs/run-001/abs.h5',
      BASE: '/runs/run-001/base.h5',
      NOISE: '/runs/run-001/noise.h5',
    },
    active_data_type: 'ABS',
    ready_for_calc: true,
  },
};

describe('Studio treatment inputs', () => {
  beforeEach(() => {
    fetchTreatmentSession.mockResolvedValue(sessionPayload);
    fetchFolderListing.mockResolvedValue({ success: true, folders: [], files: [] });
    fetchTreatmentQueue.mockResolvedValue({
      success: true,
      queue: { running: false, active_job_id: null, pending_count: 0, jobs: [] },
    });
    enqueueTreatmentRecipe.mockResolvedValue({
      success: true,
      started: true,
      queue: {
        running: true,
        active_job_id: 'job-1',
        pending_count: 0,
        jobs: [{
          job_id: 'job-1',
          recipe: { label: 'recipe-1' },
          status: 'running',
          phase: 'preparing',
        }],
      },
    });
    enqueueStandardFolderTreatment.mockResolvedValue({
      success: true,
      queue: {
        running: false,
        active_job_id: null,
        pending_count: 1,
        jobs: [{ job_id: 'folder-job', label: 'next-folder', status: 'queued', phase: 'queued' }],
      },
    });
    postTreatment.mockResolvedValue({ success: true });
  });

  test('shows source, role and processing sections with queue controls', async () => {
    renderStudioTabs();

    await waitFor(() => expect(fetchTreatmentSession).toHaveBeenCalledWith('test-session'));
    expect(await screen.findByRole('heading', { name: 'Processing' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Source files' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Input roles' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Queue' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'SAM cleaning' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'SAM cleaning' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Advanced: Stitch' })).toBeInTheDocument();
  });

  test('adds current recipe and starts it without a manual queue action', async () => {
    fetchTreatmentSession.mockResolvedValue(readySessionPayload);
    renderStudioTabs();

    expect(await screen.findByRole('heading', { name: 'Queue' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Queue label'), { target: { value: 'recipe-1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add recipe' }));

    await waitFor(() => expect(enqueueTreatmentRecipe).toHaveBeenCalledWith('test-session', {
      label: 'recipe-1',
      cleaning: {
        state: 'pending',
        enabled: true,
        angle_threshold: 1,
        surface_threshold: 1,
        data_types: ['ABS', 'BASE', 'NOISE'],
      },
      convert_to_h5: false,
      profile: 'VD2',
    }));
    expect(await screen.findByText('running · preparing')).toBeInTheDocument();
    expect(screen.getByText('recipe-1')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run queue' })).not.toBeInTheDocument();
  });

  test.each([
    ['Set', false, false, false],
    ['Set/Convert', true, false, false],
    ['Set/Convert/Clean', true, true, false],
    ['Set/Convert/Calc', true, false, true],
    ['Set/Convert/Clean/Calc', true, true, true],
  ])('queues %s with immutable action flags', async (action, convert, clean, calculate) => {
    const nextFolder = '/runs/next-folder';
    fetchTreatmentSession.mockResolvedValue({ ...readySessionPayload, allowed_root: '/runs' });
    fetchFolderListing.mockImplementation((_sessionId, folderPath) => Promise.resolve({
      success: true,
      folders: folderPath === '/runs' ? [{ name: 'next-folder', path: nextFolder }] : [],
      files: [],
    }));
    renderStudioTabs();

    fireEvent.click(await screen.findByRole('button', { name: 'Select Folder' }));
    const nextFolderButton = await screen.findByRole('button', { name: 'next-folder' });
    fireEvent.contextMenu(nextFolderButton);
    fireEvent.click(screen.getByRole('button', { name: action }));

    await waitFor(() => expect(enqueueStandardFolderTreatment).toHaveBeenCalledWith('test-session', {
      folder_path: nextFolder,
      label: 'next-folder',
      profile: 'VD2',
      convert,
      clean,
      calculate,
      angle_threshold: 1,
      surface_threshold: 1,
    }));
  });

  test('accepts another folder click while the first enqueue request is pending', async () => {
    const firstFolder = '/runs/first-folder';
    const secondFolder = '/runs/second-folder';
    let resolveFirst;
    fetchTreatmentSession.mockResolvedValue({ ...readySessionPayload, allowed_root: '/runs' });
    fetchFolderListing.mockImplementation((_sessionId, folderPath) => Promise.resolve({
      success: true,
      folders: folderPath === '/runs'
        ? [
            { name: 'first-folder', path: firstFolder },
            { name: 'second-folder', path: secondFolder },
          ]
        : [],
      files: [],
    }));
    enqueueStandardFolderTreatment
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({
        success: true,
        started: false,
        queue: { running: true, jobs: [] },
      });
    renderStudioTabs();

    fireEvent.click(await screen.findByRole('button', { name: 'Select Folder' }));
    const firstButton = await screen.findByRole('button', { name: 'first-folder' });
    const secondButton = await screen.findByRole('button', { name: 'second-folder' });
    fireEvent.contextMenu(firstButton);
    fireEvent.click(screen.getByRole('button', { name: 'Set' }));
    fireEvent.contextMenu(secondButton);
    fireEvent.click(screen.getByRole('button', { name: 'Set/Convert/Calc' }));

    await waitFor(() => expect(enqueueStandardFolderTreatment).toHaveBeenCalledTimes(2));
    await act(async () => {
      resolveFirst({ success: true, started: true, queue: { running: true, jobs: [] } });
      await Promise.resolve();
    });
  });

  test('keeps failed queue job visible with backend error', async () => {
    fetchTreatmentSession.mockResolvedValue(readySessionPayload);
    enqueueTreatmentRecipe.mockResolvedValue({
      success: true,
      queue: {
        running: false,
        active_job_id: null,
        pending_count: 0,
        jobs: [{
          job_id: 'job-failed',
          label: 'recipe-1',
          status: 'failed',
          phase: 'error',
          error: 'conversion failed',
        }],
      },
    });
    renderStudioTabs();

    await screen.findByRole('heading', { name: 'Queue' });
    fireEvent.click(screen.getByRole('button', { name: 'Add recipe' }));

    expect(await screen.findByText('failed · error')).toBeInTheDocument();
    expect(screen.getByText('conversion failed')).toBeInTheDocument();
  });

  test('restores a backend cleaning preview after reload and blocks OD, queue, and Apply', async () => {
    fetchTreatmentSession.mockResolvedValue({
      ...readySessionPayload,
      session: {
        ...readySessionPayload.session,
        cleaning_preview: {
          ready: true,
          data_type: 'ABS',
          file_path: '/runs/run-001/abs.h5',
          source_measurements: 8,
          cleaned_measurements: 6,
        },
      },
    });
    renderStudioTabs();

    expect(await screen.findByText(/backend cleaning preview/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Calculate OD' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add recipe' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Cleaning' }));
    expect(await screen.findByRole('button', { name: 'Apply mask to H5' })).toBeDisabled();
  });

  test('invalidates Apply after threshold drift without orphaning the backend preview', async () => {
    fetchTreatmentSession.mockResolvedValue(readySessionPayload);
    postTreatment.mockResolvedValue({
      success: true,
      cleaning: {
        state_updated: true,
        source_measurements: 10,
        original_measurements: 10,
        cleaned_measurements: 8,
        pass_retention_rate: 80,
        retention_rate: 80,
        sam_angle_min: 0.1,
        sam_angle_max: 0.4,
        sam_angle_mean: 0.25,
      },
      cleaning_view: null,
    });
    renderStudioTabs();

    await screen.findByRole('heading', { name: 'Queue' });
    fireEvent.click(screen.getByRole('button', { name: 'Cleaning' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Preview cleaning' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Apply mask to H5' })).toBeEnabled());

    fireEvent.change(screen.getByLabelText('Angle Threshold (degrees)'), { target: { value: '2.0' } });
    expect(screen.getByRole('button', { name: 'Apply mask to H5' })).toBeDisabled();
    expect(screen.getByText(/must be refreshed with the current thresholds/i)).toBeInTheDocument();
  });

  test('blocks changing cleaning target while a different role preview is pending', async () => {
    fetchTreatmentSession.mockResolvedValue({
      ...readySessionPayload,
      session: {
        ...readySessionPayload.session,
        cleaning_preview: {
          ready: true,
          data_type: 'ABS',
          file_path: '/runs/run-001/abs.h5',
        },
      },
    });
    renderStudioTabs();

    await screen.findByText(/backend cleaning preview/i);
    fireEvent.click(screen.getByRole('button', { name: 'Cleaning' }));
    fireEvent.change(await screen.findByLabelText('Clean File'), { target: { value: 'BASE' } });

    expect(updateSelectionConfig).not.toHaveBeenCalled();
    expect(screen.getByText(/Apply or reset the ABS cleaning preview before selecting another role/i)).toBeInTheDocument();
  });
});
