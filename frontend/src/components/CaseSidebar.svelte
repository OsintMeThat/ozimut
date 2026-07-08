<script>
  import { api } from '../lib/api.js';
  import { caseState, reloadCase, toast } from '../lib/state.svelte.js';
  import Icon from './Icon.svelte';

  const ENTITY_ICONS = {
    person: 'user',
    organization: 'layers',
    alias: 'user',
    account: 'globe',
    email: 'note',
    phone: 'hash',
    place: 'pin',
    event: 'clock',
    media: 'image',
    proof: 'proof',
    domain: 'globe',
    ip: 'hash',
    vehicle: 'grip',
    note: 'note',
  };

  let notes = $state('');
  let notesLoadedFor = $state(null);
  let saveTimer;
  let saved = $state(true);
  let section = $state({ notes: true, entities: true });

  $effect(() => {
    const id = caseState.current?.id;
    if (id && id !== notesLoadedFor) {
      notesLoadedFor = id;
      api.get(`/api/cases/${id}/notes`).then((r) => (notes = r.text));
    } else if (!id) {
      notesLoadedFor = null;
      notes = '';
    }
  });

  function onNotesInput() {
    saved = false;
    clearTimeout(saveTimer);
    const id = caseState.current?.id;
    saveTimer = setTimeout(async () => {
      if (!id) return;
      try {
        await api.put(`/api/cases/${id}/notes`, { text: notes });
        saved = true;
      } catch (e) {
        toast(`Notes not saved: ${e.message}`, 'danger');
      }
    }, 700);
  }

  async function confirmEntity(entity) {
    await api.patch(`/api/cases/${caseState.current.id}/entities/${entity.id}`, {
      status: 'confirmed',
    });
    await reloadCase();
  }

  async function removeEntity(entity) {
    await api.del(`/api/cases/${caseState.current.id}/entities/${entity.id}`);
    await reloadCase();
    toast(`Removed “${entity.label}”`, 'info');
  }

  const entities = $derived(caseState.current?.entities ?? []);
  const suggested = $derived(entities.filter((e) => e.provenance?.status === 'suggested'));
  const confirmed = $derived(entities.filter((e) => e.provenance?.status !== 'suggested'));
</script>

<aside class="sidebar">
  {#if !caseState.current}
    <div class="empty">
      <div class="empty-icon"><Icon name="folder" size={34} /></div>
      <h3>No case open</h3>
      <p>
        Use any tool right away — a scratch session is created when needed. Open or create a case
        to keep an investigation together.
      </p>
    </div>
  {:else}
    <div class="case-head">
      <h3>{caseState.current.name}</h3>
      <span class="path mono">{caseState.current.id}</span>
    </div>

    <div class="sections">
      <!-- Notes -->
      <button class="section-head" onclick={() => (section.notes = !section.notes)}>
        <Icon name={section.notes ? 'chevronDown' : 'chevronRight'} size={13} />
        <span>Notes</span>
        {#if !saved}<span class="badge">saving…</span>{/if}
      </button>
      {#if section.notes}
        <textarea
          class="textarea notes mono"
          bind:value={notes}
          oninput={onNotesInput}
          placeholder="Case notes (markdown)…"
        ></textarea>
      {/if}

      <!-- Entities -->
      <button class="section-head" onclick={() => (section.entities = !section.entities)}>
        <Icon name={section.entities ? 'chevronDown' : 'chevronRight'} size={13} />
        <span>Entities</span>
        <span class="count">{entities.length}</span>
      </button>
      {#if section.entities}
        {#if suggested.length}
          <div class="suggest-note">Suggested by tools — confirm or dismiss:</div>
          {#each suggested as e (e.id)}
            <div class="entity suggested">
              <Icon name={ENTITY_ICONS[e.type] ?? 'note'} size={14} />
              <div class="e-body">
                <span class="e-label">{e.label}</span>
                <span class="e-type">{e.type} · by {e.provenance?.by}</span>
              </div>
              <button class="btn btn-ghost btn-sm" title="Confirm" onclick={() => confirmEntity(e)}>
                <Icon name="check" size={13} />
              </button>
              <button class="btn btn-ghost btn-sm" title="Dismiss" onclick={() => removeEntity(e)}>
                <Icon name="x" size={13} />
              </button>
            </div>
          {/each}
        {/if}
        {#each confirmed as e (e.id)}
          <div class="entity">
            <Icon name={ENTITY_ICONS[e.type] ?? 'note'} size={14} />
            <div class="e-body">
              <span class="e-label">{e.label}</span>
              <span class="e-type">{e.type}</span>
            </div>
            <button class="btn btn-ghost btn-sm del" title="Delete" onclick={() => removeEntity(e)}>
              <Icon name="trash" size={13} />
            </button>
          </div>
        {:else}
          {#if !suggested.length}
            <div class="none">Tools file entities here as you work.</div>
          {/if}
        {/each}
      {/if}
    </div>
  {/if}
</aside>

<style>
  .sidebar {
    width: var(--sidebar-w);
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    background: var(--bg-1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
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
  .path {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .sections {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
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
  .section-head:hover {
    color: var(--text-1);
  }
  .count {
    margin-left: auto;
    color: var(--text-3);
    font-weight: 600;
  }
  .notes {
    min-height: 130px;
    font-size: var(--fs-xs);
    margin: 0 4px 10px;
    width: calc(100% - 8px);
  }
  .entity {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 6px 8px;
    border-radius: var(--r-sm);
    color: var(--text-2);
  }
  .entity:hover {
    background: var(--bg-2);
  }
  .entity.suggested {
    background: var(--accent-soft);
    border: 1px dashed var(--accent);
    margin-bottom: 4px;
  }
  .e-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .e-label {
    font-size: var(--fs-sm);
    color: var(--text-1);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .e-type {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .del {
    opacity: 0;
  }
  .entity:hover .del {
    opacity: 1;
  }
  .suggest-note {
    font-size: var(--fs-xs);
    color: var(--accent);
    padding: 2px 8px 6px;
  }
  .none {
    font-size: var(--fs-xs);
    color: var(--text-3);
    padding: 4px 8px 12px;
  }
</style>
