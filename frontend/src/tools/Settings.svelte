<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { toast, prefs, applyPrefs } from '../lib/state.svelte.js';
  import { formatCoords, parseHomeView } from '../lib/coords.js';
  import { formatDistance, formatArea } from '../lib/measure.js';
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

  const TABS = [
    { id: 'preferences', label: 'Preferences', icon: 'sliders' },
    { id: 'imagery', label: 'Imagery', icon: 'key' },
    { id: 'usage', label: 'Usage', icon: 'chart' },
    { id: 'about', label: 'About', icon: 'compass' },
  ];
  let tab = $state('preferences');

  const REPO_URL = 'https://github.com/OsintMeThat/azimut';
  const SITE_URL = 'https://osintmethat.com';

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

  const COORD_CHOICES = [
    { id: 'dd', label: 'Decimal' },
    { id: 'dms', label: 'DMS' },
    { id: 'mgrs', label: 'MGRS' },
  ];
  const UNIT_CHOICES = [
    { id: 'metric', label: 'Metric' },
    { id: 'imperial', label: 'Imperial' },
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
  let about = $state({ version: '', workspace_root: '' });
  // the home-view fields are edited as text, so a half-typed "-" or "48." isn't
  // fought by the number parser mid-keystroke; committed on change
  let home = $state({ lat: '', lon: '', zoom: '' });
  let mention = $state('');
  // the analyst's logo: app-wide like the API keys, and under the same rule —
  // it lives beside settings.json and only ever reaches a case as pixels in a
  // rendered proof PNG. `sigBust` re-fetches the <img> after a replace.
  let signature = $state(false);
  let sigBust = $state(0);
  let sigInput = $state(null);

  // The downloaders age faster than Azimut releases: sites change, and a stale
  // yt-dlp just stops finding media. They can be refreshed from PyPI in place,
  // without waiting for (or reinstalling) the app — see engine/scrapers.py.
  const SCRAPER_LABELS = { 'yt-dlp': 'yt-dlp', 'gallery-dl': 'gallery-dl' };
  let scrapers = $state([]);
  let checking = $state(false);
  let updating = $state({}); // { [dist]: true } while its request is in flight

  async function loadScrapers(check = false) {
    const path = check ? '/api/settings/scrapers?check=true' : '/api/settings/scrapers';
    scrapers = (await api.get(path)).scrapers;
  }

  // Opt-in, never on mount: Azimut is local-first, so opening Settings must not
  // phone out. The user asks, and only then do we look at PyPI.
  async function checkScrapers() {
    if (checking) return;
    checking = true;
    try {
      await loadScrapers(true);
      const stale = scrapers.filter((s) => s.outdated);
      const failed = scrapers.find((s) => s.check_error);
      if (failed) toast(`Could not reach PyPI: ${failed.check_error}`, 'danger');
      else if (!stale.length) toast('Downloaders are up to date', 'ok');
    } catch (e) {
      toast(`Could not check for updates: ${e.message}`, 'danger');
    } finally {
      checking = false;
    }
  }

  async function updateScraper(dist) {
    if (updating[dist]) return;
    updating[dist] = true;
    try {
      const r = await api.post(`/api/settings/scrapers/${dist}/update`);
      if (!r.ok) toast(`${dist}: ${r.detail}`, 'danger');
      else toast(`${dist} ${r.detail}`, r.restart_required ? 'warn' : 'ok');
      await loadScrapers();
      // keep the "restart to use it" state visible — a reload would drop it
      if (r.ok && r.restart_required) {
        const entry = scrapers.find((s) => s.dist === dist);
        if (entry) entry.restart_required = true;
      }
    } catch (e) {
      toast(`${dist}: ${e.message}`, 'danger');
    } finally {
      updating[dist] = false;
    }
  }

  async function resetScraper(dist) {
    try {
      const r = await api.del(`/api/settings/scrapers/${dist}`);
      await loadScrapers();
      if (r.restart_required) toast(`${dist} reverted — restart Azimut to use it`, 'warn');
      else toast(`${dist} reverted to the bundled version`, 'ok');
    } catch (e) {
      toast(`${dist}: ${e.message}`, 'danger');
    }
  }

  async function load() {
    const s = await api.get('/api/settings');
    signature = !!s.signature;
    keys = { mapbox: s.api_keys.mapbox ?? '', google: s.api_keys.google ?? '' };
    usage = s.usage;
    month = s.month;
    enabled = { mapbox: s.providers_enabled.mapbox ?? true, google: s.providers_enabled.google ?? true };
    overrides = { mapbox: !!s.usage_overrides.mapbox, google: !!s.usage_overrides.google };
    eco = s.eco_zoom_fallback;
    ecoMaxZoom = s.eco_max_zoom ?? ECO_MAX_ZOOM;
    about = { version: s.version ?? '', workspace_root: s.workspace_root ?? '' };
    home = { lat: String(s.home_view.lat), lon: String(s.home_view.lon), zoom: String(s.home_view.zoom) };
    mention = s.post_mention ?? '';
    applyPrefs(s); // the rest of the app reads these live
    await loadScrapers().catch(() => {}); // local disk read; never blocks Settings
  }

  // Every preference saves on change — no "Save" button to forget. The server's
  // answer is the source of truth, so clamped/normalised values show up here.
  async function savePrefs(patch) {
    try {
      const saved = await api.put('/api/settings/prefs', patch);
      applyPrefs(saved);
      return saved;
    } catch (e) {
      toast(`Could not save preferences: ${e.message}`, 'danger');
      await load().catch(() => {}); // don't leave a rejected value on screen
      return null;
    }
  }

  async function uploadSignature(event) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append('file', file);
    try {
      await api.post('/api/settings/signature', body);
      signature = true;
      sigBust++;
      toast('Signature saved', 'ok');
    } catch (e) {
      toast(`Could not save the signature: ${e.message}`, 'danger');
    }
    if (sigInput) sigInput.value = ''; // let the same file be picked again
  }

  async function removeSignature() {
    try {
      await api.del('/api/settings/signature');
      signature = false;
      toast('Signature removed', 'ok');
    } catch (e) {
      toast(`Could not remove the signature: ${e.message}`, 'danger');
    }
  }

  function saveProviderPrefs() {
    savePrefs({
      providers_enabled: enabled,
      usage_overrides: overrides,
      eco_zoom_fallback: eco,
      eco_max_zoom: Number(ecoMaxZoom) || ECO_MAX_ZOOM,
    });
  }

  async function saveEcoZoom() {
    const saved = await savePrefs({
      eco_zoom_fallback: eco,
      eco_max_zoom: Number(ecoMaxZoom) || ECO_MAX_ZOOM,
    });
    if (saved) ecoMaxZoom = saved.eco_max_zoom; // reflect the server's clamping
  }

  async function saveHome() {
    const view = parseHomeView(home);
    if (!view) {
      toast('Home view needs a latitude, a longitude and a zoom', 'danger');
      await load();
      return;
    }
    const saved = await savePrefs({ home_view: view });
    // echo back what the server stored — a point off the globe is refused there
    if (saved) {
      home = {
        lat: String(saved.home_view.lat),
        lon: String(saved.home_view.lon),
        zoom: String(saved.home_view.zoom),
      };
    }
  }

  // a live sample so the format choice is legible before it's applied elsewhere
  const coordSample = $derived(
    formatCoords(Number(home.lat) || 48.8584, Number(home.lon) || 2.2945, prefs.coordFormat)
  );

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
    <span class="sub">Applies to every case on this machine</span>
  </div>

  <div class="split">
    <nav class="rail" aria-label="Settings sections">
      {#each TABS as t (t.id)}
        <button
          class="rail-tab"
          class:active={tab === t.id}
          onclick={() => (tab = t.id)}
          aria-current={tab === t.id ? 'page' : undefined}
        >
          <Icon name={t.icon} size={15} />
          {t.label}
        </button>
      {/each}
    </nav>

    <div class="pane">
      {#if tab === 'preferences'}
        <section class="group">
          <h3>Coordinates</h3>
          <div class="row">
            <div class="row-label">
              <span>Format</span>
              <span class="row-hint">How every tool prints a latitude/longitude.</span>
            </div>
            <div class="seg" role="group" aria-label="Coordinate format">
              {#each COORD_CHOICES as c (c.id)}
                <button
                  class="seg-btn"
                  class:on={prefs.coordFormat === c.id}
                  onclick={() => savePrefs({ coord_format: c.id })}
                >{c.label}</button>
              {/each}
            </div>
          </div>
          <p class="sample mono">{coordSample}</p>
          <p class="note">
            Display only — captures, proofs and <span class="mono">case.json</span> always
            keep decimal degrees, so a case reads the same for everyone.
          </p>
        </section>

        <section class="group">
          <h3>Measurements</h3>
          <div class="row">
            <div class="row-label">
              <span>Units</span>
              <span class="row-hint">The Satellite ruler, area and readouts.</span>
            </div>
            <div class="seg" role="group" aria-label="Units">
              {#each UNIT_CHOICES as c (c.id)}
                <button
                  class="seg-btn"
                  class:on={prefs.units === c.id}
                  onclick={() => savePrefs({ units: c.id })}
                >{c.label}</button>
              {/each}
            </div>
          </div>
          <p class="sample mono">
            {formatDistance(1234, prefs.units)} · {formatArea(52000, prefs.units)}
          </p>
        </section>

        <section class="group">
          <h3>Satellite home view</h3>
          <p class="intro">
            Where the Satellite tab opens. A case artifact or a “go to coordinates”
            handoff still wins — this is only the starting point.
          </p>
          <div class="grid-3">
            <label class="field">
              <span>Latitude</span>
              <input class="input mono" bind:value={home.lat} onchange={saveHome} inputmode="decimal" spellcheck="false" />
            </label>
            <label class="field">
              <span>Longitude</span>
              <input class="input mono" bind:value={home.lon} onchange={saveHome} inputmode="decimal" spellcheck="false" />
            </label>
            <label class="field">
              <span>Zoom</span>
              <input class="input mono" bind:value={home.zoom} onchange={saveHome} type="number" min="1" max="21" />
            </label>
          </div>
        </section>

        <section class="group">
          <h3>Post composer</h3>
          <div class="row">
            <div class="row-label">
              <span>Default mention</span>
              <span class="row-hint">Pre-filled on a new draft. Leave empty for none.</span>
            </div>
            <input
              class="input mention"
              bind:value={mention}
              onchange={() => savePrefs({ post_mention: mention })}
              placeholder="@GeoConfirmed"
              spellcheck="false"
            />
          </div>
        </section>

        <section class="group">
          <h3>Signature</h3>
          <div class="row">
            <div class="row-label">
              <span>Your logo</span>
              <span class="row-hint">
                A transparent PNG, under 2 MB. Stays on this machine — the proof
                composer stamps it onto proofs you tick “Signature” on, and
                nothing else ever carries it.
              </span>
            </div>
            <div class="sig-side">
              {#if signature}
                <img class="sig-preview" src={`/api/settings/signature.png?v=${sigBust}`} alt="Your signature" />
              {/if}
              <div class="sig-buttons">
                <button class="btn btn-sm" onclick={() => sigInput?.click()}>
                  {signature ? 'Replace…' : 'Choose PNG…'}
                </button>
                {#if signature}
                  <button class="btn btn-danger btn-sm" onclick={removeSignature}>Remove</button>
                {/if}
              </div>
            </div>
            <input
              bind:this={sigInput}
              class="sig-file"
              type="file"
              accept="image/png"
              onchange={uploadSignature}
            />
          </div>
        </section>
      {/if}

      {#if tab === 'imagery'}
        <section class="group">
          <h3>API keys</h3>
          <p class="intro">
            Optional. Azimut's built-in basemaps (Esri, OSM, OpenTopoMap) never need a key — your own
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
                    <input type="checkbox" bind:checked={enabled[k.id]} onchange={saveProviderPrefs} />
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

        <section class="group">
          <h3><Icon name="shield" size={14} /> Provider terms, encoded</h3>
          <ul class="rules">
            <li>Google tiles are never cached to disk, and a Google capture is a flattened screenshot with the copyright line burned into its footer; both are conditions of Google's Map Tiles API terms.</li>
            <li>Mapbox captures keep the © Mapbox © OpenStreetMap attribution in their provenance.</li>
            <li>Keys are never bundled into a shared case or export.</li>
          </ul>
        </section>
      {/if}

      {#if tab === 'usage'}
        <section class="group">
          <h3>Tile usage · {month}</h3>
          <p class="intro">
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
                        <input type="checkbox" bind:checked={overrides[k.id]} onchange={saveProviderPrefs} />
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
            <input type="checkbox" bind:checked={eco} onchange={saveEcoZoom} />
            Eco mode: use free imagery when zoomed out, up to z ≤
            <input
              class="input eco-zoom"
              type="number"
              min="1"
              max="21"
              bind:value={ecoMaxZoom}
              onchange={saveEcoZoom}
              disabled={!eco}
              aria-label="Eco mode zoom threshold"
            />
          </label>
          <button class="btn btn-ghost btn-sm" onclick={() => load()} title="Refresh counters">
            <Icon name="reset" size={13} /> Refresh
          </button>
        </section>
      {/if}

      {#if tab === 'about'}
        <section class="group">
          <h3>Azimut</h3>
          <dl class="facts">
            <dt>Version</dt>
            <dd class="mono">{about.version || '—'}</dd>
            <dt>Workspace</dt>
            <dd class="mono">{about.workspace_root || '—'}</dd>
            <dt>License</dt>
            <dd>AGPL-3.0-or-later</dd>
          </dl>
          <p class="note">
            The workspace is a plain folder: cases, media and proofs are files you can
            zip, back up or put under git. No account, no telemetry, no upload — network
            access only happens when a tool inherently needs it (map tiles, geocoding,
            media download), always directly to the third party.
          </p>
          <div class="links">
            <a class="btn btn-sm" href={REPO_URL} target="_blank" rel="noreferrer">
              <Icon name="link" size={13} /> Source & issues <Icon name="external" size={11} />
            </a>
            <a class="btn btn-sm" href={SITE_URL} target="_blank" rel="noreferrer">
              <Icon name="globe" size={13} /> osintmethat.com <Icon name="external" size={11} />
            </a>
          </div>
        </section>

        <section class="group">
          <h3>Downloaders</h3>
          <p class="note">
            Media download leans on two projects that track sites as they change. They
            age faster than Azimut does — if a link stops resolving, update these first.
          </p>
          {#each scrapers as s (s.dist)}
            <div class="row">
              <div class="row-label">
                <span>{SCRAPER_LABELS[s.dist] ?? s.dist}</span>
                <span class="row-hint">
                  <span class="mono">{s.version || 'not installed'}</span>
                  {#if s.source === 'runtime'}
                    · updated in place{#if s.bundled_version}, shipped with {s.bundled_version}{/if}
                  {:else}
                    · as shipped
                  {/if}
                  {#if s.restart_required}
                    · <span class="stale">restart to apply</span>
                  {:else if s.outdated}
                    · <span class="stale">{s.latest} available</span>
                  {:else if s.latest}
                    · up to date
                  {/if}
                </span>
              </div>
              <div class="scraper-actions">
                {#if s.source === 'runtime'}
                  <button class="btn btn-sm" onclick={() => resetScraper(s.dist)}>Revert</button>
                {/if}
                <button
                  class="btn btn-sm"
                  class:btn-primary={s.outdated}
                  disabled={updating[s.dist]}
                  onclick={() => updateScraper(s.dist)}
                >
                  {updating[s.dist] ? 'Updating…' : 'Update'}
                </button>
              </div>
            </div>
          {/each}
          <div class="links">
            <button class="btn btn-sm" disabled={checking} onclick={checkScrapers}>
              <Icon name="download" size={13} />
              {checking ? 'Checking…' : 'Check for updates'}
            </button>
          </div>
          <p class="note">
            Checking and updating are the only things here that use the network, and only
            when you press them — the newest release is fetched from PyPI into your
            workspace, verified against the hash PyPI publishes, and used instead of the
            bundled copy. <strong>Revert</strong> goes back to the version this build
            shipped with, if an update ever makes things worse.
          </p>
        </section>
      {/if}
    </div>
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

  /* a preferences window, not a dashboard: a rail of sections on the left,
     one flat scrolling pane on the right — no cards, no boxes */
  .split {
    flex: 1;
    display: flex;
    min-height: 0;
  }
  .rail {
    width: 168px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 4px 8px 8px 12px;
    border-right: 1px solid var(--border);
  }
  .rail-tab {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 10px;
    border: 0;
    border-radius: var(--r-md);
    background: none;
    color: var(--text-2);
    font: inherit;
    font-size: var(--fs-sm);
    text-align: left;
    cursor: pointer;
    transition: background 0.12s var(--ease), color 0.12s var(--ease);
  }
  .rail-tab:hover {
    background: var(--bg-2);
    color: var(--text-1);
  }
  .rail-tab.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }

  .pane {
    flex: 1;
    overflow-y: auto;
    padding: 6px 18px 32px;
    max-width: 640px;
  }
  .group {
    padding: 14px 0 18px;
    border-bottom: 1px solid var(--border);
  }
  .group:last-child {
    border-bottom: 0;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: var(--fs-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-3);
    margin-bottom: 12px;
  }

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 8px;
  }
  .row-label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--fs-sm);
    color: var(--text-1);
  }
  .row-hint {
    color: var(--text-3);
    font-size: var(--fs-xs);
    line-height: 1.4;
  }
  .scraper-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  /* the one state worth pulling the eye: this downloader will fail on real links */
  .stale {
    color: var(--warn, var(--text-1));
    font-weight: 500;
  }
  .sig-side {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .sig-preview {
    /* checkerboard: a logo is meant to be transparent — show whether it is */
    max-width: 88px;
    max-height: 44px;
    padding: 4px;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background-color: var(--bg-2);
    background-image:
      linear-gradient(45deg, var(--bg-3) 25%, transparent 25% 75%, var(--bg-3) 75%),
      linear-gradient(45deg, var(--bg-3) 25%, transparent 25% 75%, var(--bg-3) 75%);
    background-size: 10px 10px;
    background-position: 0 0, 5px 5px;
  }
  .sig-buttons {
    display: flex;
    gap: 6px;
  }
  .sig-file {
    display: none;
  }

  /* segmented control — one row of mutually exclusive choices */
  .seg {
    display: flex;
    flex-shrink: 0;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    overflow: hidden;
  }
  .seg-btn {
    padding: 5px 12px;
    border: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-2);
    color: var(--text-2);
    font: inherit;
    font-size: var(--fs-xs);
    cursor: pointer;
    transition: background 0.12s var(--ease), color 0.12s var(--ease);
  }
  .seg-btn:first-child {
    border-left: 0;
  }
  .seg-btn:hover {
    background: var(--bg-3);
    color: var(--text-1);
  }
  .seg-btn.on {
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 600;
  }

  .sample {
    color: var(--text-2);
    font-size: var(--fs-sm);
    padding: 6px 9px;
    border-radius: var(--r-sm);
    background: var(--bg-2);
    border: 1px solid var(--border);
    display: inline-block;
    margin-top: 4px;
  }
  .note {
    color: var(--text-3);
    font-size: var(--fs-xs);
    line-height: 1.5;
    margin-top: 8px;
  }
  /* same voice as .note, but leading a group instead of trailing one */
  .intro {
    color: var(--text-3);
    font-size: var(--fs-xs);
    line-height: 1.5;
    margin: 0 0 14px;
  }

  .grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 90px;
    gap: 10px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    font-weight: 600;
  }
  .mention {
    width: 200px;
    flex-shrink: 0;
  }

  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 18px;
    margin: 0;
    font-size: var(--fs-sm);
  }
  .facts dt {
    color: var(--text-3);
    font-size: var(--fs-xs);
    align-self: center;
  }
  .facts dd {
    margin: 0;
    color: var(--text-1);
    overflow-wrap: anywhere;
  }
  .links {
    display: flex;
    gap: 8px;
    margin-top: 14px;
    flex-wrap: wrap;
  }
  .links .btn {
    gap: 6px;
    text-decoration: none;
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
