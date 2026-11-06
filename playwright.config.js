const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'site-tests',
  timeout: 180000,
  expect: { timeout: 120000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4173' },
  webServer: {
    command: 'node site-tests/serve.js',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});
