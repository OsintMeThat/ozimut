<script>
  import { api } from '../lib/api.js';
  import { caseState, uiState, reloadCase, toast } from '../lib/state.svelte.js';
  import {
    adjustDefaults, buildOps, previewStyle, isNeutral, uid, videoSeed, initialQuad, VIDEO_ADJUST_IDS,
  } from '../lib/inspect.js';
  import Icon from '../components/Icon.svelte';
  import SelectionMenu from './inspect/SelectionMenu.svelte';
  import FrameMenu from './inspect/FrameMenu.svelte';
  import CollageCanvas from './inspect/CollageCanvas.svelte';
  import CollageMenu from './inspect/CollageMenu.svelte';
  import SaveGallery from './inspect/SaveGallery.svelte';
  import SaveMenu from './inspect/SaveMenu.svelte';

  // The Inspect tool is a *scratch workspace*. Opening a photo/video starts a
  // session; captured frames, per-frame adjustments, video tuning and a collage
  // layout all live here as plain data. Nothing becomes case media until the Save
  // tab commits it — the recipes are re-derived full-res on the backend then.
  const TAB_META = {
    selection: { label: 'Selection', icon: 'video' },
    frame: { label: 'Frame', icon: 'image' },
    collage: { label: 'Collage', icon: 'layers' },
    save: { label: 'Save', icon: 'save' },
  };

  let mediaList = $state([]);
  let loadedFor = $state(null);
  let filters = $state([]);
  let analyses = $state([]);
  let probeInfo = $state(null);

  let activeTab = $state('selection');
  let collageSelectedId = $state(null);
  let saving = $state(false);
  const saveUi = $state({ selected: {}, folder: '' });
  // the saved session this workspace came from (if any) — re-saving overwrites it
  // in place instead of forking a new named session.
  let openedSession = $state(null);
  const sessionModal = $state({ open: false, mode: 'save', name: null, title: '', list: [], busy: false });

  // the live session (reset on source / case change)
  const session = $state({
    source: null,
    videoAdjust: {},
    frames: [],
    activeFrameId: null,
    collage: { width: 1600, height: 800, background: '#12141c', transparent: false, nodes: [] },
    saved: {},
  });

  // viewer bridge (video seek + crop overlay), mirrors the old shared object
  const shared = $state({ currentTime: 0, seekTo: null, cropMode: false });
  let videoEl = $state();
  let cropDraw = $state(null);

  const videoFilters = $derived(filters.filter((f) => VIDEO_ADJUST_IDS.includes(f.id)));
  const tabs = $derived(
    session.source?.kind === 'video' ? ['selection', 'frame', 'collage', 'save'] : ['frame', 'collage', 'save']
  );
  const activeFrame = $derived(session.frames.find((f) => f.id === session.activeFrameId) ?? null);
  const framePreview = $derived(activeFrame ? previewStyle(filters, activeFrame.adjust) : { filter: '', transform: '' });
  const videoPreview = $derived(previewStyle(videoFilters, session.videoAdjust));

  const savables = $derived.by(() => {
    const out = [];
    const cid = caseState.current?.id;
    if (session.source?.kind === 'video' && !isNeutral(videoFilters, session.videoAdjust)) {
      const t = session.source.thumbnail ? `/files/${cid}/${session.source.thumbnail}` : null;
      out.push({ key: 'video', kind: 'video', label: 'Video 1', thumb: t, saved: !!session.saved.video });
    }
    let imgN = 0;
    for (const fr of session.frames) {
      imgN += 1;
      out.push({
        key: `frame:${fr.id}`, kind: 'frame', frame: fr, thumb: fr.url,
        label: `Image ${imgN}`, filter: previewStyle(filters, fr.adjust).filter,
        saved: !!session.saved[`frame:${fr.id}`],
      });
    }
    if (session.collage.nodes.length) {
      out.push({
        key: 'collage', kind: 'collage', label: 'Collage 1',
        thumb: null, collage: session.collage, saved: !!session.saved.collage,
      });
    }
    return out;
  });

  // -- lifecycle ------------------------------------------------------------
  $effect(() => {
    const id = caseState.current?.id;
    if (id !== loadedFor) {
      loadedFor = id;
      mediaList = [];
      resetSession();
      if (id) refresh(id);
    }
  });

  $effect(() => {
    if (uiState.tool === 'inspect' && uiState.inspectPath && mediaList.length) {
      const target = mediaList.find((m) => m.path === uiState.inspectPath);
      uiState.inspectPath = null;
      if (target) select(target);
    }
  });

  // reopen a saved session from the sidebar (like proofs/posts)
  $effect(() => {
    if (uiState.tool === 'inspect' && uiState.openInspect && mediaList.length) {
      const name = uiState.openInspect;
      uiState.openInspect = null;
      openSession(name);
    }
  });

  $effect(() => {
    if (shared.seekTo != null && videoEl) {
      videoEl.currentTime = shared.seekTo;
      shared.seekTo = null;
    }
  });

  async function ensureOps() {
    if (filters.length) return;
    const ops = await api.get('/api/inspect/ops');
    filters = ops.filters.filter((f) => f.id !== 'crop');
    analyses = ops.analyses;
  }

  async function refresh(id = caseState.current?.id) {
    if (!id) return;
    mediaList = await api.get(`/api/cases/${id}/media`);
  }

  function resetSession() {
    for (const fr of session.frames) if (fr.url?.startsWith('blob:')) URL.revokeObjectURL(fr.url);
    session.source = null;
    session.videoAdjust = {};
    session.frames = [];
    session.activeFrameId = null;
    session.collage = { width: 1600, height: 800, background: '#12141c', transparent: false, nodes: [] };
    session.saved = {};
    saveUi.selected = {};
    saveUi.folder = '';
    openedSession = null;
    collageSelectedId = null;
    shared.currentTime = 0;
    shared.cropMode = false;
    cropDraw = null;
  }

  async function select(item) {
    await ensureOps();
    resetSession();
    session.source = item;
    try {
      probeInfo = await api.get(
        `/api/cases/${caseState.current.id}/inspect/probe?path=${encodeURIComponent(item.path)}`
      );
    } catch {
      probeInfo = { kind: item.kind };
    }
    if (item.kind === 'video') {
      session.videoAdjust = adjustDefaults(videoFilters);
      activeTab = 'selection';
    } else {
      const frame = makeFrame(item.path, null, `/files/${caseState.current.id}/${item.path}`);
      session.frames.push(frame);
      session.activeFrameId = frame.id;
      activeTab = 'frame';
    }
  }

  function makeFrame(path, time, url) {
    return {
      id: uid('fr'), path, time, url,
      adjust: adjustDefaults(filters), crop: null,
      w: probeInfo?.width, h: probeInfo?.height,
    };
  }

  // Render a recipe (video frame / image + ops) to a blob URL, no filing.
  async function renderUrl(path, time, ops = []) {
    const res = await fetch(`/api/cases/${caseState.current.id}/inspect/render-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, time: time ?? null, ops }),
    });
    if (!res.ok) {
      let detail = 'render failed';
      try {
        detail = (await res.json()).detail;
      } catch {
        /* non-json */
      }
      throw new Error(detail);
    }
    return URL.createObjectURL(await res.blob());
  }

  function imageSize(url) {
    return new Promise((resolve) => {
      const im = new Image();
      im.onload = () => resolve({ w: im.naturalWidth, h: im.naturalHeight });
      im.onerror = () => resolve({ w: probeInfo?.width || 320, h: probeInfo?.height || 240 });
      im.src = url;
    });
  }

  // -- frame capture (Selection) -------------------------------------------
  async function capture(time) {
    try {
      const url = await renderUrl(session.source.path, time, []);
      const frame = makeFrame(session.source.path, time, url);
      // frames captured from a tuned video inherit those gear adjustments
      frame.adjust = videoSeed(filters, session.videoAdjust);
      session.frames.push(frame);
      session.activeFrameId = frame.id;
      toast('Frame added to tray — not saved yet', 'ok');
    } catch (e) {
      toast(e.message, 'danger');
    }
  }

  // Collage pieces are snapshots frozen at add-time: the modified image is baked
  // now and later frame edits never change it (deliberate — see SPEC).
  async function addToCollage(frame) {
    try {
      const ops = buildOps(filters, frame.adjust, frame.crop);
      const url = await renderUrl(frame.path, frame.time, ops);
      const dim = await imageSize(url);
      const count = session.collage.nodes.length;
      const off = 30 + (count % 4) * 40;
      const quad = initialQuad(dim.w, dim.h, session.collage.width * 0.5, off, off);
      const node = {
        id: uid('nd'), frameId: frame.id, url, w: dim.w, h: dim.h,
        save: { path: frame.path, time: frame.time ?? null, ops }, quad,
      };
      session.collage.nodes.push(node);
      collageSelectedId = node.id;
    } catch (e) {
      toast(e.message, 'danger');
    }
  }

  function removeFrame(id) {
    const fr = session.frames.find((f) => f.id === id);
    if (fr?.url?.startsWith('blob:')) URL.revokeObjectURL(fr.url);
    session.frames = session.frames.filter((f) => f.id !== id);
    // collage pieces are independent snapshots — they stay.
    delete session.saved[`frame:${id}`];
    if (session.activeFrameId === id) session.activeFrameId = session.frames[0]?.id ?? null;
  }

  // -- crop overlay (Frame tab) --------------------------------------------
  function frac(e, el) {
    const r = el.getBoundingClientRect();
    return {
      x: Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1),
      y: Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1),
    };
  }
  function cropDown(e) {
    if (!shared.cropMode || !activeFrame) return;
    e.preventDefault();
    const p = frac(e, e.currentTarget);
    cropDraw = { sx: p.x, sy: p.y, x: p.x, y: p.y, w: 0, h: 0 };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function cropMove(e) {
    if (!cropDraw) return;
    const p = frac(e, e.currentTarget);
    cropDraw = {
      sx: cropDraw.sx, sy: cropDraw.sy,
      x: Math.min(cropDraw.sx, p.x), y: Math.min(cropDraw.sy, p.y),
      w: Math.abs(p.x - cropDraw.sx), h: Math.abs(p.y - cropDraw.sy),
    };
  }
  function cropUp() {
    if (cropDraw && cropDraw.w > 0.02 && cropDraw.h > 0.02 && activeFrame) {
      activeFrame.crop = { x: cropDraw.x, y: cropDraw.y, w: cropDraw.w, h: cropDraw.h };
      shared.cropMode = false;
    }
    cropDraw = null;
  }
  const cropBox = $derived(cropDraw ?? activeFrame?.crop ?? null);

  // -- save (the only gate that files entities) ----------------------------
  async function saveSelected() {
    const cid = caseState.current.id;
    const folder = saveUi.folder?.trim() || null;
    const chosen = savables.filter((it) => saveUi.selected[it.key]);
    if (!chosen.length) return;
    saving = true;
    try {
      const frameItems = chosen
        .filter((it) => it.kind === 'frame')
        .map((it) => ({
          path: it.frame.path,
          time: it.frame.time ?? null,
          ops: buildOps(filters, it.frame.adjust, it.frame.crop),
        }));
      if (frameItems.length) {
        await api.post(`/api/cases/${cid}/inspect/save-frames`, { items: frameItems, folder });
        for (const it of chosen) if (it.kind === 'frame') session.saved[it.key] = true;
      }
      if (chosen.some((it) => it.kind === 'video')) {
        await api.post(`/api/cases/${cid}/inspect/enhance-video`, {
          path: session.source.path, params: session.videoAdjust, folder,
        });
        session.saved.video = true;
      }
      if (chosen.some((it) => it.kind === 'collage')) {
        // each node carries its frozen snapshot recipe (path/time/ops)
        const nodes = session.collage.nodes.map((n) => ({ src: n.save, quad: n.quad }));
        await api.post(`/api/cases/${cid}/inspect/compose`, {
          width: Math.round(session.collage.width),
          height: Math.round(session.collage.height),
          background: session.collage.transparent ? null : session.collage.background,
          nodes, folder,
        });
        session.saved.collage = true;
      }
      await reloadCase();
      await refresh();
      saveUi.selected = {};
      toast(`Saved ${chosen.length} item${chosen.length === 1 ? '' : 's'} to the case`, 'ok');
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      saving = false;
    }
  }

  // -- saveable sessions (persist the whole workspace, reopen later) --------
  function sessionSpec() {
    return {
      source: { path: session.source.path, kind: session.source.kind },
      videoAdjust: { ...session.videoAdjust },
      activeFrameId: session.activeFrameId,
      frames: session.frames.map((f) => ({
        id: f.id, path: f.path, time: f.time, adjust: { ...f.adjust }, crop: f.crop, w: f.w, h: f.h,
      })),
      collage: {
        width: session.collage.width, height: session.collage.height,
        background: session.collage.background, transparent: session.collage.transparent,
        nodes: session.collage.nodes.map((n) => ({
          id: n.id, frameId: n.frameId, save: n.save, w: n.w, h: n.h, quad: n.quad,
        })),
      },
    };
  }

  function openSaveDialog() {
    sessionModal.mode = 'save';
    sessionModal.name = openedSession?.name ?? null;
    sessionModal.title = openedSession?.title || session.source?.label || session.source?.filename || 'Inspect session';
    sessionModal.open = true;
  }

  async function openLoadDialog() {
    sessionModal.mode = 'open';
    sessionModal.busy = true;
    sessionModal.open = true;
    try {
      sessionModal.list = await api.get(`/api/cases/${caseState.current.id}/inspect/sessions`);
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      sessionModal.busy = false;
    }
  }

  async function confirmSaveSession() {
    const title = sessionModal.title.trim();
    if (!title) return;
    sessionModal.busy = true;
    try {
      const res = await api.post(`/api/cases/${caseState.current.id}/inspect/sessions`, {
        name: sessionModal.name, title, spec: sessionSpec(),
      });
      openedSession = { name: res.name, title };
      await reloadCase();
      sessionModal.open = false;
      toast('Session saved — reopen it from the sidebar', 'ok');
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      sessionModal.busy = false;
    }
  }

  async function openSession(name) {
    await ensureOps();
    if (!mediaList.length) await refresh();
    let spec;
    try {
      spec = await api.get(`/api/cases/${caseState.current.id}/inspect/sessions/${name}`);
    } catch (e) {
      toast(e.message, 'danger');
      return;
    }
    resetSession();
    const src = mediaList.find((m) => m.path === spec.source.path) ?? spec.source;
    session.source = src;
    try {
      probeInfo = await api.get(
        `/api/cases/${caseState.current.id}/inspect/probe?path=${encodeURIComponent(src.path)}`
      );
    } catch {
      probeInfo = { kind: src.kind };
    }
    session.videoAdjust = spec.videoAdjust ?? adjustDefaults(videoFilters);
    for (const f of spec.frames ?? []) {
      try {
        const url = await renderUrl(f.path, f.time, []);
        session.frames.push({ ...f, url });
      } catch {
        /* skip a frame whose source is gone */
      }
    }
    session.activeFrameId = spec.activeFrameId ?? session.frames[0]?.id ?? null;
    const nodes = [];
    for (const n of spec.collage?.nodes ?? []) {
      try {
        nodes.push({ ...n, url: await renderUrl(n.save.path, n.save.time, n.save.ops) });
      } catch {
        /* skip a node whose source is gone */
      }
    }
    session.collage = {
      width: spec.collage?.width ?? 1600,
      height: spec.collage?.height ?? 800,
      background: spec.collage?.background ?? '#12141c',
      transparent: spec.collage?.transparent ?? false,
      nodes,
    };
    openedSession = { name, title: spec.title || name };
    activeTab = src.kind === 'video' ? 'selection' : 'frame';
    sessionModal.open = false;
  }

  async function deleteSession(name) {
    try {
      await api.del(`/api/cases/${caseState.current.id}/inspect/sessions/${name}`);
      sessionModal.list = sessionModal.list.filter((s) => s.name !== name);
      if (openedSession?.name === name) openedSession = null;
      await reloadCase();
    } catch (e) {
      toast(e.message, 'danger');
    }
  }
</script>

<div class="tool">
  <div class="tool-header">
    <h2>Inspect</h2>
    <span class="sub">a scratch workspace — capture, tune, collage; save only what you keep</span>
    <div class="spacer"></div>
    {#if caseState.current}
      <button class="btn btn-sm" onclick={openLoadDialog} title="Reopen a saved session">
        <Icon name="folderOpen" size={14} /> Open
      </button>
      <button class="btn btn-sm" disabled={!session.source} onclick={openSaveDialog} title="Save this workspace">
        <Icon name="save" size={14} /> Save session
      </button>
    {/if}
    <select
      class="input source-select"
      value={session.source?.path ?? ''}
      onchange={(e) => {
        const m = mediaList.find((x) => x.path === e.target.value);
        if (m) select(m);
      }}
    >
      <option value="" disabled>Choose a media…</option>
      {#each mediaList as m (m.path)}
        <option value={m.path}>{m.label || m.filename}</option>
      {/each}
    </select>
  </div>

  {#if !caseState.current}
    <div class="empty">
      <Icon name="inspect" size={40} />
      <p>Open a case and add media to start inspecting.</p>
      <button class="btn btn-primary" onclick={() => (uiState.tool = 'media')}>Go to Media Library</button>
    </div>
  {:else if !session.source}
    <div class="empty">
      <Icon name="inspect" size={40} />
      <p>Choose a media above to open it.</p>
      {#if mediaList.length === 0}
        <button class="btn" onclick={() => (uiState.tool = 'media')}>Add media first</button>
      {/if}
    </div>
  {:else}
    <div class="tabbar">
      {#each tabs as t (t)}
        <button class="tab" class:active={activeTab === t} onclick={() => (activeTab = t)}>
          <Icon name={TAB_META[t].icon} size={15} /> {TAB_META[t].label}
        </button>
      {/each}
    </div>

    <div class="workspace">
      <div class="viewer" class:pad={activeTab !== 'collage' && activeTab !== 'save'}>
        {#if activeTab === 'selection'}
          <div class="frame">
            <!-- svelte-ignore a11y_media_has_caption -->
            <video
              bind:this={videoEl}
              src={`/files/${caseState.current.id}/${session.source.path}`}
              controls
              ontimeupdate={() => (shared.currentTime = videoEl?.currentTime ?? 0)}
              style:filter={videoPreview.filter}
              style:transform={videoPreview.transform}
            ></video>
          </div>
        {:else if activeTab === 'frame'}
          {#if activeFrame}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="frame"
              class:cropping={shared.cropMode}
              onpointerdown={cropDown}
              onpointermove={cropMove}
              onpointerup={cropUp}
            >
              <img src={activeFrame.url} alt="frame" style:filter={framePreview.filter} style:transform={framePreview.transform} />
              {#if cropBox}
                <div
                  class="crop-box"
                  style:left={`${cropBox.x * 100}%`}
                  style:top={`${cropBox.y * 100}%`}
                  style:width={`${cropBox.w * 100}%`}
                  style:height={`${cropBox.h * 100}%`}
                ></div>
              {/if}
            </div>
          {:else}
            <div class="hint-mid">
              <Icon name="image" size={34} />
              <p>No frame selected — capture frames in the Selection tab.</p>
            </div>
          {/if}
        {:else if activeTab === 'collage'}
          <CollageCanvas {session} bind:selectedId={collageSelectedId} />
        {:else if activeTab === 'save'}
          <SaveGallery {savables} {saveUi} />
        {/if}
      </div>

      <aside class="panel">
        {#if activeTab === 'selection'}
          <SelectionMenu {probeInfo} {shared} {videoFilters} {session} {capture} />
        {:else if activeTab === 'frame'}
          <FrameMenu {session} {filters} {analyses} {activeFrame} {shared} {removeFrame} setActive={(id) => (session.activeFrameId = id)} />
        {:else if activeTab === 'collage'}
          <CollageMenu {session} {filters} bind:selectedId={collageSelectedId} {addToCollage} />
        {:else if activeTab === 'save'}
          <SaveMenu {savables} {saveUi} {saving} save={saveSelected} />
        {/if}
      </aside>
    </div>
  {/if}

  {#if sessionModal.open}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-back" onclick={() => (sessionModal.open = false)} role="presentation">
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <div class="modal" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
        <div class="modal-head">
          <h3>{sessionModal.mode === 'save' ? 'Save session' : 'Open session'}</h3>
          <button class="btn btn-ghost btn-xs" onclick={() => (sessionModal.open = false)} aria-label="Close">
            <Icon name="x" size={15} />
          </button>
        </div>

        {#if sessionModal.mode === 'save'}
          <p class="modal-hint">Persist this whole workspace — frames, adjustments and the collage — to reopen later. Saving the session does not file any media.</p>
          <input
            class="input"
            placeholder="Session name"
            bind:value={sessionModal.title}
            onkeydown={(e) => e.key === 'Enter' && confirmSaveSession()}
          />
          <div class="modal-actions">
            <button class="btn btn-sm" onclick={() => (sessionModal.open = false)}>Cancel</button>
            <button class="btn btn-primary btn-sm" disabled={sessionModal.busy || !sessionModal.title.trim()} onclick={confirmSaveSession}>
              <Icon name="save" size={14} /> Save
            </button>
          </div>
        {:else}
          {#if sessionModal.busy}
            <p class="modal-hint">Loading…</p>
          {:else if sessionModal.list.length === 0}
            <p class="modal-hint">No saved sessions yet.</p>
          {:else}
            <div class="session-list">
              {#each sessionModal.list as s (s.name)}
                <div class="session-row">
                  <button class="session-open" onclick={() => openSession(s.name)}>
                    <span class="session-title">{s.title}</span>
                    <span class="session-meta">{s.frames} frame{s.frames === 1 ? '' : 's'} · {s.collage} collage piece{s.collage === 1 ? '' : 's'}</span>
                  </button>
                  <button class="btn btn-ghost btn-xs" onclick={() => deleteSession(s.name)} aria-label="Delete session">
                    <Icon name="trash" size={14} />
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .tool {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  .tool-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 14px 16px 12px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  h2 {
    font-size: var(--fs-lg);
    font-weight: 700;
  }
  .sub {
    color: var(--text-3);
    font-size: var(--fs-sm);
  }
  .spacer {
    flex: 1;
  }
  .source-select {
    max-width: 280px;
  }
  .empty,
  .hint-mid {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--text-3);
    text-align: center;
  }
  .hint-mid p {
    max-width: 260px;
    font-size: var(--fs-sm);
  }
  .tabbar {
    display: flex;
    gap: 4px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: var(--r-md);
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--text-3);
  }
  .tab:hover {
    color: var(--text-1);
    background: var(--bg-2);
  }
  .tab.active {
    color: var(--accent);
    background: var(--accent-soft);
  }
  .workspace {
    flex: 1;
    display: flex;
    min-height: 0;
  }
  .viewer {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-0);
    overflow: auto;
  }
  .viewer.pad {
    padding: 18px;
  }
  .frame {
    position: relative;
    display: inline-block;
    line-height: 0;
    touch-action: none;
    box-shadow: var(--shadow-2);
  }
  .frame.cropping {
    cursor: crosshair;
  }
  .frame img,
  .frame video {
    max-width: 100%;
    max-height: calc(100vh - var(--topbar-h) - 160px);
    display: block;
  }
  .crop-box {
    position: absolute;
    border: 1.5px solid var(--accent);
    box-shadow: 0 0 0 9999px rgba(6, 9, 14, 0.55);
    pointer-events: none;
  }
  .panel {
    width: 320px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-1);
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: auto;
    padding: 14px;
  }
  .modal-back {
    position: fixed;
    inset: 0;
    background: rgba(6, 9, 14, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
  }
  .modal {
    width: 420px;
    max-width: calc(100vw - 40px);
    max-height: calc(100vh - 80px);
    overflow: auto;
    background: var(--bg-1);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-lg, 12px);
    box-shadow: var(--shadow-2);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .modal-head h3 {
    font-size: var(--fs-md);
    font-weight: 700;
  }
  .modal-hint {
    color: var(--text-3);
    font-size: var(--fs-sm);
    margin: 0;
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .session-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .session-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .session-open {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg-2);
  }
  .session-open:hover {
    border-color: var(--accent);
  }
  .session-title {
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--text-1);
  }
  .session-meta {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
</style>
