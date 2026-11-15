// Read-only regression: real wheel scrolling in both menu columns and no blurred backdrops.
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EASYERP_URL || 'http://127.0.0.1:8092';
const output = process.env.EASYERP_SCROLL_OUTPUT || path.join(__dirname, '../reports/menu-scrolling');
const passed = [], check = (name, condition) => { assert.ok(condition, name); passed.push(name); console.log('PASS: ' + name); };
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: process.env.EASYERP_BROWSER_CHANNEL || 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1480, height: 760 }, hasTouch: true });
  const page = await context.newPage(), errors = []; let writes = 0;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => { if (route.request().method() !== 'GET') { writes++; await route.abort(); } else await route.continue(); });
  const open = async route => {
    await page.goto(base + '/?mode=demo&start=2026-01-01&end=2026-12-31#/' + route);
    await page.waitForFunction(() => document.querySelector('#department-bar button') && !document.querySelector('#content .loading'));
    assert.equal(await page.locator('.error-panel').count(), 0);
  };
  const inViewport = () => page.locator('.object-picker-menu').evaluate(menu => { const r = menu.getBoundingClientRect(); return !menu.hidden && r.width > 0 && r.height > 0 && r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1; });
  const columnFits = selector => page.locator(selector).evaluate(column => { const r = column.getBoundingClientRect(), menu = column.closest('.object-picker-menu').getBoundingClientRect(); return r.top >= menu.top && r.bottom <= menu.bottom && column.scrollHeight > column.clientHeight; });
  const lastVisible = selector => page.locator(selector).evaluate(column => { const last = column.lastElementChild.getBoundingClientRect(), r = column.getBoundingClientRect(); return last.top >= r.top && last.bottom <= r.bottom + 1; });
  try {
    // These effective viewports include limited-height windows and the space available at higher browser zoom.
    for (const [width, height] of [[1480, 760], [1184, 608], [986, 506], [390, 844], [800, 400]]) {
      await page.setViewportSize({ width, height });
      await open('data?department=finance&object=' + encodeURIComponent('finance.资产负债表来源明细表'));
      await page.locator('#object-filter').click();
      check(width + 'x' + height + ' menu stays inside viewport', await inViewport());
      check(width + 'x' + height + ' category column is constrained and scrollable', await columnFits('.object-group-list'));
      await page.locator('.object-group-list').evaluate(column => { column.scrollTop = 0; });
      await page.locator('.object-group-list').hover({ position: { x: 25, y: 20 } });
      const before = await page.evaluate(() => scrollY);
      await page.mouse.wheel(0, 2000);
      await page.waitForFunction(() => document.querySelector('.object-group-list')?.scrollTop > 0);
      check(width + 'x' + height + ' wheel reveals last category without closing menu', await lastVisible('.object-group-list') && await page.locator('.object-picker-menu').isVisible());
      check(width + 'x' + height + ' menu scrolling leaves page stationary', await page.evaluate(() => scrollY) === before);
      if (width === 1480) await page.screenshot({ path: path.join(output, 'finance-menu-scrolled.png') });
      if (width === 390) await page.screenshot({ path: path.join(output, 'finance-menu-mobile-scrolled.png') });
      const last = page.locator('[data-object-group]').last();
      await last.click();
      const target = await page.locator('.object-submenu:visible [data-object-value]').last().getAttribute('data-object-value');
      await page.locator('.object-submenu:visible [data-object-value]').last().click();
      await page.waitForFunction(value => document.querySelector('.table-edit-panel')?.dataset.editSource === value, target);
      check(width + 'x' + height + ' last category table remains selectable', true);
    }
    await page.setViewportSize({ width: 1184, height: 608 });
    await open('archive?department=rd');
    // Browser-only menu data makes a long second level without writing fixture records.
    await page.evaluate(() => {
      const objects = Array.from({ length: 40 }, (_, index) => ({ schema: 'rd', name: '产品滚动检查' + index, label: '产品滚动检查 ' + index }));
      document.querySelector('#content').innerHTML = window.easyerpObjectMenu.render(objects, objects[0]);
      document.querySelector('#object-filter').onchange = event => { window.menuTestSelection = event.target.value; };
    });
    await page.locator('#object-filter').click();
    check('long submenu stays within viewport', await inViewport() && await columnFits('.object-submenu:not([hidden])'));
    await page.locator('.object-submenu:visible').hover({ position: { x: 35, y: 20 } });
    await page.mouse.wheel(0, 3000);
    await page.waitForFunction(() => document.querySelector('.object-submenu:not([hidden])')?.scrollTop > 0);
    check('second-level wheel reveals final record', await lastVisible('.object-submenu:not([hidden])') && await page.locator('.object-picker-menu').isVisible());
    check('second-level scrolling does not move category column', await page.locator('.object-group-list').evaluate(column => column.scrollTop === 0));
    await page.locator('.object-submenu:visible button').last().click();
    check('final second-level record can be chosen', await page.evaluate(() => window.menuTestSelection === 'rd.产品滚动检查39'));
    await page.locator('#object-filter').focus(); await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowRight'); await page.keyboard.press('End');
    check('keyboard End scrolls last second-level record into view', await lastVisible('.object-submenu:not([hidden])'));
    await page.keyboard.press('Escape');
    await page.locator('#object-filter').evaluate(element => { element.style.position = 'fixed'; element.style.top = '8px'; element.style.left = '16px'; element.style.zIndex = '100'; });
    await page.setViewportSize({ width: 800, height: 200 });
    await page.locator('#object-filter').click();
    check('very short viewport permits a menu below 160px', await inViewport() && await page.locator('.object-picker-menu').evaluate(element => element.offsetHeight < 160));
    await page.keyboard.press('Escape');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await open('plans?department=production'); await page.locator('#entry-open').click();
    await page.locator('.plan-formula .katex').first().waitFor();
    const surfaces = await page.evaluate(() => {
      const result = [...document.querySelectorAll('dialog')].flatMap(element => [
        { id: element.id, surface: 'backdrop', filter: getComputedStyle(element, '::backdrop').backdropFilter },
        { id: element.id, surface: 'panel', filter: getComputedStyle(element).backdropFilter },
      ]);
      for (const element of document.querySelectorAll('.drawer-backdrop,.source-menu,.company-popover,.object-picker-menu')) result.push({ id: element.id || element.className, surface: 'panel', filter: getComputedStyle(element).backdropFilter });
      return result;
    });
    for (const { id, surface, filter } of surfaces) check(id + ' ' + surface + ' has no backdrop blur', !filter || filter === 'none');
    check('plan remains a centered modal with no blurred backdrop', await page.locator('#workspace-dialog').evaluate(element => element.matches(':modal') && getComputedStyle(element, '::backdrop').backdropFilter === 'none'));
    await page.screenshot({ path: path.join(output, 'production-plan-no-blur.png') });
    check('no business write requests', writes === 0); check('no uncaught browser errors', errors.length === 0);
    fs.writeFileSync(path.join(output, 'scroll-validation.json'), JSON.stringify({ status: 'PASS', checks: passed.length, passed, surfaces, writes, errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
