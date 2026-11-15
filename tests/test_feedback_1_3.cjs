// Read-only browser regression checks. Report examples are intercepted responses, never business writes.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EASYERP_URL || 'http://127.0.0.1:8092';
const output = process.env.EASYERP_FEEDBACK_OUTPUT || path.resolve(__dirname, '../reports/feedback-1-3');
const stage = process.env.EASYERP_STAGE;
const checks = [];
const check = (name, value = true) => { assert.ok(value, name); checks.push(name); console.log('PASS: ' + name); };
const examples = [
  {id:'AR001', values:{title:'测试财务月报', month:'2026-11', department:'FIN'}},
  {id:'AR002', values:{title:'测试研发季报', month:'2026-10', type:'季度审计', department:'研发部'}},
  {id:'AR003', values:{title:'测试销售年报', month:'2026-01', type:'年度审计', department:'销售'}},
  {id:'AR004', values:{title:'测试未分配月报', month:'2026-11'}},
].map(item => ({...item, kind:'report', status:'草稿', version:1, history:[]}));

(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({headless:true, channel:process.env.EASYERP_BROWSER_CHANNEL || 'msedge'});
  try {
    const page = await browser.newPage({viewport:{width:1440, height:1000}});
    const errors = [], writes = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if(request.method() !== 'GET' && request.url().includes('/api/')) writes.push(request.url()); });
    if(stage) for(const file of ['app.js', 'manual.js', 'table-edit.js', 'workspace.js', 'manual.css'])
      await page.route('**/' + file, route => route.fulfill({path:path.join(stage, 'app/web', file), contentType:file.endsWith('.js')?'text/javascript':'text/css'}));
    await page.route('**/api/workspace?*', async route => {
      const url = new URL(route.request().url());
      await route.fulfill({json:{rows:url.searchParams.get('kind')==='report'?examples:[], token:'read-only-browser-test', mode:url.searchParams.get('mode')}});
    });
    const open = async (hash, mode='demo') => {
      await page.goto(base + '/?mode=' + mode + '&start=2026-01-01&end=2026-12-31&search=#/' + hash);
      await page.locator('#content .loading').waitFor({state:'detached'});
    };
    const titles = () => page.locator('#content [data-ws-open]').evaluateAll(nodes => [...new Set(nodes.filter(n=>n.classList.contains('table-button')).map(n=>n.textContent))]);
    await open('audit?department=');
    await page.locator('[data-ws-view="quarterly"]').waitFor();
    check('audit without a department renders all periodic reports', (await titles()).length === 4 && !await page.locator('.page-heading').isHidden());
    check('review records are offered only within a department', await page.locator('[data-ws-view="records"]').count() === 0);
    await page.locator('[data-ws-view="quarterly"]').click();
    await page.waitForFunction(() => document.querySelector('[data-ws-view="quarterly"]')?.getAttribute('aria-pressed') === 'true');
    assert.deepEqual(await titles(), ['测试研发季报']);
    check('quarterly tab filters reports and displays the quarter', (await page.locator('#content').innerText()).includes('2026 Q4'));
    await page.locator('[data-department="rd"]').click();
    await page.waitForFunction(() => document.querySelector('[data-department="rd"]')?.getAttribute('aria-pressed') === 'true');
    assert.deepEqual(await titles(), ['测试研发季报']);
    check('selecting a department displays its reports across periods');
    await page.locator('#breadcrumbs [data-breadcrumb-page="audit"][data-breadcrumb-view=""][data-breadcrumb-department=""]').click();
    await page.waitForFunction(() => document.querySelectorAll('[data-department][aria-pressed="true"]').length === 0);
    check('audit breadcrumb returns to all departments', (await titles()).length === 4);
    await page.locator('[data-department="rd"]').click();
    await page.waitForFunction(() => document.querySelector('[data-department="rd"]')?.getAttribute('aria-pressed') === 'true');
    await page.locator('[data-ws-view="monthly"]').click();
    await page.waitForFunction(() => document.querySelector('[data-ws-view="monthly"]')?.getAttribute('aria-pressed') === 'true');
    assert.deepEqual(await titles(), []);
    check('department report filtering never includes another department or unknown ownership');
    await page.locator('[data-department="rd"]').click();
    await page.waitForFunction(() => document.querySelector('[data-department="rd"]')?.getAttribute('aria-pressed') === 'false');
    assert.deepEqual(new Set(await titles()), new Set(['测试财务月报', '测试未分配月报']));
    check('deselecting the department restores all monthly reports including legacy reports');
    await page.locator('[data-ws-view="yearly"]').click();
    await page.waitForFunction(() => document.querySelector('[data-ws-view="yearly"]')?.getAttribute('aria-pressed') === 'true');
    assert.deepEqual(await titles(), ['测试销售年报']);
    check('annual tab displays the year', (await page.locator('#content').innerText()).includes('2026'));
    await page.reload();
    await page.locator('[data-ws-view="yearly"][aria-pressed="true"]').waitFor();
    check('report period selection survives reload');
    await page.locator('#entry-open').click();
    await page.locator('#workspace-dialog [name="type"]').waitFor();
    check('new report inherits period type and supports explicit department selection', await page.locator('#workspace-dialog [name="type"]').inputValue() === '年度审计' && await page.locator('#workspace-dialog [name="department"]').count() === 1);
    await page.locator('#workspace-dialog [data-reference-source]').first().waitFor();
    check('workspace related-record chooser displays its source path');
    await page.locator('#workspace-dialog [data-ws-close]').first().click();
    await page.locator('[data-ws-view="items"]').click();
    await page.waitForFunction(() => document.querySelector('[data-ws-view="items"]')?.getAttribute('aria-pressed') === 'true');
    await page.screenshot({path:path.join(output,'audit.png'), fullPage:true});
    const references = await page.evaluate(async () => {
      const metadata = await (await fetch('/api/entry/meta?mode=demo')).json();
      const refs = metadata.objects.filter(o=>!o.retired).flatMap(o=>o.columns.filter(c=>c.reference && !c.retired_reference).map(c=>c.reference.target));
      return {total:refs.length, missing:refs.filter(key=>!referenceSourceHint(key, metadata.objects)),
        product:referenceSourceHint('rd.产品版本表', metadata.objects),
        material:referenceSourceHint('production.生产领退料表', metadata.objects)};
    });
    check('every active foreign-key target has a source hint', references.total > 100 && references.missing.length === 0);
    check('source hints follow actual archive and database navigation', /归档/.test(references.product) && /研发/.test(references.product) && /数据库/.test(references.material) && /生产领退料表/.test(references.material));
    await open('data?department=production&object=' + encodeURIComponent('production.库存盘点表'));
    await page.locator('[data-table-edit-toggle]').waitFor();
    await page.locator('[data-table-edit-toggle]').click();
    await page.locator('[data-table-add]').click();
    await page.locator('.table-edit-form [data-reference-source="rd.产品版本表"]').waitFor();
    check('inline create displays source hints for product versions and other references', await page.locator('.table-edit-form [data-reference-source]').count() >= 3);
    check('inline reference source is associated with its selector', await page.locator('[data-table-field="产品版本ID"]').getAttribute('aria-describedby') !== null);
    await page.screenshot({path:path.join(output,'reference-source.png'), fullPage:true});
    await page.locator('[data-table-cancel]').click();
    await page.evaluate(() => window.easyerpManual.open('production.库存盘点表'));
    await page.locator('#manual-entry [data-reference-source="rd.产品版本表"]').waitFor();
    check('full manual-entry dialog displays the same source paths');
    await page.keyboard.press('Escape');
    await open('audit?department=');
    await page.locator('#language-toggle').click();
    await page.locator('[data-ws-view="quarterly"]').filter({hasText:'Quarterly audit'}).waitFor();
    check('English audit controls translate');
    await page.locator('#language-toggle').click();
    await page.locator('[data-ws-view="quarterly"]').filter({hasText:'Quartalsprüfung'}).waitFor();
    check('German audit controls translate');
    await page.locator('#language-toggle').click();
    await page.setViewportSize({width:390, height:844});
    await page.screenshot({path:path.join(output,'audit-mobile.png'), fullPage:true});
    check('audit navigation fits narrow screens', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    while(await page.locator('html').getAttribute('data-theme') !== 'dark') await page.locator('#theme-toggle').click();
    check('dark theme keeps audit controls visible', await page.locator('[data-ws-view="quarterly"]').isVisible());
    check('no business writes were issued', writes.length === 0);
    check('no uncaught JavaScript errors', errors.length === 0);
    fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify({status:'PASS', checks:checks.length, passed:checks}, null, 2));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
