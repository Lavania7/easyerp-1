'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const os = require('node:os');
const { chromium } = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const web = path.resolve(__dirname, '../app/web');
const output = process.env.EASYERP_CALCULATOR_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(), 'easyerp-calculator-'));
const checks = [];
const check = (name, condition) => { assert.ok(condition, name); checks.push(name); console.log('PASS ' + name); };
const index = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
const header = index.match(/<header class="topbar">[\s\S]*?<\/header>/)[0];
const styles = [...index.matchAll(/<link rel="stylesheet" href="([^"]+)"\s*\/>/g)].map(match => `<link rel="stylesheet" href="${match[1]}">`).join('');
const fixture = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/preferences.js"></script>${styles}<link rel="stylesheet" href="/calculator.css"><script src="/locales.js" defer></script><script src="/i18n.js" defer></script><script src="/calculator.js" defer></script></head><body>${header}<main style="padding:30px;min-height:1800px"><button id="outside-button" type="button">Outside</button><input id="outside-input" aria-label="Outside input"><a id="outside-link" href="#other-page">Navigate</a></main></body></html>`;
const server = http.createServer((request, response) => {
  if (request.method !== 'GET') { response.writeHead(405).end(); return; }
  const name = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  if (name === '/') { response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }).end(fixture); return; }
  const file = path.resolve(web, '.' + name);
  if (!file.startsWith(web + path.sep) || !/\.(js|css|woff2?|ttf|svg)$/.test(file) || !fs.existsSync(file)) { response.writeHead(404).end(); return; }
  response.writeHead(200, { 'Content-Type': file.endsWith('.js') ? 'application/javascript; charset=utf-8' : file.endsWith('.css') ? 'text/css; charset=utf-8' : 'application/octet-stream' }).end(fs.readFileSync(file));
});
const boundsInside = (bounds, width, height) => bounds.x >= -1 && bounds.y >= -1 && bounds.x + bounds.width <= width + 1 && bounds.y + bounds.height <= height + 1;
const waitInside = async (page, width, height) => page.waitForFunction(({ width, height }) => {
  const bounds = document.querySelector('#easyerp-calculator').getBoundingClientRect();
  return bounds.x >= -1 && bounds.y >= -1 && bounds.right <= width + 1 && bounds.bottom <= height + 1;
}, { width, height });
(async () => {
  fs.mkdirSync(output, { recursive: true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  let browser;
  const errors = [];
  let writes = 0;
  try {
    browser = await chromium.launch({ headless: true, channel: process.env.EASYERP_BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    await context.addInitScript(() => {
      const NativeController = window.AbortController;
      window.calculatorTestControllers = [];
      window.AbortController = class extends NativeController {
        constructor() { super(); window.calculatorTestControllers.push(this); }
      };
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    context.on('request', request => { if (request.method() !== 'GET') writes++; });
    await context.route('**/api/**', async route => {
      if (route.request().method() !== 'GET') await route.abort();
      else await route.continue();
    });
    await page.goto(base);
    const trigger = page.locator('#calculator-toggle');
    const panel = page.locator('#easyerp-calculator');
    const input = page.locator('#calculator-expression');
    const result = page.locator('#calculator-result');
    const status = page.locator('#calculator-status');
    const key = value => page.locator('[data-calculator-key="' + value + '"]');
    const calculate = async expression => { await input.fill(expression); await input.press('Enter'); };
    await trigger.waitFor();
    check('topbar inserts one accessible closed toggle', await trigger.count() === 1 && await trigger.getAttribute('aria-pressed') === 'false' && await trigger.getAttribute('aria-expanded') === 'false');
    await page.evaluate(() => { easyerpCalculator.mount(); easyerpCalculator.mount(); });
    check('mount is idempotent', await trigger.count() === 1);
    await trigger.click();
    check('opens a focused nonmodal calculator', await panel.isVisible() && await panel.getAttribute('aria-modal') === 'false' && await input.evaluate(node => node === document.activeElement));
    await calculate('0.1+0.2');
    check('browser decimal addition is exact', await result.innerText() === '0.3');
    await input.press('+'); await input.press('4'); await input.press('Enter');
    check('keyboard continues the preceding result', await result.innerText() === '4.3');
    await calculate('1/3');
    check('nonterminating decimal shows approximation', (await result.innerText()).startsWith('≈ 0.33333333333333333333') && (await status.innerText()).includes('20'));
    await key('×').click(); await key('3').click(); await key('calculate').click();
    check('continued division retains exact intermediate rational', await result.innerText() === '1');
    await key('8').click();
    check('digit starts a fresh expression after equals', await input.inputValue() === '8');
    await key('clear').click();
    for (const value of ['(', '2', '+', '3', ')', '×', '4', 'calculate']) await key(value).click();
    check('button keypad handles parentheses and precedence', await result.innerText() === '20');
    await input.fill('12345');
    await input.evaluate(node => node.setSelectionRange(1, 4));
    await key('backspace').click();
    check('backspace deletes selected range', await input.inputValue() === '15');
    await key('9').click();
    check('keypad inserts at the current caret', await input.inputValue() === '195');
    await calculate('1/0');
    check('division by zero is readable and marks the field invalid', (await status.innerText()).includes('零') && await input.getAttribute('aria-invalid') === 'true');
    await calculate('globalThis.hacked=1');
    check('script input is rejected without execution', await input.getAttribute('aria-invalid') === 'true' && await page.evaluate(() => window.hacked === undefined));
    await calculate('1,25+2,5');
    check('decimal comma input is supported', await result.innerText() === '3.75');
    for (const [language, title, expressionLabel] of [['en', 'Calculator', 'Expression'], ['de', 'Rechner', 'Ausdruck'], ['zh', '计算器', '表达式']]) {
      while (await page.evaluate(() => ERPPreferences.language) !== language) await page.locator('#language-toggle').click();
      check(language + ' translates button, heading and expression label', await trigger.innerText() === title && await page.locator('#calculator-title').innerText() === title && await page.locator('label[for="calculator-expression"]').innerText() === expressionLabel);
      await calculate('1/0');
      const currentError = await status.innerText();
      check(language + ' translates errors', language === 'zh' ? currentError.includes('零') : language === 'en' ? currentError.includes('zero') : currentError.includes('null'));
    }
    while (await page.evaluate(() => ERPPreferences.language) !== 'en') await page.locator('#language-toggle').click();
    for (const theme of ['light', 'dark', 'system']) {
      while (await page.evaluate(() => ERPPreferences.theme) !== theme) await page.locator('#theme-toggle').click();
      const style = await panel.evaluate(node => { const css = getComputedStyle(node); return { background: css.backgroundColor, backdrop: css.backdropFilter }; });
      check(theme + ' theme has an opaque surface and no blur', style.background !== 'rgba(0, 0, 0, 0)' && style.backdrop === 'none');
      if (theme !== 'system') await page.screenshot({ path: path.join(output, 'calculator-' + theme + '.png') });
    }
    const handle = page.locator('.calculator-drag');
    const dragTo = async (x, y) => {
      const bounds = await handle.boundingBox();
      await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
      await page.mouse.down(); await page.mouse.move(x, y, { steps: 4 }); await page.mouse.up();
    };
    await dragTo(10, 10);
    check('pointer drag reaches upper left viewport edge', boundsInside(await panel.boundingBox(), 1440, 960) && (await panel.boundingBox()).x < 20 && (await panel.boundingBox()).y < 20);
    await dragTo(1439, 959);
    check('pointer drag clamps lower right edge', boundsInside(await panel.boundingBox(), 1440, 960));
    await handle.focus(); await handle.press('Home');
    const before = await panel.boundingBox();
    await handle.press('ArrowLeft');
    check('keyboard drag moves the panel', (await panel.boundingBox()).x === before.x - 16);
    await page.locator('#outside-input').fill('12+5');
    await page.locator('#outside-input').press('Escape');
    check('outside fields and Escape remain usable with calculator open', await page.locator('#outside-input').inputValue() === '12+5' && await panel.isVisible());
    await page.locator('#outside-link').click();
    check('background navigation remains usable', page.url().endsWith('#other-page') && await panel.isVisible());
    await input.focus();
    await page.evaluate(() => window.scrollTo(0, 500));
    check('panel remains fixed during page scrolling', boundsInside(await panel.boundingBox(), 1440, 960));
    await page.setViewportSize({ width: 320, height: 568 });
    await waitInside(page, 320, 568);
    check('resize keeps narrow panel and close control reachable', boundsInside(await panel.boundingBox(), 320, 568) && await page.locator('.calculator-close').isVisible());
    await calculate('9007199254740993+0.0001');
    check('narrow screen retains large exact decimals', await result.innerText() === '9007199254740993.0001');
    await page.screenshot({ path: path.join(output, 'calculator-narrow.png') });
    await page.setViewportSize({ width: 568, height: 260 });
    await waitInside(page, 568, 260);
    const body = page.locator('.calculator-body');
    await body.evaluate(node => { node.scrollTop = node.scrollHeight; });
    await key('calculate').click();
    check('short viewport scrolls keypad without losing the close header', boundsInside(await panel.boundingBox(), 568, 260) && await page.locator('.calculator-close').isVisible());
    await input.focus(); await input.press('Escape');
    check('Escape closes and returns focus to the toggle', await panel.count() === 0 && await trigger.evaluate(node => node === document.activeElement));
    check('close aborts all active panel listeners', await page.evaluate(() => calculatorTestControllers.slice(1).every(controller => controller.signal.aborted)));
    await trigger.click(); await trigger.click();
    check('second toggle click closes the panel', await panel.count() === 0 && await trigger.getAttribute('aria-pressed') === 'false');
    for (let index = 0; index < 15; index++) await page.evaluate(() => { easyerpCalculator.open(); easyerpCalculator.close(false); });
    check('repeated open close removes panels and aborts their listeners', await panel.count() === 0 && await page.evaluate(() => calculatorTestControllers.slice(1).every(controller => controller.signal.aborted)));
    await page.evaluate(() => { easyerpCalculator.open(); window.dispatchEvent(new Event('pagehide')); });
    check('leaving the page cleans up the panel', await panel.count() === 0);
    await page.evaluate(() => easyerpCalculator.destroy());
    check('destroy removes all calculator UI and listeners', await trigger.count() === 0 && await page.evaluate(() => calculatorTestControllers.every(controller => controller.signal.aborted)));
    await page.evaluate(() => easyerpCalculator.mount());
    await trigger.click();
    check('module can remount after destroy', await panel.isVisible());
    await context.close();

    const mobileContext = await browser.newContext({ viewport: { width: 360, height: 640 }, isMobile: true, hasTouch: true });
    const mobile = await mobileContext.newPage();
    mobile.on('pageerror', error => errors.push(error.message));
    await mobile.goto(base); await mobile.locator('#calculator-toggle').tap();
    await mobile.locator('.calculator-close').tap();
    await mobile.locator('#easyerp-calculator').waitFor({ state: 'detached', timeout: 2000 });
    await mobile.locator('#calculator-toggle').tap();
    const session = await mobileContext.newCDPSession(mobile);
    await session.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 1 });
    const point = (x, y) => ({ x, y, id: 0, radiusX: 1, radiusY: 1, force: 1 });
    const touchHandle = await mobile.locator('.calculator-drag').boundingBox();
    const touchStart = point(touchHandle.x + 20, touchHandle.y + 15);
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [touchStart] });
    await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [point(5, 5)] });
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    check('touch dragging remains in the mobile viewport', boundsInside(await mobile.locator('#easyerp-calculator').boundingBox(), 360, 640));
    const closeBounds = await mobile.locator('.calculator-close').boundingBox();
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point(closeBounds.x + closeBounds.width / 2, closeBounds.y + closeBounds.height / 2)] });
    await mobile.evaluate(() => new Promise(requestAnimationFrame));
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await mobile.screenshot({ path: path.join(output, 'calculator-touch.png') });
    await mobile.locator('#easyerp-calculator').waitFor({ state: 'detached', timeout: 2000 });
    check('touch close remains reachable', await mobile.locator('#easyerp-calculator').count() === 0);
    await mobileContext.close();

    if (process.env.EASYERP_CALCULATOR_LIVE_URL) {
      const live = process.env.EASYERP_CALCULATOR_LIVE_URL.replace(/\/$/, '');
      const liveContext = await browser.newContext({ viewport: { width: 1440, height: 960 } });
      const livePage = await liveContext.newPage();
      livePage.on('pageerror', error => errors.push(error.message));
      await liveContext.route('**/api/**', async route => {
        if (route.request().method() !== 'GET') { writes++; await route.abort(); }
        else await route.continue();
      });
      if (!process.env.EASYERP_CALCULATOR_NATIVE_RESOURCES) {
        await liveContext.route(live + '/calculator.*', async route => {
          const name = new URL(route.request().url()).pathname.slice(1);
          await route.fulfill({ path: path.join(web, name), contentType: name.endsWith('.css') ? 'text/css' : 'application/javascript' });
        });
        await liveContext.route(live + '/', async route => {
          const response = await route.fetch();
          let html = await response.text();
          if (!html.includes('href="/calculator.css"')) html = html.replace('<link rel="stylesheet" href="/plan-visual.css" />', '<link rel="stylesheet" href="/plan-visual.css" /><link rel="stylesheet" href="/calculator.css" />');
          if (!html.includes('src="/calculator.js"')) html = html.replace('<script src="/company.js" defer></script>', '<script src="/company.js" defer></script><script src="/calculator.js" defer></script>');
          await route.fulfill({ response, body: html });
        });
      }
      await livePage.goto(live + '/#' + '/blank?department=');
      await livePage.waitForFunction(() => !!document.querySelector('#department-bar button'));
      await livePage.locator('.workspace-blank').waitFor();
      await livePage.locator('#calculator-toggle').click();
      await livePage.locator('#calculator-expression').fill('10000000000000000.01-0.02');
      await livePage.locator('#calculator-expression').press('Enter');
      check('real workbench loads the calculator with exact arithmetic', await livePage.locator('#calculator-result').innerText() === '9999999999999999.99');
      await livePage.locator('[data-department="production"]').click();
      await livePage.waitForFunction(() => document.querySelector('[data-department="production"]')?.getAttribute('aria-pressed') === 'true');
      check('real department navigation works while calculator stays open', await livePage.locator('[data-department="production"]').getAttribute('aria-pressed') === 'true' && await livePage.locator('#easyerp-calculator').isVisible());
      await livePage.screenshot({ path: path.join(output, 'calculator-workbench.png') });
      await livePage.setViewportSize({ width: 360, height: 740 });
      await waitInside(livePage, 360, 740);
      check('real workbench topbar toggle and panel fit a narrow viewport', boundsInside(await livePage.locator('#calculator-toggle').boundingBox(), 360, 740) && boundsInside(await livePage.locator('#easyerp-calculator').boundingBox(), 360, 740));
      await livePage.screenshot({ path: path.join(output, 'calculator-workbench-narrow.png') });
      await livePage.locator('#calculator-toggle').click();
      check('real workbench second click closes the panel', await livePage.locator('#easyerp-calculator').count() === 0);
      await liveContext.close();
    }
    check('no business writes were sent', writes === 0);
    check('no browser script errors', errors.length === 0);
    fs.writeFileSync(path.join(output, 'validation.json'), JSON.stringify({ passed: checks, errors, writes, liveUrl: process.env.EASYERP_CALCULATOR_LIVE_URL || null, nativeResources: !!process.env.EASYERP_CALCULATOR_NATIVE_RESOURCES }, null, 2));
    console.log('Artifacts: ' + output);
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
