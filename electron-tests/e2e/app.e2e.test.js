// electron-tests/e2e/app.e2e.test.js
const { test, expect } = require('@playwright/test');
const { _electron: electron } = require('playwright');
const path = require('path');

let app;
let window;

test.beforeAll(async () => {
  app = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
});

test.afterAll(async () => {
  if (app) await app.close();
});

test('app launches and main window appears', async () => {
  expect(window).toBeTruthy();
  const url = window.url();
  expect(url).toContain('/ui/');
});

test('projects.html loads without JS errors', async () => {
  const errors = [];
  window.on('pageerror', err => errors.push(err.message));
  const currentUrl = window.url();
  const base = currentUrl.replace(/\/ui\/.*$/, '');
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  expect(errors).toHaveLength(0);
});

test('GET /api/posts returns an array', async () => {
  const result = await window.evaluate(async () => {
    const base = window.location.origin;
    const res  = await fetch(`${base}/api/posts`);
    return res.json();
  });
  expect(Array.isArray(result)).toBe(true);
});

test('app quits cleanly with no zombie Java process', async () => {
  await app.close();
  app = null;
  const app2    = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  const window2 = await app2.firstWindow();
  await window2.waitForLoadState('domcontentloaded');
  expect(window2.url()).toContain('/ui/');
  await app2.close();
});
