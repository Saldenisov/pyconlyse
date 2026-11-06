const key = (profile,windowId) => `pyconlyse.treatment.workspaces.${profile}${windowId?`.window.${windowId}`:''}`;
export function folderWorkspaceId(folder) {
  let hash = 2166136261;
  for (const char of folder.replace(/\//g, '\\').replace(/\\+$/, '').toLowerCase()) {
    hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  }
  return `folder-${(hash >>> 0).toString(16)}`;
}
export function readWorkspaces(profile,windowId='') {
  try {
    const saved = JSON.parse(window.localStorage.getItem(key(profile,windowId)) || 'null');
    if (saved?.items?.length && saved.items.some(w => w.id === saved.active)
      && saved.items.every(w => /^[a-zA-Z0-9-]+$/.test(w.id))) return saved;
  } catch (_error) { /* Use a workspace when storage is unavailable. */ }
  return { active: 'main', items: [{ id: 'main', label: 'Workspace 1' }] };
}
export function saveWorkspaces(profile, state,windowId='') {
  try { window.localStorage.setItem(key(profile,windowId), JSON.stringify(state)); } catch (_error) { /* In-memory mode. */ }
}
export function closeWorkspace(state, id) {
  if (state.items.length <= 1 || !state.items.some(item => item.id === id)) return state;
  const index = state.items.findIndex(item => item.id === id);
  const items = state.items.filter(item => item.id !== id);
  return { ...state, items, active: state.active === id ? items[Math.min(index, items.length - 1)].id : state.active };
}
