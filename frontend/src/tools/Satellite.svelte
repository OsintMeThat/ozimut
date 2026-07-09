<script>
  import { onMount, tick } from 'svelte';
  import L from 'leaflet';
  import 'leaflet/dist/leaflet.css';
  import { api } from '../lib/api.js';
  import { caseState, uiState, ensureCase, reloadCase, toast } from '../lib/state.svelte.js';
  import Icon from '../components/Icon.svelte';
  import Modal from '../components/Modal.svelte';

  let mapEl;
  let map;
  let tileLayer;
  let providers = $state([]);
  let providerId = $state('esri-world-imagery');
  let coordsText = $state('');
  let center = $state({ lat: 48.8584, lon: 2.2945, zoom: 16 });
  let size = $state('1000x700');
  let markerStyle = $state('crosshair'); // 'crosshair' | 'pin' | 'none'
  let moveMode = $state(false); // pin decoupled from center, draggable
  let marker = null; // Leaflet marker instance while in move mode
  let markerLatLng = $state(null); // {lat, lon} of the moved pin
  let bearing = $state(0);
  let capturing = $state(false);
  let captureHover = $state(false); // previewing the crop frame (capture group hover)
  let captures = $state([]);
  let capturesFor = $state(null);
  let capturesCollapsed = $state(false);
  let mapReady = $state(false);

  onMount(async () => {
    providers = await api.get('/api/satellite/providers');
    // leaflet-rotate patches the global L, so expose it before importing.
    window.L = L;
    await import('leaflet-rotate');
    map = L.map(mapEl, {
      center: [center.lat, center.lon],
      zoom: center.zoom,
      zoomControl: true,
      attributionControl: true,
      rotate: true,
      rotateControl: false,
      touchRotate: true,
      shiftKeyRotate: true,
    });
    setLayer();
    map.on('moveend zoomend', () => {
      const c = map.getCenter();
      center = { lat: c.lat, lon: c.lng, zoom: map.getZoom() };
    });
    map.on('rotate', () => {
      bearing = Math.round(map.getBearing());
    });
    mapReady = true;
    return () => map.remove();
  });

  function setLayer() {
    const p = providers.find((x) => x.id === providerId);
    if (!p || !map) return;
    if (tileLayer) tileLayer.remove();
    tileLayer = L.tileLayer(p.url, {
      attribution: p.attribution,
      maxZoom: p.max_zoom,
    }).addTo(map);
  }

  $effect(() => {
    providerId; // track provider changes
    setLayer();
  });

  $effect(() => {
    const id = caseState.current?.id;
    caseState.rev; // re-fetch when the case is reloaded elsewhere (e.g. sidebar delete)
    if (!id) {
      capturesFor = null;
      captures = [];
      return;
    }
    capturesFor = id;
    api.get(`/api/cases/${id}/satellite`).then((r) => (captures = r));
  });

  // the case sidebar mounts/unmounts outside this component — when it does,
  // the map container resizes, so redraw tiles for the newly exposed area
  $effect(() => {
    uiState.sidebarOpen; // track the global sidebar toggle
    if (!mapReady) return;
    tick().then(() => map?.invalidateSize());
  });

  // fly to coordinates handed off from the sidebar (place entity click) —
  // match the capture's own zoom/bearing, like clicking its card
  $effect(() => {
    const target = uiState.gotoCoords;
    if (mapReady && target && Number.isFinite(target.lat) && Number.isFinite(target.lon)) {
      uiState.gotoCoords = null;
      const zoom = Number.isFinite(target.zoom) ? target.zoom : Math.max(map.getZoom(), 16);
      map.setView([target.lat, target.lon], zoom);
      setBearing(Number.isFinite(target.bearing) ? target.bearing : 0);
    }
  });

  async function goTo() {
    const text = coordsText.trim();
    if (!text) return;
    try {
      const parsed = await api.post('/api/geo/parse', { text });
      map.setView([parsed.lat, parsed.lon], Math.max(map.getZoom(), 16));
    } catch {
      toast('Could not parse coordinates — try "50.4501, 30.5234" or DMS', 'danger');
    }
  }

  function setBearing(deg) {
    if (!map) return;
    map.setBearing(((deg % 360) + 360) % 360);
  }

  function nudgeBearing(delta) {
    setBearing(bearing + delta);
  }

  function resetNorth() {
    setBearing(0);
  }

  // --- marker (crosshair / pin), optionally decoupled from center ---

  // the coordinates shown & recorded: the moved pin, else the crop center
  const displayCoords = $derived(
    moveMode && markerLatLng ? markerLatLng : { lat: center.lat, lon: center.lon }
  );

  // crop dimensions in px — drawn as the capture-frame outline
  const frameSize = $derived(size.split('x').map(Number));

  function markerIcon(style) {
    if (style === 'pin') {
      return L.divIcon({
        className: 'sat-marker',
        iconSize: [30, 42],
        iconAnchor: [15, 42], // tip points at the location
        html: `<svg width="30" height="42" viewBox="0 0 30 42">
          <path d="M15 41 C15 41 27 24 27 14 A12 12 0 1 0 3 14 C3 24 15 41 15 41 Z"
            fill="#e5484d" stroke="#3c0c0e" stroke-width="1.5"/>
          <circle cx="15" cy="14" r="4.5" fill="#fff" stroke="#3c0c0e" stroke-width="1"/>
        </svg>`,
      });
    }
    return L.divIcon({
      className: 'sat-marker',
      iconSize: [46, 46],
      iconAnchor: [23, 23],
      html: `<svg width="46" height="46" viewBox="0 0 46 46">
        <g stroke="#000" stroke-width="4" opacity="0.55">
          <line x1="1" y1="23" x2="16" y2="23"/><line x1="30" y1="23" x2="45" y2="23"/>
          <line x1="23" y1="1" x2="23" y2="16"/><line x1="23" y1="30" x2="23" y2="45"/>
        </g>
        <g stroke="#fff" stroke-width="2">
          <line x1="1" y1="23" x2="16" y2="23"/><line x1="30" y1="23" x2="45" y2="23"/>
          <line x1="23" y1="1" x2="23" y2="16"/><line x1="23" y1="30" x2="23" y2="45"/>
          <circle cx="23" cy="23" r="2.5" fill="none"/>
        </g>
      </svg>`,
    });
  }

  function removeMarker() {
    if (marker) marker.remove();
    marker = null;
    markerLatLng = null;
  }

  function toggleMoveMode() {
    if (markerStyle === 'none') return;
    moveMode = !moveMode;
    if (!moveMode) {
      removeMarker();
      return;
    }
    const c = map.getCenter();
    marker = L.marker(c, {
      draggable: true,
      icon: markerIcon(markerStyle),
      zIndexOffset: 1000,
    }).addTo(map);
    markerLatLng = { lat: c.lat, lon: c.lng };
    marker.on('drag move', () => {
      const p = marker.getLatLng();
      markerLatLng = { lat: p.lat, lon: p.lng };
    });
  }

  // keep the live marker's look in sync with the chosen style; leaving move
  // mode (or picking "none") drops the marker
  $effect(() => {
    if (markerStyle === 'none' && moveMode) {
      moveMode = false;
      removeMarker();
    } else if (marker) {
      marker.setIcon(markerIcon(markerStyle));
    }
  });

  async function captureCrop() {
    if (capturing) return;
    capturing = true;
    const [width, height] = size.split('x').map(Number);
    // marker offset (px from crop center) + its coordinates; when the pin has
    // been moved, its container offset already accounts for map rotation
    let marker_x = 0, marker_y = 0;
    let marker_lat = center.lat, marker_lon = center.lon;
    if (moveMode && marker) {
      const ll = marker.getLatLng();
      marker_lat = ll.lat;
      marker_lon = ll.lng;
      const mapSize = map.getSize();
      const p = map.latLngToContainerPoint(ll);
      marker_x = Math.round(p.x - mapSize.x / 2);
      marker_y = Math.round(p.y - mapSize.y / 2);
    }
    try {
      const c = await ensureCase();
      const result = await api.post(`/api/cases/${c.id}/satellite/capture`, {
        lat: center.lat,
        lon: center.lon,
        zoom: center.zoom,
        width,
        height,
        provider: providerId,
        bearing,
        marker_style: markerStyle,
        marker_x,
        marker_y,
        marker_lat,
        marker_lon,
      });
      captures = [result, ...captures];
      await reloadCase();
      toast(
        result.tiles_missing
          ? `Captured with ${result.tiles_missing} missing tile(s) — no imagery there`
          : 'Satellite crop captured & filed',
        result.tiles_missing ? 'warn' : 'ok'
      );
    } catch (e) {
      toast(`Capture failed: ${e.message}`, 'danger', 6000);
    } finally {
      capturing = false;
    }
  }

  // save just the point (pin if moved, else center) as a navigable place — no image
  let savingPlace = $state(false);
  async function savePlace() {
    if (savingPlace) return;
    savingPlace = true;
    try {
      const c = await ensureCase();
      await api.post(`/api/cases/${c.id}/satellite/place`, {
        lat: displayCoords.lat,
        lon: displayCoords.lon,
        zoom: center.zoom,
        bearing,
      });
      await reloadCase();
      toast('Place saved — find it in the case sidebar', 'ok');
    } catch (e) {
      toast(`Could not save place: ${e.message}`, 'danger', 6000);
    } finally {
      savingPlace = false;
    }
  }

  async function removeCapture(item) {
    await api.del(
      `/api/cases/${caseState.current.id}/satellite?path=${encodeURIComponent(item.path)}`
    );
    captures = captures.filter((c) => c.path !== item.path);
    // the capture's place entity may have gone with it — refresh the sidebar
    await reloadCase();
  }

  // --- details modal (title + notes) ---
  let notesItem = $state(null);
  let notesText = $state('');
  let notesTitle = $state('');
  let notesSaving = $state(false);

  function openNotes(item) {
    notesItem = item;
    notesText = item.notes ?? '';
    notesTitle = item.title ?? coordsLabel(item);
  }

  async function saveNotes() {
    if (!notesItem) return;
    notesSaving = true;
    try {
      const updated = await api.patch(
        `/api/cases/${caseState.current.id}/satellite`,
        { path: notesItem.path, notes: notesText, title: notesTitle }
      );
      const idx = captures.findIndex((c) => c.path === notesItem.path);
      if (idx !== -1) captures[idx] = updated;
      notesItem = null;
      // the mirrored place entity was retitled too — refresh the sidebar
      await reloadCase();
      toast('Saved', 'ok', 1600);
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      notesSaving = false;
    }
  }

  function coordsLabel(item) {
    return `${item.lat.toFixed(6)}, ${item.lon.toFixed(6)}`;
  }

  function sendToComposer(item) {
    if (!uiState.composeQueue.includes(item.path)) uiState.composeQueue.push(item.path);
    uiState.tool = 'proof';
  }

  function fmt(value) {
    return value.toFixed(6);
  }

  async function copyCoords() {
    await navigator.clipboard.writeText(`${fmt(displayCoords.lat)}, ${fmt(displayCoords.lon)}`);
    toast('Coordinates copied', 'ok', 1600);
  }

  async function toggleCaptures() {
    capturesCollapsed = !capturesCollapsed;
    // the map container just resized — let Leaflet redraw tiles for the new size
    await tick();
    map?.invalidateSize();
  }

  // saved places (navigable points) live on the case as `place` entities
  const places = $derived(
    (caseState.current?.entities ?? []).filter((e) => e.type === 'place')
  );

  function flyToPlace(p) {
    const lat = Number(p.attrs?.lat);
    const lon = Number(p.attrs?.lon);
    if (!map || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
    map.setView([lat, lon], Number(p.attrs?.zoom) || map.getZoom());
    setBearing(Number(p.attrs?.bearing) || 0);
  }

  async function removePlace(p) {
    await api.del(`/api/cases/${caseState.current.id}/entities/${p.id}`);
    await reloadCase();
  }

  // collapse state for the two saved-work sections
  let placesCollapsed = $state(false);
  let capturesSubCollapsed = $state(false);

  // --- place edit modal (title + notes), used for both save & later edits ---
  // { id: string|null, title, notes, lat, lon, zoom, bearing }; id null = new
  let placeModal = $state(null);
  let placeSaving = $state(false);

  function openNewPlace() {
    placeModal = {
      id: null,
      title: '',
      notes: '',
      lat: displayCoords.lat,
      lon: displayCoords.lon,
      zoom: center.zoom,
      bearing,
    };
  }

  function openEditPlace(p) {
    placeModal = {
      id: p.id,
      title: p.label ?? '',
      notes: p.attrs?.notes ?? '',
      lat: Number(p.attrs?.lat),
      lon: Number(p.attrs?.lon),
      zoom: p.attrs?.zoom,
      bearing: p.attrs?.bearing,
    };
  }

  function placeCoordsLabel(m) {
    return `${m.lat.toFixed(6)}, ${m.lon.toFixed(6)}`;
  }

  async function savePlaceModal() {
    if (!placeModal || placeSaving) return;
    placeSaving = true;
    try {
      const m = placeModal;
      if (m.id) {
        // edit existing place: retitle + set/clear the note
        const title = m.title.trim() || placeCoordsLabel(m);
        await api.patch(`/api/cases/${caseState.current.id}/entities/${m.id}`, {
          label: title,
          attrs: { notes: m.notes.trim() },
        });
      } else {
        const c = await ensureCase();
        await api.post(`/api/cases/${c.id}/satellite/place`, {
          lat: m.lat,
          lon: m.lon,
          zoom: m.zoom,
          bearing: m.bearing,
          title: m.title,
          notes: m.notes,
        });
      }
      placeModal = null;
      await reloadCase();
      toast('Place saved', 'ok', 1600);
    } catch (e) {
      toast(`Could not save place: ${e.message}`, 'danger', 6000);
    } finally {
      placeSaving = false;
    }
  }
</script>

<div class="tool">
  <div class="tool-header">
    <h2>Satellite</h2>
    <span class="sub">pan to a point, capture a sourced imagery crop</span>
    <div class="spacer"></div>
    <form
      class="go-form"
      onsubmit={(e) => {
        e.preventDefault();
        goTo();
      }}
    >
      <input
        class="input"
        placeholder={'50.4501, 30.5234  ·  48°51\'29"N 2°17\'40"E'}
        bind:value={coordsText}
      />
      <button type="submit" class="btn" disabled={!coordsText.trim()}>
        <Icon name="search" size={15} /> Go
      </button>
    </form>
  </div>

  <div class="body">
    <div class="map-wrap">
      <div class="map" bind:this={mapEl}></div>

      <!-- capture-frame outline: what the crop will cover — only while a capture
           is the intent (hovering the capture group, or mid-capture) -->
      {#if captureHover || capturing}
        <div
          class="frame-overlay"
          style="width:{frameSize[0]}px;height:{frameSize[1]}px"
          aria-hidden="true"
        ></div>
      {/if}

      <!-- fixed center marker; a draggable Leaflet marker takes over in move mode -->
      {#if markerStyle !== 'none' && !moveMode}
        <div class="marker-overlay marker-{markerStyle}" aria-hidden="true">
          {#if markerStyle === 'pin'}
            <svg width="30" height="42" viewBox="0 0 30 42">
              <path
                d="M15 41 C15 41 27 24 27 14 A12 12 0 1 0 3 14 C3 24 15 41 15 41 Z"
                fill="#e5484d" stroke="#3c0c0e" stroke-width="1.5"
              />
              <circle cx="15" cy="14" r="4.5" fill="#fff" stroke="#3c0c0e" stroke-width="1" />
            </svg>
          {:else}
            <svg width="46" height="46" viewBox="0 0 46 46">
              <g stroke="#000" stroke-width="4" opacity="0.55">
                <line x1="1" y1="23" x2="16" y2="23" /><line x1="30" y1="23" x2="45" y2="23" />
                <line x1="23" y1="1" x2="23" y2="16" /><line x1="23" y1="30" x2="23" y2="45" />
              </g>
              <g stroke="#fff" stroke-width="2">
                <line x1="1" y1="23" x2="16" y2="23" /><line x1="30" y1="23" x2="45" y2="23" />
                <line x1="23" y1="1" x2="23" y2="16" /><line x1="23" y1="30" x2="23" y2="45" />
                <circle cx="23" cy="23" r="2.5" fill="none" />
              </g>
            </svg>
          {/if}
        </div>
      {/if}

      <div class="hud card">
        <button class="hud-coords mono" onclick={copyCoords} title="Copy coordinates">
          <Icon name="crosshair" size={13} />
          {fmt(displayCoords.lat)}, {fmt(displayCoords.lon)}
          <span class="z">z{center.zoom}</span>
          {#if moveMode && markerLatLng}<span class="pin-tag">pin</span>{/if}
          <Icon name="copy" size={12} />
        </button>
      </div>

      <div class="rotate-ctl card">
        <button
          class="compass"
          onclick={resetNorth}
          title={bearing ? 'Reset to north' : 'North up'}
          aria-label="Reset to north"
        >
          <svg width="34" height="34" viewBox="0 0 34 34" style="transform: rotate({-bearing}deg)">
            <circle cx="17" cy="17" r="15" fill="none" stroke="currentColor" stroke-width="1" opacity="0.4" />
            <polygon points="17,4 13,18 17,15 21,18" fill="#e5484d" />
            <polygon points="17,30 13,16 17,19 21,16" fill="#8a93a5" />
          </svg>
          <span class="n">N</span>
        </button>
        <div class="rotate-actions">
          <button class="rbtn" onclick={() => nudgeBearing(-15)} title="Rotate left 15°" aria-label="Rotate left">
            <Icon name="chevronLeft" size={15} />
          </button>
          <span class="deg mono">{bearing}°</span>
          <button class="rbtn" onclick={() => nudgeBearing(15)} title="Rotate right 15°" aria-label="Rotate right">
            <Icon name="chevronRight" size={15} />
          </button>
        </div>
        <input
          class="rotate-slider"
          type="range"
          min="0"
          max="359"
          value={bearing}
          oninput={(e) => setBearing(+e.target.value)}
          title="Drag to rotate the view"
          aria-label="Map rotation"
        />
      </div>

      <div class="capture-bar card">
        <select class="select" bind:value={providerId} title="Imagery provider">
          {#each providers as p (p.id)}
            <option value={p.id} disabled={p.needs_key}>
              {p.label}{p.needs_key ? ' (needs API key)' : ''}
            </option>
          {/each}
        </select>
        <select class="select" bind:value={markerStyle} title="Marker style">
          <option value="crosshair">✛ crosshair</option>
          <option value="pin">📍 pin</option>
          <option value="none">no marker</option>
        </select>
        <button
          class="btn btn-toggle"
          class:on={moveMode}
          onclick={toggleMoveMode}
          disabled={markerStyle === 'none'}
          title="Move the marker off-center — recorded coordinates follow the pin"
        >
          <Icon name="crosshair" size={14} /> {moveMode ? 'Moving' : 'Move pin'}
        </button>
        <span class="bar-sep" aria-hidden="true"></span>
        <div class="place-save">
          <button
            class="btn place-save-main"
            onclick={savePlace}
            disabled={savingPlace}
            title="Save just this point (the pin, or the crop center) as a navigable place — no image"
          >
            <Icon name="pin" size={15} /> {savingPlace ? 'Saving…' : 'Save place'}
          </button>
          <button
            class="btn place-save-edit"
            onclick={openNewPlace}
            title="Save place with a title and note…"
            aria-label="Save place with a title and note"
          >
            <Icon name="note" size={14} />
          </button>
        </div>
        <!-- crop size only concerns a capture, so it lives with the Capture button;
             hovering this group previews the crop frame on the map -->
        <div
          class="capture-group"
          onmouseenter={() => (captureHover = true)}
          onmouseleave={() => (captureHover = false)}
          onfocusin={() => (captureHover = true)}
          onfocusout={() => (captureHover = false)}
          role="group"
        >
          <select class="select" bind:value={size} title="Crop size">
            <option value="800x600">800 × 600</option>
            <option value="1000x700">1000 × 700</option>
            <option value="1280x800">1280 × 800</option>
            <option value="1000x1000">1000 × 1000</option>
          </select>
          <button class="btn btn-primary" onclick={captureCrop} disabled={capturing}>
            {#if capturing}
              <span class="spinner"></span> Capturing…
            {:else}
              <Icon name="satellite" size={15} /> Capture
            {/if}
          </button>
        </div>
      </div>
    </div>

    <aside class="captures" class:collapsed={capturesCollapsed}>
      <button
        type="button"
        class="cap-head"
        onclick={toggleCaptures}
        title={capturesCollapsed ? 'Show captures' : 'Hide captures'}
      >
        <Icon name={capturesCollapsed ? 'chevronLeft' : 'chevronRight'} size={15} />
        <span class="label" style="margin:0">Saved</span>
        <span class="count">{places.length + captures.length}</span>
      </button>
      {#if capturesCollapsed}
        <!-- collapsed: header acts as the toggle back to the list -->
      {:else}
        <div class="panel-scroll">
          <!-- Places: navigable points (no image) -->
          <button
            type="button"
            class="sub-head"
            onclick={() => (placesCollapsed = !placesCollapsed)}
          >
            <Icon name={placesCollapsed ? 'chevronRight' : 'chevronDown'} size={12} />
            <Icon name="pin" size={13} />
            <span>Places</span>
            <span class="count">{places.length}</span>
          </button>
          {#if !placesCollapsed}
            {#if !places.length}
              <div class="none">Use “Save place” to drop a point you can fly back to.</div>
            {:else}
              <div class="place-list">
                {#each places as p (p.id)}
                  <div class="place-row card fade-up">
                    <div class="place-main">
                      <button
                        type="button"
                        class="place-goto"
                        title="Fly the map to this point"
                        onclick={() => flyToPlace(p)}
                      >
                        <Icon name="pin" size={15} />
                        <div class="place-meta">
                          <span class="title">{p.label}</span>
                          <span class="prov">
                            z{p.attrs?.zoom}{p.attrs?.bearing ? ` · ${Math.round(p.attrs.bearing)}°` : ''}
                          </span>
                        </div>
                      </button>
                      <button
                        class="btn btn-ghost btn-sm"
                        title="Edit title & note"
                        onclick={() => openEditPlace(p)}
                      >
                        <Icon name="note" size={14} />
                      </button>
                      <button
                        class="btn btn-ghost btn-sm"
                        title="Delete place"
                        onclick={() => removePlace(p)}
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </div>
                    {#if p.attrs?.notes}
                      <div class="place-notes">{p.attrs.notes}</div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          {/if}

          <!-- Captures: sourced imagery crops (images) -->
          <button
            type="button"
            class="sub-head"
            onclick={() => (capturesSubCollapsed = !capturesSubCollapsed)}
          >
            <Icon name={capturesSubCollapsed ? 'chevronRight' : 'chevronDown'} size={12} />
            <Icon name="satellite" size={13} />
            <span>Captures</span>
            <span class="count">{captures.length}</span>
          </button>
          {#if !capturesSubCollapsed}
            {#if !captures.length}
              <div class="none">
                Captured crops land in the case with full provenance: provider, zoom, date,
                attribution.
              </div>
            {:else}
              <div class="cap-list">
              {#each captures as item (item.path)}
                <div class="cap card fade-up">
                  <a
                    class="cap-goto"
                    href={`/files/${caseState.current.id}/${item.path}`}
                    target="_blank"
                    rel="noreferrer"
                    title="Open the full image"
                  >
                    <img
                      src={`/files/${caseState.current.id}/${item.path}`}
                      alt={item.filename}
                      loading="lazy"
                    />
                    <div class="cap-meta">
                      <span class="title">{item.title ?? coordsLabel(item)}</span>
                      <span class="mono coords">{coordsLabel(item)}</span>
                      <span class="prov">z{item.zoom}{item.bearing ? ` · ${Math.round(item.bearing)}°` : ''} · {item.provider_label} · {item.fetched_at?.slice(0, 10)}</span>
                    </div>
                  </a>
                  <div class="cap-actions">
                    <button
                      class="btn btn-ghost btn-sm"
                      title="Edit title & note"
                      onclick={() => openNotes(item)}
                    >
                      <Icon name="note" size={14} />
                    </button>
                    <button
                      class="btn btn-ghost btn-sm"
                      title="Send to Proof Composer"
                      onclick={() => sendToComposer(item)}
                    >
                      <Icon name="proof" size={14} />
                    </button>
                    <a
                      class="btn btn-ghost btn-sm"
                      href={`/files/${caseState.current.id}/${item.path}`}
                      target="_blank"
                      rel="noreferrer"
                      title="Open"
                    >
                      <Icon name="external" size={14} />
                    </a>
                    <button
                      class="btn btn-ghost btn-sm"
                      title="Delete"
                      onclick={() => removeCapture(item)}
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                  {#if item.notes}
                    <div class="cap-notes">{item.notes}</div>
                  {/if}
                </div>
              {/each}
              </div>
            {/if}
          {/if}
        </div>
      {/if}
    </aside>
  </div>
</div>

<!-- satellite notes modal -->
{#if notesItem}
  <Modal title="Capture details" onclose={() => (notesItem = null)} width="420px">
    <label style="display:block;font-size:var(--fs-xs);color:var(--text-3);margin-bottom:5px">Title</label>
    <input
      class="input"
      placeholder={coordsLabel(notesItem)}
      bind:value={notesTitle}
    />
    <hr style="border:none;border-top:1px solid var(--border);margin:12px 0" />
    <div class="sat-info-rows">
      <div class="sat-info-row">
        <span class="sat-info-label">Coordinates</span>
        <span class="mono">{notesItem.lat?.toFixed(6)}, {notesItem.lon?.toFixed(6)}</span>
      </div>
      <div class="sat-info-row">
        <span class="sat-info-label">Provider</span>
        <span>{notesItem.provider_label}</span>
      </div>
      <div class="sat-info-row">
        <span class="sat-info-label">Zoom</span>
        <span>{notesItem.zoom}</span>
      </div>
      <div class="sat-info-row">
        <span class="sat-info-label">Date</span>
        <span class="mono">{notesItem.fetched_at?.slice(0, 10)}</span>
      </div>
    </div>
    <hr style="border:none;border-top:1px solid var(--border);margin:12px 0" />
    <label style="display:block;font-size:var(--fs-xs);color:var(--text-3);margin-bottom:5px">Notes</label>
    <textarea
      class="textarea"
      rows="5"
      placeholder="Add observations, links, context…"
      bind:value={notesText}
    ></textarea>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
      <button class="btn" onclick={() => (notesItem = null)}>Cancel</button>
      <button class="btn btn-primary" onclick={saveNotes} disabled={notesSaving}>
        {notesSaving ? 'Saving…' : 'Save'}
      </button>
    </div>
  </Modal>
{/if}

<!-- place edit / save-with-details modal -->
{#if placeModal}
  <Modal
    title={placeModal.id ? 'Edit place' : 'Save place'}
    onclose={() => (placeModal = null)}
    width="420px"
  >
    <label style="display:block;font-size:var(--fs-xs);color:var(--text-3);margin-bottom:5px">Title</label>
    <input
      class="input"
      placeholder={placeCoordsLabel(placeModal)}
      bind:value={placeModal.title}
    />
    <hr style="border:none;border-top:1px solid var(--border);margin:12px 0" />
    <div class="sat-info-rows">
      <div class="sat-info-row">
        <span class="sat-info-label">Coordinates</span>
        <span class="mono">{placeCoordsLabel(placeModal)}</span>
      </div>
      <div class="sat-info-row">
        <span class="sat-info-label">Zoom</span>
        <span>z{placeModal.zoom}{placeModal.bearing ? ` · ${Math.round(placeModal.bearing)}°` : ''}</span>
      </div>
    </div>
    <hr style="border:none;border-top:1px solid var(--border);margin:12px 0" />
    <label style="display:block;font-size:var(--fs-xs);color:var(--text-3);margin-bottom:5px">Notes</label>
    <textarea
      class="textarea"
      rows="5"
      placeholder="Add observations, links, context…"
      bind:value={placeModal.notes}
    ></textarea>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
      <button class="btn" onclick={() => (placeModal = null)}>Cancel</button>
      <button class="btn btn-primary" onclick={savePlaceModal} disabled={placeSaving}>
        {placeSaving ? 'Saving…' : 'Save'}
      </button>
    </div>
  </Modal>
{/if}

<style>
  .spacer {
    flex: 1;
  }
  .go-form {
    display: flex;
    gap: 8px;
    width: min(420px, 36vw);
  }
  .body {
    flex: 1;
    display: flex;
    min-height: 0;
  }
  .map-wrap {
    position: relative;
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  .map {
    position: absolute;
    inset: 0;
    background: var(--bg-2);
  }
  .frame-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    border: 1px dashed rgba(255, 255, 255, 0.55);
    box-shadow: 0 0 0 100vmax rgba(8, 11, 18, 0.28);
    pointer-events: none;
    z-index: 450;
  }
  .marker-overlay {
    position: absolute;
    top: 50%;
    left: 50%;
    pointer-events: none;
    z-index: 500;
  }
  .marker-crosshair {
    transform: translate(-50%, -50%);
  }
  .marker-pin {
    /* tip of the pin sits on the point */
    transform: translate(-50%, -100%);
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.5));
  }
  :global(.sat-marker) {
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.5));
  }
  .pin-tag {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--accent-text, #fff);
    background: var(--accent);
    border-radius: 3px;
    padding: 1px 4px;
  }
  .hud {
    position: absolute;
    top: 12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 600;
    background: rgba(16, 22, 35, 0.88);
    backdrop-filter: blur(6px);
  }
  .hud-coords {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 13px;
    font-size: var(--fs-sm);
    color: var(--text-1);
  }
  .hud-coords:hover {
    color: var(--accent);
  }
  .z {
    color: var(--text-3);
    font-size: var(--fs-xs);
  }
  .rotate-ctl {
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 600;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 10px;
    background: rgba(16, 22, 35, 0.88);
    backdrop-filter: blur(6px);
    box-shadow: var(--shadow-2);
  }
  .compass {
    position: relative;
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    color: var(--text-2);
    cursor: pointer;
  }
  .compass:hover {
    color: var(--accent);
  }
  .compass svg {
    transition: transform 0.1s linear;
  }
  .compass .n {
    position: absolute;
    top: -3px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    font-weight: 700;
    color: var(--text-3);
    pointer-events: none;
  }
  .rotate-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .rbtn {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border: 1px solid var(--border);
    border-radius: var(--radius-1);
    background: var(--bg-2);
    color: var(--text-2);
    cursor: pointer;
  }
  .rbtn:hover {
    color: var(--accent);
    border-color: var(--accent);
  }
  .deg {
    min-width: 36px;
    text-align: center;
    font-size: var(--fs-xs);
    color: var(--text-1);
  }
  .rotate-slider {
    width: 108px;
    accent-color: var(--accent);
    cursor: pointer;
  }
  .capture-bar {
    position: absolute;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 600;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: rgba(16, 22, 35, 0.92);
    backdrop-filter: blur(6px);
    box-shadow: var(--shadow-2);
  }
  .capture-bar .select {
    width: auto;
  }
  .bar-sep {
    width: 1px;
    align-self: stretch;
    background: var(--border);
    margin: 0 2px;
  }
  .capture-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .place-save {
    display: flex;
    align-items: stretch;
  }
  .place-save-main {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
  }
  .place-save-edit {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: none;
    padding-left: 8px;
    padding-right: 8px;
  }
  .btn-toggle {
    white-space: nowrap;
  }
  .btn-toggle.on {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  .spinner {
    width: 13px;
    height: 13px;
    border: 2px solid var(--accent-text);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .captures {
    width: 300px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-1);
    display: flex;
    flex-direction: column;
  }
  .captures.collapsed {
    width: 42px;
  }
  .cap-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 14px 14px 8px;
    width: 100%;
    background: none;
    border: none;
    color: var(--text-1);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .cap-head:hover {
    color: var(--accent);
  }
  .captures.collapsed .cap-head {
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    padding: 14px 0;
    height: 100%;
  }
  .captures.collapsed .cap-head .label {
    writing-mode: vertical-rl;
  }
  .count {
    font-size: var(--fs-xs);
    color: var(--text-3);
    font-weight: 600;
  }
  .none {
    padding: 8px 14px;
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .panel-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 4px 12px 12px;
    display: flex;
    flex-direction: column;
  }
  .sub-head {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 12px 2px 6px;
    background: none;
    border: none;
    font: inherit;
    font-size: var(--fs-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-2);
    text-align: left;
    cursor: pointer;
  }
  .sub-head:hover {
    color: var(--accent);
  }
  .sub-head .count {
    margin-left: auto;
    text-transform: none;
  }
  .place-notes {
    padding: 0 10px 8px 30px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    font-style: italic;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .place-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .place-row {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .place-main {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 6px 4px 4px;
  }
  .place-goto {
    display: flex;
    align-items: center;
    gap: 9px;
    flex: 1;
    min-width: 0;
    padding: 5px 6px;
    background: none;
    border: none;
    color: var(--text-2);
    text-align: left;
    cursor: pointer;
  }
  .place-goto:hover,
  .place-goto:hover .title {
    color: var(--accent);
  }
  .place-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .cap-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .cap {
    overflow: hidden;
    flex-shrink: 0;
  }
  .cap-goto {
    display: block;
    width: 100%;
    padding: 0;
    background: none;
    border: none;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }
  .cap img {
    width: 100%;
    aspect-ratio: 10 / 7;
    object-fit: cover;
    background: var(--bg-2);
  }
  .cap-goto:hover img {
    opacity: 0.9;
  }
  .cap-goto:hover .coords {
    color: var(--accent);
  }
  .cap-meta {
    padding: 8px 10px 2px;
    display: flex;
    flex-direction: column;
  }
  .title {
    font-size: var(--fs-sm);
    color: var(--text-1);
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .coords {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .cap-goto:hover .title {
    color: var(--accent);
  }
  .prov {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .cap-actions {
    display: flex;
    gap: 2px;
    padding: 4px 6px 6px;
  }
  .cap-notes {
    padding: 0 10px 8px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    font-style: italic;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .sat-info-rows {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sat-info-row {
    display: flex;
    gap: 10px;
    font-size: var(--fs-sm);
    align-items: baseline;
  }
  .sat-info-label {
    color: var(--text-3);
    font-size: var(--fs-xs);
    min-width: 80px;
    flex-shrink: 0;
  }

  /* Leaflet dark-theme adjustments */
  :global(.leaflet-container) {
    font-family: var(--font-sans);
    background: var(--bg-2);
  }
  :global(.leaflet-control-attribution) {
    background: rgba(16, 22, 35, 0.85) !important;
    color: var(--text-3) !important;
    font-size: 10px;
  }
  :global(.leaflet-control-attribution a) {
    color: var(--text-2) !important;
  }
  :global(.leaflet-bar a) {
    background: var(--bg-2) !important;
    color: var(--text-1) !important;
    border-color: var(--border) !important;
  }
  :global(.leaflet-bar a:hover) {
    background: var(--bg-3) !important;
  }
</style>
