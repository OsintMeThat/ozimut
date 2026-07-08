<script>
  import Icon from './Icon.svelte';

  let { title, onclose, width = '440px', children } = $props();

  function onkeydown(e) {
    if (e.key === 'Escape') onclose?.();
  }
</script>

<svelte:window {onkeydown} />

<div class="overlay" onclick={(e) => e.target === e.currentTarget && onclose?.()} role="presentation">
  <div class="modal fade-up" style:width role="dialog" aria-label={title}>
    <header>
      <h3>{title}</h3>
      <button class="btn btn-ghost btn-sm" onclick={onclose} aria-label="Close">
        <Icon name="x" size={15} />
      </button>
    </header>
    <div class="content">
      {@render children?.()}
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
    z-index: 900;
  }
  .modal {
    background: var(--bg-1);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-2);
    max-width: calc(100vw - 40px);
    max-height: calc(100vh - 80px);
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px 10px;
  }
  h3 {
    font-size: var(--fs-lg);
    font-weight: 700;
  }
  .content {
    padding: 4px 18px 18px;
    overflow: auto;
  }
</style>
