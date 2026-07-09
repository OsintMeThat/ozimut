<script>
  import { quadMatrix3d } from '../../lib/inspect.js';
  import Icon from '../../components/Icon.svelte';

  // Interactive collage surface. Each node is a tray frame placed as a 4-point
  // quad (canvas pixels). Drag the body to move all four corners together; drag a
  // corner handle to warp — a hand-made panorama. The same quads are sent to the
  // backend, which renders the full-res warp with PIL (see compose_perspective).
  let { session, selectedId = $bindable() } = $props();

  let wrapEl = $state();
  let availW = $state(800);
  let availH = $state(600);

  const cw = $derived(session.collage.width);
  const ch = $derived(session.collage.height);
  const scale = $derived(Math.min(availW / cw, availH / ch, 1) || 1);

  function boxOf(node) {
    return { w: node.w || 320, h: node.h || 240, url: node.url };
  }

  // client px -> canvas px (the inner surface is scaled with transform-origin 0 0)
  function toCanvas(e) {
    const r = wrapEl.getBoundingClientRect();
    return [(e.clientX - r.left) / scale, (e.clientY - r.top) / scale];
  }

  function startMove(e, node) {
    e.preventDefault();
    selectedId = node.id;
    let [px, py] = toCanvas(e);
    const move = (ev) => {
      const [nx, ny] = toCanvas(ev);
      const dx = nx - px;
      const dy = ny - py;
      node.quad = node.quad.map(([x, y]) => [x + dx, y + dy]);
      px = nx;
      py = ny;
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }

  function startWarp(e, node, corner) {
    e.preventDefault();
    e.stopPropagation();
    selectedId = node.id;
    const move = (ev) => {
      node.quad[corner] = toCanvas(ev);
      node.quad = [...node.quad];
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="wrap"
  bind:this={wrapEl}
  bind:clientWidth={availW}
  bind:clientHeight={availH}
  onpointerdown={() => (selectedId = null)}
>
  <div
    class="surface"
    class:checker={session.collage.transparent}
    style:width={`${cw}px`}
    style:height={`${ch}px`}
    style:transform={`scale(${scale})`}
    style:background={session.collage.transparent ? null : session.collage.background}
  >
    {#each session.collage.nodes as node (node.id)}
      {@const box = boxOf(node)}
      <img
        class="node"
        class:selected={node.id === selectedId}
        src={box.url}
        alt="collage piece"
        style:width={`${box.w}px`}
        style:height={`${box.h}px`}
        style:transform={quadMatrix3d(box.w, box.h, node.quad)}
        draggable="false"
        onpointerdown={(e) => (e.stopPropagation(), startMove(e, node))}
      />
      {#if node.id === selectedId}
        {#each node.quad as pt, i (i)}
          <button
            class="handle"
            style:left={`${pt[0]}px`}
            style:top={`${pt[1]}px`}
            style:width={`${16 / scale}px`}
            style:height={`${16 / scale}px`}
            onpointerdown={(e) => startWarp(e, node, i)}
            aria-label={`Warp corner ${i + 1}`}
          ></button>
        {/each}
      {/if}
    {/each}
  </div>

  {#if session.collage.nodes.length === 0}
    <div class="empty">
      <Icon name="layers" size={34} />
      <p>Add frames from the menu, then drag to move and pull the corners to warp.</p>
    </div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
    overflow: hidden;
  }
  .surface {
    position: relative;
    transform-origin: 0 0;
    box-shadow: var(--shadow-2);
    flex-shrink: 0;
  }
  /* transparent canvas: a checkerboard shows what alpha will be exported */
  .surface.checker {
    background-color: #2a2f3a;
    background-image:
      linear-gradient(45deg, rgba(255, 255, 255, 0.07) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.07) 75%),
      linear-gradient(45deg, rgba(255, 255, 255, 0.07) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.07) 75%);
    background-size: 24px 24px;
    background-position: 0 0, 12px 12px;
  }
  .node {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    cursor: move;
    user-select: none;
    outline: 1px solid transparent;
  }
  .node.selected {
    outline: 1px dashed var(--accent);
  }
  .handle {
    position: absolute;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid #10141c;
    cursor: grab;
    padding: 0;
    touch-action: none;
  }
  .empty {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--text-3);
    text-align: center;
    padding: 20px;
    pointer-events: none;
  }
  .empty p {
    max-width: 260px;
    font-size: var(--fs-sm);
  }
</style>
