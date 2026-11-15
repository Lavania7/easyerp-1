// Browser companion for test_table_edit.py. Fixtures and cleanup belong to Python.
'use strict';
const {objectValues, objectValue, selectObject}=require('./object_menu_helpers.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.EASYERP_PLAYWRIGHT_MODULE||'playwright');
const fixture=JSON.parse(process.env.EASYERP_TABLE_FIXTURE);
const passed=[];
const check=(name,condition=true)=>{assert.ok(condition,name);passed.push(name);console.log('PASS: '+name);};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.EASYERP_BROWSER_CHANNEL||'msedge'});
  try{
    const errors=[];let page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.on('pageerror',error=>errors.push(error.message));
    const base=fixture.url+'/?mode=demo&start=2026-10-01&end=2026-10-31';
    const customerURL=base+'#/archive?object='+encodeURIComponent('sales.客户档案表');
    const row=()=>page.locator('tr[data-row-id="'+fixture.customer+'"]');
    const toggle=()=>page.locator('[data-table-edit-toggle]');
    const form=()=>page.locator('.table-edit-form');
    const input=name=>form().locator('[data-table-field="'+name+'"]');
    const add=()=>page.locator('[data-table-add]');
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
    check('view mode hides add action',!await add().isVisible());
    const sizes=await page.evaluate(()=>({edit:document.querySelector('[data-table-edit-toggle]').getBoundingClientRect().height,entry:document.querySelector('#entry-open').getBoundingClientRect().height,color:getComputedStyle(document.querySelector('[data-table-edit-toggle]')).color}));
    check('blue edit button matches entry size and has white text',Math.abs(sizes.edit-sizes.entry)<=2&&sizes.color==='rgb(255, 255, 255)');
    await toggle().click();
    check('toggle enables editing and blue table treatment',await toggle().getAttribute('aria-pressed')==='true'&&await page.locator('.table-edit-panel.is-editing').count()===1);
    await add().click();await form().waitFor();
    check('add opens an inline create form for the current table',await form().getAttribute('data-table-operation')==='create'&&await page.locator('#manual-entry[open]').count()===0);
    check('new IDs are optional and editable',!await input('客户ID').isDisabled()&&await input('客户ID').getAttribute('required')===null);
    await input('客户名称').fill('取消的新增条目');await form().locator('[data-table-cancel]').click();
    await add().click();await form().waitFor();
    check('cancel discards the new draft',await input('客户名称').inputValue()==='');
    await form().locator('[data-table-cancel]').click();
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
    await fundRow().waitFor();await page.locator('.table-edit-panel.is-editing').waitFor();await fundRow().locator('[data-row-edit]').click();await form().waitFor();
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
    // An empty filtered table must still offer a local create form.
    await page.setViewportSize({width:1440,height:1000});
    const emptyURL=base+'&search='+fixture.newCustomer+'#/archive?object='+encodeURIComponent('sales.客户档案表');
    await page.goto(emptyURL);await toggle().waitFor();
    check('empty table retains normal view placeholder',await page.locator('.table-view-empty').isVisible()&&!await add().isVisible());
    await toggle().click();await add().click();await form().waitFor();
    check('empty table supports inline create',await form().getAttribute('data-table-operation')==='create');
    // Native required validation must not post a blank record.
    let createPosts=0;const countPost=request=>{if(request.method()==='POST'&&request.url().includes('/api/entry/save'))createPosts++;};
    page.on('request',countPost);
    const customerMeta=(await api('meta')).objects.find(o=>o.key==='sales.客户档案表');
    const required=customerMeta.columns.filter(c=>c.required&&!c.default&&!c.automatic&&c.name!==customerMeta.pk&&!c.retired_reference);
    check('new required fields follow the current SQL metadata',await form().locator('[data-table-field][required]').count()===required.length);
    if(required.length){
      await form().locator('[type=submit]').click();
      check('required new fields block submission',createPosts===0&&await input(required[0].name).evaluate(el=>!el.validity.valid));
    }
    await input('客户ID').fill(fixture.newCustomer);await input('客户名称').fill('新增草稿 <script>保持原文</script>');
    await input('客户来源标识').fill(fixture.run);
    await toggle().click();await toggle().click();await add().click();await form().waitFor();
    check('new draft survives leaving edit mode',(await input('客户名称').inputValue()).includes('新增草稿'));
    await page.locator('#refresh').click();await form().waitFor({state:'detached'});await add().click();await form().waitFor();
    check('new draft survives refresh',await input('客户ID').inputValue()===fixture.newCustomer);
    await selectObject(page,'production.供应商档案表');
    await page.waitForFunction(()=>document.querySelector('.table-edit-panel')?.dataset.editSource==='production.供应商档案表');
    await toggle().click();await add().click();await form().waitFor();
    check('different tables have separate new drafts',await input('名称').inputValue()==='');
    await form().locator('[data-table-cancel]').click();await selectObject(page,'sales.客户档案表');
    await page.waitForFunction(()=>document.querySelector('.table-edit-panel')?.dataset.editSource==='sales.客户档案表');
    await toggle().click();await add().click();await form().waitFor();
    await page.locator('#source-toggle').click();await page.locator('[data-source-value="live"]').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='本机数据库'&&!!document.querySelector('[data-table-edit-toggle]'));
    check('switching source exits new entry editing',await toggle().getAttribute('aria-pressed')==='false');
    await toggle().click();await add().click();await form().waitFor();
    check('live source does not inherit demo new entry values',await input('客户名称').inputValue()==='');
    await form().locator('[data-table-cancel]').click();
    await page.locator('#source-toggle').click();await page.locator('[data-source-value="demo"]').click();
    await page.waitForFunction(()=>document.querySelector('#connection').textContent==='演示数据'&&!!document.querySelector('[data-table-edit-toggle]'));
    await toggle().click();await add().click();await form().waitFor();
    check('returning to demo restores the new draft',await input('客户ID').inputValue()===fixture.newCustomer);
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('[data-table-add]').textContent.includes('Add entry'));
    check('English add label translates');
    await page.locator('#language-toggle').click();await page.waitForFunction(()=>document.querySelector('[data-table-add]').textContent.includes('Eintrag hinzufügen'));
    check('German add label translates');await page.locator('#language-toggle').click();
    await page.setViewportSize({width:390,height:844});
    check('narrow-screen create form fits viewport',await form().evaluate(el=>{const r=el.getBoundingClientRect();return r.width>300&&r.left>=0&&r.right<=innerWidth&&document.documentElement.scrollWidth<=innerWidth+1;}));
    if(fixture.screenshot)await page.screenshot({path:fixture.screenshot.replace(/\.png$/, '-create.png'),fullPage:true});
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});
    const added=()=>page.locator('tr[data-row-id="'+fixture.newCustomer+'"]');await added().waitFor();
    check('custom ID new entry is saved and appears in the table',await added().textContent().then(t=>t.includes('新增草稿')));
    check('new business text is escaped',await added().locator('script').count()===0);
    const created=await api('record',{object:'sales.客户档案表',id:fixture.newCustomer});
    check('unfilled optional new fields remain NULL',created.values['产业分类']===null);
    check('successful creation keeps edit mode enabled',await toggle().getAttribute('aria-pressed')==='true');
    await add().click();await form().waitFor();
    check('successful creation clears its draft',await input('客户ID').inputValue()===''&&await input('客户名称').inputValue()==='');
    await form().locator('[data-table-cancel]').click();
    // Let the backend assign the ID. A lost create response must reuse the same request.
    await page.setViewportSize({width:1440,height:1000});await add().click();await form().waitFor();
    await input('客户名称').fill(fixture.run+'_auto');await input('客户来源标识').fill(fixture.run);
    let firstRequest=null,autoId=null,retries=0;
    await page.route('**/api/entry/save?*',async route=>{
      const payload=route.request().postDataJSON();
      assert.equal(payload.operation,'create');assert.ok(!payload.values['客户ID']);
      if(!firstRequest){firstRequest=payload;const response=await route.fetch();assert.equal(response.status(),200);autoId=(await response.json()).records[0].id;await route.abort('failed');}
      else{assert.deepEqual(payload,firstRequest);retries++;await route.continue();}
    });
    await form().locator('[type=submit]').click();await form().locator('[data-table-edit-error]:not([hidden])').waitFor();
    check('failed create response preserves input',await input('客户名称').inputValue()===fixture.run+'_auto');
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});await page.unroute('**/api/entry/save?*');
    check('auto ID create retries identical payload',retries===1&&autoId&&!!(await api('record',{object:'sales.客户档案表',id:autoId})).version);
    page.off('request',countPost);
    // Isolate a fresh fund-entry visit from response-loss routing and customer navigation.
    await page.close();page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.on('pageerror',error=>errors.push(error.message));
    // Reference values and zero amounts must be sent verbatim; currency comes from the account.
    await page.goto(base+'#/finance?object='+encodeURIComponent('finance.资金流水表'));
    await page.waitForFunction(()=>document.querySelector('.table-edit-panel')?.dataset.editSource==='finance.资金流水表'&&!!document.querySelector('[data-table-add]'));
    if(await toggle().getAttribute('aria-pressed')!=='true')await toggle().click();
    await add().click();await form().waitFor();
    await input('资金记录ID').fill(fixture.newFund);await input('账户ID').selectOption('account');
    await input('发生时间').fill('2026-10-30T12:00');await input('金额').fill('0');await input('收支方向').selectOption('支出');
    check('new fund currency follows its source account',await form().locator('[data-table-field="币种"]').count()===0);
    assert.equal((await commit()).status(),200);await form().waitFor({state:'detached'});
    const newFund=await api('record',{object:'finance.资金流水表',id:fixture.newFund});
    check('new reference and real zero save exactly',newFund.values['账户ID']==='account'&&newFund.values['金额']==='0.0000');
    // A pre-existing primary key must fail without updating the original row.
    await add().click();await form().waitFor();await input('资金记录ID').fill(fixture.newFund);await input('账户ID').selectOption('account');await input('发生时间').fill('2026-10-30T12:00');await input('金额').fill('1');await input('收支方向').selectOption('支出');
    assert.equal((await commit()).status(),409);await form().locator('[data-table-edit-error]:not([hidden])').waitFor();
    check('duplicate new ID preserves form and existing record',await input('金额').inputValue()==='1'&&(await api('record',{object:'finance.资金流水表',id:fixture.newFund})).values['金额']==='0.0000');
    await form().locator('[data-table-cancel]').click();
    await page.goto(fixture.url+'/?mode=live#/rd');await toggle().waitFor();
    const snapshots=await objectValues(page).then(options=>options.filter(value=>value.startsWith('erp_ops.')&&!value.endsWith('导入BOM与物料对应')));
    if(snapshots.length){await selectObject(page,snapshots[0]);await page.waitForFunction(()=>document.querySelector('[data-table-edit-toggle]')?.disabled===true);check('source snapshots remain immutable');}
    check('browser has no uncaught JavaScript errors',errors.length===0);
    fs.writeFileSync(fixture.result,JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
    console.log(JSON.stringify({status:'PASS',checks:passed.length,passed},null,2));
  }catch(error){
    const page=browser.contexts()[0]?.pages()[0];
    if(page&&!page.isClosed())console.error('Browser state:',await page.evaluate(()=>({source:document.querySelector('.table-edit-panel')?.dataset.editSource,editing:document.querySelector('[data-table-edit-toggle]')?.getAttribute('aria-pressed'),addButtons:document.querySelectorAll('[data-table-add]').length,tables:document.querySelectorAll('#content table').length,loaded:!!window.easyerpTableEdit,error:document.querySelector('.error-panel')?.textContent})));
    throw error;
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
