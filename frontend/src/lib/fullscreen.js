// Fullscreen-aware overlays.
//
// The Fullscreen API paints *only* the fullscreen element's subtree, so an
// overlay parked on <body> (modals, confirms, toasts) is simply invisible while
// a tool is fullscreen — the click lands, nothing shows. Reparenting the
// overlay under the current fullscreen element keeps it on screen, and moving
// it back on exit keeps the non-fullscreen case unchanged.

/** The element a viewport-level overlay must be parented to, to be visible. */
export function overlayHost(doc = document) {
  return doc.fullscreenElement ?? doc.body;
}

/**
 * Svelte action: keep `node` parented to the current overlay host, following
 * the browser in and out of fullscreen for as long as the node lives.
 */
export function portal(node, doc = document) {
  let host = null;

  function place() {
    const next = overlayHost(doc);
    if (next && next !== host) {
      host = next;
      host.appendChild(node);
    }
  }

  place();
  doc.addEventListener('fullscreenchange', place);

  return {
    destroy() {
      doc.removeEventListener('fullscreenchange', place);
      node.remove();
    },
  };
}
