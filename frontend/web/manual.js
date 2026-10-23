'use strict';
(() => {
  const h = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const titles={sales:'销售',inventory:'采购与库存',production:'生产',finance:'财务',rd:'研发',legal:'法务',analysis:'分析报告'};
  const schemaFor={inventory:'production',production:'production',sales:'sales',finance:'finance',rd:'rd',legal:'legal',analysis:'analysis'};
  const labels={'sales.销售订单登记表':'销售订单','production.采购订单表':'采购订单','rd.BOM登记表':'BOM','finance.会计凭证表':'会计凭证'};
  const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  const dialog=document.createElement('dialog'); dialog.id='manual-entry'; dialog.className='entry-dialog'; dialog.setAttribute('aria-label','手工录入'); document.body.append(dialog);
  let catalog=null,context=null,stack=[],group='sales',showAll=false,filter='',lastFocus=null,uiVersion=0;
  const object=key=>catalog.objects.find(o=>o.key===key);
  const identifier=()=>crypto.randomUUID();
  const modeLabel=mode=>mode==='demo'?'演示数据':'正式数据';
  const query=extra=>new URLSearchParams({mode:context?.mode||state.mode,...extra});
  const name=key=>labels[key]||object(key)?.name||key;
  async function request(path,extra={},options={}) {
    const response=await fetch('/api/entry/'+path+'?'+query(extra),options);
    let body;try{body=await response.json();}catch{throw new Error('服务未返回有效结果，请保留表单后重试。');}
    if(!response.ok){const error=new Error(body.error||'操作未完成');error.fields=body.fields||[];error.status=response.status;throw error;}
    return body;
  }
  function shell(title,subtitle,body) {
    const mode=context?.mode||state.mode;
    dialog.innerHTML=`<div class="entry-head"><div><span class="entry-mode ${mode==='demo'?'demo':''}">${modeLabel(mode)}</span><h2>${h(title)}</h2><p>${h(subtitle)}</p></div><button type="button" class="icon-button" data-entry-close aria-label="关闭录入">×</button></div><div class="entry-content">${body}</div>`;
    dialog.scrollTop=0;
  }
  async function loadCatalog(mode) {
    const response=await fetch('/api/entry/meta?'+new URLSearchParams({mode}));
    const body=await response.json();if(!response.ok)throw new Error(body.error||'无法读取录入配置');catalog=body;
  }
  function showError(error) {
    let box=dialog.querySelector('.entry-error');
    if(!box){box=document.createElement('div');box.className='entry-error';box.tabIndex=-1;dialog.querySelector('.entry-content').prepend(box);}
    box.textContent=error.message;box.hidden=false;
    dialog.querySelectorAll('.entry-field.invalid').forEach(e=>e.classList.remove('invalid'));
    for(const field of error.fields||[]) dialog.querySelectorAll('.entry-field').forEach(e=>{if(e.dataset.field===field)e.classList.add('invalid');});
    box.focus();
  }
  function chooser() {
    context=null;
    const schema=schemaFor[group];
    const favorites=catalog.preferred[group]||[];
    const rows=catalog.objects.filter(o=>o.schema===schema && (showAll||favorites.includes(o.name)) && (!filter||o.name.toLowerCase().includes(filter.toLowerCase())));
    rows.sort((a,b)=>{if(showAll)return a.name.localeCompare(b.name,'zh-CN');return favorites.indexOf(a.name)-favorites.indexOf(b.name);});
    shell('手工录入','选择业务类型，填写后保存到当前数据源。',`<div class="entry-tabs">${Object.entries(titles).map(([key,label])=>`<button type="button" data-entry-group="${key}" class="${group===key?'active':''}">${label}</button>`).join('')}</div><div class="entry-chooser-tools"><input id="entry-chooser-search" type="search" placeholder="搜索业务或主录名称" aria-label="搜索录入业务" value="${h(filter)}"><select id="entry-chooser-scope" aria-label="显示范围"><option value="common" ${!showAll?'selected':''}>常用业务</option><option value="all" ${showAll?'selected':''}>全部主录</option></select></div><div class="entry-cards">${rows.map(o=>`<button type="button" class="entry-card" data-entry-object="${h(o.key)}"><span>↗</span><strong>${h(name(o.key))}</strong><small>${o.children?h(o.children.label)+' · 一次保存':'新建记录 · 支持关联资料选择'}</small></button>`).join('')||'<p class="muted">没有匹配的录入业务。</p>'}</div><p class="entry-list-note">必填项标有 *。未掌握的可选信息可留空；数量、金额为空时不会按 0 保存。保存后可从本页和 SQLview 查询同一条记录。</p>`);
  }
  function localTimestamp(value) {
    if(!value)return '';
    const d=new Date(value);if(Number.isNaN(d.getTime()))return '';
    const pad=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  function field(col, owner, values, disabled=false) {
    const obj=object(owner.object),isPK=col.name===obj.pk,value=values[col.name];
    const required=col.required&&!col.default&&!col.automatic&&!isPK;
    const id='ef-'+owner.uid+'-'+obj.columns.indexOf(col);
    const attr=`id="${id}" data-entry-value data-owner="${h(owner.uid)}" data-field="${h(col.name)}" ${required?'required':''} ${disabled?'disabled':''}`;
    let control='',hint='',wide=false;
    if(col.reference){
      control=`<div class="entry-ref"><input type="search" data-ref-search="${id}" placeholder="搜索名称或编号" aria-label="搜索${h(col.name)}的关联记录" autocomplete="off"><select ${attr} data-ref-object="${h(owner.object)}" data-selected="${h(value??'')}"><option value="">${value?h(value):'请选择关联记录'}</option>${value?`<option value="${h(value)}" selected>${h(value)}</option>`:''}</select><button type="button" data-entry-new-ref="${id}" aria-label="新建${h(object(col.reference.target)?.name)}">新建</button></div>`;
      hint=object(col.reference.target)?.name||'';
    }else if(col.options.length){
      control=`<select ${attr}><option value="">请选择</option>${col.options.map(v=>`<option value="${h(v)}" ${value===v?'selected':''}>${h(v)}</option>`).join('')}</select>`;
    }else if(col.type==='date') control=`<input ${attr} type="date" value="${h(value||'')}">`;
    else if(col.type==='timestamp with time zone'){
      control=`<input ${attr} type="datetime-local" step="1" value="${localTimestamp(value)}">`;hint='按本机时区 '+timezone+' 保存';
    }else if(col.type.startsWith('numeric')||col.type==='integer'){
      control=`<input ${attr} type="text" inputmode="decimal" value="${h(value??'')}" autocomplete="off" placeholder="请明确填写，0 也需要录入">`;
      hint=col.type==='integer'?'整数':(col.type.match(/,(\d+)\)/)?'最多 '+col.type.match(/,(\d+)\)/)[1]+' 位小数':'十进制数');
    }else if(col.type==='jsonb'||/说明|摘要|依据|内容|地址|信息|条件|原话|范围|路径|定义|结论|方法|规则|备注/.test(col.name)){
      let text=value==null?'':typeof value==='object'?JSON.stringify(value,null,2):value;
      control=`<textarea ${attr} rows="3" maxlength="20000" ${col.type==='jsonb'?'placeholder="填写有效 JSON 文本"':''}>${h(text)}</textarea>`;wide=true;
    }else{
      const maximum=col.type.match(/character\((\d+)\)/)?.[1]||20000;
      control=`<input ${attr} type="text" value="${h(value??'')}" maxlength="${maximum}" ${isPK?'placeholder="留空自动编号，也可自定义"':''}>`;
      if(isPK)hint=context.operation==='update'?'记录编号保持不变':'留空时自动生成唯一编号';
      if(col.name==='币种')hint='三个大写字母，例如 CNY、USD、EUR';
    }
    return `<label class="entry-field ${wide?'wide':''}" data-field="${h(col.name)}"><span class="entry-label">${h(col.name)}${required?'<span class="entry-required-mark">*</span>':''}</span>${control}${hint?`<small>${h(hint)}</small>`:''}</label>`;
  }
  function fields(owner,hide=[]) {
    const obj=object(owner.object),main=[],more=[];
    for(const col of obj.columns){
      if(hide.includes(col.name)||col.automatic)continue;
      const content=field(col,owner,owner.values,context.operation==='update'&&owner.uid==='parent'&&col.name===obj.pk);
      if((col.required&&col.name!==obj.pk)||obj.one_of.some(group=>group.includes(col.name)))main.push(content);else more.push(content);
    }
    return `<div class="entry-grid">${main.join('')}</div>${more.length?`<details class="entry-more"><summary>更多字段 · ${more.length} 项</summary><div class="entry-grid">${more.join('')}</div></details>`:''}${obj.rules.length?`<details class="entry-rules"><summary>填写规则 · ${obj.rules.length} 项</summary><ul>${obj.rules.map(r=>`<li>${h(r)}</li>`).join('')}</ul></details>`:''}`;
  }
  function renderForm() {
    const obj=object(context.object),editing=context.operation==='update',spec=!editing&&obj.children;
    const childHtml=spec?context.children.map((row,i)=>`<section class="entry-section"><h3>${h(spec.label)} ${i+1}<button type="button" class="entry-row-remove" data-entry-remove-row="${h(row.uid)}" ${context.children.length<=spec.minimum?'disabled':''}>移除此行</button></h3>${fields(row,[spec.parent_field])}</section>`).join('')+`<button type="button" class="entry-row-add" data-entry-add-row>＋ 添加${h(spec.label)}</button>`:'';
    shell((editing?'修改':'新建')+name(obj.key),editing?'只修改明确需要调整的字段；保存时会核对当前 SQL 记录版本。':'填写真实业务信息；主录与明细会一起保存。',`<form class="entry-form" novalidate><div class="entry-error" role="alert" tabindex="-1" hidden></div><section class="entry-section"><h3>${editing?'记录信息':'基本信息'}${editing?'<small class="muted">'+h(context.id)+'</small>':''}</h3>${fields({object:obj.key,uid:'parent',values:context.values})}</section>${childHtml}<div class="entry-footer"><p>${modeLabel(context.mode)} · ${spec?'主录和全部明细一次提交':'保存后可在前端与 SQLview 查询'}<br>可选空项保留为未登记。</p><div><button type="button" class="button" data-entry-close>${stack.length?'返回上一级':'取消'}</button><button class="button primary" type="submit" id="entry-submit">保存到${context.mode==='demo'?'演示库':'正式库'}</button></div></div></form>`);
    const version=++uiVersion;
    dialog.querySelector('form').addEventListener('submit',save);
    dialog.querySelectorAll('details.entry-more').forEach(d=>d.addEventListener('toggle',()=>{if(d.open)loadVisibleReferences(version);}));
    loadVisibleReferences(version);
  }
  function ownerByUid(uid){return uid==='parent'?context:context.children.find(r=>r.uid===uid);}
  function readValue(input,col){
    if(input.value==='')return null;
    if(col.type==='timestamp with time zone')return new Date(input.value).toISOString();
    return input.value;
  }
  function collect() {
    if(!context)return;
    for(const input of dialog.querySelectorAll('[data-entry-value]')){
      if(input.disabled)continue;
      const owner=ownerByUid(input.dataset.owner);if(!owner)continue;
      const col=object(owner.object).columns.find(c=>c.name===input.dataset.field);
      // Editing submits only touched fields, preserving untouched NULLs, empty text and timestamp precision.
      if(context.operation==='update'&&!context.touched.has(col.name))continue;
      owner.values[col.name]=readValue(input,col);
    }
  }
  async function loadReference(select, q='', version=uiVersion){
    if(!select)return;
    const requestNumber=select._requestNumber=(select._requestNumber||0)+1;
    select.dataset.loading='1';
    const selected=select.value||select.dataset.selected||'';
    try{
      const data=await request('options',{object:select.dataset.refObject,field:select.dataset.field,q,selected});
      if(version!==uiVersion||!select.isConnected||requestNumber!==select._requestNumber)return;
      select.innerHTML='<option value="">请选择关联记录</option>'+data.rows.map(r=>`<option value="${h(r.value)}" ${r.value===selected?'selected':''}>${h(r.label)}</option>`).join('');
      if(!data.rows.length)select.options[0].textContent='尚无记录，可先点“新建”';
      select.dataset.loaded='1';
      const search=select.parentElement.querySelector('input');search.placeholder=data.more?'搜索名称或编号（当前显示前 50 项）':'搜索名称或编号';
    }catch(error){if(version===uiVersion&&select.isConnected)showError(error);}finally{select.dataset.loading='0';}
  }
  async function loadVisibleReferences(version){
    const selects=[...dialog.querySelectorAll('select[data-ref-object]')].filter(el=>!el.dataset.loaded&&!(el.closest('details')&&!el.closest('details').open));
    for(let i=0;i<selects.length;i+=3){if(version!==uiVersion)return;await Promise.all(selects.slice(i,i+3).map(el=>loadReference(el,'',version)));}
  }
  async function begin(key, editing=null) {
    const obj=object(key);if(!obj)throw new Error('该主录暂不支持录入');
    const mode=context?.mode||state.mode;
    context={object:key,uid:'parent',mode,values:editing?.values||{},operation:editing?'update':'create',id:editing?.id,version:editing?.version,touched:new Set(),children:[],requestId:null};
    if(!editing&&obj.children){for(let i=0;i<obj.children.minimum;i++)context.children.push({object:obj.children.object,uid:identifier(),values:{'行号':String(i+1)}});}
    renderForm();dialog.querySelector('[data-entry-value]:not([disabled])')?.focus();
  }
  async function save(event) {
    event.preventDefault();
    const form=event.target;if(context.busy)return;
    if(!form.reportValidity())return;
    try{
      collect();
      const obj=object(context.object),values={...context.values};
      if(context.operation==='update')for(const key of Object.keys(values))if(!context.touched.has(key))delete values[key];
      const payload={request_id:context.requestId||(context.requestId=identifier()),object:context.object,operation:context.operation,values};
      if(context.operation==='update'){payload.id=context.id;payload.version=context.version;}
      if(context.children.length)payload.children=context.children.map(row=>({object:row.object,values:row.values}));
      context.busy=true;form.classList.add('entry-busy');form.querySelector('button[type=submit]').textContent='正在保存…';
      const send=()=>request('save',{}, {method:'POST',headers:{'Content-Type':'application/json','X-EasyERP-Token':catalog.token},body:JSON.stringify(payload)});
      let result;
      try{result=await send();}catch(error){if(error.status!==403)throw error;await loadCatalog(context.mode);result=await send();}
      context.busy=false;
      const parent=result.records[0];
      if(stack.length){
        const previous=stack.pop();context=previous.context;const owner=ownerByUid(previous.owner);owner.values[previous.field]=parent.id;context.touched.add(previous.field);context.requestId=null;renderForm();return;
      }
      const savedObject=context.object,savedMode=context.mode;
      shell('保存成功','业务记录已写入当前数据源。',`<div class="entry-success"><div class="entry-success-symbol">✓</div><h3>已保存到${modeLabel(savedMode)}</h3><p>${h(name(savedObject))}${result.records.length>1?'及 '+(result.records.length-1)+' 条明细':''}已一起保存。</p><p class="entry-saved-id">${h(parent.id)}</p><div class="entry-success-actions"><button class="button primary" data-entry-view="${h(savedObject)}" data-entry-id="${h(parent.id)}">查看保存的记录</button><button class="button" data-entry-continue="${h(savedObject)}">继续录入同类</button><button class="button" data-entry-close>完成</button></div></div>`);
      // Reload reference labels and current query results after the database commit.
      if(state.mode===savedMode){try{const refreshed=await api('meta');if(state.mode===savedMode){meta=refreshed;await render();if(drawerState)await openDetail(drawerState.kind,drawerState.key,drawerState.object);}}catch{toast('已保存成功；列表暂未刷新，可稍后点击刷新。');}}
    }catch(error){context.busy=false;form.classList.remove('entry-busy');const button=form.querySelector('button[type=submit]');if(button)button.textContent='保存到'+(context.mode==='demo'?'演示库':'正式库');showError(error);}
  }
  function close(){
    if(context?.busy)return;
    uiVersion++;
    if(stack.length){context=stack.pop().context;renderForm();return;}
    dialog.close();context=null;lastFocus?.focus();
  }
  async function open(key=null,editId=null){
    lastFocus=document.activeElement;stack=[];context=null;catalog=null;
    shell('手工录入','正在读取可录入业务…','<div class="entry-loading">正在读取主录与填写规则…</div>');
    if(!dialog.open)dialog.showModal();
    try{
      await loadCatalog(state.mode);
      if(key){const editing=editId?{...await request('record',{object:key,id:editId}),id:editId}:null;await begin(key,editing);}
      else{group=titles[route]?route:'sales';showAll=false;filter='';chooser();}
    }catch(error){showError(error);}
  }
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  dialog.addEventListener('input',event=>{
    const el=event.target;
    if(el.id==='entry-chooser-search'){
      filter=el.value;const start=el.selectionStart;chooser();const replacement=dialog.querySelector('#entry-chooser-search');replacement.focus();replacement.setSelectionRange(start,start);return;
    }
    if(el.dataset.refSearch){clearTimeout(el._debounce);const version=uiVersion;el._debounce=setTimeout(()=>loadReference(dialog.querySelector('#'+el.dataset.refSearch),el.value,version),220);return;}
    if(el.hasAttribute('data-entry-value')&&context){context.touched.add(el.dataset.field);context.requestId=null;}
  });
  dialog.addEventListener('change',event=>{if(event.target.id==='entry-chooser-scope'){showAll=event.target.value==='all';chooser();}else if(event.target.hasAttribute('data-entry-value')&&context){if(event.target.dataset.refObject)event.target.dataset.selected=event.target.value;context.touched.add(event.target.dataset.field);context.requestId=null;}});
  dialog.addEventListener('click',async event=>{
    const button=event.target.closest('button');if(!button)return;
    try{
      if(button.hasAttribute('data-entry-close'))close();
      else if(button.dataset.entryGroup){group=button.dataset.entryGroup;filter='';chooser();}
      else if(button.dataset.entryObject)await begin(button.dataset.entryObject);
      else if(button.hasAttribute('data-entry-add-row')){collect();if(context.children.length>=100)throw new Error('一次最多录入 100 条明细');context.children.push({object:object(context.object).children.object,uid:identifier(),values:{'行号':String(context.children.length+1)}});context.requestId=null;renderForm();}
      else if(button.dataset.entryRemoveRow){collect();context.children=context.children.filter(r=>r.uid!==button.dataset.entryRemoveRow);context.requestId=null;renderForm();}
      else if(button.dataset.entryNewRef){
        collect();const select=dialog.querySelector('#'+button.dataset.entryNewRef),owner=ownerByUid(select.dataset.owner),col=object(owner.object).columns.find(c=>c.name===select.dataset.field);
        if(stack.length>=8)throw new Error('关联资料层级较深，请先完成最基础资料。');
        stack.push({context,owner:select.dataset.owner,field:select.dataset.field});await begin(col.reference.target);
      }else if(button.dataset.entryContinue){context=null;await begin(button.dataset.entryContinue);}
      else if(button.dataset.entryView){const key=button.dataset.entryView,id=button.dataset.entryId;close();await openDetail('record',id,key);}
    }catch(error){showError(error);}
  });
  document.querySelector('#entry-open').addEventListener('click',()=>open());
  window.easyerpManual={
    open,
    decorateDrawer(source,base){
      const key=viewOrigins[source]||source;
      const obj=meta?.objects.find(o=>o.schema+'.'+o.name===key&&o.kind==='r');
      if(!obj||base[obj.pk]==null)return;
      const button=document.createElement('button');button.type='button';button.className='button entry-drawer-edit';button.textContent='编辑这条记录';
      button.addEventListener('click',()=>open(key,String(base[obj.pk])));document.querySelector('#drawer .drawer-header p')?.after(button);
    }
  };
})();
