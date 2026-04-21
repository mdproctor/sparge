// electron-tests/e2e/refine.e2e.test.js
const { test, expect } = require('@playwright/test');
const { _electron: electron } = require('playwright');
const path = require('path');

let app;
let window;

async function api(method, endpoint, body = null) {
  const base = new URL(window.url()).origin;
  return window.evaluate(async ({ method, url, body }) => {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const text = await res.text();
    try { return { status: res.status, body: JSON.parse(text) }; }
    catch { return { status: res.status, body: text }; }
  }, { method, url: `${base}${endpoint}`, body });
}

test.beforeAll(async () => {
  app = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
  await window.waitForTimeout(3000); // wait for Java server to start
});

test.afterAll(async () => {
  if (app) await app.close();
});

// ── API contract tests ─────────────────────────────────────────────────────────

test('GET /api/posts/nonexistent/refine returns 404', async () => {
  const r = await api('GET', '/api/posts/nonexistent-slug-xyz/refine');
  expect(r.status).toBe(404);
});

test('POST /api/posts/nonexistent/refine returns 404', async () => {
  const r = await api('POST', '/api/posts/nonexistent-slug-xyz/refine',
    { accepted_checks: [] });
  expect(r.status).toBe(404);
});

test('POST /api/posts/nonexistent/refine/accept returns 404', async () => {
  const r = await api('POST', '/api/posts/nonexistent-slug-xyz/refine/accept',
    { accepted: [] });
  expect(r.status).toBe(404);
});

test('GET /api/posts/nonexistent/md-raw returns 404', async () => {
  const r = await api('GET', '/api/posts/nonexistent-slug-xyz/md-raw');
  expect(r.status).toBe(404);
});

// ── UI structure tests ─────────────────────────────────────────────────────────

test('refine panel is hidden on launch', async () => {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/index.html`);
  await window.waitForLoadState('domcontentloaded');

  const panel = window.locator('#refine-panel');
  await expect(panel).toBeAttached();
  await expect(panel).not.toBeVisible();
});

test('pipeline toggle button is attached to the DOM', async () => {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/index.html`);
  await window.waitForLoadState('domcontentloaded');

  // Button exists in the DOM and starts with display:none inline style.
  // Visibility depends on whether the active project has MD-generated posts,
  // so we only verify the element is attached, not its runtime visibility.
  const btn = window.locator('#btn-pipeline');
  await expect(btn).toBeAttached();
});

test('accept refined button is hidden on launch', async () => {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/index.html`);
  await window.waitForLoadState('domcontentloaded');

  await expect(window.locator('#btn-accept-refined')).not.toBeVisible();
});

test('suggestion list container is attached', async () => {
  // window is already on index.html from the previous test
  await expect(window.locator('#refine-suggestion-list')).toBeAttached();
});

test('add-all and remove-all buttons are attached', async () => {
  // window is already on index.html from the previous test
  await expect(window.locator('#btn-add-all')).toBeAttached();
  await expect(window.locator('#btn-remove-all')).toBeAttached();
});

// ── Regression test: white screen bug ─────────────────────────────────────────
// (ensure refine panel additions didn't break the main UI)

test('main UI still loads projects page correctly after refine panel additions', async () => {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  await expect(window.locator('#topbar')).toBeVisible({ timeout: 5000 });
  await expect(window.locator('#logo-name')).toHaveText('Sparge');
  await expect(window.locator('#proj-list')).toBeAttached();
});
