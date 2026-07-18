/**
 * Creating a note entity. A note is just an entity of type `note` whose body
 * lives in `attrs.content`; `attrs.folder` files it into a My-work folder
 * (''=unfiled). Lifted out of the case sidebar so the desktop organizer's
 * right-click menu can create notes the same way.
 *
 * Does not reload the case: the caller refetches once it returns.
 */
import { api } from './api.js';

export async function createNote(caseId, { title, folder = '', content = '' }) {
  const label = (title ?? '').trim();
  if (!label) throw new Error('Title required');
  await api.post(`/api/cases/${caseId}/entities`, {
    type: 'note',
    label,
    attrs: { content: content ?? '', folder: (folder ?? '').trim() },
  });
}
