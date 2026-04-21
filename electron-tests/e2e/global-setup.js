// electron-tests/e2e/global-setup.js
// Removes stale E2E test projects from ~/sparge-projects/ before each test run.
// Test projects are identified by the "E2E " name prefix — all E2E tests must use it.
'use strict';
const fs   = require('fs');
const path = require('path');
const os   = require('os');

const PROJECTS_DIR  = path.join(os.homedir(), 'sparge-projects');
const PROJECTS_JSON = path.join(PROJECTS_DIR, 'projects.json');

module.exports = async function globalSetup() {
  if (!fs.existsSync(PROJECTS_JSON)) return;

  const projects = JSON.parse(fs.readFileSync(PROJECTS_JSON, 'utf8'));
  const keep = [];

  for (const project of projects) {
    if (project.name?.startsWith('E2E ')) {
      const dir = path.join(PROJECTS_DIR, project.id);
      if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
    } else {
      keep.push(project);
    }
  }

  fs.writeFileSync(PROJECTS_JSON, JSON.stringify(keep, null, 2));
};
