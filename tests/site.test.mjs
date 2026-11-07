import assert from 'node:assert/strict';
import {before, after, test} from 'node:test';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {chromium, firefox, webkit} from 'playwright';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const browserName = process.env.SITE_BROWSER || 'chromium';
const engines = {chromium, firefox, webkit};
assert.ok(engines[browserName], `Unknown SITE_BROWSER: ${browserName}`);
let server, browser, url;

before(async () => {
  server = createServer(async (request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    const file = pathname === '/' ? 'site/index.html'
      : /^\/py\/[a-z_]+\.py$/.test(pathname) ? `src/mfm/${path.basename(pathname)}` : null;
    if (!file) { response.writeHead(404); response.end(); return; }
    try {
      const data = await readFile(path.join(root, file));
      response.writeHead(200, {
        'Content-Type': file.endsWith('.html') ? 'text/html' : 'text/plain',
        'Cache-Control': 'no-store',
      });
      response.end(data);
    } catch {
      response.writeHead(404); response.end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  url = `http://127.0.0.1:${server.address().port}/`;
  browser = await engines[browserName].launch();
});

after(async () => {
  await browser?.close();
  await new Promise(resolve => server?.close(resolve));
});

const runtimeRequest = request => /pyodide|\.wasm(?:\?|$)|python_stdlib/.test(request.url());

for (const width of [375, 1440]) {
  test(`cold navigation and scrolling do not download Python at ${width}px`, async t => {
    const context = await browser.newContext({viewport: {width, height: 900}});
    try {
      const page = await context.newPage();
      const requests = [];
      page.on('request', request => { if (runtimeRequest(request)) requests.push(request.url()); });
      await page.goto(url, {waitUntil: 'networkidle'});
      await page.locator('#try').scrollIntoViewIfNeeded();
      // Give the old IntersectionObserver auto-start time to issue its request.
      await page.waitForTimeout(500);
      assert.deepEqual(requests, [], 'Python must wait for an explicit demo start');
      assert.ok(await page.locator('#start-demo').isVisible());
      assert.ok(await page.locator('#acq').isDisabled());
      assert.equal(await page.locator('#fleet').getAttribute('aria-busy'), 'false');
      assert.ok((await page.locator('#install').innerText()).includes('python3 -m venv'));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      t.diagnostic(JSON.stringify(await page.evaluate(() => ({
        width: innerWidth,
        documentTransferBytes: performance.getEntriesByType('navigation')[0].transferSize,
        resourceTransferBytes: performance.getEntriesByType('resource').reduce((sum, r) => sum + r.transferSize, 0),
        resourceRequests: performance.getEntriesByType('resource').map(r => r.name),
      }))));
    } finally { await context.close(); }
  });
}

async function waitForPython(page) {
  await page.waitForFunction(() => window.__MFM_READY__ ||
    document.getElementById('boot')?.textContent.includes('could not load'), null, {timeout: 90000});
  assert.equal(await page.evaluate(() => window.__MFM_READY__), true,
    `Real Python demo did not start: ${await page.locator('#fleet').innerText()}`);
  assert.equal(await page.locator('.rn').count(), 3);
}

test('keyboard activation downloads real Python and enforces the lease lifecycle', {timeout: 120000}, async () => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    const requests = [], errors = [];
    page.on('request', request => { if (runtimeRequest(request)) requests.push(request.url()); });
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(url, {waitUntil: 'networkidle'});
    const start = page.locator('#start-demo');
    await start.focus();
    await start.press('Enter');
    assert.equal(await page.locator('#fleet').getAttribute('aria-busy'), 'true');
    await waitForPython(page);
    assert.ok(requests.some(request => request.endsWith('.wasm')), 'a real WASM engine must load');
    assert.equal(await page.evaluate(() => document.activeElement?.dataset.id), 'm1-01');
    await page.locator('#acq').click();
    assert.ok((await page.locator('#log').innerText()).includes('leased m1-01 to demo-123'));
    await page.locator('#acq').click();
    assert.ok((await page.locator('#log').innerText()).includes('runner m1-01 is not ready'));
    await page.locator('#rel').click();
    assert.ok((await page.locator('#log').innerText()).includes('m1-01 draining after success'));
    assert.equal(await page.locator('.rn[data-id="m1-01"] .st').textContent(), 'draining');
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});

test('a blocked download explains local fallback and can be retried', {timeout: 120000}, async () => {
  const context = await browser.newContext({viewport: {width: 375, height: 900}});
  try {
    const page = await context.newPage();
    const loader = '**/pyodide.js';
    await page.route(loader, route => route.abort('failed'));
    await page.goto(url, {waitUntil: 'networkidle'});
    await page.locator('#start-demo').click();
    await page.waitForFunction(() => document.getElementById('start-demo').textContent.includes('Retry'));
    assert.ok((await page.locator('#boot').innerText()).includes('local commands below'));
    assert.equal(await page.locator('#fleet').getAttribute('aria-busy'), 'false');
    assert.ok(await page.locator('#acq').isDisabled());
    assert.ok(await page.locator('#start-demo').isEnabled());
    await page.unroute(loader);
    await page.locator('#start-demo').click();
    await waitForPython(page);
    await page.locator('#acq').click();
    assert.ok((await page.locator('#log').innerText()).includes('leased m1-01'));
  } finally { await context.close(); }
});

test('without JavaScript the local instructions and explanation stay usable', async () => {
  const context = await browser.newContext({javaScriptEnabled: false, viewport: {width: 375, height: 900}});
  try {
    const page = await context.newPage();
    await page.goto(url);
    assert.ok((await page.locator('noscript').innerText()).includes('run the same Python code locally'));
    assert.equal(await page.locator('#start-demo').isVisible(), false);
    assert.ok((await page.locator('#install').innerText()).includes('python3 -m venv'));
    assert.ok(await page.locator('#acq').isDisabled());
  } finally { await context.close(); }
});
