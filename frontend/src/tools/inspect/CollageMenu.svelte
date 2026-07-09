<script>
  import { previewStyle } from '../../lib/inspect.js';
  import Icon from '../../components/Icon.svelte';

  // Right-panel menu for the Collage tab: add tray frames to the canvas, set the
  // canvas size/background, and act on the selected piece. The layout stays in
  // session.collage until the Save tab commits it to a single flattened image.
  // Each added piece is a frozen snapshot of the frame's current look (addToCollage).
  let { session, filters, selectedId = $bindable(), addToCollage } = $props();

  const onCanvas = (id) => session.collage.nodes.some((n) => n.frameId === id);
  const selected = $derived(session.collage.nodes.find((n) => n.id === selectedId) ?? null);

  function removeNode(id) {
    session.collage.nodes = session.collage.nodes.filter((n) => n.id !== id);
    if (selectedId === id) selectedId = null;
  }

  function bringFront(id) {
    const i = session.collage.nodes.findIndex((n) => n.id === id);
    if (i !== -1) session.collage.nodes.push(session.collage.nodes.splice(i, 1)[0]);
  }

  function resetWarp(node) {
    const xs = node.quad.map((p) => p[0]);
    const ys = node.quad.map((p) => p[1]);
    const x0 = Math.min(...xs);
    const y0 = Math.min(...ys);
    const x1 = Math.max(...xs);
    const y1 = Math.max(...ys);
    node.quad = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  }
</script>

<div class="module">
  <p class="hint">Pieces are the frames you captured. Add them, drag to arrange, pull corners to warp into a panorama.</p>

  <div class="section">
    <div class="section-head"><span>Frames</span></div>
    <div class="grid">
      {#each session.frames as fr (fr.id)}
        {@const look = previewStyle(filters, fr.adjust)}
        <button class="tile" class:used={onCanvas(fr.id)} onclick={() => addToCollage(fr)} title={onCanvas(fr.id) ? 'Add again (fresh snapshot)' : 'Add to canvas'}>
          <img src={fr.url} alt="frame" style:filter={look.filter} style:transform={look.transform} />
          <span class="add"><Icon name="plus" size={12} /></span>
        </button>
      {/each}
    </div>
    {#if session.frames.length === 0}<p class="empty">No frames captured yet.</p>{/if}
  </div>

  <div class="section">
    <div class="section-head"><span>Canvas</span></div>
    <div class="controls">
      <label>Width <input type="number" min="16" max="8192" step="20" bind:value={session.collage.width} /></label>
      <label>Height <input type="number" min="16" max="8192" step="20" bind:value={session.collage.height} /></label>
      <label class="bg">Fill <input type="color" bind:value={session.collage.background} disabled={session.collage.transparent} /></label>
    </div>
    <label class="check">
      <input type="checkbox" bind:checked={session.collage.transparent} />
      Transparent canvas <span class="sub">— export only the pieces (PNG alpha)</span>
    </label>
  </div>

  {#if selected}
    <div class="section">
      <div class="section-head"><span>Selected piece</span></div>
      <div class="actions">
        <button class="btn btn-sm" onclick={() => bringFront(selected.id)}><Icon name="layers" size={13} /> Front</button>
        <button class="btn btn-sm" onclick={() => resetWarp(selected)}><Icon name="reset" size={13} /> Unwarp</button>
        <button class="btn btn-sm danger" onclick={() => removeNode(selected.id)}><Icon name="trash" size={13} /> Remove</button>
      </div>
    </div>
  {/if}

  <button class="btn btn-sm w-full" disabled title="Automatic stitching is coming soon">
    <Icon name="hash" size={14} /> Auto panorama (coming soon)
  </button>
</div>

<style>
  .module {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .hint,
  .empty {
    color: var(--text-3);
    font-size: var(--fs-xs);
    margin: 0;
  }
  .section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .section + .section {
    border-top: 1px solid var(--border);
    padding-top: 12px;
  }
  .section-head {
    font-weight: 600;
    font-size: var(--fs-sm);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    max-height: 200px;
    overflow: auto;
  }
  .tile {
    position: relative;
    aspect-ratio: 1;
    border-radius: var(--r-sm);
    overflow: hidden;
    border: 2px solid transparent;
    padding: 0;
  }
  .tile.used {
    border-color: var(--border-strong);
  }
  .tile img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .tile .add {
    position: absolute;
    bottom: 3px;
    right: 3px;
    background: var(--accent);
    color: #10141c;
    border-radius: 4px;
    display: flex;
    padding: 1px;
  }
  .controls {
    display: flex;
    gap: 8px;
  }
  .controls label {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: var(--fs-xs);
    color: var(--text-3);
    flex: 1;
  }
  .controls input[type='number'] {
    width: 100%;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    padding: 4px 6px;
    color: var(--text-1);
    font-size: var(--fs-sm);
  }
  .controls .bg input {
    height: 28px;
    padding: 0;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
  }
  .controls .bg input:disabled {
    opacity: 0.4;
  }
  .check {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-xs);
    color: var(--text-2);
    cursor: pointer;
  }
  .check .sub {
    color: var(--text-3);
  }
  .actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .danger {
    color: var(--danger, #d86a6a);
  }
  .w-full {
    width: 100%;
    justify-content: center;
  }
</style>
