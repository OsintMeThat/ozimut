/**
 * Pure selection math for the desktop organizer's tile grid — kept out of the
 * component so it's unit-tested without a DOM. The component measures tile
 * rects (getBoundingClientRect) and drives these; nothing here touches the DOM.
 */

/**
 * Ids of tiles whose rect intersects the marquee rectangle. Rects and the
 * marquee are `{id, left, top, right, bottom}` / `{left, top, right, bottom}`
 * in the same coordinate space. Edge contact counts as a hit; a zero-area
 * marquee (a click that never dragged) selects nothing.
 */
export function marqueeHits(rects, marquee) {
  const { left, top, right, bottom } = marquee;
  if (right <= left || bottom <= top) return [];
  return rects
    .filter((r) => r.left <= right && r.right >= left && r.top <= bottom && r.bottom >= top)
    .map((r) => r.id);
}

/** Normalize a drag's two corners into a {left,top,right,bottom} rectangle. */
export function marqueeRect(x0, y0, x1, y1) {
  return {
    left: Math.min(x0, x1),
    top: Math.min(y0, y1),
    right: Math.max(x0, x1),
    bottom: Math.max(y0, y1),
  };
}

/**
 * Next selection after clicking `id`, given the modifier keys and the current
 * visual `order` of ids (used for shift-range).
 *   - meta/ctrl: toggle `id` in/out of the set.
 *   - shift:     select the contiguous range from the anchor to `id`.
 *   - plain:     select just `id`.
 * Returns `{ selected: string[], anchor: string }`; pass the returned anchor
 * back in as `anchor` on the next call.
 */
export function toggleSelection(selected, id, { shift = false, meta = false } = {}, order = [], anchor = null) {
  const set = new Set(selected);
  if (meta) {
    set.has(id) ? set.delete(id) : set.add(id);
    return { selected: [...set], anchor: id };
  }
  if (shift && anchor && order.length) {
    const a = order.indexOf(anchor);
    const b = order.indexOf(id);
    if (a !== -1 && b !== -1) {
      const [lo, hi] = a <= b ? [a, b] : [b, a];
      return { selected: order.slice(lo, hi + 1), anchor };
    }
  }
  return { selected: [id], anchor: id };
}
