<script>
  import { quadMatrix3d } from '../../lib/inspect.js';

  // Read-only miniature of a collage layout — the same node quads/urls the Save
  // tab will composite, scaled to fit its container. Used for the Save gallery
  // thumbnail so a collage no longer shows an empty placeholder.
  let { collage } = $props();

  let availW = $state(150);
  let availH = $state(112);

  const cw = $derived(collage.width || 1);
  const ch = $derived(collage.height || 1);
  const scale = $derived(Math.min(availW / cw, availH / ch) || 0);
  const boxOf = (n) => ({ w: n.w || 320, h: n.h || 240, url: n.url });
</script>

<div class="prev" bind:clientWidth={availW} bind:clientHeight={availH}>
  <div
    class="surface"
    class:checker={collage.transparent}
    style:width={`${cw}px`}
    style:height={`${ch}px`}
    style:transform={`scale(${scale})`}
    style:background={collage.transparent ? null : collage.background}
  >
    {#each collage.nodes as node (node.id)}
      {@const box = boxOf(node)}
      <img
        class="node"
        src={box.url}
        alt="collage piece"
        style:width={`${box.w}px`}
        style:height={`${box.h}px`}
        style:transform={quadMatrix3d(box.w, box.h, node.quad)}
        draggable="false"
      />
    {/each}
  </div>
</div>

<style>
  .prev {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  .surface {
    position: relative;
    transform-origin: center;
    flex-shrink: 0;
  }
  .surface.checker {
    background-color: #2a2f3a;
    background-image:
      linear-gradient(45deg, rgba(255, 255, 255, 0.07) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.07) 75%),
      linear-gradient(45deg, rgba(255, 255, 255, 0.07) 25%, transparent 25%, transparent 75%, rgba(255, 255, 255, 0.07) 75%);
    background-size: 16px 16px;
    background-position: 0 0, 8px 8px;
  }
  .node {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    user-select: none;
  }
</style>
