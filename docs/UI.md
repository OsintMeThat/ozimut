# Azimut — UI direction & information architecture

Status: **direction v1** (2026-07-15). Companion to [SPEC.md](SPEC.md) §6–7 — the
spec says *what* tools exist; this doc says *where they live on screen* and *what
they look like*. Nothing here is implemented yet; rollout order at the bottom.

## 1. The two problems

1. **Look & feel**: the current skin is the generic "AI dashboard" — navy-blue
   dark theme, glowing accents, display font, rounded floating cards, marketing
   copy in the chrome. It undermines trust in a tool for evidence work.
2. **Scale**: a flat left rail works at 5 tools. The spec promises ~20 more
   (v2–v4). A flat rail of 25 entries is the GIMP-toolbox failure mode: tools
   mixed together, no visible order, nobody knows where to click next.

## 2. Design direction — the "pro desk" look

Reference points our users already trust: QGIS, Google Earth Pro, DaVinci
Resolve, Lightroom, Obsidian. Dense, flat, sober instruments — not SaaS
landing pages. Everything is tokenized in `frontend/src/app.css`, so this is a
token + shared-primitives pass, not a rewrite.

| Element | Today (AI tell) | Target |
|---|---|---|
| Font | Oxanium display, uppercase, 0.22em tracking | One workhorse UI font everywhere (system stack or Inter); mono for data (coords, hashes — already good, keep) |
| Palette | Blue-tinted navy + amber + glows | Neutral gray dark theme; **one** accent reserved for selection & the primary action only; no glow, ever |
| Shape | 6/10/14px radii, floating cards, pill badges | 2–4px radii, flat panels with visible splitters, rectangular badges |
| Density | Card grids, generous padding | Dense rows, tighter spacing, list + grid toggle where cards exist |
| Type hierarchy | Everything 600, uppercase micro-labels | Few weights; hierarchy by size and placement, not boldness |
| Motion | fade-up, hover lifts | None — instant state changes |
| Copy | Tagline in topbar, instructional italics in panels | No slogans in chrome (tagline → README/About); affordances discoverable, not explained in prose |
| Rail | 76px icon-above-label buttons (mobile pattern) | Compact workspace rail, tooltips (see §3) |

## 3. Information architecture — workspaces, not a tool list

**Principle: the rail holds a fixed, small set of *workspaces* named by
activity, in investigation-pipeline order. Tools ship as tabs/modes *inside*
a workspace — never as new rail entries.** (DaVinci Resolve "pages" model:
few pages in workflow order, media pool persistent across all of them.)

The spec has already been converging on this organically — Frame Extractor and
Panorama folded into Inspect, ELA into its Analyze fold-out, Reverse Search
into Media Library, reference viewers into Satellite. This formalizes it.

| Workspace | Today | Future tools land here as tabs/modes |
|---|---|---|
| **Collect** | Media Library (import, URL download) | Reverse Search launcher, Channel Monitor, Evidence Locker, archive-on-download |
| **Examine** | Inspect (Selection / Frame / Collage / Analyze) | EXIF & Metadata, OCR, Image Compare, Manipulation Hints, Shadow Clock, audio analysis, auto-panorama |
| **Map** | Satellite | **One persistent map, many modes**: Capture, Satellite Compare, Ground Imagery, Coordinates, Measures, Viewshed, OSM Query, Map Board pins/layers |
| **Compose** | Proof Composer, Post Composer | Report Builder, GIF maker |
| **Case** | (sidebar only) | Notes, Case Board / Relations, Timeline, Search Orchestrator |

Rules that keep it sane:

- **Max two levels.** Workspace → tab. Never deeper. Preserves SPEC principle 3
  ("one tool, useful in 30 seconds").
- **One Map.** Eight of the planned tools are "the map + a mode or layer".
  They are modes of a single map workspace (Google Earth model), sharing
  center/zoom/provider state — never separate rail entries.
- **One media viewer.** The Examine analyzers are panels over the currently
  open media, like Analyze already is.
- **Deep links target tabs** (`#map/capture`, `#examine/exif`), extending the
  existing `#satellite`-style scheme.
- **Command palette (Ctrl+K)** — "capture satellite", "open EXIF" — the
  escape hatch that keeps 20+ tools one keystroke away.
- **Navigation follows the object too**: from any media — "Examine", "Locate
  on map", "Add to proof"; the derivation-chain breadcrumb (SPEC §7) is the
  connective tissue. The rail is for starting; objects are for continuing.

## 4. Sidebar consolidation

Today the same items appear in three taxonomies: Media Library facets, Saved
Work grouped by producing tool, and My Work folders. Under the workspace
model, each workspace lists its own artifacts, so the case sidebar slims to:

- **Notes** (unchanged)
- **My Work** — the analyst's folders (the only user-owned taxonomy)
- **Selection details** — provenance / derivation chain / entity editor for
  whatever is selected anywhere in the app

Saved-work-grouped-by-tool disappears as a duplicate view once each workspace
shows its own output.

## 5. Rollout

1. **Token pass** — fonts, radii, density, neutral palette, kill
   tagline/animations. No logic changes.
2. **Workspace shell** — rail → 5 workspaces with tab strips; mostly moving
   existing components (Inspect is already internally tabbed — it's the
   template). Deep links extended.
3. **Sidebar consolidation** (with or after step 2).
4. **Command palette** — once tool count justifies it.
