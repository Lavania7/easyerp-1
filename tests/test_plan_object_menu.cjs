// Read-only browser checks for feedback 2 and 4. No fixture or business writes.
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EASYERP_URL || 'http://127.0.0.1:8092';
const output = process.env.EASYERP_SCREENSHOT_DIR || path.join(__dirname, '../reports/plan-object-menu');
const passed = [], check = (name, condition) => { assert.ok(condition, name); passed.push(name); console.log('PASS: ' + name); };
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: process.env.EASYERP_BROWSER_CHANNEL || 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(), errors = [], failed = [], external = []; let writes = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400) failed.push(response.url()); });
  page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/')) writes++; if (!request.url().startsWith(base) && !request.url().startsWith('data:')) external.push(request.url()); });
  const open = async (route, mode = 'demo') => {
    await page.goto(base + '/?mode=' + mode + '&start=2026-01-01&end=2026-12-31#/' + route);
    await page.waitForFunction(() => !document.querySelector('#content .loading') && document.querySelector('#department-bar button'));
    assert.equal(await page.locator('.error-panel').count(), 0);
  };
  const selected = () => page.locator('#object-filter').getAttribute('value');
  try {
    const meta = await (await page.request.get(base + '/api/meta?mode=demo')).json();
    for (const department of ['finance', 'legal', 'production', 'rd', 'sales', 'analysis']) {
      for (const area of ['data', 'archive']) {
        await open(area + '?department=' + department);
        const actual = await page.locator('[data-object-value]').evaluateAll(elements => elements.map(element => element.dataset.objectValue));
        const expected = meta.objects.filter(object => object.kind === 'r' && object.standalone && !object.retired && object.schema === department && object.area === area).map(object => object.schema + '.' + object.name);
        check(department + ' ' + area + ' keeps every allowed table exactly once', actual.length > 0 && JSON.stringify([...actual].sort()) === JSON.stringify(expected.sort()) && new Set(actual).size === actual.length);
        await page.locator('#object-filter').click();
        check(department + ' ' + area + ' opens two-level categories', await page.locator('.object-picker-menu').isVisible() && await page.locator('[data-object-group]').count() > 0 && await page.locator('.object-submenu:visible').count() === 1);
        await page.keyboard.press('Escape');
      }
    }
    await open('data?department=production&object=' + encodeURIComponent('production.生产领退料表'), 'live');
    await page.locator('#object-filter').click();
    await page.locator('[data-object-group]').filter({ hasText: /^交付/ }).hover();
    check('hovering Delivery reveals both record and line tables', await page.locator('.object-submenu:visible [data-object-value]').count() === 2 && await page.locator('.object-submenu:visible').innerText().then(text => text.includes('交付记录表') && text.includes('交付明细表')));
    const bounds = await page.locator('.object-picker-menu').boundingBox();
    check('floating menu stays in viewport', bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= 1440 && bounds.y + bounds.height <= 1000);
    await page.screenshot({ path: path.join(output, 'grouped-table-menu.png') });
    await page.locator('.object-submenu:visible [data-object-value="production.交付记录表"]').click();
    await page.waitForFunction(() => document.querySelector('.table-edit-panel')?.dataset.editSource === 'production.交付记录表');
    check('submenu selection changes table and preserves data source', await selected() === 'production.交付记录表' && new URL(page.url()).searchParams.get('mode') === 'live');
    await page.reload(); await page.locator('#object-filter').waitFor();
    check('selection survives reload with current item marked', await selected() === 'production.交付记录表' && await page.locator('[data-object-value="production.交付记录表"]').getAttribute('aria-checked') === 'true');
    await page.locator('#object-filter').focus(); await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowRight');
    check('keyboard moves into the submenu', await page.locator('.object-submenu:visible button:focus').count() === 1);
    await page.keyboard.press('ArrowLeft'); check('left arrow returns to category', await page.locator('[data-object-group]:focus').count() === 1);
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter'); await page.locator('#object-filter').waitFor();
    check('Enter selects a leaf and closes menu', !await page.locator('.object-picker-menu').isVisible());
    await page.locator('#object-filter').click(); await page.locator('#title').click();
    check('outside click closes menu', !await page.locator('.object-picker-menu').isVisible());
    await open('plans?department=production'); await page.locator('#entry-open').click();
    const dialog = page.locator('#workspace-dialog');
    await dialog.locator('.katex').first().waitFor(); await page.evaluate(() => document.fonts.ready);
    const rectangle = await dialog.boundingBox();
    check('plan editor is a centered modal', await dialog.evaluate(element => element.matches(':modal')) && Math.abs(rectangle.x + rectangle.width / 2 - 720) < 2 && Math.abs(rectangle.y + rectangle.height / 2 - 500) < 2);
    check('three LaTeX formulas render with accessible MathML', await dialog.locator('.plan-formula .katex').count() === 3 && await dialog.locator('math').count() === 3 && await dialog.locator('.katex-error').count() === 0);
    await page.waitForFunction(() => document.querySelector('[data-ws-save]')?.disabled === false);
    check('formula panel leaves business fields and save available', await dialog.locator('[name=title]').isVisible() && await dialog.locator('[data-ws-save]').isVisible() && !await dialog.locator('[data-ws-save]').isDisabled());
    await page.screenshot({ path: path.join(output, 'production-plan-centered.png') });
    for (const language of ['en', 'de']) {
      await page.locator('#language-toggle').evaluate(element => element.click());
      await page.waitForFunction(language => document.documentElement.lang === language, language);
      await page.waitForFunction(() => !/[\u4e00-\u9fff]/.test(document.querySelector('.plan-calculation').innerText));
      check(language + ' translates formula labels and retains equations', await dialog.locator('.plan-formula .katex').count() === 3);
    }
    await page.locator('#theme-toggle').evaluate(element => element.click());
    await page.locator('#theme-toggle').evaluate(element => element.click());
    await page.screenshot({ path: path.join(output, 'production-plan-dark.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    check('narrow plan fits viewport and keeps footer visible', await dialog.evaluate(element => { const box = element.getBoundingClientRect(); return box.x >= 0 && box.right <= innerWidth && box.y >= 0 && box.bottom <= innerHeight && element.scrollWidth <= element.clientWidth; }) && await dialog.locator('[data-ws-save]').isVisible());
    await dialog.locator('.plan-calculation').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'production-plan-mobile.png') });
    await page.keyboard.press('Escape');
    check('Escape closes plan and restores focus', !await dialog.isVisible() && await page.locator('#entry-open').evaluate(element => document.activeElement === element));
    await open('data?department=production'); await page.locator('#object-filter').click();
    await page.locator('[data-object-group]').filter({ hasText: /^交付|^Delivery|^Lieferung/ }).click();
    check('touch-sized menu keeps both columns inside narrow screen', await page.locator('.object-picker-menu').evaluate(element => { const box = element.getBoundingClientRect(); return box.x >= 0 && box.right <= innerWidth; }) && await page.locator('.object-submenu:visible button').count() === 2);
    await page.screenshot({ path: path.join(output, 'grouped-table-menu-mobile.png') });
    await page.locator('.object-submenu:visible button').last().click();
    await page.waitForFunction(() => document.querySelector('#object-filter')?.getAttribute('aria-expanded') === 'false');
    check('touch selection closes menu', !await page.locator('.object-picker-menu').isVisible());
    await page.setViewportSize({ width: 1440, height: 1000 });
    await open('workflow?department=production'); await page.locator('#entry-open').click();
    check('workflow keeps its existing floating editor', await dialog.isVisible() && !await dialog.evaluate(element => element.matches(':modal')) && await dialog.locator('.plan-calculation').count() === 0);
    await page.keyboard.press('Escape');
    check('no business write requests', writes === 0); check('no external page dependencies', external.length === 0);
    check('no failed resources', failed.length === 0); check('no uncaught browser errors', errors.length === 0);
    fs.writeFileSync(path.join(output, 'validation.json'), JSON.stringify({ status: 'PASS', checks: passed.length, passed, writes, errors, failed, external }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
