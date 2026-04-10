// playwright.config.js
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir:  './electron-tests/e2e',
  timeout:   60000,
  use: { headless: process.env.CI ? true : false },
});
