import { describe, expect, it, vi } from 'vitest';
import { render } from 'svelte/server';
import ProofToolbar from './ProofToolbar.svelte';

const DRAW_TOOLS = [
  { id: 'select', icon: 'hand', label: 'Select / move', shortcut: 'v' },
  { id: 'rect', icon: 'square', label: 'Box', shortcut: 'r' },
  { id: 'text', icon: 'text', label: 'Text', shortcut: 't' },
];

function props(overrides = {}) {
  return {
    canUndo: true,
    canRedo: true,
    undo: vi.fn(),
    redo: vi.fn(),
    drawTools: DRAW_TOOLS,
    tool: 'rect',
    palette: ['#ff5252', '#40c4ff'],
    activeColor: '#ff5252',
    selectedShape: null,
    strokeW: 4,
    setColor: vi.fn(),
    setStroke: vi.fn(),
    fit: vi.fn(),
    layout: 'grid',
    setLayoutMode: vi.fn(),
    guide: null,
    tweetGuides: { '16:9': 16 / 9, '4:5': 4 / 5 },
    panelCount: 2,
    applyMagic: vi.fn(),
    ...overrides,
  };
}

describe('ProofToolbar core (always visible)', () => {
  it('shows history, every draw tool and fit regardless of active tool', () => {
    const { body } = render(ProofToolbar, { props: props({ tool: 'select' }) });
    expect(body).toContain('Undo (Ctrl+Z)');
    expect(body).toContain('Redo');
    expect(body).toContain('Box (r)');
    expect(body).toContain('Text (t)');
    expect(body).toContain('Fit view (f)');
  });
});

describe('ProofToolbar context controls (colour + size)', () => {
  it('hides the colour palette and size slider when idle (Select, nothing selected)', () => {
    const { body } = render(ProofToolbar, {
      props: props({ tool: 'select', selectedShape: null }),
    });
    expect(body).not.toContain('aria-label="color #ff5252"');
    expect(body).not.toContain('stroke-slider');
  });

  it('shows the colour palette and size slider while a draw tool is active', () => {
    const { body } = render(ProofToolbar, { props: props({ tool: 'rect' }) });
    expect(body).toContain('aria-label="color #ff5252"');
    expect(body).toContain('aria-label="color #40c4ff"');
    expect(body).toContain('custom color');
    expect(body).toContain('stroke-slider');
  });

  it('shows the colour palette and size slider when a shape is selected under Select', () => {
    const { body } = render(ProofToolbar, {
      props: props({ tool: 'select', selectedShape: { kind: 'rect', strokeWidth: 3 } }),
    });
    expect(body).toContain('aria-label="color #ff5252"');
    expect(body).toContain('stroke-slider');
  });

  it('ranges the size slider for font size when a text shape is selected', () => {
    const { body } = render(ProofToolbar, {
      props: props({ tool: 'select', selectedShape: { kind: 'text', fontSize: 40 } }),
    });
    expect(body).toMatch(/class="stroke-slider[^"]*"[\s\S]*?max="120"/);
  });
});

describe('ProofToolbar document controls (overflow flyout)', () => {
  it('carries layout modes, tweet guides and the magic repack action', () => {
    const { body } = render(ProofToolbar, { props: props() });
    expect(body).toContain('Grid layout: panels flow in rows');
    expect(body).toContain('Free layout: drag panels anywhere');
    expect(body).toContain('>16:9<');
    expect(body).toContain('>4:5<');
    expect(body).toContain('Repack panels');
  });

  it('disables the magic repack when there are no panels', () => {
    const { body } = render(ProofToolbar, { props: props({ panelCount: 0 }) });
    expect(body).toMatch(/title="Repack panels[^"]*"[^>]*disabled/);
  });
});
