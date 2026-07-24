# Azimut v0.2.2

## OSINT toolkit at a glance

- **Sources:** import or download media, reach login-walled posts with your own browser session, record hashes and provenance, inspect frames, crops, collages, panoramas and ELA, then prepare reverse-image searches.
- **Maps:** convert coordinates, geocode places, capture attributed imagery, compare providers, rotate and measure maps, save references and review AOI grids.
- **Evidence:** organise media, places, proofs and notes in portable cases with folders, links, Markdown notebooks and PDF output.
- **Publishing:** build annotated Geo Proofs and prepare evidence-linked Geo Reports for X, Bluesky or Mastodon without posting automatically.

## What changed

- **Gated downloads.** Downloads now get past a login wall. Public media is still fetched without any session; only when a post turns out to need an account does Media offer to borrow a signed-in browser's cookies or an exported `cookies.txt`. The session is used for that download, kept private in your workspace, and never leaves the machine. Chromium on Windows can't be read, so Azimut points you to the file route instead.
- **Responsive Geo Proof toolbar.** The proof toolbar reflows to fit narrow screens instead of overflowing, and remembers the colour and stroke width you last drew with.

## Install or upgrade

Download the ready-to-run asset for Windows, Linux x86_64 or Apple Silicon macOS from this release and run it. Each binary includes the browser UI, `ffmpeg` and `ffprobe`; no Python or system FFmpeg is needed. Intel Macs are supported through `pipx install azimut` or `pip install azimut`.

Existing cases open in place; no manual export or import is required.
