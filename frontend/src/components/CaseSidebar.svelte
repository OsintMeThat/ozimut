<script>
  import { api } from '../lib/api.js';
  import {
    caseState,
    uiState,
    reloadCase,
    toast,
    setSidebarWidth,
    persistSidebarWidth,
  } from '../lib/state.svelte.js';
  import { DEFAULT_W } from '../lib/sidebar.js';
  import { buildTree, subtreeCount, flattenPaths, folderOf } from '../lib/folderTree.js';
  import { assignFolder as fileEntity } from '../lib/filing.js';
  import { deletePlan } from '../lib/chain.js';
  import { openEntity, gotoCapture, ENTITY_TOOL } from '../lib/navigate.js';
  import Icon from './Icon.svelte';
  import Modal from './Modal.svelte';
  import ConfirmDialog from './ConfirmDialog.svelte';
  import EntityDetails from './EntityDetails.svelte';

  const ENTITY_ICONS = {
    person: 'user',
    organization: 'layers',
    alias: 'user',
    account: 'globe',
    email: 'note',
    phone: 'hash',
    place: 'pin',
    capture: 'satellite',
    event: 'clock',
    media: 'image',
    proof: 'proof',
    post: 'post',
    domain: 'globe',
    ip: 'hash',
    vehicle: 'grip',
    note: 'note',
    'inspect-session': 'inspect',
  };

  // Entity types backed by a file on disk — deleting them everywhere drops the file.
  const FILE_BACKED = new Set(['media', 'capture', 'proof', 'post', 'inspect-session']);

  const VIDEO_EXTS = new Set(['mp4', 'mov', 'webm', 'mkv', 'avi', 'm4v']);
  // Media entities normally carry the same `kind` the Media Library uses to tell
  // video from image; fall back to the file extension for entities filed before
  // that attr existed.
  function isVideo(e) {
    if (e.attrs?.kind) return e.attrs.kind === 'video';
    const ext = e.attrs?.path?.split('.').pop()?.toLowerCase();
    return !!ext && VIDEO_EXTS.has(ext);
  }
  const entityIcon = (e) => (e.type === 'media' && isVideo(e) ? 'video' : ENTITY_ICONS[e.type] ?? 'note');

  // ── case notes (single notes.md) ─────────────────────────────────────────
  let caseNotes = $state('');
  let caseNotesLoadedFor = $state(null);
  let saveTimer;
  let saved = $state(true);
  let section = $state({ notes: false, suggestions: true, mywork: true });

  $effect(() => {
    const id = caseState.current?.id;
    if (id && id !== caseNotesLoadedFor) {
      caseNotesLoadedFor = id;
      api.get(`/api/cases/${id}/notes`).then((r) => (caseNotes = r.text));
    } else if (!id) {
      caseNotesLoadedFor = null;
      caseNotes = '';
    }
  });

  function onCaseNotesInput() {
    saved = false;
    clearTimeout(saveTimer);
    const id = caseState.current?.id;
    saveTimer = setTimeout(async () => {
      if (!id) return;
      try {
        await api.put(`/api/cases/${id}/notes`, { text: caseNotes });
        saved = true;
      } catch (e) {
        toast(`Notes not saved: ${e.message}`, 'danger');
      }
    }, 700);
  }

  // ── entities ─────────────────────────────────────────────────────────────
  const entities = $derived(caseState.current?.entities ?? []);
  const links = $derived(caseState.current?.links ?? []);
  const suggested = $derived(entities.filter((e) => e.provenance?.status === 'suggested'));
  const confirmed = $derived(entities.filter((e) => e.provenance?.status !== 'suggested'));

  async function confirmEntity(entity) {
    await api.patch(`/api/cases/${caseState.current.id}/entities/${entity.id}`, {
      status: 'confirmed',
    });
    await reloadCase();
  }

  // Dismiss a suggestion outright (quick triage — no heavy confirmation).
  async function dismissSuggestion(entity) {
    await api.del(`/api/cases/${caseState.current.id}/entities/${entity.id}`);
    await reloadCase();
    toast(`Dismissed "${entity.label}"`, 'info');
  }

  // clicking a row: notes open the editor, captures open their image, places
  // navigate the map — everything else opens its tool
  function onEntityActivate(entity) {
    if (entity.type === 'note') return openEditNote(entity);
    if (entity.type === 'capture') return openInfo(entity);
    openEntity(entity);
  }

  // openEntity / gotoCapture live in lib/navigate.js — the case sidebar and the
  // Details editor send an analyst to the same place.

  // ── My work: the analyst's own nested folder tree ('/'-separated paths) ────
  let newFolder = $state(''); // top-level create input
  let addingUnder = $state(undefined); // folder path currently gaining a child
  let newSubName = $state('');
  let expanded = $state({}); // path -> bool (absent = collapsed)
  let dragEntityId = $state(null);
  let dragOverFolder = $state(undefined); // folder path being hovered

  const caseFolders = $derived(caseState.current?.folders ?? []);

  const tree = $derived(buildTree(caseFolders, confirmed));
  const allFolders = $derived(flattenPaths(tree));
  // everything not yet filed — the inbox you file (or inspect) items from
  const unfiled = $derived(confirmed.filter((e) => !folderOf(e)));
  let unfiledOpen = $state(false);
  let unfiledTypeFilter = $state(null);
  const TYPE_LABEL = {
    media: 'Media', capture: 'Satellite', note: 'Notes', proof: 'Proofs',
    post: 'Posts', place: 'Places', 'inspect-session': 'Inspect',
  };
  // chip counts, in a stable order (declaration order of TYPE_LABEL, then anything unmapped)
  const unfiledTypes = $derived.by(() => {
    const counts = new Map();
    for (const e of unfiled) counts.set(e.type, (counts.get(e.type) ?? 0) + 1);
    return Object.keys(TYPE_LABEL)
      .filter((t) => counts.has(t))
      .concat([...counts.keys()].filter((t) => !(t in TYPE_LABEL)))
      .map((t) => ({ type: t, label: TYPE_LABEL[t] ?? t, count: counts.get(t) }));
  });
  const unfiledFiltered = $derived(
    unfiledTypeFilter ? unfiled.filter((e) => e.type === unfiledTypeFilter) : unfiled
  );
  $effect(() => {
    // drop a stale filter when its type disappears from Unfiled (e.g. filed away)
    if (unfiledTypeFilter && !unfiled.some((e) => e.type === unfiledTypeFilter)) unfiledTypeFilter = null;
  });

  const isExpanded = (path) => expanded[path] === true;
  function toggle(path) { expanded[path] = !isExpanded(path); }
  function focus(node) { node.focus(); }

  async function createFolder(fullName) {
    const name = (fullName ?? newFolder).trim();
    if (!name) return;
    if (fullName == null) newFolder = '';
    try {
      await api.post(`/api/cases/${caseState.current.id}/folders`, { name });
      let acc = '';
      for (const seg of name.split('/')) { acc = acc ? `${acc}/${seg}` : seg; expanded[acc] = true; }
      await reloadCase();
    } catch (e) {
      toast(e.message, 'danger');
    }
  }

  function startAddSub(path) {
    addingUnder = path;
    newSubName = '';
    expanded[path] = true;
  }
  async function submitAddSub() {
    const name = newSubName.trim();
    const parent = addingUnder;
    addingUnder = undefined;
    newSubName = '';
    if (!name || parent === undefined) return;
    await createFolder(parent ? `${parent}/${name}` : name);
  }

  // File (or unfile, with folder='') an entity into a My-work folder, then
  // refresh. Routing lives in lib/filing.js so the desktop organizer files
  // items the same way.
  async function assignFolder(entity, folder) {
    await fileEntity(caseState.current.id, entity, folder);
    await reloadCase();
  }

  // drag & drop wiring
  function onDragStart(ev, entity) {
    dragEntityId = entity.id;
    ev.dataTransfer.effectAllowed = 'move';
    ev.dataTransfer.setData('text/plain', entity.id);
  }
  function onDropFolder(ev, folder) {
    ev.preventDefault();
    dragOverFolder = undefined;
    const entity = entities.find((e) => e.id === dragEntityId);
    dragEntityId = null;
    if (entity) assignFolder(entity, folder).catch((e) => toast(e.message, 'danger'));
  }

  // ── confirmation dialog (replaces browser confirm()) ──────────────────────
  let confirmState = $state(null); // { title, message, detail, confirmLabel, tone, icon, action }
  let confirmBusy = $state(false);

  async function runConfirm() {
    const s = confirmState;
    if (!s) return;
    confirmBusy = true;
    try {
      await s.action();
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      confirmBusy = false;
      confirmState = null;
    }
  }

  // Delete everywhere: removes the entity and its underlying file(s). Used from
  // the details panel (and the note modal) — irreversible, danger tone.
  //
  // Whatever hangs off the entity is spelled out before the click: sessions that
  // cannot outlive it go too, outputs made from it stay and keep a record of
  // what they lost. Nothing cascades into an output — ever (ONTOLOGY §3).
  function askDeleteEverywhere(entity, onDone) {
    confirmState = {
      title: 'Delete everywhere?',
      message: `“${entity.label}” will be removed from the case and its tool.`,
      detail: FILE_BACKED.has(entity.type)
        ? 'This permanently deletes the underlying file(s) on disk — it cannot be undone.'
        : 'This permanently removes it from the case — it cannot be undone.',
      consequences: deletePlan(entities, links, entity.id),
      confirmLabel: 'Delete everywhere',
      tone: 'danger',
      icon: 'trash',
      action: async () => {
        await api.del(`/api/cases/${caseState.current.id}/entities/${entity.id}`);
        await reloadCase();
        toast(`Deleted "${entity.label}"`, 'info');
        onDone?.();
      },
    };
  }

  // Remove from My work: just clears the filing. The item stays in its tool.
  function askRemoveFromMyWork(entity) {
    confirmState = {
      title: 'Remove from My work?',
      message: `“${entity.label}” is unfiled. Nothing is deleted.`,
      detail: 'It stays available in the case and its tool. Only your filing here is cleared.',
      confirmLabel: 'Remove from My work',
      tone: 'default',
      icon: 'folderMinus',
      action: () => assignFolder(entity, ''),
    };
  }

  function askDeleteFolder(path) {
    const prefix = path + '/';
    const inside = entities.filter((e) => {
      const f = folderOf(e);
      return f === path || (f && f.startsWith(prefix));
    });
    const subs = allFolders.filter((f) => f.startsWith(prefix)).length;
    confirmState = {
      title: 'Remove this folder?',
      message: subs
        ? `“${path}” and its ${subs} subfolder(s) will be removed from My work.`
        : `“${path}” will be removed from My work.`,
      detail: 'Items inside are unfiled. No files are deleted.',
      confirmLabel: 'Remove folder',
      tone: 'default',
      icon: 'folderMinus',
      action: async () => {
        for (const e of inside) await assignFolder(e, '');
        await api.del(
          `/api/cases/${caseState.current.id}/folders?name=${encodeURIComponent(path)}`
        );
        await reloadCase();
      },
    };
  }

  // ── details panel (docs/UI.md §4) ─────────────────────────────────────────
  // The editor body lives in EntityDetails.svelte (shared with the Media
  // Library modal). The sidebar only tracks which entity is selected and
  // scrolls it into view.
  let infoEntity = $state(null);
  let detailsEl = $state(null);

  function openInfo(entity) {
    infoEntity = entity;
    requestAnimationFrame(() => detailsEl?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }

  // ── note entities ─────────────────────────────────────────────────────────
  let noteModal = $state(null);
  // shape: { entity: obj|null, title: string, folder: string, content: string }
  let noteModalSaving = $state(false);

  function openNewNote() {
    noteModal = { entity: null, title: '', folder: '', content: '' };
  }

  function openEditNote(entity) {
    noteModal = {
      entity,
      title: entity.label,
      folder: entity.attrs?.folder ?? '',
      content: entity.attrs?.content ?? '',
    };
  }

  async function saveNote() {
    if (!noteModal) return;
    const { entity, title, folder, content } = noteModal;
    if (!title.trim()) { toast('Title required', 'warn'); return; }
    noteModalSaving = true;
    try {
      const attrs = { content, folder: folder.trim() };
      if (!entity) {
        await api.post(`/api/cases/${caseState.current.id}/entities`, {
          type: 'note', label: title.trim(), attrs,
        });
        toast('Note created', 'ok', 1600);
      } else {
        await api.patch(`/api/cases/${caseState.current.id}/entities/${entity.id}`, {
          label: title.trim(), attrs,
        });
        toast('Note saved', 'ok', 1600);
      }
      await reloadCase();
      noteModal = null;
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      noteModalSaving = false;
    }
  }

  // --- resize: the sidebar's left edge is a drag handle ---
  let resizing = $state(false);
  const KEY_STEP = 16;

  function startResize(e) {
    if (e.button !== 0) return;
    e.preventDefault(); // don't start a text selection under the cursor
    const startX = e.clientX;
    const startW = uiState.sidebarW;
    resizing = true;
    // dragging left (a smaller clientX) widens the sidebar — it grows into the canvas
    const move = (ev) => setSidebarWidth(startW + startX - ev.clientX);
    const up = () => {
      resizing = false;
      persistSidebarWidth(); // one write per drag, not one per frame
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  function onResizeKey(e) {
    const step = { ArrowLeft: KEY_STEP, ArrowRight: -KEY_STEP }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    setSidebarWidth(uiState.sidebarW + step);
    persistSidebarWidth();
  }

  function resetWidth() {
    setSidebarWidth(DEFAULT_W);
    persistSidebarWidth();
  }

  // A width dragged out on a wide screen would eat a narrower window whole, so
  // re-clamp against the viewport as it changes. The clamped-down value is not
  // written back — what the user actually chose is what a later session restores.
  $effect(() => {
    const onWindowResize = () => setSidebarWidth(uiState.sidebarW);
    window.addEventListener('resize', onWindowResize);
    return () => window.removeEventListener('resize', onWindowResize);
  });
</script>

<aside class="sidebar" class:resizing style="width: {uiState.sidebarW}px">
  <!-- a <button> rather than a bare div: the handle must be focusable and
       keyboard-driven (arrows resize), and the element carries that for free -->
  <button
    type="button"
    class="resizer"
    aria-label="Resize sidebar"
    title="Drag to resize · double-click to reset"
    onpointerdown={startResize}
    ondblclick={resetWidth}
    onkeydown={onResizeKey}
  ></button>

  {#if !caseState.current}
    <div class="empty">
      <div class="empty-icon"><Icon name="folder" size={34} /></div>
      <h3>No case open</h3>
      <p>Tools work without one. Create a case to keep the investigation together.</p>
    </div>
  {:else}
    <div class="case-head">
      <h3>{caseState.current.name}</h3>
      <span class="path mono">{caseState.current.id}</span>
    </div>

    <div class="sections">

      <!-- 1 · Case Notes (single notes.md) -->
      <button class="section-head" onclick={() => (section.notes = !section.notes)}>
        <Icon name={section.notes ? 'chevronDown' : 'chevronRight'} size={13} />
        <span>Case Notes</span>
        {#if !saved}<span class="badge">saving…</span>{/if}
      </button>
      {#if section.notes}
        <textarea
          class="textarea notes mono"
          bind:value={caseNotes}
          oninput={onCaseNotesInput}
          placeholder="Case notes (markdown)…"
        ></textarea>
      {/if}

      <!-- 2 · Suggestions (tool-suggested entities: confirm or dismiss) -->
      {#if suggested.length > 0}
        <button class="section-head" onclick={() => (section.suggestions = !section.suggestions)}>
          <Icon name={section.suggestions ? 'chevronDown' : 'chevronRight'} size={13} />
          <span>Suggestions</span>
          <span class="count">{suggested.length}</span>
        </button>
        {#if section.suggestions}
          {#each suggested as e (e.id)}
            <div class="entity suggested">
              <Icon name={entityIcon(e)} size={14} />
              <div class="e-body">
                <span class="e-label">{e.label}</span>
                <span class="e-meta">{e.type} · {e.provenance?.by}</span>
              </div>
              <button class="btn btn-ghost btn-sm" title="Confirm" onclick={() => confirmEntity(e)}>
                <Icon name="check" size={13} />
              </button>
              <button class="btn btn-ghost btn-sm" title="Dismiss" onclick={() => dismissSuggestion(e)}>
                <Icon name="x" size={13} />
              </button>
            </div>
          {/each}
        {/if}
      {/if}

      <!-- 3 · My work (your own folders; file items from their details panel) -->
      <div class="section-head-row">
        <button class="section-head" onclick={() => (section.mywork = !section.mywork)}>
          <Icon name={section.mywork ? 'chevronDown' : 'chevronRight'} size={13} />
          <span>My work</span>
          <span class="count">{confirmed.length}</span>
        </button>
        <button class="btn btn-ghost btn-sm new-note-btn" title="New note" onclick={openNewNote}>
          <Icon name="plus" size={13} /><Icon name="note" size={13} />
        </button>
      </div>

      {#if section.mywork}
        <!-- create a top-level folder -->
        <form class="new-folder" onsubmit={(e) => { e.preventDefault(); createFolder(); }}>
          <input class="input" placeholder="New folder…" bind:value={newFolder} />
          <button class="btn btn-sm" type="submit" title="Create folder" disabled={!newFolder.trim()}>
            <Icon name="plus" size={13} />
          </button>
        </form>

        <div class="tree">
          {#each tree as node (node.path)}
            {@render folderNode(node, 0)}
          {/each}

          {#if unfiled.length > 0}
            <div
              class="frow"
              role="button"
              tabindex="0"
              onclick={() => (unfiledOpen = !unfiledOpen)}
              onkeydown={(e) => e.key === 'Enter' && (unfiledOpen = !unfiledOpen)}
            >
              <Icon name={unfiledOpen ? 'chevronDown' : 'chevronRight'} size={12} />
              <Icon name="layers" size={13} />
              <span class="fname">Unfiled</span>
              <span class="fcount">{unfiled.length}</span>
            </div>
            {#if unfiledOpen}
              {#if unfiledTypes.length > 1}
                <div class="chip-row">
                  {#each unfiledTypes as t (t.type)}
                    <button
                      class="chip"
                      class:active={unfiledTypeFilter === t.type}
                      onclick={() => (unfiledTypeFilter = unfiledTypeFilter === t.type ? null : t.type)}
                    >
                      {t.label}<span class="chip-count">{t.count}</span>
                    </button>
                  {/each}
                </div>
              {/if}
              {#each unfiledFiltered as e (e.id)}
                {@render entityRow(e, 1)}
              {/each}
            {/if}
          {/if}

          {#if tree.length === 0 && unfiled.length === 0}
            <div class="none">
              Everything you save lands here; create folders to organize it.
            </div>
          {/if}
        </div>
      {/if}


      <!-- 4 · Details (selection editor — docs/UI.md §4; shared body) -->
      {#if infoEntity}
        <div bind:this={detailsEl}>
          <div class="section-head-row">
            <div class="section-head static">
              <Icon name="note" size={13} />
              <span>Details</span>
            </div>
            <button class="btn btn-ghost btn-sm" title="Close details" onclick={() => (infoEntity = null)}>
              <Icon name="x" size={13} />
            </button>
          </div>
          <div class="details">
            <EntityDetails
              entityId={infoEntity.id}
              onclose={() => (infoEntity = null)}
              ondeleted={() => (infoEntity = null)}
            />
          </div>
        </div>
      {/if}

    </div>
  {/if}
</aside>

<!-- one folder node + its subtree (recursive) -->
{#snippet folderNode(node, depth)}
  <div
    class="frow"
    class:dropping={dragOverFolder === node.path}
    style="padding-left: {8 + depth * 14}px"
    role="button"
    tabindex="0"
    ondragover={(e) => { e.preventDefault(); dragOverFolder = node.path; }}
    ondragleave={() => (dragOverFolder = undefined)}
    ondrop={(e) => onDropFolder(e, node.path)}
    onclick={() => toggle(node.path)}
    onkeydown={(e) => e.key === 'Enter' && toggle(node.path)}
  >
    <Icon name={isExpanded(node.path) ? 'chevronDown' : 'chevronRight'} size={12} />
    <Icon name={isExpanded(node.path) ? 'folderOpen' : 'folder'} size={13} />
    <span class="fname">{node.name}</span>
    <span class="fcount">{subtreeCount(node)}</span>
    <span
      class="fact"
      role="button"
      tabindex="0"
      title="Add subfolder"
      onclick={(e) => { e.stopPropagation(); startAddSub(node.path); }}
      onkeydown={(e) => e.key === 'Enter' && (e.stopPropagation(), startAddSub(node.path))}
    >
      <Icon name="plus" size={12} />
    </span>
    <span
      class="fact fdel"
      role="button"
      tabindex="0"
      title="Remove folder"
      onclick={(e) => { e.stopPropagation(); askDeleteFolder(node.path); }}
      onkeydown={(e) => e.key === 'Enter' && (e.stopPropagation(), askDeleteFolder(node.path))}
    >
      <Icon name="folderMinus" size={12} />
    </span>
  </div>
  {#if isExpanded(node.path)}
    {#if addingUnder === node.path}
      <form
        class="new-folder sub"
        style="padding-left: {8 + (depth + 1) * 14}px"
        onsubmit={(e) => { e.preventDefault(); submitAddSub(); }}
      >
        <input
          class="input"
          placeholder="Subfolder…"
          bind:value={newSubName}
          use:focus
          onkeydown={(e) => e.key === 'Escape' && (addingUnder = undefined)}
        />
        <button class="btn btn-sm" type="submit" title="Create" disabled={!newSubName.trim()}>
          <Icon name="plus" size={13} />
        </button>
      </form>
    {/if}
    {#each node.children as child (child.path)}
      {@render folderNode(child, depth + 1)}
    {/each}
    {#each node.entities as e (e.id)}
      {@render entityRow(e, depth + 1)}
    {/each}
  {/if}
{/snippet}

<!-- one entity row (My work): activate, info, unfile -->
{#snippet entityRow(e, depth)}
  {@const isClickable = e.type === 'note' || e.type === 'capture' || !!ENTITY_TOOL[e.type]}
  <div
    class="entity"
    class:clickable={isClickable}
    class:dragging={dragEntityId === e.id}
    style="padding-left: {8 + depth * 14}px"
    draggable="true"
    ondragstart={(ev) => onDragStart(ev, e)}
    ondragend={() => { dragEntityId = null; dragOverFolder = undefined; }}
    onclick={() => onEntityActivate(e)}
    role={isClickable ? 'button' : undefined}
    tabindex={isClickable ? 0 : undefined}
    onkeydown={(ev) => ev.key === 'Enter' && onEntityActivate(e)}
  >
    <Icon name="grip" size={13} />
    <Icon name={entityIcon(e)} size={14} />
    <div class="e-body">
      <span class="e-label">{e.label}</span>
      <span class="e-meta">{e.type}</span>
    </div>
    {#if e.type === 'capture' && e.attrs?.lat != null}
      <button
        class="btn btn-ghost btn-sm act"
        title="Go to these coordinates on the map"
        onclick={(ev) => { ev.stopPropagation(); gotoCapture(e); }}
      >
        <Icon name="crosshair" size={13} />
      </button>
    {/if}
    {#if e.type === 'media' && e.attrs?.path}
      <a
        class="btn btn-ghost btn-sm act"
        title="Open in new tab"
        href={`/files/${caseState.current.id}/${e.attrs.path}`}
        target="_blank"
        rel="noreferrer"
        onclick={(ev) => ev.stopPropagation()}
      >
        <Icon name="external" size={13} />
      </a>
    {/if}
    <button
      class="btn btn-ghost btn-sm act"
      title="Info"
      onclick={(ev) => { ev.stopPropagation(); openInfo(e); }}
    >
      <Icon name="note" size={13} />
    </button>
    {#if folderOf(e)}
      <button
        class="btn btn-ghost btn-sm act del"
        title="Unfile from this folder"
        onclick={(ev) => { ev.stopPropagation(); askRemoveFromMyWork(e); }}
      >
        <Icon name="folderMinus" size={13} />
      </button>
    {/if}
  </div>
{/snippet}

<!-- Note edit / create modal -->
{#if noteModal}
  <Modal
    title={noteModal.entity ? 'Edit note' : 'New note'}
    onclose={() => (noteModal = null)}
    width="580px"
  >
    <label class="modal-label" for="note-title">Title</label>
    <input
      id="note-title"
      class="input"
      placeholder="Note title…"
      bind:value={noteModal.title}
    />

    <label class="modal-label" for="note-folder" style="margin-top:10px">Folder (in My work)</label>
    <input
      id="note-folder"
      class="input"
      placeholder="e.g. research, timeline, sources…"
      bind:value={noteModal.folder}
      list="note-folder-suggestions"
    />
    <datalist id="note-folder-suggestions">
      {#each allFolders as f (f)}<option value={f}></option>{/each}
    </datalist>

    <label class="modal-label" for="note-content" style="margin-top:10px">Content</label>
    <textarea
      id="note-content"
      class="textarea note-content"
      rows="14"
      placeholder="Write your notes in markdown…"
      bind:value={noteModal.content}
    ></textarea>

    <div class="modal-row">
      {#if noteModal.entity}
        <button
          class="btn btn-ghost btn-sm"
          style="color:var(--danger,#e55)"
          onclick={() => askDeleteEverywhere(noteModal.entity, () => (noteModal = null))}
        >
          <Icon name="trash" size={13} /> Delete note
        </button>
      {/if}
      <div style="flex:1"></div>
      <button class="btn" onclick={() => (noteModal = null)}>Cancel</button>
      <button class="btn btn-primary" onclick={saveNote} disabled={noteModalSaving}>
        {noteModalSaving ? 'Saving…' : noteModal.entity ? 'Save' : 'Create'}
      </button>
    </div>
  </Modal>
{/if}


<!-- Confirmation dialog (delete everywhere / remove from My work / remove folder) -->
{#if confirmState}
  <ConfirmDialog
    title={confirmState.title}
    message={confirmState.message}
    detail={confirmState.detail}
    consequences={confirmState.consequences}
    confirmLabel={confirmState.confirmLabel}
    tone={confirmState.tone}
    icon={confirmState.icon}
    busy={confirmBusy}
    onconfirm={runConfirm}
    oncancel={() => (confirmState = null)}
  />
{/if}

<style>
  .sidebar {
    /* width is driven by uiState.sidebarW (inline style) — see lib/sidebar.js */
    position: relative;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  /* the grab strip sits just inside the left edge, over the sections' padding */
  .resizer {
    position: absolute;
    top: 0;
    left: 0;
    width: 5px;
    height: 100%;
    z-index: 2;
    cursor: col-resize;
    background: transparent;
    transition: background 0.12s;
  }
  .resizer:hover,
  .resizer:focus-visible,
  .sidebar.resizing .resizer {
    background: var(--accent);
    outline: none;
  }
  /* a drag reads as one gesture — no text selection, no cursor flicker on hover
     targets the pointer crosses on the way */
  .sidebar.resizing {
    user-select: none;
  }
  .case-head {
    padding: 16px 16px 12px;
    border-bottom: 1px solid var(--border);
  }
  .case-head h3 {
    font-size: var(--fs-md);
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .path { font-size: var(--fs-xs); color: var(--text-3); }
  .sections { flex: 1; overflow-y: auto; padding: 8px; }
  .section-head {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 8px 8px 6px;
    font-size: var(--fs-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-2);
  }
  .section-head:hover { color: var(--text-1); }
  .section-head-row { display: flex; align-items: center; }
  .section-head-row .section-head { flex: 1; }
  .new-note-btn {
    color: var(--text-3);
    padding: 4px 6px;
    margin-right: 4px;
    display: flex;
    gap: 2px;
  }
  .new-note-btn:hover { color: var(--accent); }
  .count { margin-left: auto; color: var(--text-3); font-weight: 600; }
  .notes {
    min-height: 130px;
    font-size: var(--fs-xs);
    margin: 0 4px 10px;
    width: calc(100% - 8px);
  }
  /* tool group header (Saved work) */
  /* folder tree */
  .new-folder { display: flex; gap: 6px; padding: 2px 8px 8px; }
  .new-folder.sub { padding: 2px 8px 4px; }
  .new-folder .input { flex: 1; font-size: var(--fs-xs); }
  .tree { display: flex; flex-direction: column; gap: 1px; padding: 0 4px 4px; }
  .frow {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    padding: 6px 8px;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: var(--fs-sm);
    border: 1px solid transparent;
    cursor: pointer;
    text-align: left;
  }
  .frow:hover { background: var(--bg-2); }
  .frow.dropping { border-color: var(--accent); background: var(--accent-soft); }
  .frow > :global(svg:first-child) { color: var(--text-3); flex-shrink: 0; }
  .fname { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .fcount { color: var(--text-3); font-size: var(--fs-xs); font-weight: 600; }
  .fact { opacity: 0; color: var(--text-3); display: flex; padding: 2px; border-radius: 4px; flex-shrink: 0; }
  .fact:hover { color: var(--text-1); }
  .fdel:hover { color: var(--danger, #e55); }
  .chip-row { display: flex; flex-wrap: wrap; gap: 4px; padding: 2px 8px 6px 22px; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 7px;
    border-radius: var(--r-sm);
    font-size: var(--fs-xs);
    font-weight: 500;
    background: var(--bg-2);
    color: var(--text-2);
    border: 1px solid transparent;
  }
  .chip:hover { color: var(--text-1); }
  .chip.active { background: var(--accent-soft); color: var(--accent); border-color: var(--accent); }
  .chip-count { color: inherit; opacity: 0.65; font-weight: 600; }
  .frow:hover .fact { opacity: 1; }
  /* entities */
  .entity {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 6px 8px;
    border-radius: var(--r-sm);
    color: var(--text-2);
  }
  .entity:hover { background: var(--bg-2); }
  .entity.clickable { cursor: pointer; }
  .entity.dragging { opacity: 0.5; }
  .entity > :global(svg:first-child) { color: var(--text-3); cursor: grab; flex-shrink: 0; }
  .entity.suggested {
    background: var(--accent-soft);
    border: 1px dashed var(--accent);
    margin-bottom: 4px;
  }
  .e-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .e-label {
    font-size: var(--fs-sm);
    color: var(--text-1);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .e-meta {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .act { opacity: 0; flex-shrink: 0; }
  .entity:hover .act { opacity: 1; }
  .del:hover { color: var(--danger, #e55); }
  .none { font-size: var(--fs-xs); color: var(--text-3); padding: 4px 8px 12px; line-height: 1.45; }
  /* note modal */
  .modal-label { display: block; font-size: var(--fs-xs); color: var(--text-3); margin: 8px 0 4px; }
  .section-head.static { cursor: default; }
  .details {
    padding: 4px 8px 10px;
    border-bottom: 1px solid var(--border);
    font-size: var(--fs-sm);
  }
  .note-content { width: 100%; resize: vertical; font-family: var(--font-mono); font-size: var(--fs-xs); }
  .modal-row { display: flex; align-items: center; gap: 8px; margin-top: 14px; }
</style>
