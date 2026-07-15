<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { toast } from '../lib/state.svelte.js';
  import {
    monthCount,
    tilesOfFree,
    freeTierShare,
    usageBlocked,
    USAGE_LINKS,
    BLOCK_SHARE,
    ECO_MAX_ZOOM,
  } from '../lib/usage.js';
  import Icon from '../components/Icon.svelte';

  // The keyed imagery providers the app knows how to light up (IMAGERY_PROVIDERS.md).
  // Keys are app-wide, stored locally in settings.json, never written into a
  // case folder or export bundle — they're the user's own billing identity.
  const KEYED = [
    {
      id: 'mapbox',
      label: 'Mapbox',
      field: 'Mapbox public access token',
      placeholder: 'pk.…',
      help: 'https://account.mapbox.com/access-tokens/',
      usage: USAGE_LINKS.mapbox,
      unlocks: 'Mapbox Satellite basemap',
      overage:
        'Beyond 200k free tiles/month, Mapbox bills extra tiles automatically ($0.50 per 1,000, pay-as-you-go, no hard cap). Set a spending alert in your Mapbox account.',
    },
    {
      id: 'google',
      label: 'Google',
      field: 'Google Maps Platform API key',
      placeholder: 'AIza…',
      help: 'https://developers.google.com/maps/documentation/tile/get-api-key',
      usage: USAGE_LINKS.google,
      unlocks: 'Google Satellite basemap (Map Tiles API)',
      overage:
        'Beyond 100k free tiles/month, Google bills extra tiles to your Cloud project ($0.60 per 1,000; Google also enforces 15k tiles/day). A quota cap in the Cloud Console makes it stop serving instead of billing.',
    },
  ];

  let keys = $state({ mapbox: '', google: '' });
  let shown = $state({ mapbox: false, google: false });
  let usage = $state({});
  let month = $state('');
  let saving = $state(false);
  let testing = $state({ mapbox: false, google: false });
  let testResult = $state({ mapbox: null, google: null }); // { ok, detail } | null
  // keyed-provider preferences (IMAGERY_PROVIDERS.md) — saved on toggle
  let enabled = $state({ mapbox: true, google: true });
  let overrides = $state({ mapbox: false, google: false });
  let eco = $state(true);
  let ecoMaxZoom = $state(ECO_MAX_ZOOM);

  async function load() {
    const s = await api.get('/api/settings');
    keys = { mapbox: s.api_keys.mapbox ?? '', google: s.api_keys.google ?? '' };
    usage = s.usage;
    month = s.month;
    enabled = { mapbox: s.providers_enabled.mapbox ?? true, google: s.providers_enabled.google ?? true };
    overrides = { mapbox: !!s.usage_overrides.mapbox, google: !!s.usage_overrides.google };
    eco = s.eco_zoom_fallback;
    ecoMaxZoom = s.eco_max_zoom ?? ECO_MAX_ZOOM;
  }

  async function savePrefs() {
    try {
      const saved = await api.put('/api/settings/prefs', {
        providers_enabled: enabled,
        usage_overrides: overrides,
        eco_zoom_fallback: eco,
        eco_max_zoom: Number(ecoMaxZoom) || ECO_MAX_ZOOM,
      });
      ecoMaxZoom = saved.eco_max_zoom; // reflect the server's clamping
    } catch (e) {
      toast(`Could not save preferences: ${e.message}`, 'danger');
    }
  }

  onMount(() => {
    load().catch((e) => toast(`Could not load settings: ${e.message}`, 'danger'));
  });

  async function saveKeys() {
    if (saving) return;
    saving = true;
    try {
      await api.put('/api/settings/keys', { mapbox: keys.mapbox, google: keys.google });
      testResult = { mapbox: null, google: null }; // stale verdicts for new keys
      toast('Keys saved. Keyed basemaps now appear in the Satellite tab', 'ok');
    } catch (e) {
      toast(`Could not save keys: ${e.message}`, 'danger');
    } finally {
      saving = false;
    }
  }

  // exercise the *saved* key against the real service (Mapbox: one tile;
  // Google: createSession) so a typo shows up here, not mid-investigation
  async function testKey(id) {
    if (testing[id]) return;
    testing[id] = true;
    testResult[id] = null;
    try {
      await api.put('/api/settings/keys', { [id]: keys[id] }); // test what's in the field
      testResult[id] = await api.post(`/api/settings/keys/${id}/test`);
    } catch (e) {
      testResult[id] = { ok: false, detail: e.message };
    } finally {
      testing[id] = false;
    }
  }
</script>

<div class="tool">
  <div class="tool-header">
    <h2>Settings</h2>
  </div>

  <div class="body">
    <section class="card block">
      <h3><Icon name="key" size={15} /> Imagery API keys</h3>
      <p class="hint">
        Optional. Azimut's built-in basemaps (Esri, OSM) never need a key — your own
        Mapbox / Google keys just unlock extra official basemaps in the Satellite tab.
        Keys stay in <span class="mono">settings.json</span> on this machine.
      </p>

      {#each KEYED as k (k.id)}
        <div class="key-row">
          <label for="key-{k.id}">
            {k.field}
            <a href={k.help} target="_blank" rel="noreferrer" title="How to get one">
              how to get one <Icon name="external" size={11} />
            </a>
          </label>
          <div class="key-line">
            <input
              id="key-{k.id}"
              class="input"
              type={shown[k.id] ? 'text' : 'password'}
              placeholder={k.placeholder}
              bind:value={keys[k.id]}
              autocomplete="off"
              spellcheck="false"
            />
            <button
              class="btn btn-ghost btn-sm"
              onclick={() => (shown[k.id] = !shown[k.id])}
              title={shown[k.id] ? 'Hide key' : 'Show key'}
              aria-label={shown[k.id] ? 'Hide key' : 'Show key'}
            >
              <Icon name={shown[k.id] ? 'eyeOff' : 'eye'} size={14} />
            </button>
            <button
              class="btn btn-sm"
              onclick={() => testKey(k.id)}
              disabled={testing[k.id] || !keys[k.id].trim()}
              title="Save this key, then exercise it against the real service"
            >
              {testing[k.id] ? 'Testing…' : 'Test'}
            </button>
          </div>
          <div class="key-foot">
            <span class="unlocks">Unlocks: {k.unlocks}</span>
            {#if keys[k.id]}
              <label
                class="toggle"
                title="Hide or show this basemap in the Satellite tab — the key stays saved"
              >
                <input type="checkbox" bind:checked={enabled[k.id]} onchange={savePrefs} />
                enabled
              </label>
            {/if}
            {#if testResult[k.id]}
              <span class="verdict" class:ok={testResult[k.id].ok} class:bad={!testResult[k.id].ok}>
                <Icon name={testResult[k.id].ok ? 'check' : 'alert'} size={12} />
                {testResult[k.id].ok ? 'Key works' : testResult[k.id].detail}
              </span>
            {/if}
          </div>
        </div>
      {/each}

      <div class="actions">
        <button class="btn btn-primary" onclick={saveKeys} disabled={saving}>
          {saving ? 'Saving…' : 'Save keys'}
        </button>
      </div>
    </section>

    <section class="card block">
      <h3><Icon name="chart" size={15} /> Tile usage · {month}</h3>
      <p class="hint">
        Keyed providers bill per tile served. Azimut counts exactly what goes out to
        each provider (live map + captures, browser cache hits excluded), so this
        matches their billing as closely as possible. Local bookkeeping only — the
        counter never leaves this machine.
      </p>
      {#if KEYED.some((k) => keys[k.id] || monthCount(usage, k.id, month))}
        <div class="usage">
          {#each KEYED as k (k.id)}
            {#if keys[k.id] || monthCount(usage, k.id, month)}
              {@const count = monthCount(usage, k.id, month)}
              {@const share = freeTierShare(count, k.id)}
              <div class="usage-row">
                <div class="usage-line">
                  <span class="usage-name">
                    {k.label}
                    <a href={k.usage} target="_blank" rel="noreferrer"
                      title="The provider's own usage & limits dashboard — the counter that actually bills"
                    >usage & limits <Icon name="external" size={11} /></a>
                  </span>
                  <span class="mono">{tilesOfFree(count, k.id)}</span>
                </div>
                <div class="meter-track" aria-hidden="true">
                  <div
                    class="meter-fill"
                    class:hot={share >= BLOCK_SHARE}
                    style="width:{Math.min(share * 100, 100)}%"
                  ></div>
                </div>
                {#if usageBlocked(count, k.id, overrides)}
                  <p class="blocked">
                    <Icon name="alert" size={12} />
                    Paused at {Math.round(BLOCK_SHARE * 100)}% of the free tier — the map and
                    captures fall back to free imagery until next month, or:
                  </p>
                {/if}
                {#if share >= BLOCK_SHARE || overrides[k.id]}
                  <label class="toggle override" title="Serve past the pause — extra tiles are billed by the provider">
                    <input type="checkbox" bind:checked={overrides[k.id]} onchange={savePrefs} />
                    keep serving past {Math.round(BLOCK_SHARE * 100)}% (billed)
                  </label>
                {/if}
                <p class="overage">{k.overage}</p>
              </div>
            {/if}
          {/each}
        </div>
      {:else}
        <p class="none">No keyed provider configured yet.</p>
      {/if}
      <label
        class="toggle eco"
        title="Zoomed out this far, billed basemaps silently swap to free imagery — paid detail only matters up close"
      >
        <input type="checkbox" bind:checked={eco} onchange={savePrefs} />
        Eco mode: use free imagery when zoomed out, up to z ≤
        <input
          class="input eco-zoom"
          type="number"
          min="1"
          max="21"
          bind:value={ecoMaxZoom}
          onchange={savePrefs}
          disabled={!eco}
          aria-label="Eco mode zoom threshold"
        />
      </label>
      <button class="btn btn-ghost btn-sm" onclick={() => load()} title="Refresh counters">
        <Icon name="reset" size={13} /> Refresh
      </button>
    </section>

    <section class="card block">
      <h3><Icon name="shield" size={15} /> Provider terms, encoded</h3>
      <ul class="rules">
        <li>Google tiles are never cached to disk, and a Google capture is a flattened screenshot with the copyright line burned into its footer; both are conditions of Google's Map Tiles API terms.</li>
        <li>Mapbox captures keep the © Mapbox © OpenStreetMap attribution in their provenance.</li>
        <li>Keys are never bundled into a shared case or export.</li>
      </ul>
    </section>
  </div>
</div>

<style>
  .tool {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  .tool-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 14px 18px 10px;
  }
  .tool-header h2 {
    font-size: var(--fs-lg);
  }
  .sub {
    color: var(--text-3);
    font-size: var(--fs-sm);
  }
  .body {
    flex: 1;
    overflow-y: auto;
    padding: 6px 18px 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-width: 720px;
  }
  .block {
    padding: 16px;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-md);
    margin-bottom: 6px;
  }
  .hint {
    color: var(--text-3);
    font-size: var(--fs-sm);
    margin-bottom: 14px;
    line-height: 1.5;
  }
  .key-row {
    margin-bottom: 14px;
  }
  .key-row label {
    display: flex;
    align-items: baseline;
    gap: 10px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    font-weight: 600;
    margin-bottom: 5px;
  }
  .key-row label a {
    color: var(--accent);
    font-weight: 400;
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .key-line {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .key-line .input {
    flex: 1;
    font-family: var(--font-mono);
  }
  .key-foot {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-top: 4px;
    font-size: var(--fs-xs);
  }
  .unlocks {
    color: var(--text-3);
  }
  .verdict {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .verdict.ok {
    color: var(--ok);
  }
  .verdict.bad {
    color: var(--danger);
  }
  .actions {
    margin-top: 4px;
  }
  .usage {
    margin: 0 0 10px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    font-size: var(--fs-sm);
  }
  .usage-line {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 5px;
  }
  .usage-name {
    font-weight: 600;
    color: var(--text-2);
  }
  .meter-track {
    height: 5px;
    border-radius: var(--r-sm);
    background: var(--bg-2);
    border: 1px solid var(--border);
    overflow: hidden;
  }
  .meter-fill {
    height: 100%;
    background: var(--accent);
    border-radius: inherit;
    transition: width 0.3s var(--ease);
  }
  .meter-fill.hot {
    background: var(--danger);
  }
  .overage {
    margin-top: 5px;
    color: var(--text-3);
    font-size: var(--fs-xs);
    line-height: 1.4;
  }
  .usage-name a {
    color: var(--accent);
    font-weight: 400;
    font-size: var(--fs-xs);
    margin-left: 8px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    cursor: pointer;
    user-select: none;
  }
  .toggle input {
    accent-color: var(--accent);
    margin: 0;
  }
  .toggle.override {
    margin-top: 6px;
    color: var(--danger);
  }
  .toggle.eco {
    display: flex;
    margin: 2px 0 10px;
  }
  .eco-zoom {
    width: 58px;
    padding: 2px 6px;
    font-family: var(--font-mono);
  }
  .blocked {
    margin-top: 6px;
    color: var(--danger);
    font-size: var(--fs-xs);
    display: flex;
    align-items: center;
    gap: 5px;
    line-height: 1.4;
  }
  .none {
    color: var(--text-3);
    font-size: var(--fs-sm);
    margin-bottom: 10px;
  }
  .rules {
    margin: 0;
    padding-left: 18px;
    color: var(--text-2);
    font-size: var(--fs-sm);
    display: flex;
    flex-direction: column;
    gap: 6px;
    line-height: 1.45;
  }
</style>
