'use strict';
(() => {
  const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const when=v=>v?new Date(v).toLocaleString(window.ERPUI?.locale()||'zh-CN',{hour12:false}):'—';
  const dialog=document.createElement('dialog');
  dialog.id='import-interface';dialog.className='import-dialog';dialog.setAttribute('aria-label','表格导入');document.body.append(dialog);
  let meta=null,tab='check',mode='live',results=[],history=null,events=[],offset=0,scope='all',filter='',busy=false,prompting=false,focus=null,notice='',job=0;
  const confirmation=document.createElement('dialog');confirmation.className='import-dialog import-confirm-dialog';confirmation.setAttribute('aria-label','导入确认');document.body.append(confirmation);
  let answer=null,confirmationFocus=null;
  function finishConfirmation(value){const resolve=answer;answer=null;confirmation.close();if(confirmationFocus?.isConnected)confirmationFocus.focus();resolve?.(value);}
  confirmation.addEventListener('cancel',event=>{event.preventDefault();finishConfirmation(null);});
  confirmation.addEventListener('keydown',event=>{if(event.key==='Escape')event.stopPropagation();});
  confirmation.addEventListener('click',event=>{const button=event.target.closest('button');if(button?.hasAttribute('data-import-answer'))finishConfirmation(button.dataset.importAnswer||null);});
  function ask(message,explanation,no,yes){
    confirmationFocus=document.activeElement;
    confirmation.innerHTML=`<header class="import-head"><h2>${h(message)}</h2><button type="button" class="icon-button" data-import-answer="" aria-label="取消导入">×</button></header><div class="import-confirm-body"><p>${h(explanation)}</p><div class="import-confirm-actions"><button type="button" class="button" autofocus data-import-answer="${h(no.value)}">${h(no.label)}</button><button type="button" class="button primary" data-import-answer="${h(yes.value)}">${h(yes.label)}</button></div></div>`;
    return new Promise(resolve=>{answer=resolve;confirmation.showModal();});
  }
  const files=new Map(),type=id=>meta?.types.find(t=>t.id===id);
  async function request(path,{file,payload,query={}}={}){
    const options=file?{method:'POST',headers:{'Content-Type':'application/octet-stream','X-EasyERP-Token':meta.token},body:file}:payload?{method:'POST',headers:{'Content-Type':'application/json','X-EasyERP-Token':meta.token},body:JSON.stringify(payload)}:{};
    const url='/api/import/'+path+'?'+new URLSearchParams({mode,...query});
    let response=await fetch(url,options);
    if(response.status===403&&options.method){
      const refreshed=await fetch('/api/import/meta?'+new URLSearchParams({mode}));
      if(refreshed.ok){meta=await refreshed.json();options.headers['X-EasyERP-Token']=meta.token;response=await fetch(url,options);}
    }
    let body;try{body=await response.json();}catch{throw new Error('服务未返回有效结果，请重试。');}
    if(!response.ok){const error=new Error(body.error||'操作未完成');error.status=response.status;throw error;}return body;
  }
  async function load(){
    meta=await request('meta');
    if(tab==='history')history=await request('history',{query:{offset}});
    if(tab==='types')events=(await request('events')).rows;
  }
  function status(r){
    if(r.error)return {text:'检查未完成',css:'bad'};
    if(r.execution)return {text:'已导入',css:'ok'};
    if(r.match?.type_id==='standard-master')return {text:r.label,css:r.can_execute?'ok':'bad'};
    if(r.match){
      if(!type(r.match.type_id)?.enabled)return {text:'已停用 · 不可导入',css:'off'};
      if(r.requires_recheck)return {text:'规则已更新 · 请重新检查',css:'bad'};
      return {text:'格式已登记 · 仅检查',css:'ok'};
    }
    return {text:r.status==='invalid'?'无法检查':'需要新增支持',css:'bad'};
  }
  function preview(r){
    if(!r.preview?.length)return '';
    const columns=r.match.columns;
    return `<details class="import-preview"><summary>预览前${r.preview.length}条，共${r.row_count}条</summary><div class="table-wrap"><table><thead><tr><th>文件行号</th>${columns.map(c=>`<th data-i18n-ignore>${h(c)}</th>`).join('')}</tr></thead><tbody>${r.preview.map(row=>`<tr><td>${row.line}</td>${columns.map(c=>`<td data-i18n-ignore title="${h(row.values[c])}">${!String(row.values[c]??'').trim()?'<span class="muted" data-ui-label>空</span>':h(row.values[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  function record(r){
    const s=status(r),match=r.match,standard=match?.type_id==='standard-master';
    const instruction=r.execution?`处理${r.execution.rows_imported}条：新增${r.execution.created??r.execution.rows_imported}条、更新${r.execution.updated??0}条、未变${r.execution.unchanged??0}条 · ${when(r.execution.imported_at)}`:standard?r.reason:match?(type(match.type_id)?.enabled?'此类型目前只支持格式检查。':'此类型已停用，可在表格类型中恢复。'):r.error||r.reason;
    return `<article class="import-result"><div class="import-result-top"><strong data-i18n-ignore>${h(r.filename)}</strong><span class="import-status ${s.css}">${h(s.text)}</span></div><p>${h(match?match.type_name+' / '+match.profile_name:instruction)}</p>${match?`<div class="import-record-note">${h(instruction)}</div>`:''}
      ${standard?preview(r):''}
      ${standard&&!r.execution&&r.blank_cells?`<p class="import-gap-note">检测到${r.blank_rows}行中有${r.blank_cells}个空白单元格，导入前会询问是否继续。</p>`:''}
      ${standard&&!r.execution&&r.generated_id_count?`<p class="import-small">${r.generated_id_count}条记录的主键为空，将自动编号；更新已有记录请填写原编号。</p>`:''}
      ${standard&&!r.execution&&r.existing_count?`<p class="import-small">检测到${r.existing_count}条已有记录，导入前会询问合并方式。</p>`:''}
      ${standard&&tab==='check'&&r.can_execute&&files.has(r.id)?`<div class="import-commit"><p>空白值不会清除原数据；已有记录可选择覆盖非空值或只补原空白项。</p><button type="button" class="button primary" data-import-execute="${r.id}" ${busy?'disabled':''}>导入${mode==='demo'?'演示库':'正式库'}（${r.row_count}条）</button></div>`:''}
      ${standard&&tab==='check'&&r.requires_recheck&&files.has(r.id)?`<button type="button" class="button" data-import-recheck="${r.id}" ${busy?'disabled':''}>重新检查此文件</button>`:''}
      ${r.id?`<details><summary>检查记录 #${r.id} · ${when(r.recorded_at)}</summary><dl><dt>文件 SHA-256</dt><dd class="import-hash" data-i18n-ignore>${h(r.sha256)}</dd><dt>检查时状态</dt><dd>${match?(r.enabled_at_check?'已启用':'已停用'):'未识别为已登记类型'}</dd><dt>工作表</dt><dd>${h((r.sheets||[]).map(s=>(s.name||'文本表格')+'（'+s.physical_rows+' 行，含表头及说明）').join('、')||'—')}</dd>${match?`<dt>识别依据</dt><dd>第 ${match.header_row} 行表头 · ${match.columns.length} 列 · 列名及顺序一致</dd>`:''}<dt>登记版本</dt><dd>${h(r.catalog_version)}</dd></dl></details>`:''}</article>`;
  }
  function checkPanel(){
    const enabled=meta.types.filter(t=>t.enabled);
    return `<div class="import-check-grid"><section><label class="import-upload ${busy?'busy':''}" id="import-drop"><span class="import-upload-icon">↥</span><strong>${busy?'正在检查文件…':'选择或拖入表格'}</strong><span>XLSX、CSV、TXT · 每个文件最多 16 MB</span><input id="import-files" type="file" multiple accept=".xlsx,.csv,.txt" aria-label="选择待检查表格" ${busy?'disabled':''}><span class="button primary">选择文件并检查格式</span></label><p class="import-small">标准CSV的空缺经确认后导入；已有记录可选用最新非空值，或只补填原空白项。完全空白的行会跳过，每批最多5000条。其他类型仍只检查格式。</p><div class="import-results" aria-live="polite">${results.map(record).join('')||'<div class="import-empty">选择文件后，这里会显示识别结果。</div>'}</div></section><aside class="import-side"><h3>可导入目录 <span>${enabled.length}</span></h3><p>标准主录表支持直接导入，其他已登记类型支持格式检查。</p>${enabled.map(t=>`<div class="import-mini"><strong>${h(t.name)}</strong><small>${t.immutable?`${t.profiles.length}张主录表 · 始终启用`:`${t.profiles.length} 个格式版本 · ${t.sample_count} 份样例验证`}</small></div>`).join('')}<button class="text-button" data-import-tab="types">管理表格类型 →</button></aside></div>`;
  }
  function typePanel(){
    const search=filter.toLocaleLowerCase();
    const rows=meta.types.filter(t=>(scope==='all'||(scope==='enabled')===t.enabled)&&(!search||[t.name,t.description,window.ERPUI?.t(t.name)].join(' ').toLocaleLowerCase().includes(search)));
    return `<div class="import-tools"><label>显示范围 <select id="import-scope"><option value="all" ${scope==='all'?'selected':''}>全部类型</option><option value="enabled" ${scope==='enabled'?'selected':''}>可导入</option><option value="disabled" ${scope==='disabled'?'selected':''}>已停用</option></select></label><input id="import-search" type="search" placeholder="搜索表格类型" aria-label="搜索表格类型" value="${h(filter)}"><span>共 ${rows.length} 类</span></div><p class="import-small">标准主录表始终启用。其他类型可停用或恢复，历史记录保留。</p><div class="import-types">${rows.map(t=>`<article class="import-type ${t.enabled?'':'disabled'}" data-import-type="${h(t.id)}"><div class="import-result-top"><span class="import-module">${h(t.module)}</span><span class="import-status ${t.enabled?'ok':'off'}">${t.immutable?'始终启用':t.enabled?'可用于导入':'已停用'}</span></div><h3>${h(t.name)}</h3><p>${h(t.description)}</p><div class="import-type-meta">${t.immutable?`${t.profiles.length}张主录表 · CSV`:`${t.profiles.length} 个版本 · ${t.sample_count} 份样例`}<br>登记于 ${when(t.registered_at)}</div><details><summary>查看已登记格式</summary><div class="import-profile-list">${t.profiles.map(p=>`<div class="import-profile"><strong>${h(p.name)}</strong><p>${p.container.toUpperCase()}${p.sheet?' / '+h(p.sheet):''} · 第 ${p.header_row} 行表头 · ${p.columns.length} 列</p>${t.immutable?'':`<p class="import-columns" data-i18n-ignore>${p.columns.map(h).join('、')}</p>`}</div>`).join('')}</div></details>${t.immutable?'<p class="import-fixed">标准主录表不可停用。</p>':`<button class="button ${t.enabled?'':'primary'}" data-import-toggle="${h(t.id)}" ${busy?'disabled':''}>${t.enabled?'停用此类型':'恢复此类型'}</button>`}</article>`).join('')||'<div class="import-empty">没有匹配的类型。</div>'}</div><details class="import-event-log"><summary>最近的类型变更（${events.length}）</summary>${events.length?`<div class="table-wrap"><table><thead><tr><th>时间</th><th>表格类型</th><th>操作</th></tr></thead><tbody>${events.map(e=>`<tr><td>${when(e.recorded_at)}</td><td>${h(type(e.type_id)?.name||e.type_id)}</td><td>${e.enabled?'恢复':'停用'}</td></tr>`).join('')}</tbody></table></div>`:'<p class="import-small">尚无启停变更。</p>'}</details>`;
  }
  function historyPanel(){
    return `<div class="import-history-heading"><p>保留文件校验值、检查结果和导入结果。标准CSV成功导入后可查询批次记录。</p><button class="button" data-import-refresh>刷新记录</button></div><div class="import-results">${history?.rows.map(record).join('')||'<div class="import-empty">当前数据来源还没有检查记录。</div>'}</div><div class="pagination"><span>共 ${history?.total||0} 条 · ${history?.total?offset+1:0}–${Math.min(offset+(history?.rows.length||0),history?.total||0)}</span><button data-import-page="-20" ${offset===0?'disabled':''}>上一页</button><button data-import-page="20" ${offset+20>=(history?.total||0)?'disabled':''}>下一页</button></div>`;
  }
  function render(){
    dialog.innerHTML=`<header class="import-head"><div><span class="import-eyebrow">IMPORT</span><h2>表格导入</h2><p>检查文件，预览数据，再导入标准主录表。</p></div><button class="icon-button" data-import-close aria-label="关闭导入" ${busy?'disabled':''}>×</button></header><div class="import-scope-note"><span>${mode==='demo'?'演示数据':'正式数据'}</span><span>已开放标准主录表CSV导入；其他类型仅检查格式。</span></div><nav class="import-tabs" aria-label="导入功能">${[['check','检查文件'],['types','表格类型'],['history','检查记录']].map(([key,title])=>`<button class="${tab===key?'active':''}" data-import-tab="${key}" ${busy?'disabled':''}>${title}</button>`).join('')}</nav><div class="import-body">${notice?`<p class="import-notice" role="status">${h(notice)}</p>`:''}${tab==='types'?typePanel():tab==='history'?historyPanel():checkPanel()}</div><footer class="import-footer"><span>按主键合并；空白值不清除原数据，失败时整批回滚。</span><button class="button" data-import-close ${busy?'disabled':''}>关闭</button></footer>`;
    const input=dialog.querySelector('#import-files');if(input)input.onchange=()=>inspect([...input.files]);
    const drop=dialog.querySelector('#import-drop');
    if(drop){drop.ondragover=e=>{e.preventDefault();drop.classList.add('dragging');};drop.ondragleave=()=>drop.classList.remove('dragging');drop.ondrop=e=>{e.preventDefault();if(!busy)inspect([...e.dataTransfer.files]);};}
    const search=dialog.querySelector('#import-search');if(search)search.oninput=()=>{const pos=search.selectionStart;filter=search.value;render();const next=dialog.querySelector('#import-search');next.focus();next.setSelectionRange(pos,pos);};
    const select=dialog.querySelector('#import-scope');if(select)select.onchange=()=>{scope=select.value;render();};
  }
  async function inspect(selected){
    if(busy||!selected.length)return;
    if(selected.length>10){notice='一次最多检查 10 个文件，请分批选择。';render();return;}
    const currentJob=++job;busy=true;notice='';results=[];files.clear();render();
    try{
      for(const file of selected){
        if(currentJob!==job)return;
        try{if(file.size>meta.max_file_bytes)throw new Error('单个文件不能超过 16 MB。');const result=await request('check',{file,query:{filename:file.name}});if(currentJob!==job)return;results.push(result);files.set(result.id,file);}
        catch(error){if(currentJob!==job)return;results.push({filename:file.name,error:error.message});}render();
      }
      if(currentJob===job)notice='检查完成。确认预览后可导入标准主录表；检查阶段不保存业务记录。';
    }catch(error){if(currentJob===job)notice=error.message;}finally{if(currentJob===job){busy=false;render();}}
  }
  async function execute(id){
    const result=results.find(r=>r.id===Number(id)),file=files.get(Number(id));
    if(busy||prompting||!result?.can_execute||!file)return;
    let choices=result.retry_choices;
    prompting=true;
    try{
      if(!choices){
        if(result.blank_cells&&!result.incomplete_confirmed){
          const approved=await ask('检查到表信息不全，是否还要导入？','空白项会保留为空，不会清除已有值。选择“否”将取消本次导入。',{value:'no',label:'否，取消导入'},{value:'yes',label:'是，继续导入'});
          if(approved!=='yes')return;result.incomplete_confirmed=true;
        }
        let merge=null;
        if(result.existing_count){
          merge=await ask('是否要使用最新一次的数据？','选择“是”：用CSV非空值覆盖已有值；选择“否”：保留已有非空值，只补填原来的空白项。两者都不会用空数据覆盖原数据。',{value:'fill_empty',label:'否，只补原空白项'},{value:'latest',label:'是，使用最新数据'});
          if(merge===null)return;
        }
        choices={allow_incomplete:result.incomplete_confirmed?'true':'false',...(merge?{merge}:{})};
        const errors=result.merge_validation?.[merge||'latest']||[];
        if(errors.length){notice=errors.join('；');render();return;}
        result.retry_choices=choices;
      }
    }finally{prompting=false;}
    busy=true;notice='正在导入，请等待整批处理完成…';render();
    try{
      result.execution=await request('execute',{file,query:{filename:file.name,check_id:result.id,...choices}});
      result.can_execute=false;result.label='已导入';notice='导入完成，业务记录已保存。';
      window.dispatchEvent(new CustomEvent('erp:data-changed',{detail:{mode}}));
    }catch(error){notice=error.message;if([400,409].includes(error.status)){result.can_execute=false;result.requires_recheck=true;result.retry_choices=null;}}
    finally{busy=false;render();}
  }
  async function activate(next){if(busy)return;tab=next;notice='';try{await load();render();dialog.scrollTop=0;}catch(error){notice=error.message;render();}}
  function close(){if(busy||prompting)return;job++;dialog.close();focus?.focus();}
  dialog.addEventListener('click',async e=>{
    const button=e.target.closest('button');if(!button)return;
    if(button.hasAttribute('data-import-close'))return close();
    if(button.dataset.importExecute)return execute(button.dataset.importExecute);
    if(button.dataset.importRecheck){const file=files.get(Number(button.dataset.importRecheck));if(file)return inspect([file]);}
    if(button.dataset.importTab)return activate(button.dataset.importTab);
    if(button.hasAttribute('data-import-refresh'))return activate(tab);
    if(button.dataset.importPage){offset=Math.max(0,offset+Number(button.dataset.importPage));return activate('history');}
    if(button.dataset.importToggle&&!busy){
      const t=type(button.dataset.importToggle);if(t.immutable)return;
      busy=true;notice='';render();
      try{meta=await request('settings',{payload:{type_id:t.id,enabled:!t.enabled,version:t.version}});events=(await request('events')).rows;notice=t.enabled?'已停用此表格类型。':'已恢复此表格类型。';}
      catch(error){notice=error.message;try{await load();}catch{}}
      finally{busy=false;render();}
    }
  });
  dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
  dialog.addEventListener('keydown',e=>{if(e.key==='Escape')e.stopPropagation();});
  window.addEventListener('erp:language-changed',()=>{if(dialog.open&&meta&&!busy)render();});
  document.querySelector('#import-open').onclick=async()=>{
    focus=document.activeElement;mode=state.mode;tab='check';offset=0;notice='';results=[];files.clear();
    dialog.innerHTML='<div class="import-body">正在读取已登记格式…</div>';dialog.showModal();
    try{await load();render();dialog.scrollTop=0;}catch(error){dialog.innerHTML=`<div class="import-body"><p>${h(error.message)}</p><button class="button" data-import-close>关闭</button></div>`;}
  };
})();
