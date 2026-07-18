import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './api.js';
import { createBookmark } from './bookmarks.js';

vi.mock('./api.js', () => ({ api: { post: vi.fn(async () => ({})) } }));

beforeEach(() => api.post.mockClear());

describe('createBookmark', () => {
  it('posts a bookmark entity with url, notes and filing folder', async () => {
    await createBookmark('case-1', {
      title: 'Leak site', url: 'https://example.com/x', folder: 'Sources', notes: 'seen once',
    });
    expect(api.post).toHaveBeenCalledWith('/api/cases/case-1/entities', {
      type: 'bookmark',
      label: 'Leak site',
      attrs: { url: 'https://example.com/x', notes: 'seen once', folder: 'Sources' },
    });
  });

  it('trims the title, url, folder and notes', async () => {
    await createBookmark('case-1', {
      title: '  Leak site  ', url: '  https://example.com/x  ', folder: '  Sources  ',
    });
    expect(api.post).toHaveBeenCalledWith('/api/cases/case-1/entities', {
      type: 'bookmark',
      label: 'Leak site',
      attrs: { url: 'https://example.com/x', notes: '', folder: 'Sources' },
    });
  });

  it('rejects a blank title without hitting the API', async () => {
    await expect(createBookmark('case-1', { title: '  ', url: 'https://x.com' })).rejects.toThrow(
      'Title required'
    );
    expect(api.post).not.toHaveBeenCalled();
  });

  it('rejects a non-http URL without hitting the API', async () => {
    await expect(
      createBookmark('case-1', { title: 'Bad', url: 'javascript:alert(1)' })
    ).rejects.toThrow('http(s) URL');
    expect(api.post).not.toHaveBeenCalled();
  });
});
