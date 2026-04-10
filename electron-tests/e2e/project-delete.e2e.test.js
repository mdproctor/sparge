// electron-tests/e2e/project-delete.e2e.test.js
// E2E test: project deletion works in the Electron app
const { test, expect } = require('@playwright/test');
const { _electron: electron } = require('playwright');
const path = require('path');
const fs   = require('fs');
const os   = require('os');

let app;
let window;

async function api(method, endpoint, body = null) {
  const base = new URL(window.url()).origin;
  return window.evaluate(async ({ method, url, body }) => {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return { status: res.status, body: await res.json().catch(() => ({})) };
  }, { method, url: `${base}${endpoint}`, body });
}

async function navigateToProjects() {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  await window.waitForTimeout(800);
}

let projectsDir = null;

async function getProjectsDir() {
  if (projectsDir) return projectsDir;
  const r = await api('GET', '/api/config');
  // projects_dir is stored in ~/.sparge/config.json; derive from active project path if available
  projectsDir = path.join(os.homedir(), 'sparge-projects');
  return projectsDir;
}

async function createTestProject(name) {
  const r = await api('POST', '/api/projects', {
    name,
    serve_root: path.join(os.tmpdir(), 'sparge-e2e-test'),
    posts_dir: 'posts',
    assets_dir: 'assets',
    md_dir: 'md',
  });
  expect(r.status).toBe(200);
  return r.body.id;
}

async function deleteTestProject(pid) {
  const r = await api('DELETE', `/api/projects/${pid}`);
  // Also remove the project directory left on disk (API preserves data intentionally)
  const dir = path.join(await getProjectsDir(), pid);
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
  return r;
}

test.beforeAll(async () => {
  app = await electron.launch({ args: [path.join(__dirname, '..', '..', 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
  await window.waitForTimeout(1500);
});

test.afterAll(async () => {
  if (app) await app.close();
});

test('delete button exists with correct data attributes', async () => {
  const pid = await createTestProject('E2E Delete Attribute Test');
  try {
    await navigateToProjects();
    const btn = window.locator(`button.danger[data-id="${pid}"]`);
    await expect(btn).toBeVisible({ timeout: 5000 });
    expect(await btn.getAttribute('data-id')).toBe(pid);
    expect(await btn.getAttribute('data-name')).toBe('E2E Delete Attribute Test');
  } finally {
    await deleteTestProject(pid);
  }
});

test('clicking delete with confirm removes the project card', async () => {
  const pid = await createTestProject('E2E Delete Click Test');
  await navigateToProjects();

  const btn = window.locator(`button.danger[data-id="${pid}"]`);
  await expect(btn).toBeVisible({ timeout: 5000 });

  // Handle the confirm() dialog — accept it
  window.once('dialog', dialog => dialog.accept());

  await btn.click();
  await window.waitForTimeout(800);

  // Project card must be gone
  const remaining = window.locator(`button.danger[data-id="${pid}"]`);
  await expect(remaining).toHaveCount(0, { timeout: 3000 });

  // UI deleted from projects.json; clean up the directory left on disk
  await deleteTestProject(pid);
});

test('confirm dialog cancel does NOT delete the project', async () => {
  const pid = await createTestProject('E2E Delete Cancel Test');
  try {
    await navigateToProjects();

    const btn = window.locator(`button.danger[data-id="${pid}"]`);
    await expect(btn).toBeVisible({ timeout: 5000 });

    // Dismiss the confirm dialog (cancel)
    window.once('dialog', dialog => dialog.dismiss());
    await btn.click();
    await window.waitForTimeout(500);

    // Project card must STILL be there
    await expect(window.locator(`button.danger[data-id="${pid}"]`)).toHaveCount(1);

    // And API must still list it
    const r = await api('GET', '/api/projects');
    const ids = r.body.map(p => p.id);
    expect(ids).toContain(pid);
  } finally {
    await deleteTestProject(pid);
  }
});

test('API DELETE returns 200 and project disappears from list', async () => {
  const pid = await createTestProject('E2E Delete API Test');

  const deleteResult = await deleteTestProject(pid);
  expect(deleteResult.status).toBe(200);
  expect(deleteResult.body.deleted).toBe(pid);

  const listResult = await api('GET', '/api/projects');
  const ids = listResult.body.map(p => p.id);
  expect(ids).not.toContain(pid);
});
