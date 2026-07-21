<script>
  import Icon from '../../components/Icon.svelte';

  let {
    canUndo,
    canRedo,
    undo,
    redo,
    drawTools,
    tool = $bindable(),
    palette,
    activeColor,
    selectedShape,
    strokeW,
    setColor,
    setStroke,
    fit,
    layout,
    setLayoutMode,
    guide = $bindable(),
    tweetGuides,
    panelCount,
    applyMagic,
  } = $props();
</script>

<div class="toolbar">
  <button class="tb-btn" title="Undo (Ctrl+Z)" disabled={!canUndo} onclick={undo}>
    <Icon name="undo" size={18} />
  </button>
  <button class="tb-btn" title="Redo (Ctrl+Shift+Z / Ctrl+Y)" disabled={!canRedo} onclick={redo}>
    <Icon name="redo" size={18} />
  </button>
  <div class="tb-sep"></div>
  {#each drawTools as entry (entry.id)}
    <button
      class="tb-btn"
      class:active={tool === entry.id}
      title="{entry.label} ({entry.shortcut})"
      onclick={() => (tool = entry.id)}
    >
      <Icon name={entry.icon} size={18} />
    </button>
  {/each}
  <div class="tb-sep"></div>
  {#each palette as entry (entry)}
    <button
      class="color-btn"
      class:active={activeColor === entry}
      style:background={entry}
      title="Same color = same feature"
      onclick={() => setColor(entry)}
      aria-label={`color ${entry}`}
    ></button>
  {/each}
  <label
    class="color-btn color-pick"
    class:active={!palette.includes(activeColor)}
    style:background={activeColor}
    title="Custom color"
  >
    <Icon name="plus" size={12} />
    <input
      type="color"
      value={activeColor}
      oninput={(event) => setColor(event.target.value)}
      aria-label="custom color"
    />
  </label>
  <div class="tb-sep"></div>
  <input
    class="stroke-slider"
    type="range"
    min={selectedShape?.kind === 'text' ? 8 : 1}
    max={selectedShape?.kind === 'text' ? 120 : 24}
    step="1"
    value={selectedShape?.kind === 'text'
      ? (selectedShape.fontSize ?? 28)
      : (selectedShape?.strokeWidth ?? strokeW)}
    oninput={(event) => setStroke(+event.target.value)}
    title={selectedShape?.kind === 'text'
      ? 'Font size'
      : selectedShape
        ? 'Stroke width (selected)'
        : 'Stroke width'}
  />
  <div class="tb-sep"></div>
  <button class="tb-btn" title="Fit view (f)" onclick={fit}>
    <Icon name="eye" size={18} />
  </button>
  <div class="tb-sep"></div>
  <button
    class="tb-btn"
    class:active={layout !== 'free'}
    title="Grid layout: panels flow in rows"
    onclick={() => setLayoutMode('grid')}
  >
    <Icon name="grid" size={18} />
  </button>
  <button
    class="tb-btn"
    class:active={layout === 'free'}
    title="Free layout: drag panels anywhere"
    onclick={() => setLayoutMode('free')}
  >
    <Icon name="layers" size={18} />
  </button>
  <div class="tb-sep"></div>
  {#each Object.keys(tweetGuides) as entry (entry)}
    <button
      class="tb-btn tb-guide"
      class:active={guide === entry}
      title={`Preview the ${entry} tweet crop. Everything outside is cut off`}
      onclick={() => (guide = guide === entry ? null : entry)}
    >{entry}</button>
  {/each}
  <button
    class="tb-btn tb-magic"
    title={`Repack panels toward ${guide ?? '16:9'} and reset panel sizes`}
    disabled={!panelCount}
    onclick={applyMagic}
  >
    <Icon name="wand" size={18} />
  </button>
</div>

<style>
  .toolbar {
    width: 52px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 12px 0;
    border-right: 1px solid var(--border);
    background: var(--bg-1);
  }
  .tb-btn {
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--r-sm);
    color: var(--text-3);
  }
  .tb-btn:hover { color: var(--text-1); background: var(--bg-2); }
  .tb-btn.active { color: var(--text-1); background: var(--bg-3); }
  .tb-guide { font-size: 11px; font-weight: 700; }
  .tb-magic:not(:disabled) { color: var(--accent); }
  .tb-magic:not(:disabled):hover { background: var(--accent-soft); }
  .tb-magic:disabled { opacity: 0.4; cursor: default; }
  .tb-sep {
    width: 26px;
    height: 1px;
    background: var(--border);
    margin: 4px 0;
  }
  .color-btn {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid transparent;
    transition: border-color 0.12s var(--ease);
    flex-shrink: 0;
  }
  .color-btn:hover { border-color: var(--text-3); }
  .color-btn.active {
    border-color: var(--text-1);
    box-shadow: 0 0 0 2px var(--bg-1), 0 0 0 3.5px var(--text-3);
  }
  .color-pick {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent-text);
    cursor: pointer;
    position: relative;
    overflow: hidden;
  }
  .color-pick input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }
  .stroke-slider {
    width: 80px;
    transform: rotate(-90deg);
    margin: 34px 0;
    accent-color: var(--accent);
  }
  .tb-btn:disabled { opacity: 0.35; cursor: default; }
  .tb-btn:disabled:hover { color: var(--text-3); background: none; }
</style>
