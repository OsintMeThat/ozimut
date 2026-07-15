import { describe, it, expect } from 'vitest';
import {
  monthKey,
  monthCount,
  tilesShort,
  tilesOfFree,
  freeTierShare,
  usageBlocked,
  displayProviderId,
  layerCell,
  FREE_TIER,
  BLOCK_SHARE,
  ECO_MAX_ZOOM,
  USAGE_LINKS,
} from './usage.js';

describe('monthKey', () => {
  it('formats a UTC year-month bucket', () => {
    expect(monthKey(new Date(Date.UTC(2026, 6, 14)))).toBe('2026-07');
    expect(monthKey(new Date(Date.UTC(2026, 11, 31)))).toBe('2026-12');
  });
});

describe('monthCount', () => {
  const usage = { google: { '2026-07': 1234 }, mapbox: { '2026-07': 87 } };

  it('reads the month bucket for a meter', () => {
    expect(monthCount(usage, 'google', '2026-07')).toBe(1234);
  });

  it('is zero for unknown meters or empty usage', () => {
    expect(monthCount(usage, 'bing', '2026-07')).toBe(0);
    expect(monthCount(undefined, 'google', '2026-07')).toBe(0);
    expect(monthCount(usage, 'google', '2026-01')).toBe(0);
  });
});

describe('tilesShort', () => {
  it('is a compact map-pill readout', () => {
    expect(tilesShort(767)).toBe('767 tiles');
    expect(tilesShort(12430)).toBe('12,430 tiles');
    expect(tilesShort(1)).toBe('1 tile');
  });
});

describe('tilesOfFree', () => {
  it('shows the count against the documented free allowance', () => {
    expect(tilesOfFree(767, 'mapbox')).toBe('767 / 200,000 free tiles');
    expect(tilesOfFree(12430, 'google')).toBe('12,430 / 100,000 free tiles');
  });

  it('falls back to the plain count for meters without a known allowance', () => {
    expect(tilesOfFree(42, 'bing')).toBe('42 tiles');
  });
});

describe('freeTierShare', () => {
  it('is the fraction of the free allowance used', () => {
    expect(freeTierShare(100_000, 'mapbox')).toBe(0.5);
    expect(freeTierShare(150_000, 'google')).toBe(1.5); // over — UI can warn
    expect(freeTierShare(500, 'unknown')).toBe(0);
  });

  it('free tiers stay in sync with the label helper', () => {
    expect(FREE_TIER.mapbox).toBe(200_000);
    expect(FREE_TIER.google).toBe(100_000);
  });
});

describe('usageBlocked', () => {
  it('pauses a meter at the block share of its free tier', () => {
    expect(usageBlocked(FREE_TIER.google * BLOCK_SHARE, 'google')).toBe(true);
    expect(usageBlocked(FREE_TIER.google * BLOCK_SHARE - 1, 'google')).toBe(false);
  });

  it('the per-provider override lifts the pause', () => {
    expect(usageBlocked(FREE_TIER.mapbox, 'mapbox', { mapbox: true })).toBe(false);
    expect(usageBlocked(FREE_TIER.mapbox, 'mapbox', { google: true })).toBe(true);
  });

  it('unmetered providers never block', () => {
    expect(usageBlocked(10_000_000, 'bing')).toBe(false);
  });
});

describe('displayProviderId', () => {
  const google = { id: 'google-satellite', meter: 'google' };
  const esri = { id: 'esri-world-imagery', meter: null };

  it('keeps free providers as-is at any zoom', () => {
    expect(displayProviderId(esri, 3)).toBe('esri-world-imagery');
    expect(displayProviderId(esri, 19)).toBe('esri-world-imagery');
  });

  it('eco mode swaps billed basemaps for free imagery when zoomed out', () => {
    expect(displayProviderId(google, ECO_MAX_ZOOM)).toBe('esri-world-imagery');
    expect(displayProviderId(google, ECO_MAX_ZOOM + 1)).toBe('google-satellite');
    expect(displayProviderId(google, ECO_MAX_ZOOM, { eco: false })).toBe('google-satellite');
  });

  it('the eco threshold is configurable (default z15)', () => {
    expect(ECO_MAX_ZOOM).toBe(15);
    expect(displayProviderId(google, 17, { ecoMaxZoom: 17 })).toBe('esri-world-imagery');
    expect(displayProviderId(google, 15, { ecoMaxZoom: 12 })).toBe('google-satellite');
  });

  it('a paused meter always falls back, even zoomed in', () => {
    expect(displayProviderId(google, 19, { blocked: true })).toBe('esri-world-imagery');
  });

  it('handles the pre-load undefined provider', () => {
    expect(displayProviderId(undefined, 10)).toBe(undefined);
  });
});

describe('layerCell', () => {
  const google = { id: 'google-satellite', tile_size: 1024, oversample: 2 };
  const mapbox = { id: 'mapbox-satellite', tile_size: 512, oversample: 1 };
  const esri = { id: 'esri-world-imagery', tile_size: 256, oversample: 1 };

  it('shrinks the cell by the display oversample', () => {
    expect(layerCell(google, 16)).toBe(512); // 1024px tile shown 2× down = z+1 detail
    expect(layerCell(mapbox, 16)).toBe(512); // no oversample — native cell
    expect(layerCell(esri, 16)).toBe(256);
  });

  it('boosts only the z17 bracket for oversampled providers (soft z18 mosaic)', () => {
    expect(layerCell(google, 17)).toBe(256); // z19 detail for the z17 view
    expect(layerCell(google, 18)).toBe(512); // back to the cheap 2×
    expect(layerCell(mapbox, 17)).toBe(512); // non-oversampled providers unaffected
  });

  it('never goes below the 256px minimum cell', () => {
    expect(layerCell({ tile_size: 256, oversample: 2 }, 17)).toBe(256);
  });
});

describe('USAGE_LINKS', () => {
  it('points each billed meter at its provider dashboard', () => {
    expect(Object.keys(USAGE_LINKS).sort()).toEqual(Object.keys(FREE_TIER).sort());
    for (const url of Object.values(USAGE_LINKS)) expect(url).toMatch(/^https:\/\//);
  });
});
