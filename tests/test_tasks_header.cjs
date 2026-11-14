'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const f=JSON.parse(process.env.EASYERP_TASKS_FIXTURE),passed=[];
const check=(name,condition=true)=>{assert.ok(condition,name);passed.push(name);console.log('PASS: '+name);};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(f.url+'/?mode=demo&end=2026-10-31#/tasks');
    const row=()=>page.locator('tr[data-row-id="'+f.purpose+'"]');
    await row().waitFor();
    check('My Work has edit toggle beside its record count',await page.locator('.table-toolbar .count + [data-table-edit-toggle]').count()===1);
    check('task maps to its own purpose record rather than parent fund',await row().getAttribute('data-row-object')==='finance.资金用途核定表'&&await row().getAttribute('data-row-id')===f.purpose);
    check('view mode hides task edit controls',!await row().locator('[data-row-edit]').isVisible());
    await page.locator('[data-table-edit-toggle]').click();
    check('My Work uses the shared blue edit mode',await page.locator('.table-edit-panel.is-editing').count()===1);
    await row().locator('[data-row-edit]').click();
    const form=()=>page.locator('.table-edit-form'),field=name=>form().locator('[data-table-field="'+name+'"]');
    await form().waitFor();
    check('task editor loads the authoritative record',await field('用途核定ID').inputValue()===f.purpose&&await field('资金记录ID').inputValue()===f.cash);
    await field('依据').fill('我的工作编辑保存验收');
    let response=page.waitForResponse(r=>r.url().includes('/api/entry/save')&&r.request().method()==='POST');
    await form().locator('[type=submit]').click();assert.equal((await response).status(),200);await form().waitFor({state:'detached'});await row().waitFor();
    check('saving refreshes My Work and keeps editing enabled',await page.locator('[data-table-edit-toggle]').getAttribute('aria-pressed')==='true');
    await row().locator('[data-row-edit]').click();await form().waitFor();
    check('saved task content is read back from SQL',await field('依据').inputValue()==='我的工作编辑保存验收');
    await field('状态').selectOption('已撤销');
    response=page.waitForResponse(r=>r.url().includes('/api/entry/save')&&r.request().method()==='POST');
    await form().locator('[type=submit]').click();assert.equal((await response).status(),200);await row().waitFor({state:'detached'});
    await page.locator('.table-edit-panel[data-edit-source="tasks"]').waitFor();
    check('resolved task leaves the pending list after save');
    // All mixed task rows use their source table and task number for editing.
    const tasks=await (await page.request.get(f.url+'/api/tasks?mode=demo&end=2026-10-31&tz=Asia%2FShanghai')).json();
    for(const task of tasks.rows){const target=page.locator('tr[data-row-object="'+task['来源']+'"][data-row-id="'+task['编号']+'"]');assert.equal(await target.count(),1,task['来源']+': '+task['编号']);}
    check('all displayed task types preserve their own source identity');
    await page.locator('#company-trigger').click();await page.locator('[data-company-select]').waitFor();await page.locator('[data-company-select]').selectOption(f.company);
    await page.waitForFunction(name=>document.querySelector('#company-brand-name').textContent===name,f.companyName);
    await page.keyboard.press('Escape');
    const desktop=await page.evaluate(()=>{
      const header=document.querySelector('.topbar').getBoundingClientRect(),name=document.querySelector('#company-brand-name'),trigger=document.querySelector('#company-trigger').getBoundingClientRect(),divider=document.querySelector('.topbar-divider').getBoundingClientRect(),crumb=document.querySelector('.breadcrumb').getBoundingClientRect(),side=document.querySelector('#sidebar').getBoundingClientRect();
      return {full:header.x===0&&Math.abs(header.width-innerWidth)<1,ordered:trigger.right<=divider.left&&divider.right<=crumb.left,below:side.top>=header.bottom-1,name:name.textContent,noClamp:getComputedStyle(name).webkitLineClamp==='none',hasOldTitle:!!document.querySelector('.company-brand-copy small')};
    });
    check('topbar spans the full page width from the left edge',desktop.full);
    check('company full name precedes a vertical divider and breadcrumb',desktop.name===f.companyName&&desktop.noClamp&&desktop.ordered);
    check('old Current Company caption is removed',!desktop.hasOldTitle);
    check('sidebar starts below the full-width topbar',desktop.below);
    if(f.desktopScreenshot)await page.screenshot({path:f.desktopScreenshot,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar-height'))>=document.querySelector('.topbar').getBoundingClientRect().height-1);
    const mobile=await page.evaluate(()=>{const name=document.querySelector('#company-brand-name'),header=document.querySelector('.topbar').getBoundingClientRect(),crumb=document.querySelector('.breadcrumb').getBoundingClientRect();return {name:name.textContent,fit:document.documentElement.scrollWidth<=innerWidth&&name.scrollHeight<=name.clientHeight+1,crumbVisible:crumb.width>0,headerHeight:header.height};});
    check('long company name wraps fully on narrow screens',mobile.name===f.companyName&&mobile.fit&&mobile.headerHeight>76);
    check('mobile topbar retains the workspace breadcrumb',mobile.crumbVisible);
    await page.locator('#menu').click();
    check('mobile sidebar opens below the resized header',await page.locator('#sidebar').evaluate(el=>el.getBoundingClientRect().top>=document.querySelector('.topbar').getBoundingClientRect().bottom-1));
    await page.locator('#menu').click();
    await page.locator('#company-trigger').click();check('company popover remains available from mobile topbar',await page.locator('#company-popover').isVisible());await page.keyboard.press('Escape');
    while(await page.locator('html').getAttribute('data-theme')!=='dark')await page.locator('#theme-toggle').click();
    check('dark theme keeps topbar divider visible',await page.locator('.topbar-divider').evaluate(el=>getComputedStyle(el).backgroundColor)!=='rgba(0, 0, 0, 0)');
    if(f.mobileScreenshot)await page.screenshot({path:f.mobileScreenshot,fullPage:true});
    await page.locator('#language-toggle').click();check('English labels preserve full company name',await page.locator('#company-brand-name').innerText()===f.companyName);
    await page.locator('#language-toggle').click();check('German labels preserve full company name',await page.locator('#company-brand-name').innerText()===f.companyName);
    check('no uncaught JavaScript errors',errors.length===0);
    fs.writeFileSync(f.result,JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
