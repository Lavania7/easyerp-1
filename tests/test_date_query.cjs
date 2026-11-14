'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const f=JSON.parse(process.env.EASYERP_DATE_FIXTURE),passed=[];
const check=(name,value=true)=>{assert.ok(value,name);passed.push(name);console.log('PASS: '+name);};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let writes=0;
  page.on('pageerror',error=>errors.push(error.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/'))writes++;});
  const base=f.url+'/?mode=demo&start=2026-10-10&end=2026-10-10';
  for(const route of ['overview','tasks','sales','inventory','production','rd','finance','legal','analysis']){
   await page.goto(base+'#/'+route);await page.locator('#content .loading').waitFor({state:'detached'});
   check(route+' always shows Start and End date labels',(await page.locator('.query-date-label').allTextContents()).join('|')==='起始日期|截止日期');
   check(route+' enables both date controls',await page.locator('#start-trigger').isVisible()&&await page.locator('#end-trigger').isVisible()&&await page.locator('#start-trigger').isEnabled()&&await page.locator('#end-trigger').isEnabled()&&await page.locator('#date-presets').isVisible());
   assert.equal(await page.locator('.error-panel').count(),0);
  }
  await page.goto(base+'#/sales');await page.locator('.table-edit-panel').waitFor();await page.locator('#search').fill(f.run);
  async function dates(start,end){
   await page.evaluate(({start,end})=>{for(const [id,value] of Object.entries({start,end})){const input=document.querySelector('#'+id);input.value=value;input.dispatchEvent(new Event('change',{bubbles:true}));}},{start,end});
  }
  async function queryOrders(){const result=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/list'&&new URL(r.url()).searchParams.get('kind')==='orders');await page.locator('#apply').click();return (await result).json();}
  await dates('2026-10-09','2026-10-10');let orders=await queryOrders();check('changing the start date updates actual order results',Number(orders.total[0].count)===2);
  await dates('2026-10-10','2026-10-10');orders=await queryOrders();check('a single selected day filters the correct order',Number(orders.total[0].count)===1&&orders.rows[0]['订单ID']===f.order);
  await page.goto(base+'#/analysis?object='+encodeURIComponent('analysis.分析报告登记表'));await page.locator('#object-filter').waitFor();await page.locator('#search').fill(f.run);
  const reports=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/explore'&&new URL(r.url()).searchParams.get('search')===f.run);await page.locator('#apply').click();assert.equal(Number((await (await reports).json()).total[0].count),2);
  check('record browser applies its actual generation date');
  check('company name caret is removed',await page.locator('.company-brand-chevron').count()===0);
  await page.locator('#company-trigger').click();await page.locator('[data-company-select]').waitFor();
  check('company lookup still includes companies with unknown foundation dates',await page.locator('[data-company-select] option[value="'+f.company+'"]').count()===1);
  await page.locator('[data-company-select]').selectOption(f.company);await page.keyboard.press('Escape');
  check('company name still opens its information window',await page.locator('#company-brand-name').innerText()==='日期筛选验收公司（演示）');
  if(f.desktopScreenshot)await page.screenshot({path:f.desktopScreenshot,fullPage:true});
  await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('.query-date-label').textContent==='Start date');check('English date labels translate');
  await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('.query-date-label').textContent==='Startdatum');check('German date labels translate');await page.locator('#language-toggle').click();
  await page.setViewportSize({width:390,height:844});check('narrow-screen date controls remain visible',await page.locator('#start-trigger').isVisible()&&await page.locator('#end-trigger').isVisible());check('date controls fit the viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  while(await page.locator('html').getAttribute('data-theme')!=='dark')await page.locator('#theme-toggle').click();
  if(f.mobileScreenshot)await page.screenshot({path:f.mobileScreenshot,fullPage:true});
  await dates('2026-10-11','2026-10-10');await page.locator('#apply').click();await page.locator('#toast').waitFor();check('reversed date ranges show validation instead of changing dates',(await page.locator('#toast').innerText()).includes('有效的起止日期')&&await page.locator('#start').inputValue()==='2026-10-11');
  check('browser issued no business writes',writes===0);check('no uncaught JavaScript errors',errors.length===0);
  fs.writeFileSync(f.result,JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
