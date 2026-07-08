# Ozimut

**The OSINT investigator's workbench.** One case, one folder, every tool.
Local-first: your media and your investigations never leave your machine.

Built for the open-source-investigation community — GeoConfirmed contributors,
journalists, researchers.

> Close Ozimut. Reopen the case six months later. Everything is there: the
> downloaded media, the annotated proofs, the entities and their links, the
> notes, the exports — in one plain folder you can zip, git, or share.

## v1 — Proof Studio

| Tool | What it does |
|------|--------------|
| **Media Library** | Import local files or download by URL (X, Telegram, TikTok, YouTube… via yt-dlp) → clean local file + metadata + SHA-256. |
| **Satellite** | Coordinates → imagery crop with crosshair and recorded provenance (provider, zoom, date, attribution). Esri World Imagery by default, bring-your-own-key providers supported. |
| **Proof Composer** | Compose panels side by side, annotate with colored shapes (same color = same feature), comments, legend → export `proof.png` + a re-editable spec. |
| **Post Composer** | Turn a proof into a publishable post: coordinates in all formats, plus code, attribution, character count. Copy-paste ready — Ozimut never posts for you. |

Every tool works **one-shot** (no setup, scratch session) or inside a **case**
— a plain directory holding the whole investigation.

## Install & run

```bash
pip install ozimut
ozimut            # starts on http://127.0.0.1:8477 and opens your browser
```

From source:

```bash
git clone https://github.com/ozimut/ozimut && cd ozimut
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd frontend && npm install && npm run build && cd ..
.venv/bin/ozimut
```

Frontend development (hot reload, proxied API):

```bash
.venv/bin/ozimut --no-browser &     # backend on :8477
cd frontend && npm run dev          # UI on :5173
```

## Principles

1. **Local-first, privacy-first** — no account, no telemetry, no upload; the
   server binds to `127.0.0.1` only.
2. **The case is the product** — plain JSON + media files, versionable,
   portable.
3. **One tab = one tool**, useful in 30 seconds.
4. **Orchestrator, not replacer** — integrate specialized services, don't clone
   them.
5. **Tools emit facts, the analyst decides** — no automated "magic button".
6. **Honest output** — every artifact records how it was produced.
7. **Free and open source** — no paid keys required, ever. Optional
   bring-your-own-key providers.

Full spec: [docs/SPEC.md](docs/SPEC.md).

## License

AGPL-3.0 (see [SPEC §9](docs/SPEC.md) — final confirmation pending).
