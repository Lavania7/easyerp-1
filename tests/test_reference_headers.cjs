'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EASYERP_URL || 'http://127.0.0.1:8092';
const stage = process.env.EASYERP_REFERENCE_STAGE;
const output = process.env.EASYERP_REFERENCE_OUTPUT || path.resolve(__dirname, '../reports/reference-navigation');
const checks = [];
function check(name, result = true) { assert.ok(result, name); checks.push(name); console.log('PASS ' + name); }
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const errors = [];
  let writes = 0;
  await context.route('**/api/**', async route => {
    if (route.request().method() !== 'GET') { writes++; return route.abort(); }
    return route.continue();
  });
  if (stage) await context.route(base + '/**', async route => {
    const name = new URL(route.request().url()).pathname.slice(1);
    if (['app.js', 'company.css', 'manual.js'].includes(name))
      return route.fulfill({ path: path.join(stage, name), contentType: name.endsWith('.css') ? 'text/css; charset=utf-8' : 'application/javascript; charset=utf-8' });
    return route.fallback();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const open = async (object, search = '', pageName = 'archive') => {
    await page.goto(base + '/?' + new URLSearchParams({ mode: 'live', start: '2026-11-01', end: '2026-11-15', search }) + '#/' + pageName + '?' + new URLSearchParams({ department: object.split('.')[0], object }));
    await waitTable(object);
  };
  const waitTable = object => page.waitForFunction(object => document.querySelector('#content .table-edit-panel')?.dataset.editSource === object && !document.querySelector('#content .loading'), object);
  const originText = () => page.locator('[data-reference-return]').first().innerText();
  const header = target => page.locator('#content th [data-reference="' + target + '"]').first();
  try {
    await open('rd.物料版本表', 'MV001');
    const coverage = await page.evaluate(() => {
      const failures = [];
      for (const ref of meta.references) {
        const object = ref.source_schema + '.' + ref.source_table;
        const target = ref.target_schema + '.' + ref.target_table;
        const container = document.createElement('div');
        container.innerHTML = referenceHeader(ref.source_column, ref.source_column, object);
        const link = container.querySelector('[data-reference]');
        if (!link || link.dataset.reference !== target || new URLSearchParams(link.hash.split('?')[1]).get('object') !== target)
          failures.push(object + '.' + ref.source_column + ' -> ' + target);
      }
      return { failures, count: meta.references.length, departments: [...new Set(meta.references.map(ref => ref.source_schema))].sort() };
    });
    check('all actual foreign-key headers link to their exact target (' + coverage.count + ')', coverage.failures.length === 0 || (console.log(coverage.failures), false));
    check('foreign-key coverage includes all six departments', coverage.departments.length === 6);
    check('primary and unrelated headers stay plain', await page.evaluate(() => !referenceHeader('物料版本ID', '物料版本ID', 'rd.物料版本表').includes('data-reference') && !referenceHeader('主体ID', '主体ID', 'rd.物料版本表').includes('data-reference')));
    check('MID header is visible and blue', await header('rd.物料主数据表').isVisible() && await header('rd.物料主数据表').evaluate(el => getComputedStyle(el).color === 'rgb(0, 105, 204)'));
    const row = page.locator('tr[data-row-id="MV001"]');
    await row.locator('[data-record="rd.物料主数据表"]').click();
    await page.locator('.record-inline-fields').first().waitFor();
    check('clicking the actual MID value still expands row details', await page.locator('.record-inline-panel').isVisible() && await page.locator('[data-reference-return]').count() === 0 && new URLSearchParams(page.url().split('#')[1].split('?')[1]).get('object') === 'rd.物料版本表');
    await page.locator('[data-row-details-close]').click();
    await row.locator('[data-record="rd.物料版本表"]').click();
    await page.locator('.record-inline-fields').first().waitFor();
    check('primary ID retains the same details behavior', await page.locator('.record-inline-panel').isVisible());
    await page.locator('[data-row-details-close]').click();
    await header('rd.物料主数据表').focus(); await page.keyboard.press('Enter');
    await waitTable('rd.物料主数据表');
    check('keyboard activation of the header opens the target table', await page.locator('.record-inline-panel').count() === 0 && !await page.locator('#drawer').isVisible());
    check('breadcrumb shows the full origin, arrow and target path', (await originText()).replace(/\s/g, '').includes('工作空间/归档/研发/物料版本表') && await page.locator('.breadcrumb-jump').count() === 1 && await page.locator('#crumb').innerText() === '物料主数据表');
    check('target table search is independent of the original table', await page.locator('#search').inputValue() === '');
    await page.screenshot({ path: path.join(output, 'reference-navigation-desktop.png') });
    await page.locator('[data-reference-return]').click(); await waitTable('rd.物料版本表');
    check('return restores original table, search and dates', await page.locator('#search').inputValue() === 'MV001' && await page.locator('#start').inputValue() === '2026-11-01' && await page.locator('#end').inputValue() === '2026-11-15' && await page.locator('[data-reference-return]').count() === 0);
    await open('rd.BOM明细表', 'original-query', 'data');
    check('empty filtered tables still expose FK header links', await page.locator('.table-view-empty').count() === 1 && await header('rd.物料版本表').isVisible());
    await page.evaluate(() => { state.offset = 30; });
    await header('rd.物料版本表').click(); await waitTable('rd.物料版本表');
    const original = await originText();
    await header('rd.物料主数据表').click(); await waitTable('rd.物料主数据表');
    check('multiple header jumps preserve the first origin', await originText() === original && await page.locator('[data-reference-return]').count() === 1 && await page.locator('.breadcrumb-jump').count() === 1);
    await page.reload(); await waitTable('rd.物料主数据表');
    check('origin and target survive refresh', await originText() === original);
    await page.goBack(); await waitTable('rd.物料版本表');
    check('browser Back restores the prior target with the first origin', await originText() === original);
    await page.goForward(); await waitTable('rd.物料主数据表');
    check('browser Forward restores the next target with the first origin', await originText() === original);
    await page.setViewportSize({ width: 390, height: 844 });
    check('both breadcrumb paths fit mobile screens', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1 && document.querySelector('[data-reference-return]').getBoundingClientRect().right <= innerWidth));
    await page.screenshot({ path: path.join(output, 'reference-navigation-mobile.png') });
    await page.locator('#language-toggle').click();
    await page.waitForFunction(() => document.documentElement.lang === 'en');
    check('both paths translate into English', (await originText()).includes('Workspace') && await page.locator('#crumb').innerText() === await page.evaluate(() => ERPUI.t('物料主数据表')));
    await page.locator('#language-toggle').click();
    await page.waitForFunction(() => document.documentElement.lang === 'de');
    check('German keeps the fixed return path', await page.locator('[data-reference-return]').isVisible());
    await page.locator('#language-toggle').click();
    while (await page.locator('html').getAttribute('data-theme') !== 'dark') await page.locator('#theme-toggle').click();
    await page.locator('[data-reference-return]').click(); await waitTable('rd.BOM明细表');
    check('return restores pagination and all original query state', await page.evaluate(() => state.offset === 30 && state.search === 'original-query'));
    check('header links stay readable blue in dark mode', await header('rd.物料版本表').evaluate(el => getComputedStyle(el).color === 'rgb(120, 185, 245)'));
    await header('rd.物料版本表').click(); await waitTable('rd.物料版本表');
    await page.setViewportSize({ width: 1600, height: 1000 });
    const catalog = await (await context.request.get(base + '/api/meta?mode=live')).json();
    const visited = [];
    for (const schema of ['finance', 'legal', 'production', 'rd', 'sales', 'analysis']) {
      const target = catalog.references.find(ref => ref.target_schema === schema);
      const object = target.target_schema + '.' + target.target_table;
      await page.evaluate(object => followReference(object), object); await waitTable(object);
      check(schema + ' opens its actual target table and preserves the origin', await originText() === original && await page.locator('.error-panel').count() === 0);
      visited.push(object);
    }
    const hidden = catalog.objects.filter(o => !o.standalone && catalog.references.some(ref => ref.target_schema === o.schema && ref.target_table === o.name));
    for (const object of hidden) {
      const key = object.schema + '.' + object.name;
      await page.evaluate(key => followReference(key), key); await waitTable(key);
      check('target without standalone menu opens correctly: ' + key, await page.locator('.error-panel').count() === 0);
    }
    await page.evaluate(() => followReference('production.生产工单表')); await waitTable('production.生产工单表');
    check('referenced tables retain their export action', await page.locator('#export').isVisible() && !await page.locator('#export').isDisabled());
    await page.locator('#entry-open').click();
    await page.locator('#manual-entry[open]').waitFor();
    await page.locator('#manual-entry [data-entry-value][data-field="计划数量"]').waitFor();
    check('New on a referenced workflow table opens its own entry form', await page.locator('#manual-entry [data-entry-value][data-field="计划数量"]').count() === 1 && !await page.locator('#workspace-dialog').isVisible());
    await page.keyboard.press('Escape');
    await page.locator('#manual-entry[open]').waitFor({ state: 'detached' });
    await page.locator('[data-workspace-page="archive"]').click();
    await page.waitForFunction(() => !document.querySelector('#content .loading'));
    check('manual menu navigation ends the reference journey', await page.locator('[data-reference-return]').count() === 0);
    await open('rd.BOM明细表', 'original-query', 'data');
    await header('rd.物料版本表').click(); await waitTable('rd.物料版本表');
    await page.locator('#source-toggle').click(); await page.locator('[data-source-value="demo"]').click();
    await page.waitForFunction(() => state.mode === 'demo' && !changeMode.busy && !document.querySelector('#content .loading'));
    check('source switch clears the old reference journey', await page.locator('[data-reference-return]').count() === 0 && !new URLSearchParams(page.url().split('#')[1].split('?')[1]).has('reference'));
    check('no business writes were issued', writes === 0);
    check('no uncaught JavaScript errors', errors.length === 0 || (console.log(errors), false));
    fs.writeFileSync(path.join(output, 'reference-navigation-validation.json'), JSON.stringify({ status: 'PASS', checks: checks.length, foreignKeys: coverage.count, departments: visited, hiddenTables: hidden.length, businessWrites: writes, errors, passed: checks }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
