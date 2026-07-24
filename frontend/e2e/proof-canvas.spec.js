import { test, expect } from '@playwright/test';
import { installAppFixture, openProofWithPanel } from './app.fixture.js';

test('a real Konva panel remains interactive after click and drag', async ({ page }) => {
  const fixture = await installAppFixture(page);
  await openProofWithPanel(page);

  const canvas = page.locator('.konva canvas').first();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  // The stage fills the full tool height while the fitted 16:9 panel sits near
  // its top. Use a point well inside that image, away from its footer.
  const x = box.x + box.width / 2;
  const y = box.y + Math.min(180, box.height / 3);

  await page.mouse.click(x, y);
  await expect(page.locator('.panel-row')).toHaveClass(/selected/);

  // Layout modes now live in the toolbar's overflow flyout; open it first.
  await page.getByTitle('Layout, tweet crops & repack').click();
  await page.getByTitle('Free layout: drag panels anywhere').click();
  // Changing layout intentionally clears selection. The first click above
  // covers the canvas selection regression; use the deterministic side control
  // to select the panel for the separate free-layout drag assertion.
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  await page.locator('.panel-thumb').click();
  await expect(page.locator('.panel-row')).toHaveClass(/selected/);
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 45, y + 28, { steps: 6 });
  await page.mouse.up();

  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => fixture.proofSaves.length).toBe(1);
  const savedPanel = fixture.proofSaves[0].spec.panels[0];
  expect(Number.isFinite(savedPanel.x)).toBe(true);
  expect(Number.isFinite(savedPanel.y)).toBe(true);
  fixture.expectNoUnexpectedRequests();
});

test('draws a real Konva annotation and round-trips undo and redo', async ({ page }) => {
  const fixture = await installAppFixture(page);
  await openProofWithPanel(page);

  const canvas = page.locator('.konva canvas').first();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  const x = box.x + box.width / 2 - 40;
  const y = box.y + box.height / 2 - 25;

  await page.getByTitle('Box (r)').click();
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + 90, y + 65, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator('.shape-row')).toHaveCount(1);

  await page.getByTitle('Undo (Ctrl+Z)').click();
  await expect(page.locator('.shape-row')).toHaveCount(0);
  await page.getByTitle('Redo (Ctrl+Shift+Z / Ctrl+Y)').click();
  await expect(page.locator('.shape-row')).toHaveCount(1);
  fixture.expectNoUnexpectedRequests();
});

test('a picked colour becomes the default for the next drawn shape', async ({ page }) => {
  const fixture = await installAppFixture(page);
  await openProofWithPanel(page);

  const canvas = page.locator('.konva canvas').first();
  const box = await canvas.boundingBox();
  // Same panel region the plain draw test uses, split into two small boxes.
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;

  await page.getByTitle('Box (r)').click();

  // First box: drawn with the default colour, then auto-selected.
  await page.mouse.move(cx - 38, cy - 20);
  await page.mouse.down();
  await page.mouse.move(cx - 8, cy + 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator('.shape-row')).toHaveCount(1);

  // Pick a new colour while that first box is still selected.
  await page.getByTitle('Annotation colour').click();
  await page.getByLabel('color #40c4ff').click();

  // Second box: should inherit the colour just picked, not the old default.
  await page.mouse.move(cx + 8, cy - 20);
  await page.mouse.down();
  await page.mouse.move(cx + 45, cy + 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator('.shape-row')).toHaveCount(2);

  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => fixture.proofSaves.length).toBe(1);
  const shapes = fixture.proofSaves[0].spec.shapes;
  expect(shapes[1].color).toBe('#40c4ff');
  fixture.expectNoUnexpectedRequests();
});

test('a picked stroke width becomes the default for the next drawn shape', async ({ page }) => {
  const fixture = await installAppFixture(page);
  await openProofWithPanel(page);

  const canvas = page.locator('.konva canvas').first();
  const box = await canvas.boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;

  await page.getByTitle('Box (r)').click();

  await page.mouse.move(cx - 38, cy - 20);
  await page.mouse.down();
  await page.mouse.move(cx - 8, cy + 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator('.shape-row')).toHaveCount(1);

  // Change the stroke width while the first box is still selected.
  await page.getByTitle('Stroke width', { exact: true }).click();
  await page.locator('.stroke-slider').fill('11');

  await page.mouse.move(cx + 8, cy - 20);
  await page.mouse.down();
  await page.mouse.move(cx + 45, cy + 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.locator('.shape-row')).toHaveCount(2);

  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => fixture.proofSaves.length).toBe(1);
  const shapes = fixture.proofSaves[0].spec.shapes;
  expect(shapes[1].strokeWidth).toBe(11);
  fixture.expectNoUnexpectedRequests();
});

test('the layout overflow flyout opens and closes on outside click', async ({ page }) => {
  const fixture = await installAppFixture(page);
  await openProofWithPanel(page);

  const freeBtn = page.getByTitle('Free layout: drag panels anywhere');
  // Collapsed by default: the control is in the DOM but not shown.
  await expect(freeBtn).toBeHidden();

  await page.getByTitle('Layout, tweet crops & repack').click();
  await expect(freeBtn).toBeVisible();

  // A click anywhere outside the flyout dismisses it.
  const canvas = page.locator('.konva canvas').first();
  const box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(freeBtn).toBeHidden();
  fixture.expectNoUnexpectedRequests();
});
