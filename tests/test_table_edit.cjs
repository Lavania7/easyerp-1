// Browser companion for test_table_edit.py. Fixtures and cleanup belong to Python.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const fixture=JSON.parse(process.env.EASYERP_TABLE_FIXTURE);
const passed=[];
const check=(name,condition=true)=>{assert.ok(condition,name);passed.push(name);console.log('PASS: '+name);};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const base=fixture.url+'/?mode=demo&start=2026-10-01&end=2026-10-31';
    const customerURL=base+'#/sales?object='+encodeURIComponent('sales.客户档案表');
    const row=()=>page.locator('tr[data-row-id="'+fixture.customer+'"]');
    const toggle=()=>page.locator('[data-table-edit-toggle]');
    const form=()=>page.locator('.table-edit-form');
    const input=name=>form().locator('[data-table-field="'+name+'"]');
    const api=async(path,params={},payload=null)=>{
      const response=await page.request.fetch(fixture.url+'/api/entry/'+path+'?'+new URLSearchParams({mode:'demo',...params}),{
        method:payload?'POST':'GET',headers:{'Content-Type':'application/json','X-EasyERP-Token':fixture.token},...(payload?{data:payload}:{})
      });
      assert.equal(response.status(),200);return response.json();
    };
    const begin=async()=>{await row().locator('[data-row-edit]').click();await form().waitFor();};
    const commit=async()=>{
      const response=page.waitForResponse(r=>r.url().includes('/api/entry/save')&&r.request().method()==='POST');
      await form().locator('[type=submit]').click();return response;
    };
    await page.goto(customerURL);await toggle().waitFor();
    check('view mode hides row edit actions',!await row().locator('[data-row-edit]').isVisible());
    const sizes=await page.evaluate(()=>({edit:document.querySelector('[data-table-edit-toggle]').getBoundingClientRect().height,entry:document.querySelector('#entry-open').getBoundingClientRect().height,color:getComputedStyle(document.querySelector('[data-table-edit-toggle]')).color}));
    check('blue edit button matches entry size and has white text',Math.abs(sizes.edit-sizes.entry)<=2&&sizes.color==='rgb(255, 255, 255)');
    await toggle().click();
    check('toggle enables editing and blue table treatment',await toggle().getAttribute('aria-pressed')==='true'&&await page.locator('.table-edit-panel.is-editing').count()===1);
    await begin();
    check('record ID cannot be changed',await input('客户ID').isDisabled());
    await input('客户名称').fill('表格编辑已保存 <script>原文</script>');
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});
    await page.waitForFunction(id=>document.querySelector(`tr[data-row-id="${id}"]`)?.textContent.includes('表格编辑已保存'),fixture.customer);
    check('inline edit commits and refreshes the SQL-backed list');
    check('business text is rendered as text',await row().locator('script').count()===0);
    await begin();await input('客户名称').fill('不应保存的取消内容');
    await form().locator('[data-table-cancel]').click();
    check('cancel does not save',(await api('record',{object:'sales.客户档案表',id:fixture.customer})).values['客户名称']==='表格编辑已保存 <script>原文</script>');
    await begin();await input('客户名称').fill('保留的未保存输入');
    await toggle().click();await toggle().click();await begin();
    check('leaving and reentering edit mode preserves input',await input('客户名称').inputValue()==='保留的未保存输入');
    await page.locator('#refresh').click();await form().waitFor({state:'detached'});await row().waitFor();await begin();
    check('refresh preserves draft and edit mode',await input('客户名称').inputValue()==='保留的未保存输入'&&await toggle().getAttribute('aria-pressed')==='true');
    await page.locator('#source-toggle').click();await page.locator('[data-source-value="live"]').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='本机数据库'&&!!document.querySelector('[data-table-edit-toggle]'));
    check('source switch returns to view mode',await toggle().getAttribute('aria-pressed')==='false'&&!await form().count());
    await page.locator('#source-toggle').click();await page.locator('[data-source-value="demo"]').click();
    await row().waitFor();await toggle().click();await begin();
    check('demo draft remains isolated after source switches',await input('客户名称').inputValue()==='保留的未保存输入');
    await form().locator('[data-table-cancel]').click();await begin();
    await input('客户名称').fill('冲突时保留的内容');
    const current=await api('record',{object:'sales.客户档案表',id:fixture.customer});
    await api('save',{}, {request_id:fixture.run+'_concurrent',object:'sales.客户档案表',operation:'update',id:fixture.customer,version:current.version,values:{'客户名称':'其他页面更新'}});
    assert.equal((await commit()).status(),409);
    await form().locator('[data-table-edit-error]:not([hidden])').waitFor();
    check('conflicts preserve input and do not overwrite newer data',await input('客户名称').inputValue()==='冲突时保留的内容'&&(await api('record',{object:'sales.客户档案表',id:fixture.customer})).values['客户名称']==='其他页面更新');
    await form().locator('[data-table-cancel]').click();await begin();
    await input('客户名称').fill('表格编辑最终值');
    await input('产业分类').fill('');
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});await row().waitFor();
    check('optional blanks are saved as NULL',(await api('record',{object:'sales.客户档案表',id:fixture.customer})).values['产业分类']===null);
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('[data-table-edit-toggle]')?.textContent.includes('Finish editing'));
    check('English edit labels translate');
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('[data-table-edit-toggle]')?.textContent.includes('Bearbeitung beenden'));
    check('German edit labels translate');await page.locator('#language-toggle').click();
    await page.goto(base+'#/finance');
    const fundRow=()=>page.locator('tr[data-row-id="'+fixture.fund+'"]');
    await fundRow().waitFor();await toggle().click();await fundRow().locator('[data-row-edit]').click();await form().waitFor();
    check('finance list maps to its authoritative transaction',await input('资金记录ID').inputValue()===fixture.fund);
    await input('金额').fill('9007199254740993.1234');await input('交易摘要').fill('逐行精确金额保存');
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});
    check('large decimals remain exact',(await api('record',{object:'finance.资金流水表',id:fixture.fund})).values['金额']==='9007199254740993.1234');
    await page.goto(base+'#/finance?object='+encodeURIComponent('finance.资金流水表'));await page.locator('#object-filter').waitFor();await fundRow().waitFor();if(await toggle().getAttribute('aria-pressed')!=='true')await toggle().click();await fundRow().locator('[data-row-edit]').click();await form().waitFor();
    check('fund list edits its source row and locks currency',await input('资金记录ID').inputValue()===fixture.fund&&await form().locator('[data-table-field="币种"]').count()===0);
    // A response lost after commit must retry with the identical request ID.
    let lost=false;
    await page.route('**/api/entry/save?*',async route=>{
      if(lost){await route.continue();return;}lost=true;await route.fetch();await route.abort('failed');
    });
    await input('交易摘要').fill('丢失响应后幂等重试');await form().locator('[type=submit]').click();
    await form().locator('[data-table-edit-error]:not([hidden])').waitFor();await commit();await form().waitFor({state:'detached'});
    await page.unroute('**/api/entry/save?*');
    check('lost save response retries safely',(await api('record',{object:'finance.资金流水表',id:fixture.fund})).values['交易摘要']==='丢失响应后幂等重试');
    // Verify the responsive form and dark palette in an isolated browser session.
    await page.setViewportSize({width:390,height:844});await fundRow().waitFor();await fundRow().locator('[data-row-edit]').click();await form().waitFor();
    check('narrow-screen editor fits viewport',await page.evaluate(()=>{const box=document.querySelector('.table-edit-form').getBoundingClientRect();return document.documentElement.scrollWidth<=innerWidth+1&&box.left>=0&&box.right<=innerWidth&&box.width>300;}));
    while(await page.locator('html').getAttribute('data-theme')!=='dark')await page.locator('#theme-toggle').click();
    check('dark mode retains blue editing background',await page.locator('.table-edit-form').evaluate(el=>getComputedStyle(el).backgroundColor)==='rgb(17, 40, 61)');
    if(fixture.screenshot)await page.screenshot({path:fixture.screenshot,fullPage:true});
    await form().locator('[data-table-cancel]').click();
    await page.setViewportSize({width:1440,height:1000});await page.goto(fixture.url+'/?mode=live#/rd');await toggle().waitFor();
    const snapshots=await page.locator('#object-filter option').evaluateAll(options=>options.filter(o=>o.value.startsWith('erp_ops.')&&!o.value.endsWith('导入BOM与物料对应')).map(o=>o.value));
    if(snapshots.length){await page.locator('#object-filter').selectOption(snapshots[0]);await page.waitForFunction(()=>document.querySelector('[data-table-edit-toggle]')?.disabled===true);check('source snapshots remain immutable');}
    check('browser has no uncaught JavaScript errors',errors.length===0);
    fs.writeFileSync(fixture.result,JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
    console.log(JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
