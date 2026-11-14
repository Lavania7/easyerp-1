'use strict';
(() => {
  const catalogs=new Map(),drafts=new Map(),saving=new Set();
  let enabled=false,contextKey='',active=null,openSequence=0;
  const h=esc;
  const draftKey=(mode,object,id)=>JSON.stringify([mode,object,id]);
  const modeLabel=mode=>mode==='demo'?'演示库':'正式库';

  async function request(path,mode,extra={},options={}){
    const response=await fetch('/api/entry/'+path+'?'+new URLSearchParams({mode,...extra}),options);
    let body;
    try{body=await response.json();}catch{throw new Error('服务未返回有效结果，请保留输入后重试。');}
    if(!response.ok){const error=new Error(body.error||'操作未完成');error.status=response.status;error.fields=body.fields||[];throw error;}
    return body;
  }
  async function catalog(mode,refresh=false){
    if(refresh||!catalogs.has(mode))catalogs.set(mode,request('meta',mode).catch(error=>{catalogs.delete(mode);throw error;}));
    return catalogs.get(mode);
  }
  function fieldValue(col,value){
    if(value==null)return '';
    if(col.type==='timestamp with time zone'){
      const date=new Date(value);
      return Number.isNaN(date.getTime())?'':new Date(date.getTime()+8*3600000).toISOString().slice(0,19);
    }
    if(col.type==='boolean')return String(value);
    return typeof value==='object'?JSON.stringify(value,null,2):String(value);
  }
  function field(col,obj,draft,index){
    const original=fieldValue(col,draft.base[col.name]);
    const value=draft.inputs.has(col.name)?draft.inputs.get(col.name):original;
    const locked=col.name===obj.pk||col.automatic||col.name==='币种';
    const attrs=`id="table-field-${index}" data-table-field="${h(col.name)}" data-i18n-ignore ${locked?'disabled':''} ${col.required&&!locked?'required':''}`;
    let control='',wide=false;
    if(col.reference&&!locked){
      control=`<div class="table-edit-ref"><input type="search" data-table-ref-search="${index}" placeholder="搜索名称或编号" aria-label="搜索${h(col.name)}的关联记录" autocomplete="off"><select ${attrs} data-table-reference><option value="">请选择关联记录</option>${value?`<option value="${h(value)}" selected>${h(value)}</option>`:''}</select></div>`;
    }else if(col.options.length||col.type==='boolean'){
      const choices=col.type==='boolean'?['true','false']:col.options;
      control=`<select ${attrs}><option value="">请选择</option>${choices.map(v=>`<option value="${h(v)}" ${value===v?'selected':''}>${h(v)}</option>`).join('')}</select>`;
    }else if(col.type==='date')control=`<input ${attrs} type="date" value="${h(value)}">`;
    else if(col.type==='timestamp with time zone')control=`<input ${attrs} type="datetime-local" step="1" value="${h(value)}"><small>按北京时间（UTC+8）保存</small>`;
    else if(col.type==='jsonb'||/说明|摘要|依据|内容|地址|信息|条件|原话|范围|路径|定义|结论|方法|规则|备注/.test(col.name)){
      wide=true;control=`<textarea ${attrs} rows="2" maxlength="20000">${h(value)}</textarea>`;
    }else{
      const numeric=col.type.startsWith('numeric')||col.type==='integer';
      const maximum=col.type.match(/character\((\d+)\)/)?.[1]||20000;
      control=`<input ${attrs} type="text" ${numeric?'inputmode="decimal"':''} maxlength="${maximum}" value="${h(value)}">`;
    }
    return `<label class="table-edit-field ${wide?'wide':''}"><span data-ui-label>${h(col.name)}${col.required&&!locked?' *':''}</span>${control}</label>`;
  }
  function errorBox(session,error){
    if(!session.form?.isConnected){toast(error.message);return;}
    const box=session.form.querySelector('[data-table-edit-error]');box.hidden=false;box.textContent=error.message;
    session.form.querySelectorAll('.invalid').forEach(el=>el.classList.remove('invalid'));
    for(const input of session.form.querySelectorAll('[data-table-field]')){
      if((error.fields||[]).includes(input.dataset.tableField))input.closest('label').classList.add('invalid');
    }
    box.focus();
  }
  function removeEditor(){
    openSequence++;
    if(active){
      active.row.classList.remove('table-row-selected');
      active.row.querySelector('[data-row-edit]')?.setAttribute('aria-expanded','false');
      active.editor.remove();active=null;
    }
  }
  async function loadReference(session,select,search=''){
    const version=select._version=(select._version||0)+1;
    const value=select.value;
    const col=session.obj.columns.find(c=>c.name===select.dataset.tableField);
    try{
      const result=await request('options',session.mode,{object:session.obj.key,field:col.name,q:search,selected:value});
      if(active!==session||!select.isConnected||select._version!==version)return;
      select.innerHTML='<option value="">请选择关联记录</option>'+result.rows.map(r=>`<option value="${h(r.value)}" ${r.value===value?'selected':''}>${h(r.label)}</option>`).join('');
    }catch(error){if(active===session)errorBox(session,error);}
  }
  async function openRow(row){
    const mode=state.mode,object=row.dataset.rowObject,id=row.dataset.rowId,key=draftKey(mode,object,id);
    if(saving.has(key)){toast('这条记录正在保存，请稍候。');return;}
    if(active?.key===key){active.form?.querySelector('[data-table-field]:not(:disabled)')?.focus();return;}
    removeEditor();
    const serial=openSequence;
    const editor=document.createElement('tr');editor.className='table-row-editor';
    const cell=editor.insertCell();cell.colSpan=row.cells.length;cell.innerHTML='<div class="table-editor-loading" data-ui-label>正在读取主录与填写规则…</div>';
    row.after(editor);row.classList.add('table-row-selected');row.querySelector('[data-row-edit]').setAttribute('aria-expanded','true');
    const session={row,editor,key,mode,object,id};active=session;
    try{
      const metadata=await catalog(mode);
      if(openSequence!==serial||!row.isConnected||state.mode!==mode)return;
      const obj=metadata.objects.find(o=>o.key===object);
      if(!obj)throw new Error('该主录暂不支持修改。');
      let draft=drafts.get(key);
      if(!draft){const record=await request('record',mode,{object,id});draft={base:record.values,version:record.version,inputs:new Map(),requestId:null};}
      if(openSequence!==serial||!row.isConnected||state.mode!==mode)return;
      drafts.set(key,draft);Object.assign(session,{obj,draft});
      cell.innerHTML=`<form class="table-edit-form"><div class="table-edit-heading"><strong data-ui-label>修改这条记录</strong><span data-ui-label>保存到${modeLabel(mode)}</span><code data-i18n-ignore>${h(id)}</code></div><p class="table-edit-note" data-ui-label>修改主录后，关联信息和计算结果会自动刷新。留空字段保存为 NULL。</p><div class="table-edit-error" data-table-edit-error role="alert" tabindex="-1" hidden></div><fieldset><div class="table-edit-fields">${obj.columns.filter(col=>!col.retired_reference).map((col,i)=>field(col,obj,draft,i)).join('')}</div><div class="table-edit-actions"><button type="button" class="button" data-table-cancel><span data-ui-label>取消</span></button><button type="submit" class="button primary table-edit-save" data-ui-label>保存到${modeLabel(mode)}</button></div></fieldset></form>`;
      session.form=cell.querySelector('form');
      // The row action is at the right edge of wide tables. Bring its form into view.
      row.closest('.table-wrap').scrollLeft=0;
      const remember=event=>{
        const input=event.target.closest('[data-table-field]');if(!input||input.disabled)return;
        const col=obj.columns.find(c=>c.name===input.dataset.tableField),original=fieldValue(col,draft.base[col.name]);
        if(input.value===original)draft.inputs.delete(col.name);else draft.inputs.set(col.name,input.value);
        draft.requestId=null;
      };
      session.form.addEventListener('input',remember);session.form.addEventListener('change',remember);
      session.form.addEventListener('submit',event=>{event.preventDefault();save(session);});
      session.form.querySelector('[data-table-cancel]').addEventListener('click',()=>{drafts.delete(key);removeEditor();row.querySelector('[data-row-edit]')?.focus();});
      for(const search of session.form.querySelectorAll('[data-table-ref-search]')){
        const select=search.nextElementSibling;
        search.addEventListener('input',()=>{clearTimeout(search._timer);search._timer=setTimeout(()=>loadReference(session,select,search.value),220);});
      }
      // Reference results include the selected ID, even if it is outside the first page.
      const selects=[...session.form.querySelectorAll('[data-table-reference]')];
      for(let i=0;i<selects.length;i+=3){if(active!==session)return;await Promise.all(selects.slice(i,i+3).map(select=>loadReference(session,select)));}
      if(active===session)session.form.querySelector('[data-table-field]:not(:disabled)')?.focus({preventScroll:true});
    }catch(error){if(active===session){cell.innerHTML='<div class="table-edit-error" role="alert"></div>';cell.firstChild.textContent=error.message;toast(error.message);removeEditor();}}
  }
  async function save(session){
    const {draft,key,mode,obj}=session;
    if(saving.has(key)||!session.form.reportValidity())return;
    if(!draft.inputs.size){errorBox(session,new Error('尚未修改任何字段。'));return;}
    try{
      const values={};
      for(const [name,value] of draft.inputs){
        const col=obj.columns.find(c=>c.name===name);
        values[name]=value===''?null:col.type==='timestamp with time zone'?new Date(value+window.ERPDefaults.utcOffset).toISOString():col.type==='boolean'?value==='true':value;
      }
      const payload={request_id:draft.requestId||(draft.requestId=crypto.randomUUID()),object:obj.key,operation:'update',id:session.id,version:draft.version,values};
      saving.add(key);session.form.querySelector('fieldset').disabled=true;
      const button=session.form.querySelector('[type=submit]');button.textContent='正在保存…';
      const send=async()=>request('save',mode,{}, {method:'POST',headers:{'Content-Type':'application/json','X-EasyERP-Token':(await catalog(mode)).token},body:JSON.stringify(payload)});
      try{await send();}catch(error){if(error.status!==403)throw error;await catalog(mode,true);await send();}
      drafts.delete(key);
      if(active===session)removeEditor();
      toast(mode==='demo'?'已保存到演示库，SQL数据库已更新。':'已保存到正式库，SQL数据库已更新。');
      window.dispatchEvent(new CustomEvent('erp:data-changed',{detail:{mode}}));
    }catch(error){errorBox(session,error);}
    finally{
      saving.delete(key);
      if(session.form.isConnected){session.form.querySelector('fieldset').disabled=false;session.form.querySelector('[type=submit]').textContent='保存到'+modeLabel(mode);}
    }
  }
  function syncPanel(panel){
    panel.classList.toggle('is-editing',enabled);
    const toggle=panel.querySelector('[data-table-edit-toggle]');
    toggle.setAttribute('aria-pressed',String(enabled));toggle.querySelector('span').textContent=enabled?'完成编辑':'编辑';
  }
  function mount(){
    // Drafts survive refresh, pagination and source changes, keyed by database/table/ID.
    if(active){if(active.draft?.inputs.size)toast('未保存的输入已保留，再次编辑该记录可继续。');removeEditor();}
    const panel=document.querySelector('#content .table-edit-panel');
    const key=panel?JSON.stringify([state.mode,panel.dataset.editSource]):'';
    if(key!==contextKey){enabled=false;contextKey=key;}
    if(!panel)return;
    syncPanel(panel);
    panel.querySelector('[data-table-edit-toggle]').addEventListener('click',()=>{
      enabled=!enabled;
      if(!enabled){if(active?.draft?.inputs.size)toast('未保存的输入已保留，再次编辑该记录可继续。');removeEditor();}
      syncPanel(panel);
    });
    panel.addEventListener('click',event=>{const button=event.target.closest('[data-row-edit]');if(enabled&&button)openRow(button.closest('tr'));});
  }
  window.addEventListener('beforeunload',event=>{
    if(saving.size||[...drafts.values()].some(d=>d.inputs.size)){event.preventDefault();event.returnValue='';}
  });
  window.easyerpTableEdit={mount};
  mount();
})();
