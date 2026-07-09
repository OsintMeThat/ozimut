/**
 * Inspect-session helpers, shared by the Selection / Frame / Collage / Save tabs.
 *
 * The Inspect tool is a scratch workspace: captured frames, per-frame adjustments
 * and a collage layout live here as plain data ("recipes") and only become case
 * media on an explicit Save. These pure helpers turn slider values into the live
 * CSS preview + the backend op pipeline, and handle the collage perspective math.
 */

// Order the adjust pipeline is applied in (matches the backend ORDER in bake()).
export const ADJUST_ORDER = [
  'brightness', 'contrast', 'saturation', 'gamma', 'sharpness', 'rotate', 'grayscale', 'invert',
];

let _seq = 0;
export const uid = (prefix = 'id') => `${prefix}_${Date.now().toString(36)}_${_seq++}`;

export function adjustDefaults(filters) {
  const out = {};
  for (const f of filters) out[f.id] = f.params[0]?.default ?? 0;
  return out;
}

// The video gear only exposes these css-filter ids; a frame captured from a
// tuned video inherits them so it looks like it came from the modified clip.
export const VIDEO_ADJUST_IDS = ['brightness', 'contrast', 'saturation', 'gamma', 'grayscale', 'invert'];

/** Seed a new frame's adjust values from the current video-gear values. */
export function videoSeed(filters, videoAdjust) {
  const out = adjustDefaults(filters);
  for (const id of VIDEO_ADJUST_IDS) {
    if (videoAdjust && id in videoAdjust) out[id] = videoAdjust[id];
  }
  return out;
}

const paramName = (f) => f.params[0]?.name ?? 'amount';
const defaultOf = (f) => f.params[0]?.default ?? 0;

/** Build the live-preview CSS `filter` + `transform` strings from slider values. */
export function previewStyle(filters, values) {
  values = values ?? {};
  const pick = (getter) =>
    filters
      .filter(getter)
      .map((f) => getter(f).replaceAll('{v}', values[f.id] ?? defaultOf(f)))
      .join(' ');
  return {
    filter: pick((f) => f.css),
    transform: pick((f) => f.transform),
  };
}

export function isNeutral(filters, values) {
  values = values ?? {};
  return filters.every((f) => (values[f.id] ?? defaultOf(f)) === defaultOf(f));
}

/** Turn slider values (+ optional fractional crop) into the backend op pipeline. */
export function buildOps(filters, values, crop = null) {
  values = values ?? {};
  const ops = [];
  if (crop) ops.push({ op: 'crop', params: crop });
  for (const id of ADJUST_ORDER) {
    const f = filters.find((x) => x.id === id);
    if (!f || (values[id] ?? defaultOf(f)) === defaultOf(f)) continue;
    ops.push({ op: id, params: { [paramName(f)]: values[id] } });
  }
  return ops;
}

// ---------------------------------------------------------------------------
// Collage perspective: map an image's box to a 4-point quad via a CSS matrix3d.
// Classic homography-from-4-corners (general 2D projection). The same quad is
// sent to the backend, which composites the full-res warp with PIL — so the
// on-screen preview and the saved image agree.
// ---------------------------------------------------------------------------

function adj(m) {
  return [
    m[4] * m[8] - m[5] * m[7], m[2] * m[7] - m[1] * m[8], m[1] * m[5] - m[2] * m[4],
    m[5] * m[6] - m[3] * m[8], m[0] * m[8] - m[2] * m[6], m[2] * m[3] - m[0] * m[5],
    m[3] * m[7] - m[4] * m[6], m[1] * m[6] - m[0] * m[7], m[0] * m[4] - m[1] * m[3],
  ];
}

function mul(a, b) {
  const c = new Array(9);
  for (let i = 0; i < 3; i++)
    for (let j = 0; j < 3; j++)
      c[3 * i + j] = a[3 * i] * b[j] + a[3 * i + 1] * b[3 + j] + a[3 * i + 2] * b[6 + j];
  return c;
}

function mulV(m, v) {
  return [
    m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
    m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
    m[6] * v[0] + m[7] * v[1] + m[8] * v[2],
  ];
}

function basisToPoints(p) {
  const m = [p[0][0], p[1][0], p[2][0], p[0][1], p[1][1], p[2][1], 1, 1, 1];
  const v = mulV(adj(m), [p[3][0], p[3][1], 1]);
  return mul(m, [v[0], 0, 0, 0, v[1], 0, 0, 0, v[2]]);
}

/**
 * CSS `matrix3d(...)` mapping the box (0,0)-(w,h) onto `quad`
 * (4 points: TL, TR, BR, BL, in the same pixel space as the element's parent).
 */
export function quadMatrix3d(w, h, quad) {
  const src = [[0, 0], [w, 0], [w, h], [0, h]];
  let H = mul(basisToPoints(quad), adj(basisToPoints(src)));
  H = H.map((x) => x / H[8]);
  const t = [
    H[0], H[3], 0, H[6],
    H[1], H[4], 0, H[7],
    0, 0, 1, 0,
    H[2], H[5], 0, H[8],
  ];
  return `matrix3d(${t.join(',')})`;
}

/** A sensible starting quad: the image scaled to fit `maxW`, placed at (ox, oy). */
export function initialQuad(natW, natH, maxW, ox, oy) {
  const scale = Math.min(1, maxW / (natW || maxW));
  const w = Math.round((natW || maxW) * scale);
  const h = Math.round((natH || maxW) * scale);
  return [
    [ox, oy],
    [ox + w, oy],
    [ox + w, oy + h],
    [ox, oy + h],
  ];
}
