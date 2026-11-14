// Read-only checks for the shared entry layout and retained business queries.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const baseURL=process.env.EASYERP_URL||'http://127.0.0.1:8092',passed=[];
const check=(name,condition=true)=>{assert.ok(condition,name);passed.push(name);console.log('PASS: '+name);};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let writes=0;
  page.on('pageerror',error=>errors.push(error.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/'))writes++;});
  const base=baseURL+'/?mode=demo&start=2026-10-01&end=2026-10-31';
  const meta=await (await page.request.get(baseURL+'/api/meta?mode=demo')).json(),kinds=new Map(meta.objects.map(o=>[o.schema+'.'+o.name,o.kind]));
  const specs={sales:{source:'sales.销售订单行表',kind:'orders',filter:'status-filter',detail:'order'},production:{source:'production.生产工单表',kind:'workorders',filter:'person-filter',detail:'workorder'},finance:{source:'finance.资金流水表',kind:'funds',filter:'subject-filter',detail:'fund'}};
  const waitObject=value=>page.waitForFunction(value=>document.querySelector('#object-filter')?.value===value&&document.querySelector('.table-edit-panel')?.dataset.editSource===value,value);
  async function verifyKind(kind){const values=await page.locator('#object-filter option').evaluateAll(items=>items.map(o=>o.value));assert.ok(values.length&&values.every(value=>kinds.get(value)===kind));}
  async function verifyLayout(){assert.equal(await page.locator('.table-toolbar #object-filter').count(),1);assert.equal(await page.locator('#object-mode-toggle').count(),0);assert.equal(await page.locator('.table-toolbar .source-code').count(),0);assert.ok(!(await page.locator('.table-toolbar').innerText()).includes('来源 ·'));}
  for(const [route,spec] of Object.entries(specs)){
   await page.goto(base+'#/'+route);await waitObject(spec.source);await verifyLayout();await verifyKind('r');
   check(route+' first visit uses the shared master record selector');
   check(route+' retains its business filter',await page.locator('#'+spec.filter).count()===1);
   const params=new URLSearchParams({mode:'demo',start:'2026-10-01',end:'2026-10-31',tz:'Asia/Shanghai',currency:'CNY',kind:spec.kind});
   const expected=await (await page.request.get(baseURL+'/api/list?'+params)).json();
   const count=await page.locator('.table-toolbar .count').innerText();check(route+' preserves business result counts',count.includes(String(expected.total[0].count)));
   if(expected.rows.length){
    const details=page.locator('#content [data-detail="'+spec.detail+'"]');check(route+' retains its detail entry',await details.count()>0);
    await details.first().click();await page.locator('#drawer [data-close]').waitFor();assert.equal(await page.locator('#drawer .error-panel').count(),0);await page.locator('#drawer [data-close]').click();
    await page.locator('[data-table-edit-toggle]').click();await page.locator('#content [data-row-edit]').first().click();await page.locator('.table-edit-form').waitFor();
    check(route+' retains row editing',await page.locator('.table-edit-form [data-table-field]').count()>0);await page.locator('.table-edit-form [data-table-cancel]').click();await page.locator('[data-table-edit-toggle]').click();
   }
   const exported=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/export');await page.locator('#export').click();const response=await exported;
   check(route+' export retains its business query',response.status()===200&&new URL(response.url()).searchParams.get('kind')===spec.kind&&Number(response.headers()['x-total-rows'])===Number(expected.total[0].count));
   const values=await page.locator('#object-filter option').evaluateAll(items=>items.map(o=>o.value));
   const selected=values.find(value=>value!==spec.source)||spec.source;
   await page.locator('#object-filter').selectOption(selected);await waitObject(selected);
   await page.locator('#nav a[href="#/'+route+'"]').click();await waitObject(selected);
   check(route+' normal navigation restores the selected master record');

  }
  for(const [route,schema] of Object.entries({inventory:'production',rd:'rd',legal:'legal',analysis:'analysis'})){
   await page.goto(base+'#/'+route);await page.locator('#object-filter').waitFor();await verifyLayout();check(route+' uses the same selector layout');
  }
  for(const [route,scope] of [['sales','pending'],['production','pending'],['finance','cash-income'],['finance','cash-expense']]){
   await page.goto(base+'#/overview');await page.locator('.metric[data-page="'+route+'"][data-scope="'+scope+'"]').click();await waitObject(specs[route].source);
   await page.waitForFunction(()=>!!document.querySelector('[data-clear-scope]'));await verifyLayout();
   check(route+' dashboard '+scope+' keeps the correct business list and scope',new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('scope')===scope);
   await page.locator('[data-clear-scope]').click();await page.locator('[data-clear-scope]').waitFor({state:'detached'});await waitObject(specs[route].source);
   check(route+' clears its dashboard scope without losing the shared controls');
  }
  await page.goto(base+'#/sales');await waitObject(specs.sales.source);await page.setViewportSize({width:390,height:844});
  for(const route of ['sales','production','finance']){
   await page.goto(base+'#/'+route+'?object='+encodeURIComponent(specs[route].source));await waitObject(specs[route].source);await verifyLayout();
   check(route+' unified controls fit narrow screens',await page.locator('#object-filter').isVisible()&&await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  if(process.env.EASYERP_SCREENSHOT_DIR){fs.mkdirSync(process.env.EASYERP_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:path.join(process.env.EASYERP_SCREENSHOT_DIR,'unified-entry-mobile.png'),fullPage:true});}
  await page.setViewportSize({width:1440,height:1000});
  if(process.env.EASYERP_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.EASYERP_SCREENSHOT_DIR,'unified-entry-desktop.png'),fullPage:true});
  await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.documentElement.lang==='en');check('English shared controls translate');
  await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.documentElement.lang==='de');check('German shared controls translate');
  check('no business write requests',writes===0);check('no uncaught JavaScript errors',errors.length===0);
  fs.writeFileSync(path.join(__dirname,'../reports/unified-entry-tests.json'),JSON.stringify({status:'PASS',at_utc:new Date().toISOString(),checks:passed.length,passed,business_write_requests:writes},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
