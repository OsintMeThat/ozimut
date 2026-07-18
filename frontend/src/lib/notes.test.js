import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './api.js';
import { createNote } from './notes.js';

vi.mock('./api.js', () => ({ api: { post: vi.fn(async () => ({})) } }));

beforeEach(() => api.post.mockClear());

describe('createNote', () => {
  it('posts a note entity with content and filing folder', async () => {
    await createNote('case-1', { title: 'Lead', folder: 'Research', content: 'body' });
    expect(api.post).toHaveBeenCalledWith('/api/cases/case-1/entities', {
      type: 'note',
      label: 'Lead',
      attrs: { content: 'body', folder: 'Research' },
    });
  });

  it('trims the title and folder, and defaults content to empty', async () => {
    await createNote('case-1', { title: '  Lead  ', folder: '  Research  ' });
    expect(api.post).toHaveBeenCalledWith('/api/cases/case-1/entities', {
      type: 'note',
      label: 'Lead',
      attrs: { content: '', folder: 'Research' },
    });
  });

  it('leaves the note unfiled when no folder is given', async () => {
    await createNote('case-1', { title: 'Lead' });
    expect(api.post).toHaveBeenCalledWith('/api/cases/case-1/entities', {
      type: 'note',
      label: 'Lead',
      attrs: { content: '', folder: '' },
    });
  });

  it('rejects a blank title without hitting the API', async () => {
    await expect(createNote('case-1', { title: '   ' })).rejects.toThrow('Title required');
    expect(api.post).not.toHaveBeenCalled();
  });
});
