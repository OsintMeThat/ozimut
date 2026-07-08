<script>
  import { api } from '../lib/api.js';
  import { caseState, uiState, toast } from '../lib/state.svelte.js';
  import Icon from '../components/Icon.svelte';

  const X_LIMIT = 280;
  const URL_WEIGHT = 23; // X counts every URL as 23 chars

  let coordsText = $state('');
  let geo = $state(null); // {lat, lon, dms, plus_code, links}
  let place = $state('');
  let placeLoading = $state(false);
  let title = $state('');
  let source = $state('');
  let attribution = $state('');
  let text = $state('');
  let proofPng = $state(null);
  let edited = $state(false);

  // ingest a proof handed over by the composer
  $effect(() => {
    const p = uiState.postProof;
    if (!p) return;
    uiState.postProof = null;
    title = p.title === 'Untitled proof' ? '' : p.title;
    attribution = p.attribution ?? '';
    source = p.sources?.[0] ?? '';
    proofPng = p.png ?? null;
    edited = false;
    if (p.coords) {
      coordsText = `${p.coords.lat.toFixed(6)}, ${p.coords.lon.toFixed(6)}`;
      resolveCoords();
    } else {
      regenerate();
    }
  });

  async function resolveCoords() {
    const value = coordsText.trim();
    if (!value) {
      geo = null;
      regenerate();
      return;
    }
    try {
      geo = await api.post('/api/geo/parse', { text: value });
      regenerate();
      lookupPlace();
    } catch {
      toast('Could not parse coordinates', 'danger');
    }
  }

  async function lookupPlace() {
    if (!geo) return;
    placeLoading = true;
    try {
      const r = await api.get(`/api/geo/reverse?lat=${geo.lat}&lon=${geo.lon}`);
      const a = r.address ?? {};
      place = [a.village || a.town || a.city || a.county, a.state, a.country]
        .filter(Boolean)
        .join(', ') || r.display_name || '';
      regenerate();
    } catch {
      /* offline or Nominatim down — place stays manual */
    } finally {
      placeLoading = false;
    }
  }

  function buildText() {
    const lines = [];
    lines.push(title.trim() ? `📍 Geolocated: ${title.trim()}` : '📍 Geolocated');
    if (geo) {
      lines.push('');
      lines.push(`${geo.lat.toFixed(6)}, ${geo.lon.toFixed(6)}`);
      lines.push(`${geo.dms}`);
      lines.push(`Plus code: ${geo.plus_code}`);
    }
    if (place.trim()) lines.push(place.trim());
    if (source.trim()) {
      lines.push('');
      lines.push(`Source: ${source.trim()}`);
    }
    if (attribution.trim()) {
      lines.push('');
      lines.push(attribution.trim());
    }
    return lines.join('\n');
  }

  function regenerate() {
    text = buildText();
    edited = false;
  }

  function weightedLength(t) {
    const urlRe = /https?:\/\/\S+/g;
    const stripped = t.replace(urlRe, '');
    const urls = t.match(urlRe)?.length ?? 0;
    return [...stripped].length + urls * URL_WEIGHT;
  }

  const count = $derived(weightedLength(text));
  const over = $derived(count > X_LIMIT);

  /** Split into a numbered thread at word boundaries under the weighted limit. */
  const thread = $derived.by(() => {
    if (!over) return null;
    const words = text.split(/(\s+)/);
    const parts = [];
    let current = '';
    for (const w of words) {
      const suffixReserve = 8; // " (99/99)"
      if (weightedLength(current + w) > X_LIMIT - suffixReserve && current.trim()) {
        parts.push(current.trim());
        current = w.trimStart();
      } else {
        current += w;
      }
    }
    if (current.trim()) parts.push(current.trim());
    return parts.map((p, i) => `${p}\n(${i + 1}/${parts.length})`);
  });

  async function copy(value) {
    await navigator.clipboard.writeText(value);
    toast('Copied to clipboard', 'ok', 1600);
  }
</script>

<div class="tool">
  <div class="tool-header">
    <h2>Post Composer</h2>
    <span class="sub">publishable post from your proof — you copy, you publish, Ozimut never posts</span>
  </div>

  <div class="tool-body">
    <div class="layout">
      <!-- left column: ingredients -->
      <div class="col">
        <div class="field">
          <label class="label" for="pc-title">What was geolocated</label>
          <input
            id="pc-title"
            class="input"
            placeholder="e.g. Strike on a warehouse, north of Kharkiv"
            bind:value={title}
            onchange={regenerate}
          />
        </div>

        <div class="field">
          <label class="label" for="pc-coords">Coordinates</label>
          <div class="row">
            <input
              id="pc-coords"
              class="input mono"
              placeholder="50.4501, 30.5234"
              bind:value={coordsText}
              onchange={resolveCoords}
            />
          </div>
          {#if geo}
            <div class="geo-facts card">
              <button class="fact mono" onclick={() => copy(`${geo.lat.toFixed(6)}, ${geo.lon.toFixed(6)}`)} title="Copy">
                <Icon name="crosshair" size={12} /> {geo.lat.toFixed(6)}, {geo.lon.toFixed(6)}
              </button>
              <button class="fact mono" onclick={() => copy(geo.dms)} title="Copy">
                <Icon name="globe" size={12} /> {geo.dms}
              </button>
              <button class="fact mono" onclick={() => copy(geo.plus_code)} title="Copy">
                <Icon name="hash" size={12} /> {geo.plus_code}
              </button>
              <div class="links">
                {#each Object.entries(geo.links) as [name, url] (name)}
                  <a href={url} target="_blank" rel="noreferrer" class="badge info">{name}</a>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <div class="field">
          <label class="label" for="pc-place">
            Place {#if placeLoading}<span class="loading">resolving…</span>{/if}
          </label>
          <input
            id="pc-place"
            class="input"
            placeholder="Village, Oblast, Country"
            bind:value={place}
            onchange={regenerate}
          />
        </div>

        <div class="field">
          <label class="label" for="pc-source">Source credit</label>
          <input
            id="pc-source"
            class="input"
            placeholder="https://t.me/… (original post)"
            bind:value={source}
            onchange={regenerate}
          />
        </div>

        <div class="field">
          <label class="label" for="pc-attr">Imagery attribution</label>
          <input
            id="pc-attr"
            class="input"
            placeholder="Imagery: Esri, Maxar, …"
            bind:value={attribution}
            onchange={regenerate}
          />
        </div>

        {#if proofPng && caseState.current}
          <div class="field">
            <span class="label">Attached proof</span>
            <a href={`/files/${caseState.current.id}/${proofPng}`} target="_blank" rel="noreferrer">
              <img class="proof-preview card" src={`/files/${caseState.current.id}/${proofPng}`} alt="proof" />
            </a>
          </div>
        {/if}
      </div>

      <!-- right column: the post -->
      <div class="col">
        <div class="field grow">
          <div class="post-head">
            <span class="label" style="margin: 0">Post text</span>
            {#if edited}
              <button class="btn btn-ghost btn-sm" onclick={regenerate} title="Rebuild from the fields">
                <Icon name="compass" size={13} /> regenerate
              </button>
            {/if}
            <span class="counter" class:over>{count}/{X_LIMIT}</span>
          </div>
          <textarea
            class="textarea post-text mono"
            bind:value={text}
            oninput={() => (edited = true)}
            rows="12"
          ></textarea>
          <div class="post-actions">
            <button class="btn btn-primary" onclick={() => copy(text)} disabled={!text.trim()}>
              <Icon name="copy" size={15} /> Copy post
            </button>
            {#if over}
              <span class="over-hint">over the X limit — thread below</span>
            {/if}
          </div>
        </div>

        {#if thread}
          <div class="field">
            <span class="label">As a thread ({thread.length} posts)</span>
            <div class="thread">
              {#each thread as part, i (i)}
                <div class="thread-post card">
                  <pre>{part}</pre>
                  <button class="btn btn-ghost btn-sm" onclick={() => copy(part)} title="Copy this post">
                    <Icon name="copy" size={13} />
                  </button>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .layout {
    display: grid;
    grid-template-columns: minmax(320px, 460px) minmax(360px, 1fr);
    gap: 26px;
    padding: 20px;
    max-width: 1200px;
  }
  .col {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }
  .field.grow { display: flex; flex-direction: column; }
  .row { display: flex; gap: 8px; }
  .geo-facts {
    margin-top: 8px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .fact {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    padding: 3px 6px;
    border-radius: var(--r-sm);
    text-align: left;
  }
  .fact:hover { background: var(--bg-3); color: var(--text-1); }
  .links {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    padding: 6px 6px 2px;
  }
  .loading {
    text-transform: none;
    letter-spacing: 0;
    color: var(--accent);
    font-weight: 500;
  }
  .proof-preview {
    max-height: 200px;
    object-fit: contain;
    padding: 6px;
  }
  .post-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }
  .counter {
    margin-left: auto;
    font-size: var(--fs-xs);
    font-weight: 700;
    color: var(--ok);
    font-family: var(--font-mono);
  }
  .counter.over { color: var(--danger); }
  .post-text {
    min-height: 260px;
    font-size: var(--fs-sm);
    line-height: 1.6;
  }
  .post-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
  }
  .over-hint {
    font-size: var(--fs-xs);
    color: var(--warn);
  }
  .thread {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .thread-post {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
  }
  .thread-post pre {
    flex: 1;
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-1);
  }
</style>
