/**
 * Keyed-provider usage bookkeeping (docs/IMAGERY_PROVIDERS.md).
 *
 * Billed providers (Mapbox, Google) get a per-month tile counter in
 * settings.json, maintained entirely by the backend: captures count the tiles
 * they stitch, and the live map's tiles flow through the backend proxy which
 * counts each one it serves. The frontend only reads the tally.
 */

/**
 * Documented monthly free allowances, in tile requests — a yardstick for the
 * counter, not a guarantee (providers change their pricing; verify on their
 * pricing pages — links below). Verified 2026-07: Mapbox Static Tiles
 * 200k/month then $0.50 per extra 1,000 (billed to the account's card);
 * Google 2D Map Tiles 100k/month then $0.60 per extra 1,000, plus hard
 * server-side limits of 15,000 tiles/day and 6,000/min per project — a quota
 * cap set in the Cloud Console makes it stop instead of bill.
 * Mirror of config.FREE_TIER on the backend (which enforces the soft block).
 */
export const FREE_TIER = { mapbox: 200_000, google: 100_000 };

/** Share of the free tier past which the backend pauses a provider. */
export const BLOCK_SHARE = 0.9;

/** Eco mode default: visual zoom at or below which free imagery replaces a
 * billed basemap. The live value is the user's `eco_max_zoom` setting. */
export const ECO_MAX_ZOOM = 15;

/** Where to watch the real counters and set caps, per provider. */
export const USAGE_LINKS = {
  mapbox: 'https://console.mapbox.com/account/statistics/',
  google: 'https://console.cloud.google.com/google/maps-apis/quotas',
};

/** True when a metered provider is paused: past the soft block, no override. */
export function usageBlocked(count, meter, overrides = {}) {
  const free = FREE_TIER[meter];
  if (!free || overrides[meter]) return false;
  return count >= free * BLOCK_SHARE;
}

/**
 * CSS grid-cell size for a provider's live tile layer at a view zoom: the
 * tile edge shrunk by its display oversample. Oversampled providers (Google)
 * get one extra 2× boost for the z17 view only — the z18 mosaic it would
 * otherwise show is often an older/hazier collection than z19+ (the sharp
 * aerial; measured 2026-07), so that single bracket pays 4× for z19 detail
 * while every other zoom keeps the cheap 2×.
 */
export function layerCell(provider, zoom) {
  const boost = provider.oversample === 2 && zoom === 17 ? 2 : 1;
  return Math.max(256, provider.tile_size / ((provider.oversample || 1) * boost));
}

/**
 * The provider the live map should actually display. Billed basemaps step
 * aside for free imagery when paused (soft block) or zoomed out (eco mode —
 * paid detail only matters up close); captures follow the display, so
 * provenance stays honest.
 */
export function displayProviderId(
  provider,
  zoom,
  { eco = true, blocked = false, ecoMaxZoom = ECO_MAX_ZOOM } = {}
) {
  if (!provider?.meter) return provider?.id;
  if (blocked) return 'esri-world-imagery';
  if (eco && zoom <= ecoMaxZoom) return 'esri-world-imagery';
  return provider.id;
}

/** The usage bucket for a moment in time: "YYYY-MM" (UTC, matches backend). */
export function monthKey(date = new Date()) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** This month's tally for a meter out of the settings `usage` map. */
export function monthCount(usage, meter, month = monthKey()) {
  return Number(usage?.[meter]?.[month] ?? 0);
}

/** Compact readout for the map pill: "767 tiles". */
export function tilesShort(count) {
  return `${count.toLocaleString('en-US')} tile${count === 1 ? '' : 's'}`;
}

/** Settings readout against the free allowance: "767 / 200,000 free tiles". */
export function tilesOfFree(count, meter) {
  const free = FREE_TIER[meter];
  if (!free) return tilesShort(count);
  return `${count.toLocaleString('en-US')} / ${free.toLocaleString('en-US')} free tiles`;
}

/** Share of the free allowance used this month, 0–1 (can exceed 1). */
export function freeTierShare(count, meter) {
  const free = FREE_TIER[meter];
  return free ? count / free : 0;
}
