<script>
  import Icon from './Icon.svelte';
  import { portal } from '../lib/fullscreen.js';

  // A small, styled confirmation dialog — replaces the browser confirm() popup.
  // Tone drives the accent so a destructive action reads differently from a
  // reversible one.
  //   tone: 'danger'  → deletes everywhere (irreversible, drops files)
  //   tone: 'default' → reversible (unfile, remove a folder)
  let {
    title,
    message,
    detail = '',
    confirmLabel = 'Confirm',
    tone = 'default', // 'danger' | 'default'
    icon = tone === 'danger' ? 'trash' : 'folderMinus',
    busy = false,
    onconfirm,
    oncancel,
  } = $props();

  function onkeydown(e) {
    if (e.key === 'Escape') oncancel?.();
    else if (e.key === 'Enter') onconfirm?.();
  }
</script>

<svelte:window {onkeydown} />

<div
  class="overlay"
  use:portal
  onclick={(e) => e.target === e.currentTarget && oncancel?.()}
  role="presentation"
>
  <div class="dialog" class:danger={tone === 'danger'} role="alertdialog" aria-label={title}>
    <div class="head">
      <span class="badge" class:danger={tone === 'danger'}>
        <Icon name={icon} size={18} />
      </span>
      <div class="titles">
        <h3>{title}</h3>
        <p class="msg">{message}</p>
      </div>
    </div>
    {#if detail}
      <p class="detail" class:danger={tone === 'danger'}>{detail}</p>
    {/if}
    <div class="actions">
      <button class="btn" onclick={oncancel} disabled={busy}>Cancel</button>
      <button
        class="btn {tone === 'danger' ? 'btn-danger' : 'btn-primary'}"
        onclick={onconfirm}
        disabled={busy}
      >
        {busy ? 'Working…' : confirmLabel}
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(4, 7, 12, 0.72);
    backdrop-filter: blur(3px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 950;
  }
  .dialog {
    background: var(--bg-1);
    border: 1px solid var(--border-strong);
    border-top: 3px solid var(--accent);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-2);
    width: 400px;
    max-width: calc(100vw - 40px);
    padding: 18px 18px 14px;
  }
  .dialog.danger {
    border-top-color: var(--danger, #e5484d);
  }
  .head {
    display: flex;
    gap: 13px;
    align-items: flex-start;
  }
  .badge {
    flex-shrink: 0;
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--r-md);
    background: var(--bg-2);
    color: var(--text-2);
  }
  .badge.danger {
    background: color-mix(in srgb, var(--danger, #e5484d) 16%, transparent);
    color: var(--danger, #e5484d);
  }
  .titles { min-width: 0; }
  h3 {
    font-size: var(--fs-md);
    font-weight: 700;
    margin-bottom: 3px;
  }
  .msg {
    font-size: var(--fs-sm);
    color: var(--text-2);
    line-height: 1.4;
  }
  .detail {
    font-size: var(--fs-xs);
    color: var(--text-3);
    margin: 12px 0 0;
    padding: 8px 10px;
    background: var(--bg-2);
    border-radius: var(--r-sm);
    line-height: 1.45;
  }
  .detail.danger {
    color: color-mix(in srgb, var(--danger, #e5484d) 85%, var(--text-2));
    background: color-mix(in srgb, var(--danger, #e5484d) 9%, transparent);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }
  .btn-danger {
    background: var(--danger, #e5484d);
    color: #fff;
    border-color: transparent;
  }
  .btn-danger:hover { filter: brightness(1.08); }
</style>
