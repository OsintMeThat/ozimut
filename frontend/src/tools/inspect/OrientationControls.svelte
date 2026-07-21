<script>
  import { RIGHT_ANGLE_ROTATIONS } from '../../lib/inspect.js';

  let { value = 0, disabled = false, onchange, hint } = $props();
</script>

<div class="rotation-options">
  {#each RIGHT_ANGLE_ROTATIONS as angle (angle)}
    <button
      class="btn btn-sm"
      class:active={value === angle}
      aria-pressed={value === angle}
      {disabled}
      onclick={() => onchange(angle)}
    >
      {angle > 0 ? '+' : ''}{angle}°
    </button>
  {/each}
</div>
{#if hint}<p class="hint">{hint}</p>{/if}

<style>
  .rotation-options {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
  }
  .hint {
    color: var(--text-3);
    font-size: var(--fs-xs);
    margin: 0;
  }
</style>
