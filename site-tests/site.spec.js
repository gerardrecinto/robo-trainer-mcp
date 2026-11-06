const { test, expect } = require('@playwright/test');

const READY = () => window.__RT_READY__ === true;

async function openReady(page) {
  const problems = [];
  page.on('pageerror', (e) => problems.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('requestfailed', (r) => { if (r.url().startsWith('http://127.0.0.1')) problems.push('failed ' + r.url()); });
  await page.goto('/');
  await page.waitForFunction(READY);
  return problems;
}

test('the real powerlifting tools run in the browser with the example lifter', async ({ page }) => {
  const problems = await openReady(page);
  await expect(page.locator('#res')).toContainText('358.07');
  await expect(page.locator('#res')).toContainText('362.66');
  await expect(page.locator('#res')).toContainText('Wilks (1994)');
  expect(problems).toEqual([]);
});

test('one-rep max calculator gives Epley, Brzycki and an RPE estimate', async ({ page }) => {
  await openReady(page);
  await expect(page.locator('#res1')).toContainText('116.7');
  await expect(page.locator('#res1')).toContainText('112.5');
  await page.selectOption('#rpe1', '10');
  await expect(page.locator('#res1')).toContainText('115.9');
  await page.fill('#r1', '15');
  await expect(page.locator('#res1')).toContainText('lose accuracy above about 10 reps');
  await page.fill('#r1', '0');
  await expect(page.locator('#res1')).toContainText('1 to 30 reps');
});

test('daily target calculator matches the hand-computed numbers and rejects bad input', async ({ page }) => {
  await openReady(page);
  await expect(page.locator('#res2')).toContainText('2759');
  await page.selectOption('#ng', 'lose');
  await expect(page.locator('#res2')).toContainText('2207');
  await page.fill('#na', '12');
  await expect(page.locator('#res2')).toContainText('age 18 to 100');
});

test('tool list shows all 29 tools and filters by area', async ({ page }) => {
  await openReady(page);
  await expect(page.locator('#n-tools')).toHaveText('29');
  await expect(page.locator('#grid .t')).toHaveCount(29);
  await page.fill('#q', 'pl_calculate_dots');
  await expect(page.locator('#grid .t')).toHaveCount(1);
});

test('install commands on the page are the ones that were tested', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#cmd-uvx')).toHaveText('uvx --from git+https://github.com/gerardrecinto/robo-trainer-mcp robo-trainer-mcp');
  await expect(page.locator('#cmd-pip')).toContainText('pip install git+https://github.com/gerardrecinto/robo-trainer-mcp');
  await expect(page.locator('#cmd-docker')).toContainText('ghcr.io/gerardrecinto/robo-trainer-mcp:latest');
  const config = JSON.parse(await page.locator('#cmd-config').innerText());
  expect(config.mcpServers.trainer.command).toBe('uvx');
});

for (const width of [375, 1440]) {
  test(`no horizontal scroll at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openReady(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test('every in-page link points at a real section', async ({ page }) => {
  await page.goto('/');
  const missing = await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]')]
    .map((a) => a.getAttribute('href').slice(1)).filter((id) => id && !document.getElementById(id)));
  expect(missing).toEqual([]);
});

test('the page reads fine with JavaScript off', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4173/');
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('#cmd-uvx')).toBeVisible();
  await expect(page.locator('#sources')).toContainText('Mifflin');
  await context.close();
});

test('keyboard users can reach the controls', async ({ page }) => {
  await page.goto('/');
  for (let i = 0; i < 4; i += 1) await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement && document.activeElement !== document.body)).toBe(true);
});
