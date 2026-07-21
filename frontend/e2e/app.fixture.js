import { expect } from '@playwright/test';

export const CASE_ID = 'browser-test';
export const PANEL_PATH = 'media/panel.svg';

const PANEL_SVG = `
  <svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
    <rect width="640" height="360" fill="#304b65"/>
    <path d="M0 300L180 150L300 250L450 90L640 280V360H0Z" fill="#6c8f55"/>
    <circle cx="520" cy="76" r="34" fill="#f4c95d"/>
  </svg>`;

const TILE_SVG = `
  <svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
    <rect width="256" height="256" fill="#243747"/>
    <path d="M0 190L70 120L140 175L210 80L256 140V256H0Z" fill="#4f7047"/>
  </svg>`;

const media = [{
  path: PANEL_PATH,
  filename: 'panel.svg',
  kind: 'image',
  width: 640,
  height: 360,
  source: { type: 'upload' },
  thumbnail: null,
  folder: '',
  notes: '',
}];

const caseOverview = {
  id: CASE_ID,
  name: 'Browser Test',
  scratch: false,
  entities: [],
  links: [],
  folders: [],
};

const settings = {
  coord_format: 'dd',
  units: 'metric',
  home_view: { lat: 48.8584, lon: 2.2945, zoom: 16 },
  post_mention: '@GeoConfirmed',
  post_target: 'x',
  signature_handle: '',
  update_check_on_start: false,
  update_dismissed_version: '',
  usage: {},
  usage_overrides: {},
  eco_zoom_fallback: true,
  eco_max_zoom: 15,
  free_tier: {},
  month: '2026-07',
};

const providers = [{
  id: 'esri-world-imagery',
  label: 'Esri World Imagery',
  url: 'https://tiles.invalid/{z}/{x}/{y}.png',
  attribution: 'Browser fixture',
  max_zoom: 19,
  tile_size: 256,
  oversample: 1,
  imagery: true,
  capturable: true,
}];

function json(route, body, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

/**
 * Run the real Svelte, Konva and Leaflet code while replacing only Azimut's
 * local API and files with deterministic fixtures. Any unexpected request is
 * recorded so a passing interaction test cannot silently depend on the network.
 */
export async function installAppFixture(page) {
  const unexpected = [];
  const captures = [];
  const proofSaves = [];

  await page.addInitScript((caseId) => {
    localStorage.setItem('azimut:lastCase', caseId);
    localStorage.setItem('azimut:theme', 'dark');
  }, CASE_ID);

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (url.hostname !== '127.0.0.1') {
      unexpected.push(`${request.method()} ${request.url()}`);
      return route.abort('blockedbyclient');
    }

    if (path.startsWith('/@') || path.startsWith('/src/') || path.startsWith('/node_modules/') ||
        path === '/' || path === '/index.html' || path === '/favicon.svg') {
      return route.continue();
    }

    if (path === `/files/${CASE_ID}/${PANEL_PATH}`) {
      return route.fulfill({ contentType: 'image/svg+xml', body: PANEL_SVG });
    }
    if (path.startsWith('/api/tiles/')) {
      return route.fulfill({ contentType: 'image/svg+xml', body: TILE_SVG });
    }
    if (path === '/api/events') {
      return route.fulfill({ contentType: 'text/event-stream', body: '' });
    }
    if (path === '/api/settings/signature.png') {
      return route.fulfill({ status: 404, body: '' });
    }
    if (path === '/api/settings') return json(route, settings);
    if (path === '/api/templates') return json(route, { proof: [], post: [] });
    if (path === '/api/cases') return json(route, [{ ...caseOverview, entity_count: 1 }]);
    if (path === `/api/cases/${CASE_ID}`) return json(route, caseOverview);
    if (path === `/api/cases/${CASE_ID}/media`) return json(route, media);
    if (path === `/api/cases/${CASE_ID}/satellite`) return json(route, []);
    if (path === `/api/cases/${CASE_ID}/notes`) return json(route, { text: '' });
    if (path === `/api/cases/${CASE_ID}/catalog/summary`) {
      return json(route, { total: 1, by_type: { media: 1 }, by_status: { confirmed: 1 }, by_folder: {} });
    }
    if (path === `/api/cases/${CASE_ID}/catalog/entities`) {
      return json(route, { items: [], next_cursor: null });
    }
    if (path === `/api/cases/${CASE_ID}/entities/lookup`) {
      return json(route, { entity: null });
    }
    if (path === '/api/satellite/providers') return json(route, providers);
    if (path === `/api/cases/${CASE_ID}/search-grids`) return json(route, []);
    if (path === '/api/satellite/imagery-date') {
      return json(route, { supported: false, date: null, source: null });
    }
    if (path === `/api/cases/${CASE_ID}/satellite/capture` && request.method() === 'POST') {
      const payload = request.postDataJSON();
      captures.push(payload);
      return json(route, {
        path: `media/capture-${captures.length}.png`,
        title: `Capture ${captures.length}`,
        ...payload,
        provider_label: 'Esri World Imagery',
        attribution: 'Browser fixture',
        fetched_at: '2026-07-21T00:00:00Z',
        tiles_missing: 0,
        tiles_upscaled: 0,
      });
    }
    if (path === `/api/cases/${CASE_ID}/proofs` && request.method() === 'POST') {
      const payload = request.postDataJSON();
      proofSaves.push(payload);
      return json(route, { name: 'browser-proof', png: 'proofs/browser-proof.png' });
    }

    unexpected.push(`${request.method()} ${path}`);
    return json(route, { detail: `Unhandled browser fixture request: ${path}` }, 404);
  });

  return {
    captures,
    proofSaves,
    expectNoUnexpectedRequests: () => expect(unexpected).toEqual([]),
  };
}

export async function openProofWithPanel(page) {
  await page.goto('/#proof');
  await expect(page.getByRole('heading', { name: 'Geo Proof' })).toBeVisible();
  await page.getByRole('button', { name: 'New proof' }).first().click();
  await expect(page.getByRole('heading', { name: 'Create proof' })).toBeVisible();
  await page.locator('.selectable-pick').click();
  await page.getByRole('button', { name: 'Create proof' }).click();
  await expect(page.locator('.konva canvas')).toHaveCount(2);
  await expect(page.locator('.panel-row')).toHaveCount(1);
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
}
