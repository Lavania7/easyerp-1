'use strict';
(() => {
  const OBJECT='legal.公司主体档案表',h=esc;
  const trigger=document.querySelector('#company-trigger');
  const popover=document.createElement('div');popover.id='company-popover';popover.className='company-popover';popover.hidden=true;popover.setAttribute('role','dialog');popover.setAttribute('aria-label','公司主体');document.body.append(popover);
  const dialog=document.createElement('dialog');dialog.id='company-details';dialog.className='company-dialog';dialog.setAttribute('aria-label','公司详细信息');document.body.append(dialog);
  const cache=new Map(),selected=new Map(),requests=new Map();
  let source=null,editor=null,openNumber=0;
  const groups=[
    ['公司标识',[['公司名称','公司中文名'],['公司英文名'],['公司简称'],['统一社会信用代码']]],
    ['地址与联系',[['注册地址'],['办公地址'],['联系电话'],['联系邮箱'],['官方网站'],['联系人']]],
    ['工商信息',[['法定代表人'],['成立日期'],['有效状态'],['经营范围']]],
    ['资料与备注',[['登记资料路径'],['税务资料路径'],['资料版本'],['备注']]]
  ];
  const sourceLabel=mode=>mode==='demo'?'演示数据':'正式数据';
  const storageKey=mode=>'easyerp.company.'+mode;
  function getSelected(mode){
    if(!selected.has(mode)){let value='';try{value=localStorage.getItem(storageKey(mode))||'';}catch{}selected.set(mode,value);}
    return selected.get(mode);
  }
  function setSelected(mode,id){selected.set(mode,id);try{if(id)localStorage.setItem(storageKey(mode),id);else localStorage.removeItem(storageKey(mode));}catch{}}
  function current(mode=state.mode){return cache.get(mode)?.find(row=>row['主体ID']===getSelected(mode))||null;}
  const value=text=>text==null||text===''?'<span class="muted" data-ui-label>未填写</span>':`<span data-i18n-ignore>${h(text)}</span>`;
  async function request(path,mode,extra={},options={}){
    const response=await fetch('/api/'+path+'?'+new URLSearchParams({mode,...extra}),options);
    let body;try{body=await response.json();}catch{throw new Error('服务未返回有效结果，请保留输入后重试。');}
    if(!response.ok){const error=new Error(body.error||'操作未完成');error.status=response.status;error.fields=body.fields||[];throw error;}
    return body;
  }
  function paintBrand(){
    const company=current(),label=company?.['公司名称'];
    document.querySelector('#company-brand-name').textContent=label||(window.ERPUI?.t('设置公司主体')||'设置公司主体');
    trigger.title=company?.['公司名称']||'设置公司主体';
  }
  function position(){
    if(popover.hidden)return;
    const anchor=trigger.getBoundingClientRect(),width=popover.offsetWidth;
    popover.style.left=Math.max(12,Math.min(anchor.left,innerWidth-width-12))+'px';
    popover.style.top=Math.max(12,Math.min(anchor.bottom+10,innerHeight-popover.offsetHeight-12))+'px';
  }
  function paintPopover(){
    if(popover.hidden)return;
    const rows=cache.get(state.mode),company=current();
    const summary=company?`<div class="company-summary-title"><h2 data-i18n-ignore>${h(company['公司名称'])}</h2>${company['公司英文名']?`<p data-i18n-ignore>${h(company['公司英文名'])}</p>`:'<p class="muted" data-ui-label>英文名未填写</p>'}</div><dl class="company-summary">${[['统一社会信用代码',company['统一社会信用代码']],['地址',company['办公地址']||company['注册地址']],['电话',company['联系电话']]].map(([label,text])=>`<div><dt>${label}</dt><dd>${value(text)}</dd></div>`).join('')}</dl>`:'<div class="company-empty" data-ui-label>选择已有主体，或新增公司基本信息。</div>';
    popover.innerHTML=`<div class="company-popover-head"><strong>公司主体</strong><span class="company-source">${sourceLabel(state.mode)}</span><button type="button" class="icon-button" data-company-close aria-label="关闭">×</button></div>${rows?`<label class="company-select-label"><span>当前主体</span><select data-company-select aria-label="当前主体"><option value="">请选择公司主体</option>${rows.map(row=>`<option data-i18n-ignore value="${h(row['主体ID'])}" ${row['主体ID']===company?.['主体ID']?'selected':''}>${h(row['公司名称'])}${row['有效状态']?' · '+h(row['有效状态']):''}</option>`).join('')}</select></label><p class="company-context-hint">新建业务时默认填入所属主体。</p>${summary}<div class="company-popover-actions"><button type="button" class="button" data-company-new>新增主体</button><button type="button" class="button primary" data-company-details ${company?'':'disabled'}>详细信息</button></div>`:'<p class="company-empty">正在读取公司信息…</p>'}`;
    position();
  }
  async function refresh(mode=state.mode){
    const serial=(requests.get(mode)||0)+1;requests.set(mode,serial);
    try{
      let rows=[],offset=0;
      for(;;){
        const result=await request('explore',mode,{object:OBJECT,limit:200,offset,date_filter:'0'});rows.push(...result.rows);
        offset+=result.rows.length;if(offset>=Number(result.total[0].count)||!result.rows.length)break;
      }
      if(requests.get(mode)!==serial)return;
      cache.set(mode,rows);
      if(getSelected(mode)&&!rows.some(row=>row['主体ID']===getSelected(mode)))setSelected(mode,'');
      if(!getSelected(mode)&&rows.length===1)setSelected(mode,rows[0]['主体ID']);
      if(state.mode===mode){paintBrand();paintPopover();}
    }catch(error){
      if(state.mode===mode){paintBrand();if(!popover.hidden){popover.innerHTML='<div class="company-empty" role="alert"></div>';popover.firstChild.textContent=error.message;position();}toast(error.message);}
    }
  }
  function syncSource(){
    if(source===state.mode)return;
    source=state.mode;closePopover();paintBrand();refresh(source);
  }
  function closePopover(focus=false){popover.hidden=true;trigger.setAttribute('aria-expanded','false');if(focus)trigger.focus();}
  function field(name,label,obj,values){
    const col=obj.columns.find(c=>c.name===name);if(!col)return '';
    const text=values[name]??'',wide=/地址|范围|路径|备注/.test(name);
    const attrs=`id="company-field-${obj.columns.indexOf(col)}" data-company-field="${h(name)}" ${col.required||name==='公司名称'?'required':''} data-i18n-ignore`;
    let control;
    if(col.options.length)control=`<select ${attrs}><option value="">请选择</option>${col.options.map(item=>`<option value="${h(item)}" ${item===text?'selected':''}>${h(item)}</option>`).join('')}</select>`;
    else if(wide)control=`<textarea ${attrs} rows="2" maxlength="20000">${h(text)}</textarea>`;
    else control=`<input ${attrs} type="${name==='成立日期'?'date':name==='联系邮箱'?'email':name==='联系电话'?'tel':'text'}" value="${h(text)}" maxlength="20000">`;
    return `<label class="company-field ${wide?'wide':''}"><span>${h(label||name)}${col.required||name==='公司名称'?'<span class="company-required" aria-hidden="true"> *</span>':''}</span>${control}</label>`;
  }
  function showError(error){
    const box=dialog.querySelector('[data-company-error]');if(!box)return;
    box.hidden=false;box.textContent=error.message;
    dialog.querySelectorAll('.company-field.invalid').forEach(el=>el.classList.remove('invalid'));
    for(const control of dialog.querySelectorAll('[data-company-field]'))if((error.fields||[]).includes(control.dataset.companyField))control.closest('label').classList.add('invalid');
    box.focus();
  }
  async function openDetails(create=false){
    const mode=state.mode,company=current(mode),id=create?null:company?.['主体ID'];
    if(!create&&!id)return;
    closePopover();const serial=++openNumber;
    dialog.innerHTML='<div class="company-dialog-loading">正在读取公司信息…</div>';dialog.showModal();
    try{
      const metadata=await request('entry/meta',mode),obj=metadata.objects.find(o=>o.key===OBJECT);
      const record=create?null:await request('entry/record',mode,{object:OBJECT,id});
      if(serial!==openNumber||!dialog.open)return;
      if(!obj?.columns.some(c=>c.name==='公司英文名'))throw new Error('公司信息扩展尚未安装，请运行公司档案升级脚本。');
      const values=record?.values||{};
      editor={mode,id,obj,metadata,values,version:record?.version,changed:new Set(),requestId:null,busy:false};
      dialog.innerHTML=`<form class="company-form"><header class="company-dialog-head"><div><span class="company-source">${sourceLabel(mode)}</span><h2>${create?'新增公司主体':'公司详细信息'}</h2>${id?`<p data-i18n-ignore>${h(values['公司名称'])}</p>`:''}</div><button type="button" class="icon-button" data-company-cancel aria-label="关闭公司信息">×</button></header><div class="company-dialog-body"><div class="company-error" data-company-error role="alert" tabindex="-1" hidden></div>${groups.map(([title,fields])=>`<section class="company-section"><h3>${title}</h3><div class="company-field-grid">${fields.map(([name,label])=>field(name,label,obj,values)).join('')}</div></section>`).join('')}${id?`<p class="company-record-id"><span>主体ID</span><code data-i18n-ignore>${h(id)}</code></p>`:''}</div><footer class="company-dialog-footer"><button type="button" class="button" data-company-cancel>取消</button><button type="submit" class="button primary" data-company-save>保存到${mode==='demo'?'演示库':'正式库'}</button></footer></form>`;
      dialog.querySelector('form').addEventListener('submit',save);
      dialog.querySelector('[data-company-field="公司名称"]').focus();
    }catch(error){if(serial===openNumber&&dialog.open){dialog.innerHTML='<div class="company-dialog-loading" role="alert"></div><button type="button" class="button" data-company-cancel>关闭</button>';dialog.firstChild.textContent=error.message;}}
  }
  async function save(event){
    event.preventDefault();const session=editor;if(!session||session.busy)return;
    const form=event.target;if(!form.reportValidity())return;
    if(session.id&&!session.changed.size){showError(new Error('尚未修改任何字段。'));return;}
    const values={};
    for(const input of form.querySelectorAll('[data-company-field]')){
      if(session.id&&!session.changed.has(input.dataset.companyField))continue;
      if(!session.id&&!input.value)continue;
      values[input.dataset.companyField]=input.value===''?null:input.value;
    }
    const payload={request_id:session.requestId||(session.requestId=crypto.randomUUID()),object:OBJECT,operation:session.id?'update':'create',values};
    if(session.id){payload.id=session.id;payload.version=session.version;}
    session.busy=true;form.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=true);form.querySelector('[data-company-save]').textContent='正在保存…';
    try{
      const send=()=>request('entry/save',session.mode,{}, {method:'POST',headers:{'Content-Type':'application/json','X-EasyERP-Token':session.metadata.token},body:JSON.stringify(payload)});
      let result;
      try{result=await send();}catch(error){if(error.status!==403)throw error;session.metadata=await request('entry/meta',session.mode);result=await send();}
      setSelected(session.mode,result.records[0].id);
      editor=null;dialog.close();trigger.focus();await refresh(session.mode);
      window.dispatchEvent(new CustomEvent('erp:data-changed',{detail:{mode:session.mode}}));
      toast('公司信息已保存。');
    }catch(error){showError(error);}
    finally{session.busy=false;if(editor===session){form.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=false);form.querySelector('[data-company-save]').textContent='保存到'+(session.mode==='demo'?'演示库':'正式库');}}
  }
  function closeDetails(){
    if(editor?.busy)return;
    if(editor?.changed.size&&!confirm(window.ERPUI?.t('有尚未保存的公司信息，是否放弃修改？')||'有尚未保存的公司信息，是否放弃修改？'))return;
    openNumber++;editor=null;dialog.close();trigger.focus();
  }
  trigger.addEventListener('click',()=>{if(!popover.hidden){closePopover();return;}popover.hidden=false;trigger.setAttribute('aria-expanded','true');paintPopover();popover.querySelector('select,button')?.focus();if(!cache.has(state.mode))refresh();});
  popover.addEventListener('change',event=>{if(event.target.matches('[data-company-select]')){setSelected(state.mode,event.target.value);paintBrand();paintPopover();popover.querySelector('select')?.focus();}});
  popover.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;if(button.hasAttribute('data-company-close'))closePopover(true);else if(button.hasAttribute('data-company-new'))openDetails(true);else if(button.hasAttribute('data-company-details'))openDetails();});
  dialog.addEventListener('click',event=>{if(event.target.closest('[data-company-cancel]'))closeDetails();});
  dialog.addEventListener('cancel',event=>{event.preventDefault();closeDetails();});
  const remember=event=>{const input=event.target.closest('[data-company-field]');if(!editor||!input)return;const original=String(editor.values[input.dataset.companyField]??'');if(input.value===original)editor.changed.delete(input.dataset.companyField);else editor.changed.add(input.dataset.companyField);editor.requestId=null;};
  dialog.addEventListener('input',remember);dialog.addEventListener('change',remember);
  document.addEventListener('click',event=>{if(!popover.hidden&&!event.target.closest('#company-popover,#company-trigger'))closePopover();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!popover.hidden){event.preventDefault();closePopover(true);}});
  window.addEventListener('resize',position);
  const header=document.querySelector('.topbar');
  new ResizeObserver(()=>{document.documentElement.style.setProperty('--topbar-height',Math.ceil(header.getBoundingClientRect().height)+'px');position();}).observe(header);
  window.addEventListener('erp:language-changed',paintBrand);
  window.addEventListener('storage',event=>{for(const mode of ['live','demo'])if(event.key===storageKey(mode)){selected.set(mode,event.newValue||'');if(state.mode===mode){paintBrand();paintPopover();refresh(mode);}}});
  for(const event of ['erp:data-changed','erp:company-changed'])window.addEventListener(event,e=>refresh(e.detail.mode));
  window.addEventListener('beforeunload',event=>{if(editor?.changed.size||editor?.busy){event.preventDefault();event.returnValue='';}});
  window.easyerpCompany={current,syncSource,refresh};syncSource();
})();
