'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.EASYERP_URL;
const out = process.env.EASYERP_GROUP1_OUTPUT;
const checks = [];
function check(label, pass) {assert.ok(pass, label); checks.push(label); console.log('PASS '+label);}
(async () => {
  fs.mkdirSync(out,{recursive:true});
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const context = await browser.newContext({viewport:{width:1500,height:950}});
  const errors = []; let writes = 0;
  const page = await context.newPage();
  page.on('pageerror',e => errors.push(e.message));
  await context.route('**/api/**',async route => {
    if (route.request().method() !== 'GET') {writes++; return route.abort();}
    return route.continue();
  });
  try {
    await page.goto(base+'/?mode=demo&start=2026-01-01&end=2026-12-31#/blank?department=');
    await page.waitForSelector('[data-department]');
    const data = await page.evaluate(async () => (await fetch('/api/meta?mode=demo')).json());
    const obj = data.objects.find(o=>o.kind==='r' && o.standalone && !o.retired && o.columns.length>12 && !['finance.资金流水表','sales.销售订单行表'].includes(o.schema+'.'+o.name));
    assert.ok(obj,'wide object metadata exists');
    const key = obj.schema+'.'+obj.name;
    let fixture = Object.fromEntries(obj.columns.map(c=>[c.name,null]));
    fixture[obj.pk]='UI_LAYOUT_FIXTURE';
    fixture.long_id='HIDDEN-LONG-ID';fixture.sha256='hidden-digest';fixture._table_version='fixture-version';
    await context.route('**/api/explore?**',async route => {
      const request = new URL(route.request().url());
      if (request.searchParams.get('object') !== key) return route.fallback();
      const original = await route.fetch();
      const response = await original.json();
      return route.fulfill({json:{...response,rows:[fixture],total:[{count:1}],queried_at:'2026-11-15T00:00:00+08:00'}});
    });
    const open = async () => {
      await page.goto(base+'/?mode=demo&start=2026-01-01&end=2026-12-31#/'+obj.area+'?department='+obj.schema+'&object='+encodeURIComponent(key));
      await page.locator('[data-row-id="UI_LAYOUT_FIXTURE"]').waitFor();
      await page.evaluate(()=>document.fonts.ready);
    };
    await open();
    check('group2 table tools mounted through real integration',await page.locator('[data-table-tools-mounted="true"]').count()===1);
    const header = page.locator('[data-table-scroll] thead [data-table-column]');
    check('all business fields beyond ten rendered',await header.count()===obj.columns.length);
    check('long identity and digest remain hidden',!await header.evaluateAll(nodes=>nodes.some(n=>['long_id','sha256'].includes(n.dataset.tableColumn))));
    const align = await page.evaluate(()=>{
      const a=document.querySelector('[data-dashboard-toggle]').getBoundingClientRect();
      const b=document.querySelector('[data-department="finance"]').getBoundingClientRect();
      return Math.abs(a.top-b.top)<1 && Math.abs((a.top+a.height/2)-(b.top+b.height/2))<1;
    });
    check('dashboard aligned with finance strip',align);
    const wrap=page.locator('[data-table-scroll]');
    check('wide table scrolls within center',await wrap.evaluate(el=>el.scrollWidth>el.clientWidth && el.getBoundingClientRect().right<=innerWidth));
    const before=await page.locator('[data-row-id="UI_LAYOUT_FIXTURE"]').boundingBox();
    const cellWidths=()=>page.locator('[data-row-id="UI_LAYOUT_FIXTURE"]>td').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().width));
    const widths=await cellWidths();
    await page.locator('[data-table-edit-toggle]').click();
    await page.waitForSelector('.table-edit-panel.is-editing');
    check('batch selection checkbox visible in edit mode',await page.locator('[data-tool-row-select]').isVisible());
    const after=await page.locator('[data-row-id="UI_LAYOUT_FIXTURE"]').boundingBox();
    check('edit toggle preserves original row height',Math.abs(before.height-after.height)<0.1);
    check('edit toggle preserves original cell widths',JSON.stringify(widths)===JSON.stringify(await cellWidths()));
    await page.locator('[data-table-edit-toggle]').click();
    await wrap.evaluate(el=>el.scrollLeft=0);
    const box=await wrap.boundingBox();
    await page.mouse.move(box.x+box.width-50,box.y+65);
    await page.mouse.down();
    await page.mouse.move(box.x+60,box.y+65,{steps:12});
    await page.mouse.up();
    check('mouse drag changes horizontal scroll',await wrap.evaluate(el=>el.scrollLeft>50));
    check('horizontal drag does not open row details',await page.locator('.row-details-row').count()===0 && await page.locator('[data-row-id="UI_LAYOUT_FIXTURE"]').getAttribute('aria-expanded')==='false');
    await page.screenshot({path:path.join(out,'wide-table.png')});
    for (const language of ['zh','en','de']) {
      await page.evaluate(lang=>localStorage.setItem('easyerp.language',lang),language);
      await page.goto(base+'/?mode=demo#/workflow?department=finance');
      await page.locator('.panel-head>[data-ws-new]').waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const centered=await page.locator('.panel-head').last().evaluate(el=>{
        const a=el.getBoundingClientRect(),b=el.querySelector('h2').getBoundingClientRect();
        return Math.abs((a.top+a.height/2)-(b.top+b.height/2))<1;
      });
      check('workflow plain heading centered '+language,centered);
    }
    for (const theme of ['light','dark']) {
      await page.evaluate(t=>localStorage.setItem('easyerp.theme',t),theme);
      await open();
      check('all columns in '+theme,await header.count()===obj.columns.length);
      await page.screenshot({path:path.join(out,'table-'+theme+'.png')});
    }
    await page.locator('#source-toggle').click();
    await page.keyboard.press('ArrowDown');
    check('source menu keyboard reaches database manager',await page.locator('#database-manager-open').evaluate(el=>document.activeElement===el));
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:620,height:700});
    await open();
    check('narrow page keeps horizontal overflow in table',await wrap.evaluate(el=>el.scrollWidth>el.clientWidth && document.documentElement.scrollWidth<=innerWidth+1));
    await wrap.evaluate(el=>el.scrollLeft=el.scrollWidth);
    check('narrow table reaches final business column',await header.last().evaluate(el=>{const r=el.getBoundingClientRect();return r.right<=innerWidth && r.right>0;}));
    await page.screenshot({path:path.join(out,'table-narrow.png')});
    check('no background blur introduced',await page.evaluate(()=>[...document.querySelectorAll('*')].every(el=>!getComputedStyle(el).backdropFilter.includes('blur'))));
    check('no JavaScript errors',errors.length===0);
    check('no business POST requests',writes===0);
    fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({passed:checks.length,checks,object:key,fixture:'browser response only; no business data written',errors,writes},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
