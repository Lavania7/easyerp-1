// Read-only checks for master-record browsing after SQL views are removed.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const url=process.env.EASYERP_URL||'http://127.0.0.1:8092',passed=[];
const check=(label,condition=true)=>{assert.ok(condition,label);passed.push(label);console.log('PASS: '+label);};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let writes=0;
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(request.method()==='POST'&&request.url().includes('/api/'))writes++;});
  const groups={sales:'sales',inventory:'production',production:'production',rd:'rd',finance:'finance',legal:'legal',analysis:'analysis'};
  for(const mode of ['live','demo']){
   const response=await page.request.get(url+'/api/meta?mode='+mode);assert.equal(response.status(),200);
   const meta=await response.json(),kinds=new Map(meta.objects.map(o=>[o.schema+'.'+o.name,o.kind]));
   check(mode+' catalog has 146 master tables and no SQL views',meta.objects.length===146&&meta.objects.every(o=>o.kind==='r'));
   for(const [route,schema] of Object.entries(groups)){
    // Ignore stale preferences from the removed view mode.
    await page.goto(url+'/?mode='+mode+'&start=2026-01-01&end=2026-12-31#/'+route);
    await page.locator('#object-filter').waitFor();
    check(mode+' '+route+' removes the SQL mode control',await page.locator('#object-mode-toggle').count()===0);
    const options=await page.locator('#object-filter option').evaluateAll(items=>items.map(o=>o.value));
    check(mode+' '+route+' lists only its master records',options.length>0&&options.every(value=>value.startsWith(schema+'.')&&kinds.get(value)==='r'));
    check(mode+' '+route+' renders without query errors',await page.locator('.error-panel').count()===0);
    const selected=options[Math.min(1,options.length-1)];
    await page.locator('#object-filter').selectOption(selected);
    await page.waitForFunction(value=>document.querySelector('.table-edit-panel')?.dataset.editSource===value,selected);
    await page.reload();await page.locator('#object-filter').waitFor();
    check(mode+' '+route+' retains master record selection',await page.locator('#object-filter').inputValue()===selected);
   }
  }
  await page.setViewportSize({width:390,height:844});
  check('master selector remains visible on narrow screens',await page.locator('#object-filter').isVisible());
  check('narrow layout has no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  check('no business writes',writes===0);check('no uncaught JavaScript errors',errors.length===0);
  fs.writeFileSync(path.join(__dirname,'../reports/object-mode-tests.json'),JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
