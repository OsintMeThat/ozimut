<script>
  import { uiState } from '../lib/state.svelte.js';
  import Icon from './Icon.svelte';

  const icons = { info: 'compass', ok: 'check', danger: 'alert', warn: 'alert' };
</script>

<div class="toasts">
  {#each uiState.toasts as t (t.id)}
    <div class="toast {t.kind} fade-up">
      <Icon name={icons[t.kind] ?? 'compass'} size={15} />
      <span>{t.message}</span>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    bottom: 18px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    z-index: 1000;
    pointer-events: none;
  }
  .toast {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 16px;
    border-radius: var(--r-md);
    background: var(--bg-2);
    border: 1px solid var(--border-strong);
    box-shadow: var(--shadow-2);
    font-size: var(--fs-sm);
    font-weight: 500;
    max-width: 480px;
  }
  .toast.ok {
    border-color: var(--ok);
    color: var(--ok);
  }
  .toast.danger {
    border-color: var(--danger);
    color: var(--danger);
  }
  .toast.warn {
    border-color: var(--warn);
    color: var(--warn);
  }
</style>
