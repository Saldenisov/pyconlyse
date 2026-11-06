import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import TabsControl, { summarizeFolderSetProgress } from './TabsControl';
import { TreatmentContext } from './DataWindowVD2';
import {
  enqueueStandardFolderTreatment,
  enqueueTreatmentRecipe,
  fetchFileSummary,
  fetchFolderListing,
  fetchTreatmentQueue,
  fetchTreatmentSession,
  postTreatment,
  runTreatmentQueue,
  updateSelectionConfig,
} from './api/treatmentClient';

jest.mock('./api/treatmentClient', () => ({
  TREATMENT_AUTH_MESSAGE: 'Sign in to continue data treatment, then retry your action.',
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
  runTreatmentQueue: jest.fn(),
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

function renderStudioTabs(overrides = {}, preview = null) {
  return render(
    <TreatmentContext.Provider
      value={{
        treatmentSessionId: 'test-session',
        treatmentProfile: 'VD2',
        treatmentLayoutMode: 'studio',
        requestSelectionRefresh: jest.fn(),
        ...overrides,
      }}
    >
      <TabsControl preview={preview} />
    </TreatmentContext.Provider>
  );
}

test('the tree shows names and fetches metadata only from Details', async () => {
  const path = 'E:\\DATA_VD2\\ABS.h5';
  fetchFileSummary.mockClear().mockResolvedValue({ file_summary: { number_maps: 8 } });
  fetchTreatmentSession.mockResolvedValue({ ...sessionPayload, allowed_root: 'E:\\DATA_VD2',
    session: { ...sessionPayload.session, folder_path: 'E:\\DATA_VD2' } });
  fetchFolderListing.mockResolvedValue({ folders: [], files: [
    { name: 'ABS.h5', path, suffix: '.h5', supported: true, size_bytes: 2048 },
  ] });
  renderStudioTabs({}, <section aria-label="Preview" />);
  const file = await screen.findByRole('button', { name: 'ABS.h5' });
  expect(screen.queryByText(/S:2/)).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /Source/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Save Result' })).not.toBeInTheDocument();
  expect(fetchFileSummary).not.toHaveBeenCalled();
  fireEvent.contextMenu(file);
  fireEvent.click(screen.getByRole('button', { name: 'Details' }));
  await waitFor(() => expect(fetchFileSummary).toHaveBeenCalledWith('test-session', path));
  expect(screen.getByRole('dialog', { name: 'File details' })).toHaveTextContent('2.0KB');
});

test('a folder context action submits the entire tree selection for automatic save', async () => {
  const root = 'E:\\DATA_VD2';
  const folders = ['first', 'second'].map(name => ({ name, path: `${root}\\${name}` }));
  fetchTreatmentSession.mockResolvedValue({ ...sessionPayload, allowed_root: root,
    session: { ...sessionPayload.session, folder_path: root } });
  fetchFolderListing.mockResolvedValue({ folders, files: [] });
  enqueueStandardFolderTreatment.mockResolvedValue({ queue: { running: true, jobs: [] }, started: true });
  renderStudioTabs({}, <section aria-label="Preview" />);
  fireEvent.click(await screen.findByRole('button', { name: 'first' }));
  const second = screen.getByRole('button', { name: 'second' });
  fireEvent.click(second, { ctrlKey: true });
  fireEvent.contextMenu(second);
  fireEvent.click(screen.getByRole('button', { name: 'Calculate & save', exact: true }));
  await waitFor(() => expect(enqueueStandardFolderTreatment).toHaveBeenCalledWith('test-session', expect.objectContaining({
    folder_paths: folders.map(folder => folder.path), output_naming: 'sample',
    exp_type: 'ABS+BASE+NOISE', clean: false, convert: false, calculate: true,
  })));
});

test('folder checkboxes and one Run submit a batch in the selected experiment mode', async () => {
  const root = 'E:\\DATA_VD2';
  const folders = ['Fabi', 'Sulfide'].map(name => ({ name, path: `${root}\\${name}` }));
  fetchTreatmentSession.mockResolvedValue({ ...sessionPayload, allowed_root: root,
    session: { ...sessionPayload.session, folder_path: root } });
  fetchFolderListing.mockResolvedValue({ folders, files: [] });
  enqueueStandardFolderTreatment.mockClear().mockResolvedValue({ queue: { running: true, jobs: [] }, started: true });
  renderStudioTabs({}, <section aria-label="Preview" />);

  fireEvent.click(await screen.findByRole('checkbox', { name: 'Select Fabi for batch' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Select Sulfide for batch' }));
  expect(enqueueStandardFolderTreatment).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Run selected folders (2)' }));
  await waitFor(() => expect(enqueueStandardFolderTreatment).toHaveBeenCalledWith('test-session', expect.objectContaining({
    folder_paths: folders.map(folder => folder.path), exp_type: 'ABS+BASE+NOISE',
    calculate: true, convert: false, clean: false, output_naming: 'sample',
  })));
  expect(enqueueStandardFolderTreatment).toHaveBeenCalledTimes(1);
});

test('the VD2 toolbar calculates after three manually assigned legacy files', async () => {
  const root = 'E:\\DATA_VD2';
  const inputs = [['NOISE', 'old-run-001.h5'], ['BASE', 'old-run-003.h5'], ['ABS', 'old-run-009.h5']];
  const files = inputs.map(([, name]) => ({ name, path: `${root}\\${name}`, supported: true, suffix: '.h5' }));
  let payload = { ...sessionPayload, allowed_root: root, session: { ...sessionPayload.session, folder_path: root } };
  fetchTreatmentSession.mockResolvedValue(payload);
  fetchFolderListing.mockResolvedValue({ folders: [], files });
  postTreatment.mockClear().mockImplementation(async (_sessionId, url, body) => {
    if (url.endsWith('/cache-path')) {
      const paths = { ...payload.session.paths, [body.data_type]: body.file_path };
      payload = { ...payload, session: { ...payload.session, paths, ready_for_calc: Object.keys(paths).length === 3 } };
    } else if (url.endsWith('/calc-abs')) {
      payload = { ...payload, session: { ...payload.session, result_ready: true } };
    }
    return payload;
  });
  renderStudioTabs({}, <section aria-label="Preview" />);
  const calculate = await screen.findByRole('button', { name: 'Calculate OD' });
  expect(calculate).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Cleaning' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'SK-Ana' })).toBeVisible();
  expect(screen.queryByText('Advanced settings')).not.toBeInTheDocument();
  expect(screen.queryByText('Data location')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Info' })).not.toBeInTheDocument();

  for (const [role, name] of inputs) {
    fireEvent.contextMenu(await screen.findByRole('button', { name }));
    fireEvent.click(screen.getByRole('button', { name: `Set ${role}`, exact: true }));
    await screen.findByText(`Set to ${role}: ${root}\\${name}`);
  }
  expect(calculate).toBeEnabled();
  fireEvent.click(calculate);
  await screen.findByRole('button', { name: 'Save Result' });
  expect(postTreatment).toHaveBeenCalledWith('test-session', '/api/treatment/calc-abs');
});

test('DAT double click opens a separate preview; manifest context action works for JSON', async () => {
  const onOpenManifest = jest.fn(), refresh = jest.fn();
  fetchTreatmentSession.mockResolvedValue({...sessionPayload, allowed_root:'E:\\DATA_VD2', allowed_root_exists:true,
    session:{...sessionPayload.session,folder_path:'E:\\DATA_VD2'}});
  fetchFolderListing.mockResolvedValue({success:true, folders:[], files:[
    {name:'water.dat',path:'E:\\DATA_VD2\\water.dat',suffix:'.dat',supported:true},
    {name:'vd2-manifest.json',path:'E:\\DATA_VD2\\vd2-manifest.json',suffix:'.json',supported:false}
  ]});
  postTreatment.mockResolvedValue({success:true});
  renderStudioTabs({onOpenManifest,requestSelectionRefresh:refresh});
  fireEvent.click(await screen.findByRole('button',{name:'Select Folder'}));
  fireEvent.doubleClick(await screen.findByRole('button',{name:'water.dat',exact:true}));
  await waitFor(()=>expect(postTreatment).toHaveBeenCalledWith('test-session','/api/treatment/preview/dat',{file_path:'E:\\DATA_VD2\\water.dat'}));
  await waitFor(()=>expect(refresh).toHaveBeenCalled());
  fireEvent.contextMenu(screen.getByRole('button',{name:'vd2-manifest.json',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Calculate according to manifest…'}));
  expect(onOpenManifest).toHaveBeenCalledWith('E:\\DATA_VD2\\vd2-manifest.json');
  expect(postTreatment.mock.calls.some(([,url])=>url.endsWith('/cache-path'))).toBe(false);
});

test('Cleaning exposes Absorption Base and Bruit with missing roles visibly disabled', async () => {
  window.localStorage.clear();
  fetchTreatmentSession.mockResolvedValue({...sessionPayload,session:{...sessionPayload.session,
    paths:{NOISE:'E:\\noise.h5'},path_sources:{NOISE:'E:\\noise.h5'},active_data_type:'NOISE'}});
  renderStudioTabs();
  fireEvent.click(await screen.findByRole('button',{name:'Cleaning',exact:true}));
  expect(screen.getByRole('button',{name:/Absorption Not assigned/})).toBeDisabled();
  expect(screen.getByRole('button',{name:/Base Not assigned/})).toBeDisabled();
  expect(screen.getByRole('button',{name:/Bruit \/ Noise noise.h5/})).toBeEnabled();
  expect(screen.getByRole('button',{name:/Bruit \/ Noise noise.h5/})).toHaveAttribute('aria-pressed','true');
});

test.each([true, false])('completed Set refreshes assigned files even after a tab switch (initial running=%s)', async running => {
  window.localStorage.clear(); let enqueued = false;
  fetchTreatmentSession.mockImplementation(async () => enqueued ? readySessionPayload : {
    ...sessionPayload,allowed_root:'/runs',session:{...sessionPayload.session,folder_path:'/runs'} });
  fetchTreatmentQueue.mockImplementation(async () => ({success:true,queue:{running:false,jobs:[]}}));
  fetchFolderListing.mockResolvedValue({folders:[{name:'sample',path:'/runs/sample'}],files:[]});
  enqueueStandardFolderTreatment.mockImplementation(async () => {
    enqueued=true; return {success:true,started:true,queue:{running,jobs:[]},queue_job:{recipe:{}}};
  });
  postTreatment.mockResolvedValue(sessionPayload);
  renderStudioTabs();
  fireEvent.click(await screen.findByRole('button',{name:'Select Folder'}));
  fireEvent.contextMenu(await screen.findByRole('button',{name:'sample',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Set',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Cleaning',exact:true}));
  expect(await screen.findByRole('button',{name:'Absorption abs.h5',exact:true},{timeout:4000})).toBeEnabled();
  expect(screen.getByRole('button',{name:'Base base.h5',exact:true})).toBeEnabled();
});

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
  test('manifest workspace shows its project as Data Root and never changes another window’s allowed root',async()=>{
    fetchTreatmentSession.mockResolvedValue({...sessionPayload,allowed_root:'/runs',session:{...sessionPayload.session,folder_path:'/runs/project',status_label:'Folder selected: /runs/project'}});
    postTreatment.mockImplementation((_id,url,body)=>Promise.resolve({...sessionPayload,allowed_root:'/runs',session:{...sessionPayload.session,folder_path:body.folder_path}}));
    renderStudioTabs({initialFolder:'/runs/project',manifestProjectFolder:'/runs/project'});
    await waitFor(()=>expect(screen.getByLabelText('Data Root')).toHaveValue('/runs/project'));
    fireEvent.change(screen.getByLabelText('Data Root'),{target:{value:'/runs/another'}});
    fireEvent.blur(screen.getByLabelText('Data Root'));
    await waitFor(()=>expect(postTreatment).toHaveBeenCalledWith('test-session','/api/treatment/session/folder',{folder_path:'/runs/another'}));
    expect(postTreatment.mock.calls.some(([,url])=>url==='/api/treatment/session/root')).toBe(false);
  });
  test.each(['Treatment session restored from server snapshot.','Treatment session updated.'])(
    'preserves saved empty-file settings instead of applying profile defaults: %s',async status=>{
      fetchTreatmentSession.mockResolvedValue({...sessionPayload,exp_types:['HIS','HIS+NOISE','ABS+BASE+NOISE'],calc_modes:['individual','averaged'],
        session:{...sessionPayload.session,exp_type:'HIS+NOISE',selected_data_type:'ABS+BASE',calc_mode:'individual',status_label:status,save_file_name:'water.dat'}});
      renderStudioTabs();
      expect(await screen.findByDisplayValue('water.dat')).toBeInTheDocument();
      expect(postTreatment.mock.calls.some(([,url])=>url==='/api/treatment/session/config')).toBe(false);
    });
  test('rejected folder link keeps Data Root controls available for recovery', async () => {
    fetchTreatmentSession.mockResolvedValue({ ...sessionPayload, allowed_root: '/runs/old',
      session: { ...sessionPayload.session, folder_path: '/runs/old' } });
    postTreatment.mockRejectedValue(new Error('Path is outside the allowed treatment root'));
    renderStudioTabs({ initialFolder: '/runs/new' });
    await waitFor(() => expect(screen.getByLabelText('Data Root')).toHaveValue('/runs/old'));
    expect(screen.getByText(/Cannot open selected folder: Path is outside/)).toBeInTheDocument();
  });

  test('measurement deep link preselects its folder and exposes folder processing actions', async () => {
    const folder = '/runs/dark';
    fetchTreatmentSession.mockResolvedValue({ ...sessionPayload, allowed_root: '/runs', session: { ...sessionPayload.session, folder_path: '/runs' } });
    postTreatment.mockResolvedValue({ ...sessionPayload, allowed_root: '/runs', session: { ...sessionPayload.session, folder_path: folder } });
    renderStudioTabs({ initialFolder: folder });
    const folderButton = await screen.findByRole('button', { name: 'dark', exact: true });
    expect(postTreatment).toHaveBeenCalledWith('test-session', '/api/treatment/session/folder', { folder_path: folder });
    fireEvent.contextMenu(folderButton);
    expect(screen.getByRole('button', { name: 'Set/Convert/Clean', exact: true })).toBeInTheDocument();
  });
  beforeEach(() => {
    window.localStorage.removeItem('pyconlyse.treatment.activeTab.test-session');
    window.localStorage.removeItem('pyconlyse.treatment.sessionBackup.test-session');
    window.localStorage.removeItem('pyconlyse.treatment.folderTreeOpen.test-session');
    window.localStorage.removeItem('pyconlyse.treatment.cleaningDraft.test-session.angle');
    window.localStorage.removeItem('pyconlyse.treatment.cleaningDraft.test-session.surface');
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
    expect(await screen.findByRole('heading', { name: '4 Save' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '1 Source' })).toBeInTheDocument();
    expect(screen.getByText('Input files · 0 assigned')).toBeInTheDocument();
    expect(screen.getByLabelText('Experiment type')).not.toBeVisible();
    expect(screen.getByText('Stitch', { exact: true })).not.toBeVisible();
    fireEvent.click(screen.getByText('More tools'));
    fireEvent.click(screen.getByText('Batch options'));
    expect(screen.getByRole('heading', { name: 'Queue' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'SAM cleaning' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'SAM cleaning' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Stitch' })).toBeInTheDocument();
  });

  test('restores active tab after remount', async () => {
    const { unmount } = renderStudioTabs();
    await screen.findByRole('button', { name: 'Cleaning' });
    fireEvent.click(screen.getByRole('button', { name: 'Cleaning' }));
    expect(window.localStorage.getItem('pyconlyse.treatment.activeTab.test-session')).toBe('cleaning');

    unmount();
    renderStudioTabs();
    expect(await screen.findByRole('button', { name: 'Cleaning' })).toHaveAttribute('aria-pressed', 'true');
  });

  test('the simple workflow opens advanced settings without changing treatment or starting jobs', async () => {
    const onOpenManifest = jest.fn();
    renderStudioTabs({ onOpenManifest });
    await screen.findByRole('heading', { name: '1 Source' });
    expect(screen.getByRole('heading', { name: '2 Cleaning' })).toBeVisible();
    expect(screen.getByRole('heading', { name: '3 Calculate' })).toBeVisible();
    expect(screen.getByRole('heading', { name: '4 Save' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Save Result' })).toBeDisabled();
    expect(screen.getByLabelText('Experiment type')).not.toBeVisible();
    fireEvent.click(screen.getByText('Advanced settings'));
    expect(screen.getByRole('combobox', { name: 'Experiment type' })).toHaveValue('ABS+BASE+NOISE');
    fireEvent.click(screen.getByRole('button', { name: 'Open manifest…' }));
    expect(onOpenManifest).toHaveBeenCalledWith('');
    expect(enqueueStandardFolderTreatment).not.toHaveBeenCalled();
    expect(enqueueTreatmentRecipe).not.toHaveBeenCalled();
    expect(postTreatment).not.toHaveBeenCalled();
  });

  test('loading folder inputs is explicit, submitted once, and does not clean or calculate', async () => {
    fetchTreatmentSession.mockResolvedValue({ ...readySessionPayload, allowed_root: '/runs' });
    let finish;
    enqueueStandardFolderTreatment.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    renderStudioTabs();
    const button = await screen.findByRole('button', { name: 'Load folder inputs' });
    expect(enqueueStandardFolderTreatment).not.toHaveBeenCalled();
    fireEvent.click(button); fireEvent.click(button);
    expect(enqueueStandardFolderTreatment).toHaveBeenCalledTimes(1);
    expect(enqueueStandardFolderTreatment).toHaveBeenCalledWith('test-session', expect.objectContaining({
      folder_path: '/runs/run-001', convert: true, clean: false, calculate: false,
    }));
    await act(async () => finish({ success: true, started: true, queue: { running: true, jobs: [{ job_id: 'load', label: 'run-001', status: 'running', phase: 'converting' }] } }));
    expect(screen.getByText('running · converting')).toBeVisible();
  });

  test('loading inputs keeps the selected source folder when a recipe sets its output to the parent', async () => {
    const source = '/runs/sample';
    let current = { ...readySessionPayload, allowed_root: '/runs', session: { ...readySessionPayload.session, folder_path: '/runs' } };
    fetchTreatmentSession.mockImplementation(async () => current);
    fetchFolderListing.mockImplementation(async (_id, folder) => ({ success: true,
      folders: folder === '/runs' ? [{ name: 'sample', path: source }] : [], files: [] }));
    postTreatment.mockImplementation(async (_id, _url, body) => {
      current = { ...current, session: { ...current.session, folder_path: body.folder_path } };
      return current;
    });
    enqueueStandardFolderTreatment.mockImplementation(async () => {
      current = { ...current, session: { ...current.session, folder_path: '/runs' } };
      return { success: true, queue: { running: false, jobs: [] }, queue_job: { recipe: { save_target: { save_folder: '/runs', save_file_name: 'sample.dat' } } } };
    });
    renderStudioTabs();
    fireEvent.click(await screen.findByRole('button', { name: 'Select Folder' }));
    fireEvent.click(await screen.findByRole('button', { name: 'sample', exact: true }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Load folder inputs' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Load folder inputs' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Load folder inputs' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Load folder inputs' }));
    await waitFor(() => expect(enqueueStandardFolderTreatment).toHaveBeenCalledTimes(2));
    expect(enqueueStandardFolderTreatment.mock.calls.every(([, body]) => body.folder_path === source)).toBe(true);
  });

  test('job failures stay visible while batch settings are collapsed', async () => {
    fetchTreatmentQueue.mockResolvedValue({ success: true, queue: { running: false, jobs: [{
      job_id: 'failed', label: 'water', status: 'failed', phase: 'cleaning', error: 'Input fingerprint changed',
    }] } });
    renderStudioTabs();
    expect(await screen.findByText('Input fingerprint changed')).toBeVisible();
    expect(screen.getByLabelText('SAM cleaning')).not.toBeVisible();
  });

  test('Save uses the edited output name and waits for its configuration to succeed', async () => {
    fetchTreatmentSession.mockResolvedValue({ ...readySessionPayload, session: { ...readySessionPayload.session, result_ready: true } });
    let finishConfig;
    postTreatment.mockImplementation((_id, url) => url.endsWith('/session/config')
      ? new Promise(resolve => { finishConfig = resolve; })
      : Promise.resolve({ ...readySessionPayload, saved: { save_path: '/runs/run-001/corrected.dat' } }));
    renderStudioTabs();
    const input = await screen.findByLabelText('Save File Name');
    fireEvent.change(input, { target: { value: 'corrected.dat' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Result' }));
    expect(postTreatment).toHaveBeenCalledWith('test-session', '/api/treatment/session/config', { save_file_name: 'corrected.dat' });
    expect(postTreatment.mock.calls.some(([, path]) => path === '/api/treatment/save')).toBe(false);
    await act(async () => finishConfig({ ...readySessionPayload }));
    expect(await screen.findByText('Result saved')).toBeVisible();
    expect(screen.getByText('/runs/run-001/corrected.dat')).toBeVisible();
  });

  test('a rejected output edit prevents Save and keeps its error visible', async () => {
    fetchTreatmentSession.mockResolvedValue({ ...readySessionPayload, session: { ...readySessionPayload.session, result_ready: true } });
    postTreatment.mockRejectedValue(new Error('Output folder is outside the allowed treatment root'));
    renderStudioTabs();
    fireEvent.change(await screen.findByLabelText('Save Folder'), { target: { value: '/outside' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Result' }));
    expect(await screen.findByText('Output folder is outside the allowed treatment root')).toBeVisible();
    expect(postTreatment.mock.calls.some(([, path]) => path === '/api/treatment/save')).toBe(false);
    expect(screen.queryByText('Result saved')).not.toBeInTheDocument();
  });

  test('keeps the selected folder tree open after remount', async () => {
    fetchTreatmentSession.mockResolvedValue({
      ...readySessionPayload,
      allowed_root: '/runs',
    });
    const { unmount } = renderStudioTabs();
    fireEvent.click(await screen.findByRole('button', { name: 'Select Folder' }));
    expect(screen.getByRole('tree')).toBeInTheDocument();
    expect(window.localStorage.getItem('pyconlyse.treatment.folderTreeOpen.test-session'))
      .toBe('true');

    unmount();
    renderStudioTabs();
    expect(await screen.findByRole('tree')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('/runs/run-001')).toBeInTheDocument();
  });

  test('restores browser backup into empty durable server session before preset', async () => {
    const backup = {
      ...readySessionPayload.session,
      status_label: 'ABS file selected.',
    };
    window.localStorage.setItem(
      'pyconlyse.treatment.sessionBackup.test-session',
      JSON.stringify(backup)
    );
    fetchTreatmentSession.mockResolvedValue({
      ...sessionPayload,
      session_persistence: 'sqlite',
      session: { ...sessionPayload.session, status_label: 'Treatment session is ready.' },
    });
    postTreatment.mockImplementation((_sessionId, endpoint) => (
      endpoint === '/api/treatment/session/restore'
        ? Promise.resolve({ ...readySessionPayload, session_persistence: 'sqlite' })
        : Promise.resolve(sessionPayload)
    ));

    renderStudioTabs();

    await waitFor(() => expect(postTreatment).toHaveBeenCalledWith(
      'test-session', '/api/treatment/session/restore', { session: backup }
    ));
    expect(await screen.findByDisplayValue('od.dat')).toBeInTheDocument();
  });

  test('keeps controls available if a saved browser backup is stale', async () => {
    window.localStorage.setItem(
      'pyconlyse.treatment.sessionBackup.test-session',
      JSON.stringify(readySessionPayload.session)
    );
    fetchTreatmentSession.mockResolvedValue({
      ...sessionPayload,
      session_persistence: 'sqlite',
      session: { ...sessionPayload.session, status_label: 'Treatment session is ready.' },
    });
    postTreatment.mockImplementation((_sessionId, endpoint) => (
      endpoint === '/api/treatment/session/restore'
        ? Promise.reject(new Error('Input file is missing'))
        : Promise.resolve(sessionPayload)
    ));

    renderStudioTabs();

    await screen.findByRole('heading', { name: '4 Save' });
    fireEvent.click(screen.getByText('Advanced settings'));
    expect(screen.getByRole('button', { name: 'Reset Session' })).toBeInTheDocument();
    expect(screen.getByText(/Saved treatment session could not be restored/)).toBeInTheDocument();
  });

  test('offers explicit resume for queued jobs recovered after server restart', async () => {
    fetchTreatmentQueue.mockResolvedValue({
      success: true,
      queue: {
        running: false,
        pending_count: 1,
        jobs: [{ job_id: 'saved-1', status: 'queued', recipe: { label: 'saved run' } }],
      },
    });
    runTreatmentQueue.mockResolvedValue({
      success: true,
      queue: {
        running: true,
        pending_count: 0,
        jobs: [{ job_id: 'saved-1', status: 'running', recipe: { label: 'saved run' } }],
      },
    });

    renderStudioTabs();
    fireEvent.click(await screen.findByRole('button', { name: 'Resume queue' }));

    await waitFor(() => expect(runTreatmentQueue).toHaveBeenCalledWith('test-session'));
  });

  test('keeps file controls without offering sign-in when initial preset update is rejected', async () => {
    fetchTreatmentSession.mockResolvedValue({
      ...sessionPayload,
      session: { ...sessionPayload.session, exp_type: 'HIS+NOISE' },
    });
    postTreatment.mockRejectedValueOnce(new Error(
      'Sign in to continue data treatment, then retry your action.'
    ));
    renderStudioTabs();

    expect(await screen.findByRole('heading', { name: '1 Source' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '4 Save' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
    expect(screen.queryByText('Loading treatment session...')).not.toBeInTheDocument();
  });

  test('keeps the server error visible when the default data folder also fails to load', async () => {
    fetchTreatmentSession.mockResolvedValue({
      ...sessionPayload,
      allowed_root: 'E:/missing',
      session: { ...sessionPayload.session, exp_type: 'HIS+NOISE' },
    });
    postTreatment.mockRejectedValueOnce(new Error(
      'Sign in to continue data treatment, then retry your action.'
    ));
    fetchFolderListing.mockRejectedValue(new Error('Folder does not exist'));
    renderStudioTabs();

    await waitFor(() => expect(fetchFolderListing).toHaveBeenCalledWith('test-session', 'E:/missing'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign in to continue data treatment');
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
    expect(screen.queryByText('Folder does not exist')).not.toBeInTheDocument();
  });

  test('adds current recipe and starts it without a manual queue action', async () => {
    fetchTreatmentSession.mockResolvedValue(readySessionPayload);
    renderStudioTabs();

    expect(await screen.findByRole('heading', { name: 'Queue' })).toBeInTheDocument();
    fireEvent.click(screen.getByText('Batch options'));
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
    ['Set/Convert/Calc (all maps)', true, false, true],
    ['Set/Convert/Clean/Calc', true, true, true],
  ])('queues %s with immutable action flags', async (action, convert, clean, calculate) => {
    const nextFolder = '/runs/next-folder';
    enqueueStandardFolderTreatment.mockResolvedValue({
      success: true,
      started: true,
      queue_job: {
        recipe: {
          save_target: {
            save_folder: '/runs',
            save_file_name: 'next-folder_20260929.dat',
          },
        },
      },
      queue: { running: true, jobs: [] },
    });
    fetchTreatmentSession.mockResolvedValue({
      ...readySessionPayload,
      allowed_root: '/runs',
      session: {
        ...readySessionPayload.session,
        folder_path: '/runs',
        save_folder: '/runs',
      },
    });
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
    expect(screen.getByPlaceholderText('Select a folder inside the treatment root'))
      .toHaveValue('/runs');
    expect(await screen.findByDisplayValue('next-folder_20260929.dat')).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole('button', { name: 'Set/Convert/Calc (all maps)' }));

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
    fireEvent.click(screen.getByText('Batch options'));
    fireEvent.click(screen.getByRole('button', { name: 'Add recipe' }));

    expect(await screen.findByText('failed · error')).toBeInTheDocument();
    expect(screen.getByText('conversion failed')).toBeInTheDocument();
  });

  test('shows removed-map counts and the uncleaned all-map policy in completed jobs', async () => {
    fetchTreatmentSession.mockResolvedValue(readySessionPayload);
    fetchTreatmentQueue.mockResolvedValue({
      success: true,
      queue: {
        running: false,
        jobs: [
          {
            job_id: 'cleaned-job',
            label: 'cleaned',
            status: 'completed',
            preparation: {
              folder_set: {
                cleaned: {
                  ABS: { original_measurements: 187, cleaned_measurements: 183, removed_measurements: 4 },
                },
              },
            },
          },
          {
            job_id: 'all-maps-job',
            label: 'uncleaned',
            status: 'completed',
            preparation: {
              folder_set: {
                map_policy: 'all_raw_maps',
                map_counts: {
                  ABS: { total_count: 187, used_count: 187, stored_mask_included_count: 183 },
                },
              },
            },
          },
        ],
      },
    });

    renderStudioTabs();

    expect(await screen.findByText('ABS: 183/187 maps retained · 4 removed (2.1%)'))
      .toBeInTheDocument();
    expect(screen.getByText('Uncleaned calculation · all raw maps used; saved H5 masks unchanged.'))
      .toBeInTheDocument();
    expect(screen.getByText('ABS: 187/187 raw maps used · prior mask 183/187 ignored'))
      .toBeInTheDocument();
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
    fireEvent.click(screen.getByText('Batch options'));
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

    fireEvent.click(screen.getByText('Cleaning settings'));
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
