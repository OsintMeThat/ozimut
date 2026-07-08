/**
 * Global app state (Svelte 5 runes).
 *
 * `caseState.current` is the open case (or null). Tools read it to know where
 * to file their outputs; one-shot mode transparently creates a scratch case
 * on first write (see ensureCase).
 */
import { api } from './api.js';

export const caseState = $state({
  current: null, // { id, name, scratch, entities, links, ... }
  list: [],
  loading: false,
});

export const uiState = $state({
  tool: 'media', // 'media' | 'satellite' | 'proof' | 'post'
  sidebarOpen: true,
  toasts: [],
  // cross-tool handoffs (the workbench glue):
  composeQueue: [], // media paths queued for the Proof Composer
  postProof: null, // proof spec handed to the Post Composer
});

let toastSeq = 0;

export function toast(message, kind = 'info', timeout = 3800) {
  const id = ++toastSeq;
  uiState.toasts.push({ id, message, kind });
  setTimeout(() => {
    const i = uiState.toasts.findIndex((t) => t.id === id);
    if (i !== -1) uiState.toasts.splice(i, 1);
  }, timeout);
}

export async function refreshCaseList() {
  caseState.list = await api.get('/api/cases');
}

export async function openCase(id) {
  caseState.loading = true;
  try {
    caseState.current = await api.get(`/api/cases/${id}`);
  } finally {
    caseState.loading = false;
  }
}

export async function reloadCase() {
  if (caseState.current) {
    caseState.current = await api.get(`/api/cases/${caseState.current.id}`);
  }
}

export async function createCase(name) {
  const created = await api.post('/api/cases', { name });
  await refreshCaseList();
  await openCase(created.id);
  return created;
}

/**
 * One-shot mode: make sure some case exists to receive tool output.
 * Creates a scratch case silently if none is open (spec §3.3).
 */
export async function ensureCase() {
  if (caseState.current) return caseState.current;
  const scratch = await api.post('/api/cases/scratch');
  await refreshCaseList();
  await openCase(scratch.id);
  toast('Scratch session started — promote it to keep your work', 'info');
  return caseState.current;
}

export async function promoteCase(name) {
  if (!caseState.current?.scratch) return;
  const promoted = await api.post(`/api/cases/${caseState.current.id}/promote`, { name });
  await refreshCaseList();
  await openCase(promoted.id);
  toast(`Promoted to case “${name}”`, 'ok');
}

export function closeCase() {
  caseState.current = null;
}
