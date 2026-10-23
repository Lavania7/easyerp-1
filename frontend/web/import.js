'use strict';
(() => {
  const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const when=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'—';
  const dialog=document.createElement('dialog');
  dialog.id='import-interface'; dialog.className='import-dialog'; dialog.setAttribute('aria-label','表格导入'); document.body.append(dialog);
  let meta=null,tab='check',mode='live',results=[],history=null,events=[],offset=0,scope='all',filter='',busy=false,focus=null,notice='',job=0;
  const type=id=>meta?.types.find(t=>t.id===id);
  async function request(path,{file,payload,query={}}={}) {
    const options=file?{method:'POST',headers:{'Content-Type':'application/octet-stream','X-EasyERP-Token':meta.token},body:file}:payload?{method:'POST',headers:{'Content-Type':'application/json','X-EasyERP-Token':meta.token},body:JSON.stringify(payload)}:{};
    const url='/api/import/'+path+'?'+new URLSearchParams({mode,...query});
    let response=await fetch(url,options);
    if(response.status===403 && options.method) {
      const refreshed=await fetch('/api/import/meta');
      if(refreshed.ok){meta=await refreshed.json();options.headers['X-EasyERP-Token']=meta.token;response=await fetch(url,options);}
    }
    let body;try{body=await response.json();}catch{throw new Error('服务未返回有效结果，请重试。');}
    if(!response.ok)throw new Error(body.error||'操作未完成');return body;
  }
  async function load() {
    meta=await request('meta');
    if(tab==='history')history=await request('history',{query:{offset}});
    if(tab==='types')events=(await request('events')).rows;
  }
  function status(r) {
    if(r.error)return {text:'检查未完成',css:'bad'};
    if(r.match){if(!type(r.match.type_id)?.enabled)return {text:'已停用 · 不可导入',css:'off'};if(r.requires_recheck)return {text:'规则已更新 · 请重新检查',css:'bad'};return {text:'已登记 · 可用于导入',css:'ok'};}
    return {text:r.status==='invalid'?'无法检查':'需要新增支持',css:'bad'};
  }
  function record(r) {
    const s=status(r),match=r.match;
    return `<article class="import-result"><div class="import-result-top"><strong>${h(r.filename)}</strong><span class="import-status ${s.css}">${s.text}</span></div><p>${h(match?match.type_name+' / '+match.profile_name:r.error||r.reason)}</p>${match?`<div class="import-record-note">${type(match.type_id)?.enabled?'格式识别通过，业务数据导入尚未开放。':'此类型已从可导入目录停用，可在「表格类型」中恢复。'}</div>`:''}${r.id?`<details><summary>检查记录 #${r.id} · ${when(r.recorded_at)}</summary><dl><dt>文件 SHA-256</dt><dd class="import-hash">${h(r.sha256)}</dd><dt>检查时状态</dt><dd>${match?(r.enabled_at_check?'已启用':'已停用'):'未识别为已登记类型'}</dd><dt>工作表</dt><dd>${h(r.sheets.map(s=>(s.name||'文本表格')+'（'+s.physical_rows+' 行，含表头及说明）').join('、')||'—')}</dd>${match?`<dt>识别依据</dt><dd>第 ${match.header_row} 行表头 · ${match.columns.length} 列 · 列名及顺序一致</dd>`:''}<dt>登记版本</dt><dd>${h(r.catalog_version)}</dd></dl></details>`:''}</article>`;
  }
  function checkPanel() {
    const enabled=meta.types.filter(t=>t.enabled);
    return `<div class="import-check-grid"><section><label class="import-upload ${busy?'busy':''}" id="import-drop"><span class="import-upload-icon">↥</span><strong>${busy?'正在检查文件…':'选择或拖入表格'}</strong><span>XLSX、CSV、TXT · 每个文件最多 16 MB</span><input id="import-files" type="file" multiple accept=".xlsx,.csv,.txt" aria-label="选择待检查表格" ${busy?'disabled':''}><span class="button primary">选择文件并检查格式</span></label><p class="import-small">仅检查格式并保存检查记录，原文件不修改。文件中的业务明细不会保存或写入数据库。</p><div class="import-results" aria-live="polite">${results.map(record).join('')||'<div class="import-empty">选择文件后，这里会显示识别结果。</div>'}</div></section><aside class="import-side"><h3>可导入目录 <span>${enabled.length}</span></h3><p>已登记且启用的表格类型。新增格式需要增加功能后再登记。</p>${enabled.map(t=>`<div class="import-mini"><strong>${h(t.name)}</strong><small>${t.profiles.length} 个格式版本 · ${t.sample_count} 份样例验证</small></div>`).join('')||'<p>所有类型均已停用。</p>'}<button class="text-button" data-import-tab="types">管理表格类型 →</button></aside></div>`;
  }
  function typePanel() {
    const rows=meta.types.filter(t=>(scope==='all'||(scope==='enabled')===t.enabled)&&(!filter||(t.name+t.description).includes(filter)));
    return `<div class="import-tools"><label>显示范围 <select id="import-scope"><option value="all" ${scope==='all'?'selected':''}>全部类型</option><option value="enabled" ${scope==='enabled'?'selected':''}>可导入</option><option value="disabled" ${scope==='disabled'?'selected':''}>已停用</option></select></label><input id="import-search" type="search" placeholder="搜索表格类型" aria-label="搜索表格类型" value="${h(filter)}"><span>共 ${rows.length} 类</span></div><p class="import-small">类型设置对整个工作空间生效。停用会将该类型移出可导入目录；历史检查记录保留，可随时恢复。</p><div class="import-types">${rows.map(t=>`<article class="import-type ${t.enabled?'':'disabled'}"><div class="import-result-top"><span class="import-module">${h(t.module)}</span><span class="import-status ${t.enabled?'ok':'off'}">${t.enabled?'可用于导入':'已停用'}</span></div><h3>${h(t.name)}</h3><p>${h(t.description)}</p><div class="import-type-meta">${t.profiles.length} 个版本 · ${t.sample_count} 份样例<br>登记于 ${when(t.registered_at)}</div><details><summary>查看已登记格式</summary>${t.profiles.map(p=>`<div class="import-profile"><strong>${h(p.name)}</strong><p>${p.container.toUpperCase()}${p.sheet?' / '+h(p.sheet):''} · 第 ${p.header_row} 行表头 · ${p.columns.length} 列</p><p class="import-columns">${p.columns.map(h).join('、')}</p></div>`).join('')}</details><button class="button ${t.enabled?'':'primary'}" data-import-toggle="${h(t.id)}" ${busy?'disabled':''}>${t.enabled?'停用此类型':'恢复此类型'}</button></article>`).join('')||'<div class="import-empty">没有匹配的类型。</div>'}</div><details class="import-event-log"><summary>最近的类型变更（${events.length}）</summary>${events.length?`<div class="table-wrap"><table><thead><tr><th>时间</th><th>表格类型</th><th>操作</th></tr></thead><tbody>${events.map(e=>`<tr><td>${when(e.recorded_at)}</td><td>${h(type(e.type_id)?.name||e.type_id)}</td><td>${e.enabled?'恢复':'停用'}</td></tr>`).join('')}</tbody></table></div>`:'<p class="import-small">尚无启停变更。</p>'}</details>`;
  }
  function historyPanel() {
    return `<div class="import-history-heading"><p>保留文件校验值、识别结果和检查时状态。下方徽标始终按当前类型设置显示。</p><button class="button" data-import-refresh>刷新记录</button></div><div class="import-results">${history?.rows.map(record).join('')||'<div class="import-empty">当前数据来源还没有检查记录。</div>'}</div><div class="pagination"><span>共 ${history?.total||0} 条 · ${history?.total?offset+1:0}–${Math.min(offset+(history?.rows.length||0),history?.total||0)}</span><button data-import-page="-20" ${offset===0?'disabled':''}>上一页</button><button data-import-page="20" ${offset+20>=(history?.total||0)?'disabled':''}>下一页</button></div>`;
  }
  function render() {
    dialog.innerHTML=`<header class="import-head"><div><span class="import-eyebrow">IMPORT</span><h2>表格导入</h2><p>先确认格式，再逐步接入业务数据。</p></div><button class="icon-button" data-import-close aria-label="关闭导入">×</button></header><div class="import-scope-note"><span>${mode==='demo'?'演示数据':'正式数据'}</span> 当前开放格式检查与类型管理，业务数据导入尚未开放。</div><nav class="import-tabs" aria-label="导入功能">${[['check','检查文件'],['types','表格类型'],['history','检查记录']].map(([key,title])=>`<button class="${tab===key?'active':''}" data-import-tab="${key}" ${busy?'disabled':''}>${title}</button>`).join('')}</nav><div class="import-body">${notice?`<p class="import-notice" role="status">${h(notice)}</p>`:''}${tab==='types'?typePanel():tab==='history'?historyPanel():checkPanel()}</div><footer class="import-footer"><span>新格式需要增加支持。已登记表示格式可识别，不代表数据已入库。</span><button class="button" data-import-close>关闭</button></footer>`;
    const input=dialog.querySelector('#import-files');if(input)input.onchange=()=>inspect([...input.files]);
    const drop=dialog.querySelector('#import-drop');
    if(drop){drop.ondragover=e=>{e.preventDefault();drop.classList.add('dragging');};drop.ondragleave=()=>drop.classList.remove('dragging');drop.ondrop=e=>{e.preventDefault();if(!busy)inspect([...e.dataTransfer.files]);};}
    const search=dialog.querySelector('#import-search');if(search)search.oninput=()=>{const pos=search.selectionStart;filter=search.value;render();const next=dialog.querySelector('#import-search');next.focus();next.setSelectionRange(pos,pos);};
    const select=dialog.querySelector('#import-scope');if(select)select.onchange=()=>{scope=select.value;render();};
  }
  async function inspect(files) {
    if(busy||!files.length)return;
    if(files.length>10){notice='一次最多检查 10 个文件，请分批选择。';render();return;}
    const currentJob=++job,checkMode=mode;
    busy=true;notice='';results=[];render();
    try{
      for(const file of files){
        if(currentJob!==job)return;
        try{if(file.size>meta.max_file_bytes)throw new Error('单个文件不能超过 16 MB。');const result=await request('check',{file,query:{filename:file.name,mode:checkMode}});if(currentJob!==job)return;results.push(result);}
        catch(error){if(currentJob!==job)return;results.push({filename:file.name,error:error.message});}render();
      }
      const refreshed=await request('meta');if(currentJob!==job)return;meta=refreshed;notice='检查完成。业务数据未写入数据库。';
    }catch(error){if(currentJob===job)notice=error.message;}finally{if(currentJob===job){busy=false;render();}}
  }
  async function activate(next) {
    if(busy)return;tab=next;notice='';
    try{await load();render();}catch(error){notice=error.message;render();}
  }
  function close(){job++;busy=false;dialog.close();focus?.focus();}
  dialog.addEventListener('click',async e=>{
    const button=e.target.closest('button');if(!button)return;
    if(button.hasAttribute('data-import-close'))return close();
    if(button.dataset.importTab)return activate(button.dataset.importTab);
    if(button.hasAttribute('data-import-refresh'))return activate(tab);
    if(button.dataset.importPage){offset=Math.max(0,offset+Number(button.dataset.importPage));return activate('history');}
    if(button.dataset.importToggle&&!busy){
      const t=type(button.dataset.importToggle);busy=true;notice='';render();
      try{meta=await request('settings',{payload:{type_id:t.id,enabled:!t.enabled,version:t.version}});events=(await request('events')).rows;notice=t.enabled?'已停用「'+t.name+'」，同类文件现在不可用于导入。':'已恢复「'+t.name+'」。';}
      catch(error){notice=error.message;try{await load();}catch{}}
      finally{busy=false;render();}
    }
  });
  dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
  document.querySelector('#import-open').onclick=async()=>{
    focus=document.activeElement;mode=state.mode;tab='check';offset=0;notice='';results=[];
    dialog.innerHTML='<div class="import-body">正在读取已登记格式…</div>';dialog.showModal();
    try{await load();render();}catch(error){dialog.innerHTML=`<div class="import-body"><p>${h(error.message)}</p><button class="button" data-import-close>关闭</button></div>`;}
  };
})();
