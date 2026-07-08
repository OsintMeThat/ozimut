<script>
  import {
    caseState,
    refreshCaseList,
    openCase,
    createCase,
    promoteCase,
    closeCase,
    toast,
  } from '../lib/state.svelte.js';
  import Icon from './Icon.svelte';
  import Modal from './Modal.svelte';

  let open = $state(false);
  let modal = $state(null); // 'create' | 'promote' | null
  let nameInput = $state('');
  let busy = $state(false);

  async function toggle() {
    open = !open;
    if (open) await refreshCaseList();
  }

  async function pick(id) {
    open = false;
    await openCase(id);
  }

  async function submit() {
    if (!nameInput.trim() || busy) return;
    busy = true;
    try {
      if (modal === 'create') {
        await createCase(nameInput.trim());
        toast(`Case “${nameInput.trim()}” created`, 'ok');
      } else if (modal === 'promote') {
        await promoteCase(nameInput.trim());
      }
      modal = null;
      nameInput = '';
    } catch (e) {
      toast(e.message, 'danger');
    } finally {
      busy = false;
    }
  }

  const named = $derived(caseState.list.filter((c) => !c.scratch));
  const scratches = $derived(caseState.list.filter((c) => c.scratch));
</script>

<div class="switcher">
  <button class="current" onclick={toggle} title="Switch case">
    <Icon name={caseState.current ? 'folderOpen' : 'folder'} size={16} />
    {#if caseState.current}
      <span class="name">{caseState.current.name}</span>
      {#if caseState.current.scratch}<span class="badge accent">scratch</span>{/if}
    {:else}
      <span class="name none">No case — one-shot mode</span>
    {/if}
    <Icon name="chevronDown" size={14} />
  </button>

  {#if caseState.current?.scratch}
    <button
      class="btn btn-primary btn-sm"
      onclick={() => {
        modal = 'promote';
        nameInput = '';
      }}
    >
      <Icon name="upload" size={13} /> Keep as case…
    </button>
  {/if}

  {#if open}
    <button class="backdrop" onclick={() => (open = false)} aria-label="Close menu"></button>
    <div class="menu card fade-up">
      <button
        class="item new"
        onclick={() => {
          open = false;
          modal = 'create';
          nameInput = '';
        }}
      >
        <Icon name="plus" size={15} /> New case…
      </button>
      {#if caseState.current}
        <button class="item" onclick={() => { closeCase(); open = false; }}>
          <Icon name="x" size={15} /> Close case (one-shot mode)
        </button>
      {/if}
      {#if named.length}
        <div class="section">Cases</div>
        {#each named as c (c.id)}
          <button class="item" class:active={c.id === caseState.current?.id} onclick={() => pick(c.id)}>
            <Icon name="folder" size={15} />
            <span class="grow">{c.name}</span>
            <span class="meta">{c.entity_count} entities</span>
          </button>
        {/each}
      {/if}
      {#if scratches.length}
        <div class="section">Scratch sessions</div>
        {#each scratches as c (c.id)}
          <button class="item" class:active={c.id === caseState.current?.id} onclick={() => pick(c.id)}>
            <Icon name="clock" size={15} />
            <span class="grow">{c.id}</span>
          </button>
        {/each}
      {/if}
      {#if !named.length && !scratches.length}
        <div class="hint">No cases yet — tools work without one.</div>
      {/if}
    </div>
  {/if}
</div>

{#if modal}
  <Modal
    title={modal === 'create' ? 'New case' : 'Keep this session as a case'}
    onclose={() => (modal = null)}
  >
    <form
      onsubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label class="label" for="case-name">Case name</label>
      <!-- svelte-ignore a11y_autofocus -->
      <input
        id="case-name"
        class="input"
        placeholder="e.g. Kharkiv strike — March 2026"
        bind:value={nameInput}
        autofocus
      />
      <div class="actions">
        <button type="button" class="btn" onclick={() => (modal = null)}>Cancel</button>
        <button type="submit" class="btn btn-primary" disabled={!nameInput.trim() || busy}>
          {modal === 'create' ? 'Create' : 'Promote'}
        </button>
      </div>
    </form>
  </Modal>
{/if}

<style>
  .switcher {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .current {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: var(--r-sm);
    color: var(--text-1);
    font-size: var(--fs-sm);
    font-weight: 600;
    border: 1px solid transparent;
    max-width: 380px;
  }
  .current:hover {
    background: var(--bg-2);
    border-color: var(--border);
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .name.none {
    color: var(--text-3);
    font-weight: 500;
  }
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 90;
    cursor: default;
  }
  .menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    min-width: 300px;
    max-height: 420px;
    overflow: auto;
    z-index: 100;
    box-shadow: var(--shadow-2);
    padding: 6px;
  }
  .section {
    font-size: var(--fs-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--text-3);
    padding: 10px 10px 4px;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 100%;
    padding: 8px 10px;
    border-radius: var(--r-sm);
    font-size: var(--fs-sm);
    color: var(--text-1);
    text-align: left;
  }
  .item:hover {
    background: var(--bg-2);
  }
  .item.active {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .item.new {
    color: var(--accent);
    font-weight: 600;
  }
  .grow {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }
  .hint {
    padding: 14px 10px;
    color: var(--text-3);
    font-size: var(--fs-sm);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
</style>
