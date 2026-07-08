# Ozimut — OSINT/GEOINT workbench

> One app, one tab per tool. Local-first: your media and your investigations never
> leave your machine. Built for the geolocation and open-source-investigation
> community (GeoConfirmed contributors, journalists, researchers).

Status: **draft spec v0.1** — everything here is open to change.

---

## 1. Why

Practitioners juggle a dozen half-broken web pages and manual workflows every day:
composing a geolocation proof in a paint program, comparing satellite providers in
four browser tabs, hand-writing Overpass queries, losing evidence to link rot,
re-deriving sun positions. Nothing integrates them, and the tools that exist are
either abandoned, paid, or require uploading sensitive media to someone's server.

Ozimut bundles those daily gestures into one installable app with a simple promise:
**everything runs on your machine.**

## 2. Principles

1. **Local-first, privacy-first.** No account, no telemetry, no upload. Network is
   used only when a tool inherently needs it (map tiles, geocoding, media download)
   and always to third parties directly — never through an Ozimut server.
2. **One tab = one tool.** Each tool is independently useful in 30 seconds, no
   manual. Tools share data through a common case workspace (see §5), but never
   require it.
3. **Free and open source.** Free APIs and local computation only; no paid keys
   required for any core feature.
4. **Honest output.** Every artifact records how it was produced (source, timestamps,
   parameters, imagery attribution) — proofs are auditable by design.
5. **English UI**, international community.

## 3. Architecture

- **Backend**: Python 3.11+, FastAPI serving on `localhost`. All processing (OpenCV,
  ffmpeg, yt-dlp, pytesseract, …) runs in the backend. The engine already written in
  `frame-geolocator/geolocation_proof/` (frame extraction, Esri tile fetch with
  placeholder detection and zoom fallback, panorama stitching via cv2.Stitcher,
  annotated-proof rendering, plus codes, Nominatim) is migrated here as the first
  engine modules.
- **Frontend**: web UI served by the backend, opened in the default browser (or a
  window via pywebview later). Tabs on the left, tool canvas on the right.
  Framework: lightweight (Svelte or vanilla + Leaflet for maps, Konva/canvas for
  annotation). No build complexity beyond one bundler.
- **Distribution**: `pip install ozimut` + `ozimut` command for technical users;
  PyInstaller single-file executables (Windows/Linux/macOS) for everyone else.
- **Storage**: plain files under a user-chosen workspace directory — JSON + media
  folders, versionable with git if the user wants. No database server; SQLite only
  for indexes/caches.

## 4. Tools

Phasing rule: v1 must cover the full "video + coordinates → publishable proof" flow
end to end, because that is the workflow nothing else provides.

### v1 — the proof pipeline (MVP)

| Tab | What it does |
|-----|--------------|
| **Frame Extractor** | Drop a video: timeline scrubber, auto-suggested sharpest frames per time bin, one-click capture of any frame. Frames land in the case workspace. |
| **Panorama** | Select a time window of the video, stitch it into one wide view (cv2.Stitcher, PANORAMA→SCANS→middle-out fallback). |
| **Satellite** | Enter/click coordinates: Esri World Imagery crop centered on the point (zoom fallback + "no data" placeholder detection), crosshair marker, attribution recorded. |
| **Proof Composer** | The heart of v1. Frames/panoramas and the satellite crop side by side; draw colored boxes/ellipses/lines **with the mouse**, same color = same feature across panels; layout rows; export `proof.png` + a draft post text (coordinates, plus code, place name, attribution). |
| **Coordinates** | Convert DMS/decimal/MGRS/plus code/geohash; reverse geocode (Nominatim); quick-open links to Google Maps/Yandex/Bing/OSM at the point. |

### v2 — daily-driver verification tools

| Tab | What it does |
|-----|--------------|
| **Satellite Compare** | Same coordinates across Esri / Sentinel-2 (date slider) / Bing side by side, synchronized pan/zoom — imagery history and provider comparison. |
| **Image Compare** | Overlay two images with an opacity/swipe slider + pixel difference — frame vs satellite, or two imagery dates. |
| **Shadow Clock** | Mark a shadow on a photo, get possible capture times for given coordinates and date range (sun-position math, local). |
| **EXIF & Metadata** | Photos and videos: GPS, timestamps, device, codecs — parsed locally, with a "what was stripped" hint. |
| **Reverse Search Launcher** | Any image/frame → auto-generated search links for Google/Yandex/Bing/TinEye (opens browser tabs; no scraping). |
| **Media Downloader** | URL (X, Telegram, TikTok, YouTube, …) → clean local file + metadata JSON via yt-dlp. This is the tool that justifies being a desktop app. |
| **OCR** | Read signs/plates on a frame (tesseract), detect script/language. |

### v3 — investigation layer

| Tab | What it does |
|-----|--------------|
| **Case Board** | Entities (accounts, people, places, events, media) and typed links between them; graph, timeline and map views; stored as plain JSON/markdown in the workspace. |
| **Evidence Locker** | Every piece of evidence: SHA-256, timestamps, source URL, notes; one-click Wayback Machine archiving; exportable chain-of-custody log. |
| **Timeline Builder** | Timestamped events from mixed sources aligned on an interactive timeline + map. |
| **Report Builder** | Assemble proofs, maps, timeline extracts and notes into a publishable HTML/PDF report. |

### v4 — exploration & advanced

| Tab | What it does |
|-----|--------------|
| **OSM Query (Overpass)** | Form-based feature search ("water towers within 2 km of a railway") → results on map, no Overpass QL knowledge needed. |
| **Viewshed / Line of Sight** | From a point, what terrain is visible (public DEM tiles) — validate "can this ridge be seen from here?". |
| **Map Measures** | Distance, bearing/azimuth (the app's namesake), area, camera field-of-view cone placed on the map. |
| **Déjà Vu** | Perceptual-hash index of known/old clips — flags recycled footage. Local index first; optional community-shared index later. |
| **Manipulation Hints** | ELA, JPEG quantization, noise inconsistencies — first-pass tampering indicators, honestly labeled as *hints*. |
| **Channel Monitor** | Watch Telegram channels/accounts, auto-archive media into the workspace, queue items for geolocation. (Needs care: rate limits, ToS.) |

### Explicit non-goals

- No cloud, no accounts, no hosted service, no telemetry.
- No automated geolocation "magic button" — Ozimut prepares materials and lets the
  analyst reason (the tools-emit-facts / analyst-decides split).
- No scraping features designed to evade platform blocks; the downloader uses yt-dlp
  as-is and inherits its capabilities.
- No paid API dependencies, ever, for core features.

## 5. The case workspace

A directory per investigation (`~/Ozimut/cases/<case>/` by default):

```
case.json          # case metadata, entities, links (v3)
media/             # source videos/photos + download metadata
frames/            # extracted frames (named by source + timestamp)
panoramas/
satellite/         # crops + tile provenance (zoom, provider, date, attribution)
proofs/            # composed proofs + their editable specs (re-open & re-edit)
evidence.jsonl     # hash/timestamp/source journal (v3)
```

Every tool reads and writes here; a proof spec saved once can be reopened and
re-edited (the compose format from `geolocation_proof/compose_proof.py` is the
starting point). Plain files → users can git/zip/share a case.

## 6. Reused engine (from frame-geolocator)

Migrate as `ozimut/engine/` (no dependency on the old repo):

- frame extraction + candidates (`prepare_proof.extract_frame`)
- Esri tile math, fetch, placeholder detection, zoom fallback (`fetch_satellite`)
- plus codes + Nominatim reverse geocoding
- panorama stitcher (`stitch_panorama.stitch_window`)
- proof spec renderer (`compose_proof`) — becomes the export path of the mouse-driven
  composer; the JSON spec format is kept so proofs stay re-editable

All of it already has offline tests; migrate the tests with the code.

## 7. Milestones

1. **M0 — skeleton**: repo, FastAPI app, tab shell, workspace handling, one trivial
   tool (Coordinates) end to end, packaged binary proven on Linux + Windows.
2. **M1 — proof pipeline**: Frame Extractor → Satellite → Proof Composer with mouse
   annotation → export. *The demo video of this is the community launch.*
3. **M2 — Panorama + Coordinates polish**, first public release (GitHub + X post).
4. **M3+**: v2 tools by community demand, then the investigation layer.

## 8. Open questions

- Frontend framework final pick (Svelte vs vanilla) — decide at M0.
- pywebview window vs default browser — start with browser, revisit.
- License: MIT vs AGPL (AGPL deters closed-source forks of a community tool; MIT
  maximizes adoption). Leaning AGPL-3.0 — to confirm.
- Déjà Vu community index: needs infra + moderation; out of scope until v4.
- Name/handle availability check: GitHub org/repo `ozimut`, x.com handle, domain.
