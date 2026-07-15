# Keyed imagery providers — Mapbox & Google

> Azimut ships two optional user-keyed basemaps alongside the key-less defaults
> (Esri, OSM). The rules below are why their code looks the way it does — they come
> from Google's and Mapbox's terms, not from taste. Read alongside SPEC.md §6
> "v1 notes → Tile providers" (legal-only policy).
>
> Implemented in [`engine/tiles.py`](../src/azimut/engine/tiles.py),
> [`engine/google_tiles.py`](../src/azimut/engine/google_tiles.py),
> [`engine/tilecache.py`](../src/azimut/engine/tilecache.py) and
> [`api/settings.py`](../src/azimut/api/settings.py).

## Legal rules (decided — do not relax)

| Rule | Why |
|------|-----|
| Keys are **user-supplied**, stored **locally**, **never** bundled into a shared case/zip. | Principle 7; keys are the user's own billing identity. |
| Core features never require a key. Key-less providers (Esri, OSM) stay the default. | Principle 7. |
| **Never** ship/suggest/document unofficial endpoints (`mt1.google.com`, `khms*`, …). Only official APIs. | Legal-only policy. |
| **Google tiles must NOT be cached to disk.** | Google's Map Tiles API forbids pre-fetch/store/cache/offline use of tiles ([policies](https://developers.google.com/maps/documentation/tile/policies)). |
| A Google **capture** is allowed only as a **flattened, attributed screenshot** (single PNG, attribution burned in) — never a store of raw tiles. | Google Geo Guidelines permit screenshots in reports/periodicals ≤5,000 copies **with attribution**; the anti-cache clause forbids tile hoarding. Two different acts. |
| Every capture keeps provider **attribution** (Google/Mapbox + data providers, e.g. Maxar) unmodified. For Google it is **burned into the image footer**. | Attribution is a condition of the allowed use, not a courtesy. |

### Per-provider capability matrix

| Provider | `needs_key` | auth style | `capturable` | `cacheable` (tile disk cache) | attribution source |
|----------|:-----------:|------------|:------------:|:-----------------------------:|--------------------|
| Esri World Imagery | no | — | yes | yes | static string |
| OpenStreetMap | no | — | yes | yes | static string |
| **Mapbox Satellite** | yes | access token in URL | yes | yes¹ | `© Mapbox © OpenStreetMap` (+ Maxar) |
| **Google Satellite** | yes | **session token** | yes (flattened+attributed only) | **NO** | dynamic copyright from viewport endpoint |

¹ Display + static-image capture with attribution is permitted; plan-level
caching/redistribution limits vary, so the cache stays modest (30-day TTL) and
attribution always on.

## Google is not a static `{key}` URL

It needs a session token, minted and refreshed transparently before the rest of the
pipeline sees a normal XYZ template:

1. `POST https://tile.googleapis.com/v1/createSession?key={API_KEY}` →
   `{"session":"<token>","expiry":"<unix>",…}`. Session params (mapType) are part
   of the token identity.
2. Tiles: `GET https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?session={token}&key={API_KEY}`
3. Refresh on expiry or on 401/403.
4. Attribution: `GET https://tile.googleapis.com/tile/v1/viewport?session={token}&key={API_KEY}&zoom={z}&north=&south=&east=&west=`
   → `copyright` (e.g. `"Map data ©2026 Google, Maxar Technologies"`). Never reduced
   to just "Google".

The **token** may be cached; tiles may not.

## Measured findings (2026-07)

**Tile sizes.** Mapbox serves **512px** tiles: it bills 256px tiles 4× vs 512px for
the same ground area at the same m/px. Google serves **1024px hi-DPI** tiles
(`scale=scaleFactor4x, highDpi=true`): it bills per *request* regardless of tile
size, so one request covers sixteen 256px tiles' worth of ground at the same m/px —
verified pixel-identical. Mapbox's `@2x` equivalent is *upsampled* (softer), which
is why Mapbox stays at 512.

**Oversampling.** The live map oversamples Google 2× (1024px tiles in 512px cells,
one zoom deeper) because Google's mid-zoom mosaics are verifiably softer than its
deep ones — net ¼ the cost of plain 256px tiles. The z17 view alone boosts to 4×
(z19 detail): the z18 mosaic it would otherwise show is often an older/hazier
collection than the z19+ aerial. Captures stay 1:1 provider pixels — no resampling
in evidence imagery.

**Billing units.** Both bill **per tile served** — Google's 2D Map Tiles SKU is
"Request that returns a 2D map tile" (session and viewport requests are free);
Mapbox Static Tiles bills per tile request when used with Leaflet. Free tiers:
Google 100k/month then $0.60/1k (plus hard limits of 15k tiles/day and 6k/min per
project), Mapbox 200k/month then $0.50/1k (no hard cap — alerts only). Metered
tiles are proxied through the backend so the counter matches billing exactly;
browser cache hits never re-count.

## Deliberately not basemaps

Street View and Google Photorealistic 3D Tiles are keyed Google products but not
tile providers — a ground-imagery tool and a 3D scene respectively. They live in the
SPEC backlog, not here.
