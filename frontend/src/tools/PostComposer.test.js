import { afterEach, describe, expect, it } from 'vitest';
import { render } from 'svelte/server';
import { caseState, uiState } from '../lib/state.svelte.js';
import PostComposer from './PostComposer.svelte';

afterEach(() => {
  caseState.current = null;
  uiState.postProof = null;
});

describe('Geo Report actions', () => {
  it('offers Save report and removes the old Copy report action', () => {
    caseState.current = { id: 'case-1', folders: [], entities: [] };

    const { body } = render(PostComposer);

    expect(body).toContain('Save report');
    expect(body).toContain('Publish on');
    expect(body).not.toContain('Copy report');
  });
});
