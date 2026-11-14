'use strict';

const $=s=>document.querySelector(s);

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const paths={overview:'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',tasks:'M6 4h12v17H6zM9 2h6v4H9zm0 8h6m-6 4h6m-6 4h4',sales:'M3 5h18v15H3zm0 4h18m-7 4h4m-4 3h4',inventory:'M3 7l9-5 9 5v11l-9 5-9-5zm0 0 9 5 9-5m-9 5v11',production:'M3 21V9l6 3V7l6 4V3h5l1 18zm4-4h1m4 0h1m4 0h1',rd:'m8 3 4 4-4 4m5 5 4-4 4 4M3 14h7v7H3z',finance:'M3 5h18v16H3zm0 4h18m-8 4h8m-5 3h2',legal:'M12 2v20M5 6h14M5 6l-4 8h8zm14 0-4 8h8zM8 22h8',analysis:'M3 3v18h18M7 16l4-5 4 2 5-7'};

const icon=k=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[k]||paths.overview}"/></svg>`;

const navs=[['overview','仪表盘'],['plans','企业计划'],['workflow','工作流'],['data','数据中心'],['archive','档案馆'],['audit','审计'],['tasks','工作流'],['sales','销售'],['inventory','采购与库存'],['production','生产'],['rd','研发'],['finance','财务'],['legal','法务'],['analysis','分析报告']];
const url=new URL(location.href);

const today=new Date(Date.now()+8*60*60*1000).toISOString().slice(0,10);

const state={mode:url.searchParams.get('mode')||'live',start:url.searchParams.get('start')||today.slice(0,8)+'01',end:url.searchParams.get('end')||today,currency:window.ERPDefaults.currency,tz:window.ERPDefaults.timeZone,search:url.searchParams.get('search')||'',offset:0,limit:30,scope:'',status:'',person:'',subject:''};

let meta=null,sequence=0,detailSequence=0,drawerState=null,drawerTab='basic',route='overview',exploreObject='',lastList=null;

const defaults={sales:'sales.销售订单行表',production:'production.完工记录表',finance:'finance.资金流水表',inventory:'production.采购订单表',rd:'rd.BOM明细表',legal:'legal.合同审阅表',analysis:'analysis.分析报告登记表'};
const businessLists={sales:'orders',finance:'funds'};

const knownRefs={'订单ID':'sales.销售订单登记表','销售订单行ID':'sales.销售订单行表','工单号':'production.生产工单表','资金记录ID':'finance.资金流水表','账户ID':'finance.资金账户档案表','客户ID':'sales.客户档案表','项目ID':'rd.项目登记表','产品版本ID':'rd.产品版本表','物料版本ID':'rd.物料版本表','BOM登记ID':'rd.BOM登记表','发布批次ID':'rd.发布批次表','单位ID':'rd.计量单位表','票据ID':'finance.发票登记表','用途核定ID':'finance.资金用途核定表','采购单ID':'production.采购订单表','采购订单行ID':'production.采购订单行表','人员ID':'finance.人员档案表','确认人ID':'finance.人员档案表','负责人ID':'finance.人员档案表','主体ID':'legal.公司主体档案表','所有权主体ID':'legal.公司主体档案表','文件ID':'rd.项目文件登记表','库存事件ID':'production.库存变动表','发货事件ID':'production.发货记录表','到货ID':'production.到货记录表','验收ID':'production.验收记录表'};



function decimal(value){if(value===null||value===undefined)return 'N/A';const s=String(value),parts=s.split('.');if(!/^-?\d+$/.test(parts[0]))return esc(s);let fraction=(parts[1]||'').replace(/0+$/,'');fraction=fraction.padEnd(2,'0');return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+fraction;}

function quantity(value){if(value===null||value===undefined)return 'N/A';return esc(String(value).replace(/(\.\d*?)0+$/,'$1').replace(/\.$/,''));}

function dateText(value){if(!value)return 'N/A';if(String(value).length===10)return esc(value);const d=new Date(value);if(Number.isNaN(d.getTime()))return esc(value);return d.toLocaleString(window.ERPUI?.locale()||'zh-CN',{timeZone:state.tz,hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}

function badge(value){if(value==null)return '<span class="muted">N/A</span>';const text=String(value),type=/待|新建|部分|中|差异|未关闭/.test(text)?'warn':/取消|撤销|撤回|不匹配|超额/.test(text)?'red':/关闭|完成|核定|发布|履约/.test(text)?'':'neutral';return `<span class="badge ${type}">${esc(text)}</span>`;}

function empty(title='尚无相关记录',_sub='',graph=false){return `<div class="empty ${graph?'graph':''}">${esc(title)}</div>`;}
function panel(title,body,sub='',action=''){return `<section class="panel"><div class="panel-head"><h2>${esc(title)}${sub?`<small>${esc(sub)}</small>`:''}</h2>${action}</div>${body}</section>`;}

function more(label,page,obj=''){return `<button class="panel-link" data-page="${page}" data-object="${esc(obj)}">${label} ↗</button>`;}

function link(value,object,label=value){return `<button class="table-button" data-i18n-ignore title="${esc(value)}" data-record="${esc(object)}" data-id="${esc(value)}">${esc(label)}</button>`;}


function refFor(key,object){const o=meta?.objects.find(x=>x.schema+'.'+x.name===object);if(o&&o.kind==='r'&&o.pk===key)return object;const r=meta?.references.find(x=>`${x.source_schema}.${x.source_table}`===object&&x.source_column===key);return r?`${r.target_schema}.${r.target_table}`:knownRefs[key];}



function display(value,key,row={},object=''){if(value==null)return '<span class="muted">N/A</span>';if(typeof value==='boolean')return value?'是':'否';if(/状态|进展/.test(key))return badge(value);if(/日期|时间|月份/.test(key))return dateText(value);if(/金额|实付|单价|收入|成本|差额|余额|税额|分摊$/.test(key)&&/^-?\d+(\.\d+)?$/.test(String(value)))return `<span class="number">${decimal(value)}</span>`;if(/数量|工时|用量|比例|^期间入库$|^期间出库$/.test(key))return quantity(value);const target=refFor(key,object);if(target){let label=value;if(target==='rd.计量单位表')label=meta.units?.find(x=>x['单位ID']===value)?.['单位名称']||value;if(target==='finance.人员档案表')label=meta.people.find(x=>x['人员ID']===value)?.['姓名']||value;if(target==='legal.公司主体档案表')label=meta.subjects.find(x=>x['主体ID']===value)?.['公司名称']||value;return link(value,target,label)+(label!==value?`<span class="secondary">${esc(value)}</span>`:'');}return esc(typeof value==='object'?JSON.stringify(value):value);}

const pencilIcon='<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 5 5M4 15 15 4a3.5 3.5 0 0 1 5 5L9 20l-6 1zM4 15l5 5"/></svg>';
function editOrigin(source){const key=source;return meta?.objects.find(o=>o.schema+'.'+o.name===key&&o.kind==='r'&&!o.retired);}
function editToggle(source,supported=!!editOrigin(source)){return `<button type="button" class="button primary table-edit-toggle" data-table-edit-toggle aria-pressed="false" ${supported?'':'disabled title="请在对应业务主录中修改。"'}>${pencilIcon}<span>编辑</span></button>`;}
function table(rows,columns=null,options={}){
  if(!rows?.length)return empty(options.emptyTitle||'N/A',options.emptySub||'当前查询范围内没有记录。');
  const cols=columns||Object.keys(rows[0]).filter(k=>!k.startsWith('_')).slice(0,10).map(k=>[k,k]);
  const origin=options.editObject&&editOrigin(options.editObject),key=origin&&origin.schema+'.'+origin.name;
  const editable=!!(origin||options.editRecord);
  return `<div class="table-wrap"><table><thead><tr>${cols.map(c=>`<th>${esc(c[1])}</th>`).join('')}${options.detail?'<th></th>':''}${editable?'<th class="table-edit-column">修改</th>':''}</tr></thead><tbody>${rows.map(row=>{
    const target=options.editRecord?options.editRecord(row):origin&&row[origin.pk]!=null?{object:key,id:row[origin.pk]}:null;
    return `<tr ${target?`data-row-object="${esc(target.object)}" data-row-id="${esc(target.id)}"`:''}>${cols.map(([field,label,format])=>`<td title="${esc(row[field]??'N/A')}">${format?format(row[field],row):display(row[field],field,row,options.object||'')}</td>`).join('')}${options.detail?`<td><button class="table-button" data-detail="${options.detail}" data-id="${esc(row[options.id])}">查看 ↗</button></td>`:''}${editable?`<td class="table-edit-column">${target?`<button type="button" class="table-row-edit" data-row-edit aria-label="修改这条记录" aria-expanded="false">${pencilIcon}<span data-ui-label>修改</span></button>`:'<span class="muted">N/A</span>'}</td>`:''}</tr>`;
  }).join('')}</tbody></table></div>`;
}

function params(extra={}){return new URLSearchParams({...state,...extra,currency:window.ERPDefaults.currency,tz:window.ERPDefaults.timeZone});}

async function api(path,extra={}){const r=await fetch('/api/'+path+'?'+params(extra));let body;try{body=await r.json();}catch{throw new Error('前端服务未返回有效数据');}if(!r.ok)throw new Error(body.error||'暂时无法读取数据');return body;}

function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,4200);}

const DATE_PRESETS={year:['01-01','12-31'],q1:['01-01','03-31'],q2:['04-01','06-30'],q3:['07-01','09-30'],q4:['10-01','12-31']};
function datePresetYear(){
  const date=[$('#start').value,$('#end').value,today].find(value=>/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number(value.slice(0,4))>0);
  return date.slice(0,4);
}
function syncDatePresets(){
  syncQueryDates();
  const year=datePresetYear(),disabled=$('#start').disabled||$('#end').disabled;
  $('#date-presets').setAttribute('aria-label',`${year}年日期快捷选择`);
  document.querySelectorAll('[data-date-preset]').forEach(button=>{
    const range=DATE_PRESETS[button.dataset.datePreset];
    const active=$('#start').value===`${year}-${range[0]}`&&$('#end').value===`${year}-${range[1]}`;
    button.disabled=disabled;
    button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',String(active));
    button.title=disabled?'此视图未启用日期范围':`${year}年${button.dataset.datePreset==='year'?'全年':button.dataset.datePreset.toUpperCase()}（按开始日期所在年份）`;
  });
}
$('#date-presets').addEventListener('click',event=>{
  const button=event.target.closest('[data-date-preset]');
  if(!button||button.disabled||$('#start').disabled||$('#end').disabled)return;
  const range=DATE_PRESETS[button.dataset.datePreset];
  if(!range)return;
  const year=datePresetYear();
  $('#start').value=`${year}-${range[0]}`;
  $('#end').value=`${year}-${range[1]}`;
  $('#apply').click();
});
for(const id of ['start','end'])$('#'+id).addEventListener('input',syncDatePresets);

function sync(){window.easyerpCompany?.syncSource();for(const id of ['start','end','search'])$('#'+id).value=state[id];$('#connection').textContent=state.mode==='demo'?'演示数据':'本机数据库';syncSourceMenu();$('#source-toggle').classList.toggle('demo',state.mode==='demo');$('#source-toggle').title='选择数据源';$('#demo-notice').hidden=state.mode!=='demo';const u=new URL(location.href);for(const k of ['mode','start','end','currency','tz','search'])u.searchParams.set(k,state[k]);history.replaceState(null,'',u);syncDatePresets();}

function move(page,object=''){exploreObject=object;state.offset=0;state.status='';const q=new URLSearchParams();if(object)q.set('object',object);if(state.scope)q.set('scope',state.scope);const hash='/'+page+(q.size?'?'+q:'');if(location.hash==='#'+hash)render();else location.hash=hash;}

function monetary(rows,key,completeKey=null){if(!rows?.length)return {value:'N/A',unknown:true};if(completeKey&&rows.some(r=>r[completeKey]!==r['记录数']))return {value:'待核定',unknown:true};return {value:rows.map(r=>`${decimal(r[key])}<span class="unit">${esc(r['币种']||'币种N/A')}</span>`).join('<br>'),unknown:rows.every(r=>r[key]==null),multi:rows.length>1};}

function metric(label,value,action){const v=typeof value==='object'?value:{value:String(value),unknown:false};return `<button class="metric" ${action}><span class="label">${label}<span class="chevron">↗</span></span><div class="value ${v.unknown?'unknown':''} ${v.multi?'multi':''}">${v.value}</div></button>`;}
const recordAction=(obj)=>`data-page="${obj.split('.')[0]==='finance'?'finance':obj.split('.')[0]==='sales'?'sales':'inventory'}" data-object="${obj}" data-scope="confirmed"`;



function trend(rows){const valid=rows.filter(r=>r['收入已填数']===r['记录数']&&r['成本已填数']===r['记录数']);if(!valid.length)return empty('尚无完整核定的收入成本记录','按确认月份显示；缺失的成本不会按零绘图。',true);if(new Set(valid.map(r=>r['币种'])).size>1)return table(valid,[['所属月份','确认月份'],['币种','币种'],['收入','已确认收入'],['成本','已确认成本']]);const max=Math.max(...valid.flatMap(r=>[Math.abs(Number(r['收入'])),Math.abs(Number(r['成本']))]),1);if(valid.some(r=>Number(r['收入'])<0||Number(r['成本'])<0))return table(valid,[['所属月份','确认月份'],['币种','币种'],['收入','收入'],['成本','成本']]);const width=600,step=(width-70)/valid.length;return `<div class="panel-body"><svg class="chart" viewBox="0 0 600 205" role="img" aria-label="已核定收入与成本趋势">${[0,1,2,3].map(i=>`<line x1="25" x2="585" y1="${20+i*45}" y2="${20+i*45}"/>`).join('')}${valid.map((r,i)=>{const x=45+i*step,ih=Number(r['收入'])/max*145,ch=Number(r['成本'])/max*145;return `<g><rect class="income" x="${x}" y="${165-ih}" width="${Math.min(step*.23,30)}" height="${ih}" rx="3"><title>${esc(r['所属月份'])} 收入 ${decimal(r['收入'])} ${esc(r['币种'])}</title></rect><rect class="cost" x="${x+Math.min(step*.23,30)+5}" y="${165-ch}" width="${Math.min(step*.23,30)}" height="${ch}" rx="3"><title>成本 ${decimal(r['成本'])}</title></rect><text x="${x}" y="190">${esc(r['所属月份'].slice(0,7))}</text></g>`;}).join('')}</svg></div>`;}

async function overview(){const [d,t]=await Promise.all([api('overview'),api('tasks')]);const pending=d.pending_orders[0],work=d.pending_work[0];const cash=direction=>monetary(d.cash.filter(r=>r['收支方向']===direction),'外部金额');const count=(r,key)=>r['范围记录数']?{value:String(r[key]),unknown:false}:{value:'N/A',unknown:true};let html='<div class="metrics">';
html+=metric('订单商品实付',monetary(d.sales,'金额','实付已填数'),'data-page="sales"');
html+=metric('已确认收入',monetary(d.recognition,'已确认收入','收入已填数'),recordAction('finance.收入成本确认表'));
html+=metric('已确认结转成本',monetary(d.recognition,'已确认结转成本','成本已填数'),recordAction('finance.收入成本确认表'));
html+=metric('毛利',{value:'待核定',unknown:true},recordAction('finance.收入成本确认表'));
html+=metric('资金收入',cash('收入'),'data-page="finance" data-scope="cash-income"');
html+=metric('资金支出',cash('支出'),'data-page="finance" data-scope="cash-expense"');
html+=metric('待发货订单行',count(pending,'待发货订单行'),'data-page="sales" data-scope="pending"');
html+=metric('待完成生产执行',count(work,'待完成工单'),'data-page="workflow" data-scope="pending"');html+='</div>';
const dist=d.fulfillment.length?`<div class="distribution">${d.fulfillment.map(r=>`<div class="dist-row"><span>${esc(r['履约进展'])}</span><div class="dist-track"><div class="dist-bar" style="width:${r['数量']/Math.max(...d.fulfillment.map(x=>x['数量']),1)*100}%"></div></div><strong>${r['数量']}</strong></div>`).join('')}</div>`:empty('尚无订单履约记录','接单后，可查看履约进展与逐次发货。');

html+=`<div class="columns">${panel('收入与结转成本',trend(d.trend),'','<div class="chart-legend"><span>确认收入</span><span>结转成本</span></div>')}${panel('订单履约分布',dist,'',more('查看订单','sales'))}</div>`;
const todos=t.rows.slice(0,5);const taskbody=todos.length?`<div class="panel-body">${todos.map(r=>`<div class="list-row"><span class="dot-icon">${r['事项'].includes('资金')?'¥':'↗'}</span><div class="row-main"><button data-task="${esc(JSON.stringify(r))}">${esc(r['事项'])} · ${esc(r['内容']||r['编号'])}</button><div class="sub">${r['负责人']?esc(r['负责人']):'负责人N/A'}${r['期限']?' · '+esc(r['期限']):' · 期限N/A'}</div></div>${badge(r['状态'])}</div>`).join('')}</div>`:empty('当前没有已登记待办','这里只根据业务记录的状态和期限列出事项。');

const balances=d.balances.length?`<div class="panel-body">${d.balances.map(r=>`<div class="list-row"><div><button data-record="finance.账户期间余额表" data-id="${esc(r['余额记录ID'])}">${esc(r['账户名'])}</button><div class="sub">${esc(r['期间结束'])} · 已核定余额</div></div><div class="amount">${decimal(r['原始余额'])} <small>${esc(r['币种'])}</small></div></div>`).join('')}</div>`:empty('尚无已核定账户余额','先登记余额来源并完成账户核对。');

html+=`<div class="columns">${panel('待处理工作',taskbody,'',more('查看全部','tasks'))}${panel('账户余额',balances,'',more('查看账户','finance','finance.账户核对表'))}</div>`;
const act=d.activity.length?`<div class="panel-body">${d.activity.map(r=>`<div class="list-row"><div><button data-record="${esc(r['来源'])}" data-id="${esc(r['编号'])}">${esc(r['类型'])} · ${esc(r['编号'])}</button><div class="sub">${dateText(r['时间'])}</div></div><span class="muted">↗</span></div>`).join('')}</div>`:empty('还没有近期业务动态','订单、到货和发货会按真实事件时间排列。');

html+=`<div class="columns">${panel('库存期间收发',table(d.inventory,[['物品名称','物品'],['仓库','仓库'],['批次','批次'],['期间入库','期间入库'],['期间出库','期间出库'],['单位名称','单位']]),'',more('查看收发','inventory','production.库存变动表'))}${panel('近期业务动态',act)}</div>`;
if(d.issues.length)html+=panel('待核对问题',table(d.issues,[['规则','核对项目'],['记录ID','记录编号'],['说明','需要核实的内容']]));
return {html,time:d.queried_at};}



function pagination(total){return `<div class="pagination"><span>共 ${total} 条 · ${state.offset+1}–${Math.min(state.offset+state.limit,total)} 条</span><button data-paging="-1" ${state.offset===0?'disabled':''}>上一页</button><button data-paging="1" ${state.offset+state.limit>=total?'disabled':''}>下一页</button></div>`;}

const orderCols=[['产品名称','产品 / 版本',(v,r)=>`${v?esc(v):esc(r['原商品信息'])}<span class="secondary">${esc(r['版本名称']||'版本待映射')} · ${esc(r['平台订单号']||r['订单ID'])}</span>`],['客户名称','客户'],['创建时间','订单创建时间'],['商品实付','商品实付',(v,r)=>decimal(v)+' '+esc(r['币种'])],['数量','订单数量',(v,r)=>quantity(v)+' '+esc(r['单位名称'])],['已登记发货数量','已登记发货'],['履约进展','履约进展']];

const workCols=[['产品名称','产品 / 版本',(v,r)=>esc(v)+`<span class="secondary">${esc(r['版本名称'])} · ${esc(r['工单号'])}</span>`],['负责人','负责人'],['计划开始日期','计划开始'],['计划数量','计划数量',(v,r)=>quantity(v)+' '+esc(r['单位名称'])],['截至合格数量','已登记合格'],['截至报废数量','已登记报废'],['状态','当前状态']];

const fundCols=[['账户名','资金账户'],['发生时间','资金发生时间'],['交易摘要','摘要'],['收支方向','收支'],['金额','金额',(v,r)=>decimal(v)+' '+esc(r['币种'])],['已核定分摊金额','已核定分摊'],['分摊差额','待分摊差额'],['已确认内部划转','内部划转']];

async function list(kind,objectControls){const d=await api('list',{kind});lastList={kind,object:''};const total=d.total[0].count;let toolbar='';if(kind==='orders')toolbar=`<select id="status-filter" aria-label="履约状态"><option value="">全部履约状态</option>${['待履约','部分发货','已完成','登记发货已覆盖','单位待核','组合／版本待核','已关闭／取消'].map(v=>`<option value="${esc(v)}" ${state.status===v?'selected':''}>${v}</option>`).join('')}</select>`;

if(kind==='workorders')toolbar=`<select id="person-filter" aria-label="负责人"><option value="">全部负责人</option>${meta.people.map(r=>`<option value="${esc(r['人员ID'])}" ${state.person===r['人员ID']?'selected':''}>${esc(r['姓名'])}</option>`).join('')}</select>`;

if(kind==='funds')toolbar=`<select id="subject-filter" aria-label="资金所属主体"><option value="">全部资金主体</option>${meta.subjects.map(r=>`<option value="${esc(r['主体ID'])}" ${state.subject===r['主体ID']?'selected':''}>${esc(r['公司名称'])}</option>`).join('')}</select>`;

const source={orders:'sales.销售订单行表',workorders:'production.生产工单表',funds:'finance.资金流水表'}[kind];
return {html:`<div class="panel table-edit-panel" data-edit-source="${esc(source)}"><div class="table-toolbar">${objectControls}${toolbar}${state.scope?'<button class="panel-link" data-clear-scope>查看常规列表 ↗</button>':''}<span class="count">${total} 条记录</span>${editToggle(source)}</div>${table(d.rows,kind==='orders'?orderCols:kind==='workorders'?workCols:fundCols,{editObject:source,detail:kind==='orders'?'order':kind==='workorders'?'workorder':'fund',id:kind==='orders'?'订单ID':kind==='workorders'?'工单号':'资金记录ID'})}${total?pagination(total):''}</div>`,time:d.queried_at};}
async function tasks(){
  const d=await api('tasks');
  const editRecord=row=>editOrigin(row['来源'])&&row['编号']!=null?{object:row['来源'],id:row['编号']}:null;
  return {html:`<div class="panel table-edit-panel" data-edit-source="tasks"><div class="table-toolbar"><h2>待处理事项</h2><span class="count">${d.rows.length} 条</span>${editToggle('',true)}</div>${table(d.rows,[['事项','业务类型'],['内容','事项内容'],['负责人','负责人'],['期限','要求完成日期'],['状态','当前状态'],['编号','入口',(v,r)=>`<button class="table-button" data-task="${esc(JSON.stringify(r))}">查看详情 ↗</button>`]],{editRecord})}</div>`,time:d.queried_at};
}
async function searchResults(){const d=await api('search');return {html:panel('业务搜索结果',table(d.rows,[['业务','业务类型'],['名称','名称'],['编号','主录编号',(v,r)=>link(v,r['来源'])]]),`${d.rows.length} 条匹配记录`),time:d.queried_at};}
function deptObjects(){const schema={inventory:'production',rd:'rd',legal:'legal',analysis:'analysis',sales:'sales',finance:'finance',production:'production'}[route];
return meta.objects.filter(o=>o.kind==='r'&&o.standalone&&!o.retired&&(route==='archive'?o.area==='archive':route==='audit'?o.area==='audit':o.schema===schema&&o.area==='data'));}


function objectPreference(key){try{return localStorage.getItem('easyerp.object.'+route+'.'+key)||'';}catch{return '';}}
function rememberObject(obj){try{localStorage.setItem('easyerp.object.'+route+'.mode',obj.kind);localStorage.setItem('easyerp.object.'+route+'.'+obj.kind,obj.schema+'.'+obj.name);}catch{}}
function chooseObject(objects){
  const remembered=objectPreference('r');
  return objects.find(o=>o.schema+'.'+o.name===remembered)||objects.find(o=>o.schema+'.'+o.name===defaults[route])||objects[0];
}
function objectControls(all,current){
  return `<select id="object-filter" class="object-select" aria-label="选择主录">${all.map(o=>`<option value="${esc(o.schema+'.'+o.name)}" ${current.schema+'.'+current.name===o.schema+'.'+o.name?'selected':''}>${esc(o.label||o.name)}</option>`).join('')}</select>`;
}
async function explorer(){
  const all=deptObjects();
  let current=all.find(o=>o.schema+'.'+o.name===exploreObject);
  // Dashboard scopes target the common business list even after browsing records.
  if(!current&&businessLists[route]&&['pending','cash-income','cash-expense'].includes(state.scope))current=all.find(o=>o.schema+'.'+o.name===defaults[route]);
  if(!current)current=chooseObject(all);
  if(!current)return {html:empty('当前模块暂无可用对象。')};
  exploreObject=current.schema+'.'+current.name;rememberObject(current);
  const controls=objectControls(all,current);
  if(businessLists[route]&&exploreObject===defaults[route])return list(businessLists[route],controls);
  const d=await api('explore',{object:exploreObject,date_filter:route==='archive'?'0':'1'});lastList={object:exploreObject,date_filter:route==='archive'?'0':'1'};const total=d.total[0].count;
  const unifiedColumns={'production.采购订单表':['采购单ID','供应商','创建日期','采购内容','订单金额','币种','订单文件路径','状态'],'production.仓库档案表':['仓库ID','地点','保管方ID','主体ID','启用状态','地点标识'],'production.库存盘点表':['盘点ID','盘点日期','物料版本ID','产品版本ID','库位ID','账面数量','实盘数量','盘点差异','单位ID']};
  const columns=unifiedColumns[exploreObject]?.map(key=>[key,key]);
  return {html:`<div class="panel table-edit-panel" data-edit-source="${esc(exploreObject)}"><div class="table-toolbar">${controls}<span class="count">${total} 条</span>${editToggle(exploreObject)}</div>${table(d.rows,columns,{object:exploreObject,editObject:exploreObject})}${total?pagination(total):''}</div>`,time:d.queried_at};
}


async function render(){const token=++sequence;route=location.hash.replace(/^#\//,'').split('?')[0]||'overview';if(!navs.some(x=>x[0]===route))route='overview';if(route==='tasks')route='workflow';const nav=navs.find(x=>x[0]===route);$('#title').textContent=nav[1];$('#crumb').textContent=nav[1];$('#nav').innerHTML=navs.filter(([key])=>['overview','plans','workflow','data','archive','audit'].includes(key)).map(([key,label])=>`<a href="#/${key}" class="${key===route||(key==='data'&&['sales','inventory','production','rd','finance','legal','analysis'].includes(route))?'active':''}">${icon({plans:'production',workflow:'tasks',data:'overview',archive:'inventory',audit:'legal'}[key]||key)}<span>${label}</span></a>`).join('');$('#sidebar').classList.remove('open');sync();$('#export').disabled=['overview','tasks','plans','workflow','data','archive','audit'].includes(route);$('#export').hidden=$('#export').disabled;$('#search').placeholder=route==='tasks'?'搜索事项、编号或负责人':'搜索编号、产品或客户';for(const id of ['start','end']){$('#'+id).disabled=false;$('#'+id).hidden=false;}$('.date-filter').hidden=false;$('#date-presets').hidden=false;syncDatePresets();$('#content').innerHTML='<div class="loading">正在读取业务数据…</div>';
try{if(!meta)meta=await api('meta');updateAccess(meta);const result=route==='overview'&&state.search?await searchResults():route==='overview'?await overview():['plans','workflow','tasks','data','archive','audit'].includes(route)?await window.easyerpWorkspace.render(route):await explorer();if(token!==sequence)return;$('#content').innerHTML=result.html;$('#connection').textContent=state.mode==='demo'?'演示数据':'本机数据库';bindFilters();window.easyerpTableEdit?.mount();window.easyerpWorkspace?.mounted();}catch(err){if(token!==sequence)return;$('#content').innerHTML=`<div class="error-panel"><strong>暂时无法读取业务数据</strong><br>${esc(err.message)}<br><button class="button" data-retry>重新读取</button></div>`;$('#connection').textContent='连接待检查';$('#access-level').textContent='—';}}
function bindFilters(){
  for(const [id,key] of [['status-filter','status'],['person-filter','person'],['subject-filter','subject'],['object-filter','object']]){
    const el=$('#'+id);if(el)el.onchange=()=>{if(key==='object'){state.scope='';move(route,el.value);return;}state[key]=el.value;state.offset=0;render();};
  }
}



const detailSections={order:{basic:'sales.销售订单登记表',lines:['订单商品明细','sales.销售订单行表'],shipments:['逐次发货','production.发货记录表'],workorders:['关联工单','production.工单订单对应表'],settlements:['资金结算','finance.结算分摊表'],invoices:['发票分摊','finance.发票登记表'],aftersales:['售后反馈','sales.售后事件表'],demands:['客户需求','sales.客户需求表']},workorder:{basic:'production.生产工单表',orders:['订单对应','production.工单订单对应表'],bom:['固定发布 BOM','rd.BOM明细表'],materials:['实际领退料','production.生产领退料表'],completion:['逐次完工','production.完工记录表'],scrap:['报废事件','production.报废记录表'],files:['发布文件','rd.项目文件登记表']},fund:{basic:'finance.资金流水表',purposes:['用途核定','finance.资金用途核定表'],allocations:['结算分摊','finance.结算分摊表'],sources:['原始流水来源','finance.流水来源明细表'],transfers:['内部划转对应','finance.内部划转对应表'],duplicates:['重复记录核定','finance.重复记录对应表'],entries:['已过账分录','finance.会计分录表']}};

const relationColumns={

lines:orderCols,shipments:[['发货时间','发货日期'],['数量','数量'],['单位ID','单位'],['物流单号','物流单号'],['检验ID','检验记录'],['发货事件ID','发货记录']],

workorders:[['工单号','工单'],['对应数量','对应数量'],['单位ID','单位']],orders:[['销售订单行ID','订单行'],['对应数量','对应数量'],['单位ID','单位']],

settlements:[['发生时间','资金发生时间'],['分摊金额','结算金额'],['币种','币种'],['方向','方向'],['用途状态','核定状态'],['资金记录ID','资金来源']],

invoices:[['日期','开票日期'],['发票号码','发票号码'],['分摊金额','分摊金额'],['分摊税额','分摊税额'],['币种','币种'],['票据ID','原票记录']],

aftersales:[['发生时间','发生时间'],['类型','类型'],['原因','客户描述'],['处理状态','处理状态']],demands:[['日期','日期'],['客户原话','客户原话'],['处理状态','处理状态']],

materials:[['日期','日期'],['物料名称','物料'],['类型','领退料'],['数量','实际数量'],['单位名称','单位'],['批次','批次']],

hours:[['工序','工序'],['开始时间','开始时间'],['结束时间','结束时间'],['有效工时','有效工时'],['人员ID','人员']],

completion:[['日期','完工日期'],['批次','批次'],['合格数量','合格数量'],['不良数量','不良数量'],['单位ID','单位']],

scrap:[['日期','日期'],['批次','批次'],['数量','报废数量'],['单位ID','单位']],

bom:[['物料名称','物料'],['单件用量','单件用量'],['单位名称','单位'],['位号','位号'],['替代适用条件','替代条件']],

files:[['文件名','文件名'],['正式版本','版本'],['相对路径','相对路径'],['文件ID','文件记录']],

purposes:[['用途','资金用途'],['状态','核定状态'],['核定金额','核定金额'],['所属月份','归属月份'],['依据','依据'],['用途核定ID','用途记录']],

allocations:[['分摊金额','分摊金额'],['方向','方向'],['费用类型','费用类型'],['销售订单行ID','销售订单行'],['采购订单行ID','采购订单行'],['工单号','工单']],

sources:[['文件路径','原始文件路径'],['来源行号','文件行号'],['文件校验值','文件校验值'],['流水来源ID','来源记录']]

};

function fieldGrid(row,object){return `<dl class="field-grid">${Object.entries(row).map(([key,value])=>`<div class="field"><dt>${esc(key)}</dt><dd>${display(value,key,row,object)}</dd></div>`).join('')}</dl>`;}

function renderDrawer(){const ds=drawerState;if(!ds)return;const d=ds.data,base=d.basic?.[0];if(!base){$('#drawer-content').innerHTML=`<div class="drawer-header"><button class="icon-button drawer-close" data-close aria-label="关闭">×</button><h2>未找到对应记录</h2></div>${empty('N/A')}`;return;}const cfg=ds.kind==='record'?{basic:ds.object}:detailSections[ds.kind];const object=cfg.basic;const title=base['客户名称']||base['产品名称']||base['账户名']||base['名称']||base['项目名称']||base['平台订单号']||ds.key;let body='';if(drawerTab==='basic'){body=panel('基本信息',fieldGrid(base,object),object);if(ds.kind==='order')body+=panel('商品概览',table(d.lines,orderCols,{object:'sales.销售订单行表'}));}
if(drawerTab==='related'){if(ds.kind==='record'){body=d._relations.filter(r=>d[r.key]?.length).map(r=>panel(r.object.split('.')[1],table(d[r.key],null,{object:r.object}),r.object)).join('')||empty('尚无关联明细');}else body=Object.entries(cfg).filter(([k])=>k!=='basic').map(([key,[label,source]])=>panel(label,table(d[key],relationColumns[key]||null,{object:source}),source)).join('');}
if(drawerTab==='progress'){const events=[];for(const [key,rows] of Object.entries(d)){if(key.startsWith('_')||!Array.isArray(rows)||key==='basic')continue;for(const row of rows){const time=Object.entries(row).find(([k,v])=>/时间$|日期$/.test(k)&&v);if(time)events.push({date:time[1],label:cfg[key]?.[0]||key,row,source:cfg[key]?.[1]||ds.object});}}events.sort((a,b)=>new Date(a.date)-new Date(b.date));body=panel('已登记业务进展',events.length?`<div class="timeline">${events.map(e=>`<div class="timeline-item">${esc(e.label)}<time>${dateText(e.date)}</time>${badge(e.row['状态']||e.row['处理状态']||'已登记')}<span class="secondary">来源 ${esc(e.source)}</span></div>`).join('')}</div>`:empty('尚无带日期的关联事件'));}
if(drawerTab==='files'){const files=[];for(const [section,rows] of Object.entries(d)){if(section.startsWith('_')||!Array.isArray(rows))continue;for(const row of rows)for(const [key,value] of Object.entries(row))if(value&&/路径|依据|证据|SHA256|校验值|文件名|说明|原话/.test(key))files.push({key,value});}body=panel('文件与依据',files.length?files.map(f=>`<div class="file-card"><strong>${esc(f.key)}</strong><p>${esc(f.value)}</p><button class="text-button" data-copy="${esc(f.value)}">复制内容</button></div>`).join(''):empty('N/A文件或依据'));}
$('#drawer-content').innerHTML=`<div class="drawer-header"><button class="icon-button drawer-close" data-close aria-label="关闭详情">×</button><span class="standard-tag">${ds.kind==='record'?'主录追溯':{order:'订单详情',workorder:'工单详情',fund:'资金结算详情'}[ds.kind]}</span><h2>${esc(title)}</h2><p>${esc(ds.key)}<br>来源 ${esc(object)} · ${state.mode==='demo'?'演示数据':'正式数据'}</p><div class="drawer-tabs" role="tablist">${[['basic','基本信息'],['related','关联明细'],['progress','业务进展'],['files','文件与依据']].map(([key,label])=>`<button role="tab" aria-selected="${drawerTab===key}" class="${drawerTab===key?'active':''}" data-tab="${key}">${label}</button>`).join('')}</div></div><div class="drawer-body">${body}</div>`;window.easyerpManual?.decorateDrawer(object,base);}

async function openDetail(kind,key,object=''){const token=++detailSequence;if(object==='sales.销售订单登记表')kind='order';if(object==='production.生产工单表')kind='workorder';if(object==='finance.资金流水表')kind='fund';$('#drawer').hidden=false;$('#drawer-backdrop').hidden=false;document.body.style.overflow='hidden';$('.shell').inert=true;$('#drawer-content').innerHTML='<div class="loading">正在追溯关联记录…</div>';drawerTab='basic';try{const data=kind==='record'?await api('record',{object,id:key}):await api('detail',{kind,id:key});if(token!==detailSequence)return;drawerState={kind,key,object,data};renderDrawer();$('#drawer').scrollTop=0;$('#drawer .drawer-close')?.focus();}catch(err){$('#drawer-content').innerHTML=`<div class="drawer-header"><button class="icon-button drawer-close" data-close>×</button><h2>暂时无法查看详情</h2><p>${esc(err.message)}</p></div>`;}}

function closeDrawer(){detailSequence++;$('.shell').inert=false;drawerState=null;$('#drawer').hidden=true;$('#drawer-backdrop').hidden=true;document.body.style.overflow='';$('#refresh').focus();}

async function exportData(){if(!lastList)return;try{const r=await fetch('/api/export?'+params(lastList));if(!r.ok){const d=await r.json();throw new Error(d.error);}const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='easyerp-'+(lastList.kind||'records')+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);const total=Number(r.headers.get('X-Total-Rows')),n=Number(r.headers.get('X-Exported-Rows'));toast(n<total?`已导出前 ${n} 条，当前共有 ${total} 条；请缩小筛选范围。`:`已导出 ${n} 条记录；N/A值使用 \\N 标记。`);}catch(err){toast(err.message);}}

document.addEventListener('click',async e=>{const el=e.target.closest('button');if(!el)return;if(el.hasAttribute('data-page')){state.scope=el.dataset.scope||'';move(el.dataset.page,el.dataset.object||'');}else if(el.dataset.detail)openDetail(el.dataset.detail,el.dataset.id);else if(el.dataset.record)openDetail('record',el.dataset.id,el.dataset.record);else if(el.dataset.task){const r=JSON.parse(el.dataset.task);if(r['来源']==='workspace'){await window.easyerpWorkspace.openItem(r['编号']);return;}openDetail(r['入口']==='record'?'record':r['入口'],r['入口ID'],r['来源']);}else if(el.dataset.tab){drawerTab=el.dataset.tab;renderDrawer();}else if(el.hasAttribute('data-close'))closeDrawer();else if(el.dataset.copy){try{await navigator.clipboard.writeText(el.dataset.copy);toast('已复制');}catch{toast('请选中文字后复制');}}else if(el.dataset.paging){state.offset=Math.max(0,state.offset+Number(el.dataset.paging)*state.limit);render();}else if(el.hasAttribute('data-clear-scope')){state.scope='';move(route,exploreObject);}else if(el.hasAttribute('data-retry'))render();});

$('#apply').onclick=()=>{for(const k of ['start','end','search'])state[k]=$('#'+k).value;if(!state.start||!state.end)return toast('请选择有效的起止日期');if(state.start>state.end)return toast('请选择有效的起止日期');state.offset=0;render();};$('#search').onkeydown=e=>{if(e.key==='Enter')$('#apply').click();};$('#refresh').onclick=()=>render();$('#export').onclick=exportData;$('#drawer-backdrop').onclick=closeDrawer;document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('#manual-entry')?.open&&!document.querySelector('#import-interface')?.open&&!document.querySelector('#company-details')?.open)closeDrawer();});$('#menu').onclick=()=>$('#sidebar').classList.toggle('open');
async function changeMode(mode){
  if(changeMode.busy)return;
  const previousMode=state.mode,previousMeta=meta;
  changeMode.busy=true;$('#source-toggle').disabled=true;
  closeDrawer();state.mode=mode;state.offset=0;meta=null;sync();
  $('#content').innerHTML='<div class="loading">正在读取业务数据…</div>';
  try{meta=await api('meta');await render();}
  catch(err){state.mode=previousMode;meta=previousMeta;sync();await render();toast(err.message);}
  finally{changeMode.busy=false;$('#source-toggle').disabled=false;}
}

$('#source-toggle').onclick=()=>toggleSourceMenu();$('#back-live').onclick=()=>changeMode('live');window.addEventListener('hashchange',()=>{if(!$('#drawer').hidden)closeDrawer();const q=new URLSearchParams(location.hash.split('?')[1]||'');exploreObject=q.get('object')||'';state.scope=q.get('scope')||'';state.offset=0;render();});
(async()=>{const q=new URLSearchParams(location.hash.split('?')[1]||'');exploreObject=q.get('object')||'';state.scope=q.get('scope')||'';sync();try{meta=await api('meta');sync();await render();}catch(err){$('#content').innerHTML=`<div class="error-panel">${esc(err.message)}<br>请确认前端服务和数据库已经启动。<br><button class="button" data-retry>重新读取</button></div>`;}})();


window.addEventListener('erp:data-changed',event=>{if(event.detail.mode===state.mode){meta=null;render();}});

function accessLabel(capabilities){
  const read=capabilities?.query_read_only===true||capabilities?.read_only===true;
  const write=capabilities?.manual_entry===true&&capabilities?.read_only===false;
  return read&&write?'R&W':read?'Read':write?'Write':'—';
}
function updateAccess(capabilities){$('#access-level').textContent=accessLabel(capabilities);}
function openQueryDate(input){
  if(input.disabled||input.hidden)return;
  if(typeof input.showPicker==='function'){try{input.showPicker();}catch{input.focus();}}
}
for(const id of ['start','end']){
  const input=$('#'+id),trigger=$('#'+id+'-trigger');
  trigger.addEventListener('click',()=>openQueryDate(input));
  input.addEventListener('change',syncQueryDates);
}
function syncQueryDates(){
  for(const id of ['start','end']){
    const input=$('#'+id),trigger=$('#'+id+'-trigger');
    trigger.textContent=input.value?input.value.replaceAll('-','/'):'YYYY/MM/DD';
    trigger.disabled=input.disabled;
    trigger.parentElement.hidden=input.hidden;
  }
}
function syncSourceMenu(){
  document.querySelectorAll('[data-source-value]').forEach(button=>{
    const selected=button.dataset.sourceValue===state.mode;
    button.setAttribute('aria-checked',String(selected));
    button.tabIndex=selected?0:-1;
  });
}
function closeSourceMenu(restoreFocus=false){
  $('#source-menu').hidden=true;
  $('#source-toggle').setAttribute('aria-expanded','false');
  if(restoreFocus)$('#source-toggle').focus({preventScroll:true});
}
function toggleSourceMenu(){
  const menu=$('#source-menu'),trigger=$('#source-toggle');
  if(!menu.hidden){closeSourceMenu();return;}
  syncSourceMenu();menu.hidden=false;
  const anchor=trigger.getBoundingClientRect(),width=menu.offsetWidth,height=menu.offsetHeight;
  menu.style.left=Math.max(8,Math.min(anchor.left,window.innerWidth-width-8))+'px';
  menu.style.top=Math.max(8,anchor.top>=height+16?anchor.top-height-8:Math.min(anchor.bottom+8,window.innerHeight-height-8))+'px';
  trigger.setAttribute('aria-expanded','true');
  menu.querySelector('[aria-checked="true"]').focus({preventScroll:true});
}
$('#source-menu').addEventListener('click',event=>{
  const button=event.target.closest('[data-source-value]');if(!button)return;
  const mode=button.dataset.sourceValue;closeSourceMenu(true);
  if(mode!==state.mode)changeMode(mode);
});
document.addEventListener('click',event=>{if(!event.target.closest('#source-menu,#source-toggle'))closeSourceMenu();});
document.addEventListener('keydown',event=>{
  const menu=$('#source-menu');if(menu.hidden)return;
  if(event.key==='Escape'){event.preventDefault();closeSourceMenu(true);}
  else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
    event.preventDefault();const items=[...menu.querySelectorAll('[data-source-value]')];
    let index=items.indexOf(document.activeElement);
    index=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:items.length-1))%items.length;
    items[index].focus({preventScroll:true});
  }else if(event.key==='Tab')closeSourceMenu();
});
$('#source-toggle').addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();if($('#source-menu').hidden)toggleSourceMenu();}});
window.addEventListener('resize',()=>closeSourceMenu());

window.renderWorkspacePage=render;
