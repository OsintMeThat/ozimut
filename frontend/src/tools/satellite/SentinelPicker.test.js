import { describe, expect, it, vi } from 'vitest';
import { render } from 'svelte/server';
import SentinelPicker from './SentinelPicker.svelte';

function props(overrides = {}) {
  return {
    menuOpen: true,
    toggleMenu: vi.fn(),
    layer: 'TRUE_COLOR',
    layers: [{ id: 'TRUE_COLOR', label: 'True colour' }],
    layerHint: '',
    layersSource: 'instance',
    loadLayers: vi.fn(),
    date: '',
    month: '2026-05',
    monthLabel: () => 'May 2026',
    stepMonth: vi.fn(),
    monthGrid: () => ['2026-05-11'],
    passes: { '2026-05-11': { cloud: 4, granules: 1 } },
    cloudClass: () => 'clear',
    cloudLabel: () => '4% cloud',
    passesBusy: false,
    passesNote: '',
    passesStale: false,
    verifyingDate: '',
    dateStatus: () => undefined,
    pickDate: vi.fn(),
    clearDate: vi.fn(),
    loadPasses: vi.fn(),
    ...overrides,
  };
}

describe('SentinelPicker date safety', () => {
  it('disables dates from the previous map location', () => {
    const { body } = render(SentinelPicker, { props: props({ passesStale: true }) });
    expect(body).toContain('Refreshing dates for this location.');
    expect(body).toMatch(/<button[^>]*class="cal-day[^>]*disabled[^>]*>/);
  });

  it('marks a checked date that has no imagery as unavailable', () => {
    const { body } = render(SentinelPicker, {
      props: props({ dateStatus: () => false }),
    });
    expect(body).toMatch(/class="cal-day clear [^"]*has unavailable"/);
    expect(body).toContain('No imagery at the crosshair on 2026-05-11');
    expect(body).toMatch(/<button[^>]*class="cal-day clear [^"]*has unavailable"[^>]*disabled/);
  });

  it('shows which date is being checked', () => {
    const { body } = render(SentinelPicker, {
      props: props({ verifyingDate: '2026-05-11' }),
    });
    expect(body).toMatch(/class="cal-day clear [^"]*has verifying"/);
    expect(body).toContain('Checking imagery for 2026-05-11');
  });
});
