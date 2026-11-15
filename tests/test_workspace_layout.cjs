'use strict';
const {objectValues, objectValue, selectObject}=require('./object_menu_helpers.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const base=process.env.EASYERP_URL||'http://127.0.0.1:8092';
const staged=process.env.EASYERP_STAGED_WEB;
const output=process.env.EASYERP_LAYOUT_OUTPUT||path.resolve(__dirname,'../reports/workspace-layout');
fs.mkdirSync(output,{recursive:true});
const checks=[];
const check=(name,condition)=>{assert.ok(condition,name);checks.push(name);console.log('PASS '+name);};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  const errors=[];let writes=0;
  context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));
  // Reject all business writes even if a UI regression unexpectedly issues one.
  await context.route('**/api/**',async route=>{
    if(route.request().method()!=='GET'){writes++;await route.abort();return;}
    await route.continue();
  });
  if(staged)await context.route(base+'/**',async route=>{
    const request=new URL(route.request().url());
    const name=request.pathname==='/'?'index.html':request.pathname.slice(1);
    if(['index.html','app.js','workspace.js','workspace.css','manual.js'].includes(name)){
      await route.fulfill({path:path.join(staged,name),contentType:name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.css')?'text/css; charset=utf-8':'application/javascript; charset=utf-8'});
    }else await route.fallback();
  });
  const page=await context.newPage();
  const contentReady=()=>page.waitForFunction(()=>!document.querySelector('#content .loading')&&!!document.querySelector('#department-bar button'));
  const open=async(hash,mode='live')=>{await page.goto(base+'/?mode='+mode+'&start=2026-01-01&end=2026-12-31#/'+hash);await contentReady();};
  const module=key=>page.locator('[data-workspace-page="'+key+'"]');
  const department=key=>page.locator('[data-department="'+key+'"]');
  const waitPressed=(selector,value)=>page.waitForFunction(({selector,value})=>document.querySelector(selector)?.getAttribute('aria-pressed')===value,{selector,value});
  const toggleDashboard=async()=>{const value=await page.locator('[data-dashboard-toggle]').getAttribute('aria-pressed')==='true'?'false':'true';await page.locator('[data-dashboard-toggle]').click();await waitPressed('[data-dashboard-toggle]',value);await contentReady();};
  const clickModule=async key=>{const value=await module(key).getAttribute('aria-pressed')==='true'?'false':'true';await module(key).click();await waitPressed('[data-workspace-page="'+key+'"]',value);await contentReady();};
  const clickDepartment=async key=>{const value=await department(key).getAttribute('aria-pressed')==='true'?'false':'true';await department(key).click();await waitPressed('[data-department="'+key+'"]',value);await contentReady();};
  const isBlank=()=>page.locator('.workspace-blank').isVisible();
  try{
    await open('blank?department=');
    check('unselected workbench displays a logo and short hints',await isBlank()&&await page.locator('.workspace-watermark svg').count()===1);
    check('blank workbench hides data tools',!await page.locator('.page-heading').isVisible()&&!await page.locator('.filters').isVisible());
    check('six departments and four central review options',await page.locator('[data-department]').count()===6&&await page.locator('.sidebar-modules [data-workspace-page]').count()===4);
    await page.screenshot({path:path.join(output,'easyerp-whiteboard.png')});
    await clickDepartment('finance');
    check('department alone keeps the center blank',await isBlank());
    await clickModule('data');await page.locator('#object-filter').waitFor();
    check('content and department together open actual records',await page.locator('#object-filter').isVisible());
    await clickDepartment('finance');
    check('clicking selected department deselects it and clears data',await isBlank()&&await department('finance').getAttribute('aria-pressed')==='false'&&await module('data').getAttribute('aria-pressed')==='true');
    await clickDepartment('sales');await page.locator('#object-filter').waitFor();
    check('only one department is selected at a time',await page.locator('[data-department][aria-pressed="true"]').count()===1);
    await clickModule('archive');await page.locator('#object-filter').waitFor();
    const object=await objectValue(page);
    await page.screenshot({path:path.join(output,'easyerp-department-layout.png')});
    await toggleDashboard();
    check('dashboard preserves both underlying selections',await module('archive').getAttribute('aria-pressed')==='true'&&await department('sales').getAttribute('aria-pressed')==='true');
    check('dashboard shows company metrics and a solid blue button',await page.locator('.metrics').isVisible()&&await page.locator('[data-dashboard-toggle]').evaluate(el=>{const s=getComputedStyle(el);return s.backgroundColor==='rgb(0, 105, 204)'&&s.color==='rgb(255, 255, 255)';}));
    await page.screenshot({path:path.join(output,'easyerp-dashboard.png')});
    await page.reload();await contentReady();
    check('dashboard overlay and prior selections survive refresh',await page.locator('.metrics').isVisible()&&await module('archive').getAttribute('aria-pressed')==='true'&&await department('sales').getAttribute('aria-pressed')==='true');
    await toggleDashboard();await page.locator('#object-filter').waitFor();
    check('turning dashboard off restores the same master table',await objectValue(page)===object);
    await clickModule('archive');
    check('clicking selected content deselects it and keeps department',await isBlank()&&await page.locator('.sidebar-modules [aria-pressed="true"]').count()===0&&await department('sales').getAttribute('aria-pressed')==='true');
    await toggleDashboard();await toggleDashboard();
    check('dashboard returns to whiteboard when content was unselected',await isBlank());
    await page.goBack();await contentReady();await page.goBack();await contentReady();
    check('browser history restores the empty selection',await isBlank());
    for(const mode of process.env.EASYERP_LAYOUT_QUICK?[]:['live','demo']){
      const response=await page.request.get(base+'/api/meta?mode='+mode);assert.equal(response.status(),200);
      const meta=await response.json();
      for(const key of ['finance','legal','production','rd','sales','analysis']){
        for(const area of ['data','archive']){
          await open(area+'?department='+key,mode);await page.locator('#object-filter').waitFor();
          const values=await objectValues(page);
          const expected=meta.objects.filter(o=>o.kind==='r'&&o.standalone&&!o.retired&&o.schema===key&&o.area===area).map(o=>o.schema+'.'+o.name);
          check(mode+' '+key+' '+area+' filters all master tables by department',values.length>0&&JSON.stringify([...values].sort())===JSON.stringify([...expected].sort()));
        }
      }
    }
    await open('archive?department=finance&object='+encodeURIComponent('finance.人员档案表'),'demo');await page.locator('#object-filter').waitFor();
    await page.locator('[data-table-edit-toggle]').click();
    check('table editing still exposes the add-row control',await page.locator('[data-table-add]').isVisible());
    await page.locator('[data-table-edit-toggle]').click();
    await page.locator('#entry-open').click();await page.locator('#manual-entry input').first().waitFor();
    check('new record opens the currently selected master table',await page.locator('#manual-entry').textContent().then(t=>t.includes('人员档案表')||t.includes('人员')));
    await page.keyboard.press('Escape');
    await page.locator('#import-open').click();await page.locator('#import-interface').waitFor({state:'visible'});
    check('import remains accessible from the data workspace',await page.locator('#import-interface').isVisible());
    await page.keyboard.press('Escape');
    // Controlled read-only responses exercise mixed department plans without saving fixtures.
    await page.route('**/api/workspace?*',async route=>{
      if(new URL(route.request().url()).searchParams.get('kind')!=='plan')return route.fallback();
      const rows=[['finance','layout-finance'],['sales','layout-sales'],['','layout-unassigned']].map(([department,title],index)=>({id:'layout-'+index,kind:'plan',status:'草稿',values:{department,title},version:1,history:[]}));
      await route.fulfill({json:{rows,token:'test-only',mode:'demo'}});
    });
    await open('plans?department=finance','demo');
    check('plans filter assigned departments without guessing unassigned rows',(await page.locator('[data-ws-open]').allTextContents()).some(t=>t==='layout-finance')&&!await page.locator('#content').textContent().then(t=>t.includes('layout-sales')||t.includes('layout-unassigned')));
    await clickDepartment('sales');
    check('switching department switches the plan list',(await page.locator('[data-ws-open]').allTextContents()).some(t=>t==='layout-sales')&&!await page.locator('#content').textContent().then(t=>t.includes('layout-finance')));
    await page.unroute('**/api/workspace?*');
    await page.locator('[data-ws-new]').click();await page.locator('#workspace-form [name="department"]').waitFor();
    check('new plan defaults to the selected department name',await page.locator('#workspace-form [name="department"]').inputValue()==='销售');
    await page.keyboard.press('Escape');
    await open('workflow?department=production&view=production','demo');
    check('production workflow tab remains usable',await page.locator('[data-ws-view="production"]').getAttribute('aria-pressed')==='true');
    await toggleDashboard();await toggleDashboard();
    check('dashboard also restores a selected workflow subpage',await page.locator('[data-ws-view="production"]').getAttribute('aria-pressed')==='true');
    await clickDepartment('finance');
    check('another department cannot retain production execution data',await page.locator('[data-ws-view="production"]').count()===0&&await page.locator('#breadcrumb-list').textContent().then(t=>t.includes('财务')&&t.includes('办理事项')));
    await open('archive?department=legal&object='+encodeURIComponent('legal.公司主体档案表'),'demo');await page.locator('#object-filter').waitFor();
    const record=page.locator('#content [data-record="legal.公司主体档案表"]').first();
    if(await record.count()){
      await record.click();await page.locator('.record-inline-panel .record-inline-fields').first().waitFor();
      check('record details retain the new department breadcrumb',await page.locator('#breadcrumb-list').textContent().then(t=>t.includes('归档')&&t.includes('法务')&&t.includes('公司主体档案表'))&&await page.locator('.record-inline-panel').textContent().then(t=>t.includes('公司主体档案表'))&&!await page.locator('#drawer').isVisible());
      await page.locator('[data-row-details-close]').click();await page.locator('.record-inline-panel').waitFor({state:'detached'});await contentReady();
      check('returning from details preserves the selected department',await department('legal').getAttribute('aria-pressed')==='true');
    }
    await open('archive?department=rd','demo');await page.locator('#object-filter').waitFor();
    await page.locator('#language-toggle').click();
    await page.waitForFunction(()=>document.documentElement.lang==='en');
    check('new labels translate to English',await module('data').textContent().then(t=>t.trim()==='Database'));
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.documentElement.lang==='de');
    check('new labels translate to German',await module('data').textContent().then(t=>t.trim()==='Datenbank'));
    await page.setViewportSize({width:390,height:844});
    check('German department bar and workspace fit a narrow screen',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.documentElement.lang==='zh-CN');
    await page.screenshot({path:path.join(output,'easyerp-mobile.png')});
    await page.locator('#menu').click();await clickModule('archive');
    check('mobile navigation can deselect to a whiteboard',await isBlank());
    while(await page.locator('html').getAttribute('data-theme')!=='dark')await page.locator('#theme-toggle').click();
    check('dark whiteboard uses the existing theme surface',await page.locator('.workspace-blank').evaluate(el=>{const s=getComputedStyle(el);return s.color!=='rgb(255, 255, 255)';}));
    await page.setViewportSize({width:1600,height:1000});
    await page.screenshot({path:path.join(output,'easyerp-whiteboard-dark.png')});
    check('no business writes were attempted',writes===0);
    check('no uncaught JavaScript errors',errors.length===0);
    fs.writeFileSync(path.join(output,'frontend-layout-checks.json'),JSON.stringify({status:'PASS',staged:!!staged,checks:checks.length,passed:checks,errors,writes},null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
