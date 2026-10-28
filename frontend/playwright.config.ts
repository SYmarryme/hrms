import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', outputDir: '../var/mvp/e2e-results', workers: 1, timeout: 60000,
  reporter: 'list', use: { channel: 'msedge', headless: true, baseURL: process.env.HRMS_E2E_BASE_URL || 'http://127.0.0.1:3000',
    screenshot: 'off', video: 'off', trace: 'off' },
});
