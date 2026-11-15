'use strict';

const $ = (s) => document.querySelector(s);

const esc = (v) =>
  String(v ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );

const paths = {
  overview: 'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
  tasks: 'M6 4h12v17H6zM9 2h6v4H9zm0 8h6m-6 4h6m-6 4h4',
  sales: 'M3 5h18v15H3zm0 4h18m-7 4h4m-4 3h4',
  inventory: 'M3 7l9-5 9 5v11l-9 5-9-5zm0 0 9 5 9-5m-9 5v11',
  production: 'M3 21V9l6 3V7l6 4V3h5l1 18zm4-4h1m4 0h1m4 0h1',
  rd: 'm8 3 4 4-4 4m5 5 4-4 4 4M3 14h7v7H3z',
  finance: 'M3 5h18v16H3zm0 4h18m-8 4h8m-5 3h2',
  legal: 'M12 2v20M5 6h14M5 6l-4 8h8zm14 0-4 8h8zM8 22h8',
  analysis: 'M3 3v18h18M7 16l4-5 4 2 5-7',
};

const icon = (k) =>
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[k] || paths.overview}"/></svg>`;

const navs = [
  ['overview', '仪表盘'],
  ['mapping', '矩阵关系图'],
  ['calculations', '量化计算'],
  ['plans', '历史计划'],
  ['workflow', '工作流'],
  ['data', '活动数据'],
  ['archive', '静态数据'],
  ['delivery', '部门交付'],
  ['audit', '审计'],
  ['tasks', '工作流'],
  ['sales', '销售'],
  ['inventory', '采购与库存'],
  ['production', '生产'],
  ['rd', '研发'],
  ['finance', '财务'],
  ['legal', '法务'],
  ['analysis', '分析报告'],
];
const url = new URL(location.href);

const today = new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);

const state = {
  mode: url.searchParams.get('mode') || 'live',
  start: url.searchParams.get('start') || today.slice(0, 8) + '01',
  end: url.searchParams.get('end') || today,
  currency: window.ERPDefaults.currency,
  tz: window.ERPDefaults.timeZone,
  search: url.searchParams.get('search') || '',
  offset: 0,
  limit: 30,
  scope: '',
  status: '',
  person: '',
  subject: '',
  department: '',
  dashboard: false,
};

let meta = null,
  sequence = 0,
  detailSequence = 0,
  drawerState = null,
  drawerTab = 'basic',
  route = 'overview',
  exploreObject = '',
  lastList = null,
  drawerTrail = [],
  renderedNavigationHash = location.hash;

const defaults = {
  sales: 'sales.销售订单行表',
  production: 'production.完工记录表',
  finance: 'finance.资金流水表',
  inventory: 'production.采购订单表',
  rd: 'rd.BOM明细表',
  legal: 'legal.合同审阅表',
  analysis: 'analysis.分析报告登记表',
};
const businessLists = { sales: 'orders', finance: 'funds' };
const departmentForRoute = {
  inventory: 'production',
  production: 'production',
  sales: 'sales',
  finance: 'finance',
  rd: 'rd',
  legal: 'legal',
  analysis: 'analysis',
};
const workspacePages = ['calculations', 'workflow', 'data', 'archive', 'delivery'];
function activeWorkspacePage() {
  return departmentForRoute[route] ? 'data' : route;
}
function readWorkspaceSelection() {
  const query = new URLSearchParams(location.hash.split('?')[1] || '');
  const requested = query.get('department');
  const inferred = departmentForRoute[route] || (query.get('object') || '').split('.')[0];
  state.department = window.easyerpWorkspace
    .navigation()
    .departments.some(([key]) => key === (requested ?? inferred))
    ? (requested ?? inferred)
    : '';
  if (route === 'calculations') state.department = '';
  state.dashboard = query.get('dashboard') === '1' || route === 'overview';
  if (route === 'overview') route = 'blank';
}
function renderWorkspaceSelection() {
  const selected = activeWorkspacePage();
  const item = (key, label, extra = '') =>
    `<button type="button" class="nav-option ${key === selected ? 'active' : ''} ${extra}" data-workspace-page="${key}" aria-pressed="${key === selected}">${icon({ calculations: 'analysis', plans: 'production', workflow: 'tasks', data: 'overview', archive: 'inventory', audit: 'legal' }[key] || key)}<span>${label}</span></button>`;
  $('#nav').innerHTML =
    `<button type="button" class="nav-option nav-dashboard ${state.dashboard ? 'active' : ''}" data-dashboard-toggle aria-pressed="${state.dashboard}">${icon('overview')}<span>仪表盘</span></button><div class="sidebar-modules" role="group" aria-label="选择审阅内容">${navs
      .filter(([key]) => workspacePages.includes(key))
      .map(([key, label]) => item(key, label))
      .join('')}</div>${item('audit', '审计', 'sidebar-audit')}`;
  $('#department-bar').innerHTML = window.easyerpWorkspace
    .navigation()
    .departments.map(
      ([key, label]) =>
        `<button type="button" class="department-option ${state.department === key ? 'active' : ''}" data-department="${key}" aria-pressed="${state.department === key}">${label}</button>`
    )
    .join('');
}
function blankWorkspace() {
  return `<section class="workspace-blank" aria-label="工作空间白板"><div class="workspace-watermark" aria-hidden="true"><svg viewBox="0 0 200 200"><rect x="10" y="10" width="180" height="180" rx="48" fill="currentColor"/><path d="M61 108h80c1-32-14-50-39-50-28 0-44 21-44 47 0 31 18 48 47 48 15 0 26-4 36-12l-10-15c-8 6-15 9-25 9-16 0-24-9-25-22h60V98H81c2-14 8-22 21-22 12 0 19 8 19 19H61z" fill="var(--bg)"/></svg></div><p class="workspace-blank-name" data-i18n-ignore>easyERP</p><div class="workspace-blank-hints"><p><span>选择审阅内容</span><span>左侧栏</span></p><p><span>选择部门</span><span>上方栏</span></p><p><span>查看经营概况</span><span>仪表盘</span></p></div></section>`;
}
document.addEventListener('click', (event) => {
  const button = event.target.closest(
    '[data-workspace-page],[data-department],[data-dashboard-toggle]'
  );
  if (!button) return;
  if (button.hasAttribute('data-dashboard-toggle')) {
    if (state.dashboard) move('mapping');
    else if (route === 'mapping') move('blank');
    else move(route, exploreObject, { dashboard: true });
    return;
  }
  state.scope = '';
  state.status = '';
  state.person = '';
  state.subject = '';
  if (button.hasAttribute('data-department')) {
    const department =
      state.department === button.dataset.department ? '' : button.dataset.department;
    move(activeWorkspacePage(), '', { department });
    return;
  }
  move(
    activeWorkspacePage() === button.dataset.workspacePage ? 'blank' : button.dataset.workspacePage, '',
    button.dataset.workspacePage === 'mapping' ? { dashboard: false } : {}
  );
});

const knownRefs = {
  '订单ID': 'sales.销售订单登记表',
  '销售订单行ID': 'sales.销售订单行表',
  '工单号': 'production.生产工单表',
  '资金记录ID': 'finance.资金流水表',
  '账户ID': 'finance.资金账户档案表',
  '客户ID': 'sales.客户档案表',
  '项目ID': 'rd.项目登记表',
  '产品版本ID': 'rd.产品版本表',
  '物料版本ID': 'rd.物料版本表',
  'BOM登记ID': 'rd.BOM登记表',
  '发布批次ID': 'rd.发布批次表',
  '单位ID': 'rd.计量单位表',
  '票据ID': 'finance.发票登记表',
  '用途核定ID': 'finance.资金用途核定表',
  '采购单ID': 'production.采购订单表',
  '采购订单行ID': 'production.采购订单行表',
  '人员ID': 'finance.人员档案表',
  '确认人ID': 'finance.人员档案表',
  '负责人ID': 'finance.人员档案表',
  '主体ID': 'legal.公司主体档案表',
  '所有权主体ID': 'legal.公司主体档案表',
  '文件ID': 'rd.项目文件登记表',
  '库存事件ID': 'production.库存变动表',
  '发货事件ID': 'production.发货记录表',
  '到货ID': 'production.到货记录表',
  '验收ID': 'production.验收记录表',
};

function decimal(value) {
  if (value === null || value === undefined) return 'N/A';
  const s = String(value),
    parts = s.split('.');
  if (!/^-?\d+$/.test(parts[0])) return esc(s);
  let fraction = (parts[1] || '').replace(/0+$/, '');
  fraction = fraction.padEnd(2, '0');
  return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + fraction;
}

function quantity(value) {
  if (value === null || value === undefined) return 'N/A';
  return esc(
    String(value)
      .replace(/(\.\d*?)0+$/, '$1')
      .replace(/\.$/, '')
  );
}

function dateText(value) {
  if (!value) return 'N/A';
  if (String(value).length === 10) return esc(value);
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return esc(value);
  return d.toLocaleString(window.ERPUI?.locale() || 'zh-CN', {
    timeZone: state.tz,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function badge(value) {
  if (value == null) return '<span class="muted">N/A</span>';
  const text = String(value),
    type = /待|新建|部分|中|差异|未关闭/.test(text)
      ? 'warn'
      : /取消|撤销|撤回|不匹配|超额/.test(text)
        ? 'red'
        : /关闭|完成|核定|发布|履约/.test(text)
          ? ''
          : 'neutral';
  return `<span class="badge ${type}">${esc(text)}</span>`;
}

function empty(title = '尚无相关记录', _sub = '', graph = false) {
  return `<div class="empty ${graph ? 'graph' : ''}">${esc(title)}</div>`;
}
function panel(title, body, sub = '', action = '') {
  return `<section class="panel"><div class="panel-head"><h2>${esc(title)}${sub ? `<small>${esc(sub)}</small>` : ''}</h2>${action}</div>${body}</section>`;
}

function more(label, page, obj = '') {
  return `<button class="panel-link" data-page="${page}" data-object="${esc(obj)}">${label} ↗</button>`;
}

function link(value, object, label = value) {
  return `<button class="table-button" data-i18n-ignore title="${esc(value)}" data-record="${esc(object)}" data-id="${esc(value)}">${esc(label)}</button>`;
}

function refFor(key, object) {
  const o = meta?.objects.find((x) => x.schema + '.' + x.name === object);
  if (o && o.kind === 'r' && o.pk === key) return object;
  const r = meta?.references.find(
    (x) => `${x.source_schema}.${x.source_table}` === object && x.source_column === key
  );
  return r ? `${r.target_schema}.${r.target_table}` : knownRefs[key];
}

function referenceDestination(object) {
  const definition = meta?.objects.find((o) => o.schema + '.' + o.name === object);
  if (!definition) return null;
  const page = ['archive', 'audit', 'workflow', 'plans', 'delivery'].includes(definition.area)
    ? definition.area
    : 'data';
  const hash = navigationHash(page, object, '', definition.schema);
  return hash + '&reference=1';
}

function referenceHeader(field, label, object) {
  const reference = meta?.references.find(
    (r) => r.source_schema + '.' + r.source_table === object && r.source_column === field
  );
  const target = reference && reference.target_schema + '.' + reference.target_table;
  const href = target && referenceDestination(target);
  return href
    ? `<a class="reference-link" href="${esc(href)}" data-reference="${esc(target)}" title="${esc(target)}">${esc(label)}</a>`
    : esc(label);
}

function display(value, key, row = {}, object = '') {
  if (value == null) return '<span class="muted">N/A</span>';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (/状态|进展/.test(key)) return badge(value);
  if (/日期|时间|月份/.test(key)) return dateText(value);
  if (
    /金额|实付|单价|收入|成本|差额|余额|税额|基准工资|分摊$/.test(key) &&
    /^-?\d+(\.\d+)?$/.test(String(value))
  )
    return `<span class="number">${decimal(value)}</span>`;
  if (/数量|工时|用量|比例|^期间入库$|^期间出库$/.test(key)) return quantity(value);
  const target = refFor(key, object);
  if (target) {
    let label = value;
    if (target === 'rd.计量单位表')
      label = meta.units?.find((x) => x['单位ID'] === value)?.['单位名称'] || value;
    if (target === 'finance.人员档案表')
      label = meta.people.find((x) => x['人员ID'] === value)?.['姓名'] || value;
    if (target === 'legal.公司主体档案表')
      label = meta.subjects.find((x) => x['主体ID'] === value)?.['公司名称'] || value;
    return (
      link(value, target, label) +
      (label !== value ? `<span class="secondary">${esc(value)}</span>` : '')
    );
  }
  return esc(typeof value === 'object' ? JSON.stringify(value) : value);
}

const pencilIcon =
  '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m16 3 5 5M4 15 15 4a3.5 3.5 0 0 1 5 5L9 20l-6 1zM4 15l5 5"/></svg>';
function editOrigin(source) {
  const key = source;
  return meta?.objects.find((o) => o.schema + '.' + o.name === key && o.kind === 'r' && !o.retired);
}
function editToggle(source, supported = !!editOrigin(source)) {
  return `<button type="button" class="button primary table-edit-toggle" data-table-edit-toggle aria-pressed="false" ${supported ? '' : 'disabled title="请在对应业务主录中修改。"'}>${pencilIcon}<span>编辑</span></button>`;
}
const hiddenIdentityField = (key) => /^(sha[-_]?256|long_id|longid|长ID|长编号|长标识|身份摘要)$/i.test(key);
function table(rows, columns = null, options = {}) {
  const origin = options.editObject && editOrigin(options.editObject),
    key = origin && origin.schema + '.' + origin.name;
  const hiddenColumns = new Set(options.hiddenColumns || []);
  rows = rows || [];
  const object = meta?.objects.find(
    (o) => o.schema + '.' + o.name === (options.object || options.editObject)
  );
  const fields = [...new Set([
    ...(object?.columns || []).map((c) => c.name),
    ...rows.flatMap((row) => Object.keys(row)),
  ])];
  if (columns && options.object && object?.kind === 'r') {
    const shown = new Set(columns.map(([field]) => field));
    columns = [...columns, ...fields.filter((field) => !shown.has(field) &&
      !field.startsWith('_') && !hiddenIdentityField(field)).map((field) => [field, field])];
  }
  const cols = (
    columns ||
    fields
      .filter((k) => !k.startsWith('_') && !hiddenIdentityField(k))
      .map((k) => [k, k])
  ).filter((c) => !hiddenIdentityField(c[0]) && !hiddenColumns.has(c[0]));
  if (!cols.length)
    return empty(options.emptyTitle || 'N/A', options.emptySub || '当前查询范围内没有记录。');
  const editable = !!(origin || options.editRecord);
  const emptyRow = rows.length
    ? ''
    : `<tr class="table-view-empty"><td colspan="${cols.length + (options.detail ? 1 : 0) + (editable ? 1 : 0)}">${empty(options.emptyTitle || 'N/A')}</td></tr>`;
  return `<div class="table-wrap" data-table-scroll tabindex="0"><table><thead><tr>${cols.map(([field, label, , referenceField = field]) => `<th data-table-column="${esc(field)}">${referenceHeader(referenceField, label, options.object || options.editObject || '')}</th>`).join('')}${options.detail ? '<th></th>' : ''}${editable ? '<th class="table-edit-column">修改</th>' : ''}</tr></thead><tbody>${emptyRow}${rows
    .map((row) => {
      const target = options.editRecord
        ? options.editRecord(row)
        : origin && row[origin.pk] != null
          ? { object: key, id: row[origin.pk] }
          : null;
      return `<tr ${target ? `data-row-object="${esc(target.object)}" data-row-id="${esc(target.id)}" tabindex="0" aria-expanded="false" aria-label="展开或收起记录详情"` : ''}>${cols.map(([field, label, format]) => `<td title="${esc(row[field] ?? 'N/A')}">${format ? format(row[field], row) : display(row[field], field, row, options.object || '')}</td>`).join('')}${options.detail ? `<td><button class="table-button" data-detail="${options.detail}" data-id="${esc(row[options.id])}">查看 ↗</button></td>` : ''}${editable ? `<td class="table-edit-column">${target ? `<button type="button" class="table-row-edit" data-row-edit aria-label="修改这条记录" aria-expanded="false">${pencilIcon}<span data-ui-label>修改</span></button>` : '<span class="muted">N/A</span>'}</td>` : ''}</tr>`;
    })
    .join('')}</tbody></table></div>`;
}

function params(extra = {}) {
  return new URLSearchParams({
    ...state,
    ...extra,
    currency: window.ERPDefaults.currency,
    tz: window.ERPDefaults.timeZone,
  });
}

async function api(path, extra = {}) {
  const r = await window.easyerpFetch('/api/' + path + '?' + params(window.easyerpTableTools?.augmentParams(path, extra) || extra));
  let body;
  try {
    body = await r.json();
  } catch {
    throw new Error('前端服务未返回有效数据');
  }
  if (!r.ok) throw new Error(body.error || '暂时无法读取数据');
  window.easyerpTableTools?.rememberResult(path, extra, body);
  return body;
}

function toast(text) {
  $('#toast').textContent = text;
  $('#toast').hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($('#toast').hidden = true), 4200);
}

const DATE_PRESETS = {
  year: ['01-01', '12-31'],
  q1: ['01-01', '03-31'],
  q2: ['04-01', '06-30'],
  q3: ['07-01', '09-30'],
  q4: ['10-01', '12-31'],
};
function datePresetYear() {
  const date = [state.start, state.end, today].find(
    (value) => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number(value.slice(0, 4)) > 0
  );
  return date.slice(0, 4);
}
function syncDatePresets() {
  syncQueryDates();
  const year = datePresetYear(),
    disabled = $('#start').disabled || $('#end').disabled;
  $('#date-presets').setAttribute('aria-label', `${year}年日期快捷选择`);
  document.querySelectorAll('[data-date-preset]').forEach((button) => {
    const range = DATE_PRESETS[button.dataset.datePreset];
    const active =
      state.start === `${year}-${range[0]}` && state.end === `${year}-${range[1]}`;
    button.disabled = disabled;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
    button.title = disabled
      ? '此视图未启用日期范围'
      : `${year}年${button.dataset.datePreset === 'year' ? '全年' : button.dataset.datePreset.toUpperCase()}（按开始日期所在年份）`;
  });
}
$('#date-presets').addEventListener('click', (event) => {
  const button = event.target.closest('[data-date-preset]');
  if (!button || button.disabled || $('#start').disabled || $('#end').disabled) return;
  const range = DATE_PRESETS[button.dataset.datePreset];
  if (!range) return;
  const year = datePresetYear();
  applyQuery(`${year}-${range[0]}`, `${year}-${range[1]}`);
});

function sync() {
  window.easyerpCompany?.syncSource();
  for (const id of ['start', 'end', 'search']) $('#' + id).value = state[id];
  $('#connection').textContent = window.easyerpDatabaseSource.label;
  syncSourceMenu();
  $('#source-toggle').classList.toggle('demo', state.mode === 'demo');
  $('#source-toggle').title = '选择数据源';
  $('#demo-notice').hidden = state.mode !== 'demo';
  const u = new URL(location.href);
  for (const k of ['mode', 'start', 'end', 'currency', 'tz', 'search'])
    u.searchParams.set(k, state[k]);
  const navigation = { ...history.state, easyerpView: { ...state } };
  if (!referenceContext()) delete navigation.easyerpReference;
  history.replaceState(navigation, '', u);
  syncDatePresets();
}

function referenceContext() {
  const context = history.state?.easyerpReference;
  return context?.hash === location.hash && context.origin?.state?.mode === state.mode
    ? context
    : null;
}

function captureReferenceOrigin() {
  const href = new URL(location.href);
  const query = new URLSearchParams(href.hash.split('?')[1] || '');
  const source = document.querySelector('#content .table-edit-panel')?.dataset.editSource;
  if (meta?.objects.some((o) => o.schema + '.' + o.name === source))
    query.set('object', source);
  href.hash = '#/' + route + '?' + query;
  return {
    href: href.pathname + href.search + href.hash,
    state: { ...state },
    path: currentNavigationPath().map(({ label, business }) => ({ label, business })),
    scroll: window.scrollY,
  };
}

async function followReference(object) {
  const hash = referenceDestination(object);
  if (!hash) return;
  const origin = referenceContext()?.origin || captureReferenceOrigin();
  history.replaceState({ ...history.state, easyerpView: { ...state } }, '', location.href);
  closeDrawer();
  state.offset = 0;
  state.scope = '';
  state.status = '';
  state.search = '';
  state.person = '';
  state.subject = '';
  history.pushState({ easyerpReference: { hash, origin }, easyerpView: { ...state } }, '', hash);
  exploreObject = object;
  await render();
}

function restoreNavigationState() {
  const saved = history.state?.easyerpView;
  if (!saved) return;
  if (state.mode !== saved.mode) meta = null;
  Object.assign(state, saved);
}

document.addEventListener('click', async (event) => {
  const link = event.target.closest('[data-reference],[data-reference-return]');
  if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  if (link.hasAttribute('data-reference-return')) {
    const origin = referenceContext()?.origin;
    if (!origin) return;
    closeDrawer();
    history.pushState({ easyerpView: origin.state }, '', origin.href);
    restoreNavigationState();
    exploreObject = new URLSearchParams(location.hash.split('?')[1] || '').get('object') || '';
    await render();
    window.scrollTo(0, origin.scroll);
  } else await followReference(link.dataset.reference);
});

function move(page, object = '', extra = {}) {
  exploreObject = object;
  state.offset = 0;
  if (!Object.hasOwn(extra, 'dashboard')) state.status = '';
  const department = page === 'calculations' ? '' : extra.department ?? departmentForRoute[page] ?? state.department;
  const query = new URLSearchParams({ department });
  if (object) query.set('object', object);
  if (state.scope) query.set('scope', state.scope);
  const view =
    extra.view ??
    (page === route ? new URLSearchParams(location.hash.split('?')[1] || '').get('view') : '');
  if (view && view !== 'items') query.set('view', view);
  if (extra.dashboard) query.set('dashboard', '1');
  const hash = '/' + page + '?' + query;
  if (location.hash === '#' + hash) render();
  else location.hash = hash;
}

function navigationHash(page, object = '', view = '', department = state.department) {
  const query = new URLSearchParams({ department: page === 'calculations' ? '' : departmentForRoute[page] || department });
  if (object) query.set('object', object);
  if (view && view !== 'items') query.set('view', view);
  return '#/' + page + '?' + query;
}
function navigationTree() {
  const menu = window.easyerpWorkspace.navigation();
  const children = navs
    .filter(([key]) => [...workspacePages, 'plans', 'audit'].includes(key))
    .map(([page, label]) => {
      const node = { key: page, page, label, department: page === 'audit' ? '' : state.department, href: navigationHash(page, '', '', page === 'audit' ? '' : state.department), children: [] };
      if (page === 'calculations') { node.department = ''; node.href = navigationHash(page, '', '', ''); return node; }
      node.children = menu.departments.map(([department, name]) => {
        const child = {
          key: page + ':' + department,
          page,
          department,
          label: name,
          href: navigationHash(page, '', '', department),
          children: [],
        };
        if (menu.tabs[page])
          child.children = menu.tabs[page].map(([view, label]) => ({
            key: child.key + ':' + view,
            page,
            department,
            view,
            label,
            href: navigationHash(page, '', view, department),
            children: [],
          }));
        return child;
      });
      return node;
    });
  return {
    key: 'workspace',
    label: '工作空间',
    page: 'blank',
    href: navigationHash('blank'),
    children,
  };
}
function navigationPath(tree, key, parents = []) {
  const path = [...parents, tree];
  if (tree.key === key) return path;
  for (const child of tree.children || []) {
    const found = navigationPath(child, key, path);
    if (found) return found;
  }
  return null;
}
function referenceSourceHint(key, objects = meta?.objects || [], id = '') {
  const tree = navigationTree();
  let path;
  if (key === 'workspace.plan') path = [{ label: '历史来源' }, { label: '历史计划' }];
  else {
    const obj = objects.find((o) => (o.key || o.schema + '.' + o.name) === key);
    if (!obj) return '';
    const parent = objects.find((o) => o.children?.object === key);
    const owner = parent || obj;
    const area = ['archive', 'audit', 'workflow', 'plans', 'delivery'].includes(owner.area) ? owner.area : 'data';
    path = navigationPath(tree, area + ':' + owner.schema + '')?.slice(1) || [];
    path.push({ label: owner.label || owner.name });
    if (parent) path.push({ label: obj.label || obj.name });
  }
  if (!path?.length) return '';
  return `<small class="reference-source" ${id ? `id="${esc(id)}"` : ''} data-reference-source="${esc(key)}" data-ui-label><span>来源位置</span>：${path.map((node) => `<span>${esc(node.label)}</span>`).join(' / ')}</small>`;
}
function currentNavigationPath() {
  const tree = navigationTree(),
    menu = window.easyerpWorkspace.navigation();
  if (route === 'mapping' && !state.dashboard) return [tree, { key: 'mapping', label: '矩阵关系图', page: 'mapping' }];
  if (state.dashboard) return [tree, { key: 'overview', label: '仪表盘', page: 'overview' }];
  if (route === 'blank') return [tree];
  if (route === 'calculations') return navigationPath(tree, 'calculations') || [tree];
  const query = new URLSearchParams(location.hash.split('?')[1] || '');
  const target = query.has('reference') && meta?.objects.find((o) => o.schema + '.' + o.name === query.get('object'));
  if (target) {
    const path = navigationPath(tree, activeWorkspacePage() + ':' + target.schema + '') || [tree];
    return [...path, { label: target.label || target.name, page: route, object: query.get('object') }];
  }
  let view = menu.tabs[route]?.length
    ? new URLSearchParams(location.hash.split('?')[1] || '').get('view') || 'items'
    : '';
  if (menu.tabs[route]?.length && !menu.tabs[route].some(([key]) => key === view)) view = 'items';
  if (route === 'workflow')
    view =
      state.department === 'production' && (state.scope === 'pending' || view === 'production')
        ? 'production'
        : 'items';
  const page = activeWorkspacePage(),
    key =
      page +
      (state.department ? ':' + state.department : '') +
      (view && (state.department || page === 'audit') ? ':' + view : '');
  const path = navigationPath(tree, key) || [tree];
  const source = document.querySelector('#content .table-edit-panel')?.dataset.editSource;
  const object = meta?.objects.find((o) => o.schema + '.' + o.name === source);
  if (object) {
    const label = object.label || object.name;
    if (path.at(-1).label !== label)
      path.push({
        key: 'object:' + source,
        page: route,
        view,
        object: source,
        label,
        href: navigationHash(route, source, view),
      });
  }
  return path;
}
function breadcrumbItems(path, header = false) {
  return path
    .map((node, index) => {
      const last = index === path.length - 1,
        label = esc(node.label),
        ignore = node.business ? 'data-i18n-ignore' : '';
      const content = last
        ? `<span ${header ? 'id="crumb"' : ''} class="breadcrumb-current" aria-current="page" ${ignore} title="${label}">${label}</span>`
        : node.detailIndex !== undefined
          ? `<button type="button" data-breadcrumb-detail="${node.detailIndex}" ${ignore} title="${label}">${label}</button>`
          : `<a href="${esc(node.href)}" data-breadcrumb-page="${esc(node.page)}" data-breadcrumb-object="${esc(node.object || '')}" data-breadcrumb-view="${esc(node.view || '')}" data-breadcrumb-department="${esc(node.department ?? state.department)}" title="${label}">${label}</a>`;
      return `<li>${index ? '<span class="breadcrumb-separator" aria-hidden="true">/</span>' : ''}${content}</li>`;
    })
    .join('');
}
function renderBreadcrumbs() {
  const path = [
    ...currentNavigationPath(),
    ...drawerTrail.map((item, index) => ({
      label: item.label,
      business: true,
      detailIndex: index,
    })),
  ];
  if (drawerState && drawerTab !== 'basic')
    path.push({
      label: { related: '关联明细', progress: '业务进展', files: '文件与依据' }[drawerTab],
      business: false,
    });
  const origin = referenceContext()?.origin;
  const source = origin
    ? `<li class="breadcrumb-origin"><a class="breadcrumb-return" href="${esc(origin.href)}" data-reference-return>${origin.path.map((node, index) => `${index ? '<span class="breadcrumb-separator" aria-hidden="true">/</span>' : ''}<span ${node.business ? 'data-i18n-ignore' : 'data-ui-label'}>${esc(node.label)}</span>`).join('')}</a></li><li class="breadcrumb-jump" aria-hidden="true">→</li>`
    : '';
  $('#breadcrumb-list').innerHTML = source + breadcrumbItems(path, true);
  const drawer = document.querySelector('[data-drawer-breadcrumbs]');
  if (drawer) drawer.innerHTML = source + breadcrumbItems(path);
}
document.addEventListener('click', (event) => {
  const ancestor = event.target.closest('[data-breadcrumb-page],[data-breadcrumb-detail]');
  if (
    !ancestor ||
    event.defaultPrevented ||
    event.button !== 0 ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  event.preventDefault();
  if (ancestor.hasAttribute('data-breadcrumb-detail')) {
    const index = Number(ancestor.dataset.breadcrumbDetail),
      item = drawerTrail[index];
    if (item) openDetail(item.kind, item.key, item.object, drawerTrail.slice(0, index));
    return;
  }
  if (!$('#drawer').hidden) closeDrawer();
  state.scope = '';
  move(ancestor.dataset.breadcrumbPage, ancestor.dataset.breadcrumbObject, {
    view: ancestor.dataset.breadcrumbView,
    department: ancestor.dataset.breadcrumbDepartment,
  });
});

function monetary(rows, key, completeKey = null) {
  if (!rows?.length) return { value: 'N/A', unknown: true };
  if (completeKey && rows.some((r) => r[completeKey] !== r['记录数']))
    return { value: '待核定', unknown: true };
  return {
    value: rows
      .map((r) => `${decimal(r[key])}<span class="unit">${esc(r['币种'] || '币种N/A')}</span>`)
      .join('<br>'),
    unknown: rows.every((r) => r[key] == null),
    multi: rows.length > 1,
  };
}

function metric(label, value, action) {
  const v = typeof value === 'object' ? value : { value: String(value), unknown: false };
  return `<button class="metric" ${action}><span class="label">${label}<span class="chevron">↗</span></span><div class="value ${v.unknown ? 'unknown' : ''} ${v.multi ? 'multi' : ''}">${v.value}</div></button>`;
}
const recordAction = (obj) =>
  `data-page="${obj.split('.')[0] === 'finance' ? 'finance' : obj.split('.')[0] === 'sales' ? 'sales' : 'inventory'}" data-object="${obj}" data-scope="confirmed"`;

function trend(rows) {
  const valid = rows.filter(
    (r) => r['收入已填数'] === r['记录数'] && r['成本已填数'] === r['记录数']
  );
  if (!valid.length)
    return empty('尚无完整核定的收入成本记录', '按确认月份显示；缺失的成本不会按零绘图。', true);
  if (new Set(valid.map((r) => r['币种'])).size > 1)
    return table(valid, [
      ['所属月份', '确认月份'],
      ['币种', '币种'],
      ['收入', '已确认收入'],
      ['成本', '已确认成本'],
    ]);
  const max = Math.max(
    ...valid.flatMap((r) => [Math.abs(Number(r['收入'])), Math.abs(Number(r['成本']))]),
    1
  );
  if (valid.some((r) => Number(r['收入']) < 0 || Number(r['成本']) < 0))
    return table(valid, [
      ['所属月份', '确认月份'],
      ['币种', '币种'],
      ['收入', '收入'],
      ['成本', '成本'],
    ]);
  const width = 600,
    step = (width - 70) / valid.length;
  return `<div class="panel-body"><svg class="chart" viewBox="0 0 600 205" role="img" aria-label="已核定收入与成本趋势">${[0, 1, 2, 3].map((i) => `<line x1="25" x2="585" y1="${20 + i * 45}" y2="${20 + i * 45}"/>`).join('')}${valid
    .map((r, i) => {
      const x = 45 + i * step,
        ih = (Number(r['收入']) / max) * 145,
        ch = (Number(r['成本']) / max) * 145;
      return `<g><rect class="income" x="${x}" y="${165 - ih}" width="${Math.min(step * 0.23, 30)}" height="${ih}" rx="3"><title>${esc(r['所属月份'])} 收入 ${decimal(r['收入'])} ${esc(r['币种'])}</title></rect><rect class="cost" x="${x + Math.min(step * 0.23, 30) + 5}" y="${165 - ch}" width="${Math.min(step * 0.23, 30)}" height="${ch}" rx="3"><title>成本 ${decimal(r['成本'])}</title></rect><text x="${x}" y="190">${esc(r['所属月份'].slice(0, 7))}</text></g>`;
    })
    .join('')}</svg></div>`;
}

async function overview() {
  const [d, t] = await Promise.all([api('overview'), api('tasks')]);
  const pending = d.pending_orders[0],
    work = d.pending_work[0];
  const cash = (direction) =>
    monetary(
      d.cash.filter((r) => r['收支方向'] === direction),
      '外部金额'
    );
  const count = (r, key) =>
    r['范围记录数'] ? { value: String(r[key]), unknown: false } : { value: 'N/A', unknown: true };
  let html = '<div class="metrics">';
  html += metric('订单商品实付', monetary(d.sales, '金额', '实付已填数'), 'data-page="sales"');
  html += metric(
    '已确认收入',
    monetary(d.recognition, '已确认收入', '收入已填数'),
    recordAction('finance.收入成本确认表')
  );
  html += metric(
    '已确认结转成本',
    monetary(d.recognition, '已确认结转成本', '成本已填数'),
    recordAction('finance.收入成本确认表')
  );
  html += metric(
    '毛利',
    { value: '待核定', unknown: true },
    recordAction('finance.收入成本确认表')
  );
  html += metric('资金收入', cash('收入'), 'data-page="finance" data-scope="cash-income"');
  html += metric('资金支出', cash('支出'), 'data-page="finance" data-scope="cash-expense"');
  html += metric(
    '待发货订单行',
    count(pending, '待发货订单行'),
    'data-page="sales" data-scope="pending"'
  );
  html += metric(
    '待完成生产执行',
    count(work, '待完成工单'),
    'data-page="workflow" data-scope="pending"'
  );
  html += '</div>';
  const dist = d.fulfillment.length
    ? `<div class="distribution">${d.fulfillment.map((r) => `<div class="dist-row"><span>${esc(r['履约进展'])}</span><div class="dist-track"><div class="dist-bar" style="width:${(r['数量'] / Math.max(...d.fulfillment.map((x) => x['数量']), 1)) * 100}%"></div></div><strong>${r['数量']}</strong></div>`).join('')}</div>`
    : empty('尚无订单履约记录', '接单后，可查看履约进展与逐次发货。');

  html += `<div class="columns">${panel('收入与结转成本', trend(d.trend), '', '<div class="chart-legend"><span>确认收入</span><span>结转成本</span></div>')}${panel('订单履约分布', dist, '', more('查看订单', 'sales'))}</div>`;
  const todos = t.rows.slice(0, 5);
  const taskbody = todos.length
    ? `<div class="panel-body">${todos.map((r) => `<div class="list-row"><span class="dot-icon">${r['事项'].includes('资金') ? '¥' : '↗'}</span><div class="row-main"><button data-task="${esc(JSON.stringify(r))}">${esc(r['事项'])} · ${esc(r['内容'] || r['编号'])}</button><div class="sub">${r['负责人'] ? esc(r['负责人']) : '负责人N/A'}${r['期限'] ? ' · ' + esc(r['期限']) : ' · 期限N/A'}</div></div>${badge(r['状态'])}</div>`).join('')}</div>`
    : empty('当前没有已登记待办', '这里只根据业务记录的状态和期限列出事项。');

  const balances = d.balances.length
    ? `<div class="panel-body">${d.balances.map((r) => `<div class="list-row"><div><button data-record="finance.账户期间余额表" data-id="${esc(r['余额记录ID'])}">${esc(r['账户名'])}</button><div class="sub">${esc(r['期间结束'])} · 已核定余额</div></div><div class="amount">${decimal(r['原始余额'])} <small>${esc(r['币种'])}</small></div></div>`).join('')}</div>`
    : empty('尚无已核定账户余额', '先登记账户期间余额并完成账户核对。');

  html += `<div class="columns">${panel('待处理工作', taskbody, '', more('查看全部', 'tasks'))}${panel('账户余额', balances, '', more('查看账户', 'finance', 'finance.账户核对表'))}</div>`;
  const act = d.activity.length
    ? `<div class="panel-body">${d.activity.map((r) => `<div class="list-row"><div><button data-record="${esc(r['来源'])}" data-id="${esc(r['编号'])}">${esc(r['类型'])} · ${esc(r['编号'])}</button><div class="sub">${dateText(r['时间'])}</div></div><span class="muted">↗</span></div>`).join('')}</div>`
    : empty('还没有近期业务动态', '订单、到货和发货会按真实事件时间排列。');

  html += `<div class="columns">${panel(
    '库存期间收发',
    table(d.inventory, [
      ['物品名称', '物品'],
      ['仓库', '仓库'],
      ['批次', '批次'],
      ['期间入库', '期间入库'],
      ['期间出库', '期间出库'],
      ['单位名称', '单位'],
    ]),
    '',
    more('查看收发', 'inventory', 'production.库存变动表')
  )}${panel('近期业务动态', act)}</div>`;
  if (d.issues.length)
    html += panel(
      '待核对问题',
      table(d.issues, [
        ['规则', '核对项目'],
        ['记录ID', '记录编号'],
        ['说明', '需要核实的内容'],
      ])
    );
  return { html, time: d.queried_at };
}

function pagination(total) {
  return `<div class="pagination"><span>共 ${total} 条 · ${state.offset + 1}–${Math.min(state.offset + state.limit, total)} 条</span><button data-paging="-1" ${state.offset === 0 ? 'disabled' : ''}>上一页</button><button data-paging="1" ${state.offset + state.limit >= total ? 'disabled' : ''}>下一页</button></div>`;
}

const orderCols = [
  [
    '产品名称',
    '产品 / 版本',
    (v, r) =>
      `${v ? esc(v) : esc(r['原商品信息'])}<span class="secondary">${esc(r['版本名称'] || '版本待映射')} · ${esc(r['平台订单号'] || r['订单ID'])}</span>`,
  ],
  ['客户名称', '客户'],
  ['创建时间', '订单创建时间'],
  ['商品实付', '商品实付', (v, r) => decimal(v) + ' ' + esc(r['币种'])],
  ['数量', '订单数量', (v, r) => quantity(v) + ' ' + esc(r['单位名称'])],
  ['已登记发货数量', '已登记发货'],
  ['履约进展', '履约进展'],
];

const workCols = [
  [
    '产品名称',
    '产品 / 版本',
    (v, r) => esc(v) + `<span class="secondary">${esc(r['版本名称'])} · ${esc(r['工单号'])}</span>`,
  ],
  ['负责人', '负责人'],
  ['计划开始日期', '计划开始'],
  ['计划数量', '计划数量', (v, r) => quantity(v) + ' ' + esc(r['单位名称'])],
  ['截至合格数量', '已登记合格'],
  ['截至报废数量', '已登记报废'],
  ['状态', '当前状态'],
];

const fundCols = [
  ['账户名', '资金账户'],
  ['发生时间', '资金发生时间'],
  ['交易摘要', '摘要'],
  ['收支方向', '收支'],
  ['金额', '金额', (v, r) => decimal(v) + ' ' + esc(r['币种'])],
  ['已核定分摊金额', '已核定分摊'],
  ['分摊差额', '待分摊差额'],
  ['已确认内部划转', '内部划转'],
];

async function list(kind, objectControls) {
  const d = await api('list', { kind });
  lastList = { kind, object: '' };
  const total = d.total[0].count;
  let toolbar = '';
  if (kind === 'orders')
    toolbar = `<select id="status-filter" aria-label="履约状态"><option value="">全部履约状态</option>${['待履约', '部分发货', '已完成', '登记发货已覆盖', '单位待核', '组合／版本待核', '已关闭／取消'].map((v) => `<option value="${esc(v)}" ${state.status === v ? 'selected' : ''}>${v}</option>`).join('')}</select>`;

  if (kind === 'workorders')
    toolbar = `<select id="person-filter" aria-label="负责人"><option value="">全部负责人</option>${meta.people.map((r) => `<option value="${esc(r['人员ID'])}" ${state.person === r['人员ID'] ? 'selected' : ''}>${esc(r['姓名'])}</option>`).join('')}</select>`;

  if (kind === 'funds')
    toolbar = `<select id="subject-filter" aria-label="资金所属主体"><option value="">全部资金主体</option>${meta.subjects.map((r) => `<option value="${esc(r['主体ID'])}" ${state.subject === r['主体ID'] ? 'selected' : ''}>${esc(r['公司名称'])}</option>`).join('')}</select>`;

  const source = {
    orders: 'sales.销售订单行表',
    workorders: 'production.生产工单表',
    funds: 'finance.资金流水表',
  }[kind];
  return {
    html: `<div class="panel table-edit-panel" data-edit-source="${esc(source)}"><div class="table-toolbar">${objectControls}${toolbar}${state.scope ? '<button class="panel-link" data-clear-scope>查看常规列表 ↗</button>' : ''}<span class="count">${total} 条记录</span>${editToggle(source)}</div>${table(d.rows, kind === 'orders' ? orderCols : kind === 'workorders' ? workCols : fundCols, { editObject: source, detail: kind === 'orders' ? 'order' : kind === 'workorders' ? 'workorder' : 'fund', id: kind === 'orders' ? '订单ID' : kind === 'workorders' ? '工单号' : '资金记录ID' })}${total ? pagination(total) : ''}</div>`,
    time: d.queried_at,
  };
}
async function tasks() {
  const d = await api('tasks');
  const editRecord = (row) =>
    editOrigin(row['来源']) && row['编号'] != null
      ? { object: row['来源'], id: row['编号'] }
      : null;
  return {
    html: `<div class="panel table-edit-panel" data-edit-source="tasks"><div class="table-toolbar"><h2>待处理事项</h2><span class="count">${d.rows.length} 条</span>${editToggle('', true)}</div>${table(
      d.rows,
      [
        ['事项', '业务类型'],
        ['内容', '事项内容'],
        ['负责人', '负责人'],
        ['期限', '要求完成日期'],
        ['状态', '当前状态'],
        [
          '编号',
          '入口',
          (v, r) =>
            `<button class="table-button" data-task="${esc(JSON.stringify(r))}">查看详情 ↗</button>`,
        ],
      ],
      { editRecord }
    )}</div>`,
    time: d.queried_at,
  };
}
async function searchResults() {
  const d = await api('search');
  return {
    html: panel(
      '业务搜索结果',
      table(d.rows, [
        ['业务', '业务类型'],
        ['名称', '名称'],
        ['编号', '主录编号', (v, r) => link(v, r['来源'])],
      ]),
      `${d.rows.length} 条匹配记录`
    ),
    time: d.queried_at,
  };
}
function deptObjects() {
  const schema = departmentForRoute[route] || state.department;
  const area = route === 'archive' ? 'archive' : route === 'audit' ? 'audit' : route === 'delivery' ? 'delivery' : 'data';
  const objects = meta.objects.filter(
    (o) => o.kind === 'r' && o.standalone && !o.retired && o.schema === schema && o.area === area
  );
  if (route === 'audit') objects.push({ schema: 'workspace', name: 'report', label: '审计记录', kind: 'r' });
  return objects;
}

function objectPreference(key) {
  try {
    return (
      localStorage.getItem('easyerp.object.' + route + '.' + state.department + '.' + key) || ''
    );
  } catch {
    return '';
  }
}
function rememberObject(obj) {
  try {
    localStorage.setItem('easyerp.object.' + route + '.' + state.department + '.mode', obj.kind);
    localStorage.setItem(
      'easyerp.object.' + route + '.' + state.department + '.' + obj.kind,
      obj.schema + '.' + obj.name
    );
  } catch {}
}
function chooseObject(objects) {
  const remembered = objectPreference('r');
  return (
    objects.find((o) => o.schema + '.' + o.name === remembered) ||
    objects.find(
      (o) =>
        o.schema + '.' + o.name === defaults[departmentForRoute[route] ? route : state.department]
    ) ||
    objects[0]
  );
}
function objectControls(all, current) {
  return window.easyerpObjectMenu.render(all, current, { flat: route === 'delivery' });
}
async function explorer() {
  const all = deptObjects();
  const query = new URLSearchParams(location.hash.split('?')[1] || '');
  const linked = query.has('reference') && meta.objects.find((o) => o.schema + '.' + o.name === exploreObject && o.schema === state.department);
  if (linked && !all.includes(linked)) all.push(linked);
  let current = all.find((o) => o.schema + '.' + o.name === exploreObject);
  // Dashboard scopes target the common business list even after browsing records.
  if (
    !current &&
    businessLists[route] &&
    ['pending', 'cash-income', 'cash-expense'].includes(state.scope)
  )
    current = all.find((o) => o.schema + '.' + o.name === defaults[route]);
  if (!current) current = chooseObject(all);
  if (!current) return { html: empty('当前模块暂无可用对象。') };
  exploreObject = current.schema + '.' + current.name;
  rememberObject(current);
  const controls = objectControls(all, current);
  const businessRoute = departmentForRoute[route] ? route : state.department;
  if (
    !linked &&
    (route === 'data' || departmentForRoute[route]) &&
    businessLists[businessRoute] &&
    exploreObject === defaults[businessRoute]
  )
    return list(businessLists[businessRoute], controls);
  const d = await api('explore', {
    object: exploreObject,
    date_filter: route === 'archive' ? '0' : '1',
  });
  lastList = { object: exploreObject, date_filter: route === 'archive' ? '0' : '1' };
  const total = d.total[0].count;
  const unifiedColumns = {
    'production.供应商档案表': ['供应商ID', '名称', '联系方式', '统一社会信用代码', '户名', '账户ID', '开户行'],
    'production.采购订单表': [
      '采购单ID',
      '供应商',
      '创建日期',
      '采购内容',
      '订单金额',
      '币种',
      '订单文件路径',
      '状态',
    ],
    'production.仓库档案表': ['仓库ID', '地点', '保管方ID', '主体ID', '启用状态', '地点标识'],
    'production.库存盘点表': [
      '盘点ID',
      '盘点日期',
      '物料版本ID',
      '产品版本ID',
      '库位ID',
      '账面数量',
      '实盘数量',
      '盘点差异',
      '单位ID',
    ],
  };
  const columns = unifiedColumns[exploreObject]?.map((key) => key === '供应商'
    ? [key, key, undefined, '供应商ID']
    : [key, key]);
  const supplierItems = exploreObject === 'production.供应商档案表'
    ? '<button type="button" class="button" data-supplier-items>供应的物品</button>'
    : '';
  return {
    html: `<div class="panel table-edit-panel" data-edit-source="${esc(exploreObject)}"><div class="table-toolbar">${controls}${supplierItems}<span class="count">${total} 条</span>${editToggle(exploreObject)}</div>${table(d.rows, columns, { object: exploreObject, editObject: exploreObject, hiddenColumns: supplierItems ? ['供应的物品'] : [] })}${total ? pagination(total) : ''}</div>`,
    time: d.queried_at,
  };
}

async function render() {
  const token = ++sequence;
  renderedNavigationHash = location.hash;
  route = location.hash.replace(/^#\//, '').split('?')[0] || 'blank';
  if (!navs.some((x) => x[0] === route) && route !== 'blank') route = 'blank';
  if (route === 'tasks') route = 'workflow';
  if (route === 'plans' && !new URLSearchParams(location.hash.split('?')[1] || '').has('reference')) {
    route = 'calculations';
    history.replaceState(null, '', location.pathname + location.search + '#/calculations');
  }
  window.easyerpMappingView?.destroy?.();
  window.easyerpCalculations?.close(true);
  readWorkspaceSelection();
  renderWorkspaceSelection();
  const blank = !state.dashboard && route !== 'mapping' && (route === 'blank' || (!state.department && !['audit', 'calculations'].includes(route)));
  document.body.classList.toggle('calculations-active', route === 'calculations' && !state.dashboard);
  document.body.classList.toggle('mapping-active', route === 'mapping' && !state.dashboard);
  $('#main').classList.toggle('is-blank', blank);
  $('#title').textContent = state.dashboard
    ? '仪表盘'
    : navs.find((x) => x[0] === activeWorkspacePage())?.[1] || '工作空间';
  $('#sidebar').classList.remove('open');
  sync();
  if (meta) updateAccess(meta);
  $('.page-heading').hidden = blank || (route === 'mapping' && !state.dashboard);
  $('.filters').hidden = blank || (route === 'mapping' && !state.dashboard);
  $('#demo-notice').hidden = blank || (route === 'mapping' && !state.dashboard) || state.mode !== 'demo';
  $('#export').disabled = true;
  $('#export').hidden = true;
  $('#import-open').hidden = state.dashboard;
  $('#entry-open').hidden = state.dashboard;
  lastList = null;
  window.easyerpTableTools?.clearQuery?.();
  $('#search').placeholder = '搜索编号、产品或客户';
  for (const id of ['start', 'end']) {
    $('#' + id).disabled = false;
    $('#' + id).hidden = false;
  }
  $('.date-filter').hidden = false;
  $('#date-presets').hidden = false;
  syncDatePresets();
  if (route === 'calculations' && !state.dashboard) {
    $('.date-filter').hidden = true; $('#date-presets').hidden = true;
    $('#import-open').hidden = true; $('#search').placeholder = window.ERPUI.t('搜索ID或备注');
  }
  $('#content').innerHTML = blank
    ? blankWorkspace()
    : '<div class="loading">正在读取业务数据…</div>';
  renderBreadcrumbs();
  if (blank) return;
  try {
    if (!meta) meta = await api('meta');
    updateAccess(meta);
    const query = new URLSearchParams(location.hash.split('?')[1] || '');
    const referenced = !state.dashboard && query.has('reference') && meta.objects.find(
      (o) => o.schema + '.' + o.name === exploreObject
    );
    if (referenced) {
      $('#export').hidden = false;
      $('#export').disabled = false;
      $('#entry-open').hidden = referenced.retired;
    }
    const result = route === 'mapping' && !state.dashboard
      ? await window.easyerpMappingView.render()
      : referenced
      ? await explorer()
      : state.dashboard
        ? state.search
          ? await searchResults()
          : await overview()
        : route === 'calculations'
          ? await window.easyerpCalculations.render()
        : [...workspacePages, 'plans', 'audit'].includes(route)
          ? await window.easyerpWorkspace.render(route)
          : await explorer();
    if (token !== sequence) return;
    $('#content').innerHTML = result.html;
    $('#connection').textContent = window.easyerpDatabaseSource.label;
    bindFilters();
    window.easyerpTableEdit?.mount();
    window.easyerpTableTools?.mount();
    window.easyerpRowDetails?.mount();
    window.easyerpWorkspace?.mounted();
    if (route === 'mapping' && !state.dashboard) window.easyerpMappingView?.mounted();
    renderBreadcrumbs();
  } catch (err) {
    if (token !== sequence) return;
    $('#content').innerHTML =
      `<div class="error-panel"><strong>暂时无法读取业务数据</strong><br>${esc(err.message)}<br><button class="button" data-retry>重新读取</button></div>`;
    $('#connection').textContent = '连接待检查';
    $('#access-level').textContent = '—';
  }
}
function bindFilters() {
  for (const [id, key] of [
    ['status-filter', 'status'],
    ['person-filter', 'person'],
    ['subject-filter', 'subject'],
    ['object-filter', 'object'],
  ]) {
    const el = $('#' + id);
    if (el)
      el.onchange = () => {
        if (key === 'object') {
          state.scope = '';
          move(route, el.value);
          return;
        }
        state[key] = el.value;
        state.offset = 0;
        render();
      };
  }
}

const detailSections = {
  order: {
    basic: 'sales.销售订单登记表',
    lines: ['订单商品明细', 'sales.销售订单行表'],
    shipments: ['逐次发货', 'production.发货记录表'],
    workorders: ['关联工单', 'production.工单订单对应表'],
    settlements: ['资金结算', 'finance.结算分摊表'],
    invoices: ['发票分摊', 'finance.发票登记表'],
    aftersales: ['售后反馈', 'sales.售后事件表'],
    demands: ['客户需求', 'sales.客户需求表'],
  },
  workorder: {
    basic: 'production.生产工单表',
    orders: ['订单对应', 'production.工单订单对应表'],
    bom: ['固定发布 BOM', 'rd.BOM明细表'],
    materials: ['实际领退料', 'production.生产领退料表'],
    completion: ['逐次完工', 'production.完工记录表'],
    scrap: ['报废事件', 'production.报废记录表'],
    files: ['发布文件', 'rd.项目文件登记表'],
  },
  fund: {
    basic: 'finance.资金流水表',
    purposes: ['用途核定', 'finance.资金用途核定表'],
    allocations: ['结算分摊', 'finance.结算分摊表'],
    sources: ['原始流水来源', 'finance.流水来源明细表'],
    transfers: ['内部划转对应', 'finance.内部划转对应表'],
    duplicates: ['重复记录核定', 'finance.重复记录对应表'],
    entries: ['已过账分录', 'finance.会计分录表'],
  },
};

const relationColumns = {
  lines: orderCols,
  shipments: [
    ['发货时间', '发货日期'],
    ['数量', '数量'],
    ['单位ID', '单位'],
    ['物流单号', '物流单号'],
    ['检验ID', '检验记录'],
    ['发货事件ID', '发货记录'],
  ],

  workorders: [
    ['工单号', '工单'],
    ['对应数量', '对应数量'],
    ['单位ID', '单位'],
  ],
  orders: [
    ['销售订单行ID', '订单行'],
    ['对应数量', '对应数量'],
    ['单位ID', '单位'],
  ],

  settlements: [
    ['发生时间', '资金发生时间'],
    ['分摊金额', '结算金额'],
    ['币种', '币种'],
    ['方向', '方向'],
    ['用途状态', '核定状态'],
    ['资金记录ID', '资金来源'],
  ],

  invoices: [
    ['日期', '开票日期'],
    ['发票号码', '发票号码'],
    ['分摊金额', '分摊金额'],
    ['分摊税额', '分摊税额'],
    ['币种', '币种'],
    ['票据ID', '原票记录'],
  ],

  aftersales: [
    ['发生时间', '发生时间'],
    ['类型', '类型'],
    ['原因', '客户描述'],
    ['处理状态', '处理状态'],
  ],
  demands: [
    ['日期', '日期'],
    ['客户原话', '客户原话'],
    ['处理状态', '处理状态'],
  ],

  materials: [
    ['日期', '日期'],
    ['物料名称', '物料'],
    ['类型', '领退料'],
    ['数量', '实际数量'],
    ['单位名称', '单位'],
    ['批次', '批次'],
  ],

  hours: [
    ['工序', '工序'],
    ['开始时间', '开始时间'],
    ['结束时间', '结束时间'],
    ['有效工时', '有效工时'],
    ['人员ID', '人员'],
  ],

  completion: [
    ['日期', '完工日期'],
    ['批次', '批次'],
    ['合格数量', '合格数量'],
    ['不良数量', '不良数量'],
    ['单位ID', '单位'],
  ],

  scrap: [
    ['日期', '日期'],
    ['批次', '批次'],
    ['数量', '报废数量'],
    ['单位ID', '单位'],
  ],

  bom: [
    ['物料名称', '物料'],
    ['单件用量', '单件用量'],
    ['单位名称', '单位'],
    ['位号', '位号'],
    ['替代适用条件', '替代条件'],
  ],

  files: [
    ['文件名', '文件名'],
    ['正式版本', '版本'],
    ['相对路径', '相对路径'],
    ['文件ID', '文件记录'],
  ],

  purposes: [
    ['用途', '资金用途'],
    ['状态', '核定状态'],
    ['核定金额', '核定金额'],
    ['所属月份', '归属月份'],
    ['依据', '依据'],
    ['用途核定ID', '用途记录'],
  ],

  allocations: [
    ['分摊金额', '分摊金额'],
    ['方向', '方向'],
    ['费用类型', '费用类型'],
    ['销售订单行ID', '销售订单行'],
    ['采购订单行ID', '采购订单行'],
    ['工单号', '工单'],
  ],

  sources: [
    ['文件路径', '原始文件路径'],
    ['来源行号', '文件行号'],
    ['文件校验值', '文件校验值'],
    ['流水来源ID', '来源记录'],
  ],
};

function fieldGrid(row, object) {
  return `<dl class="field-grid">${Object.entries(row)
    .filter(([key]) => !hiddenIdentityField(key))
    .map(
      ([key, value]) =>
        `<div class="field"><dt>${esc(key)}</dt><dd>${display(value, key, row, object)}</dd></div>`
    )
    .join('')}</dl>`;
}

function detailTitle(base, key, object) {
  const definition = meta?.objects.find((o) => o.schema + '.' + o.name === object);
  return (
    base['客户名称'] ||
    base['公司名称'] ||
    base['产品名称'] ||
    base['账户名'] ||
    base['名称'] ||
    base['项目名称'] ||
    base['原始器件描述'] ||
    base['平台订单号'] ||
    base[definition?.pk] ||
    key
  );
}

function renderDrawer() {
  const ds = drawerState;
  if (!ds) return;
  const d = ds.data,
    base = d.basic?.[0];
  if (!base) {
    $('#drawer-content').innerHTML =
      `<div class="drawer-header"><button class="icon-button drawer-close" data-close aria-label="关闭">×</button><h2>未找到对应记录</h2></div>${empty('N/A')}`;
    return;
  }
  const cfg = ds.kind === 'record' ? { basic: ds.object } : detailSections[ds.kind];
  const object = cfg.basic;
  const title = detailTitle(base, ds.key, object);
  let body = '';
  if (drawerTab === 'basic') {
    body = panel('基本信息', fieldGrid(base, object), object);
    if (ds.kind === 'order')
      body += panel('商品概览', table(d.lines, orderCols, { object: 'sales.销售订单行表' }));
  }
  if (drawerTab === 'related') {
    if (ds.kind === 'record') {
      body =
        d._relations
          .filter((r) => d[r.key]?.length)
          .map((r) =>
            panel(r.object.split('.')[1], table(d[r.key], null, { object: r.object }), r.object)
          )
          .join('') || empty('尚无关联明细');
    } else
      body = Object.entries(cfg)
        .filter(([k]) => k !== 'basic')
        .map(([key, [label, source]]) =>
          panel(label, table(d[key], relationColumns[key] || null, { object: source }), source)
        )
        .join('');
  }
  if (drawerTab === 'progress') {
    const events = [];
    for (const [key, rows] of Object.entries(d)) {
      if (key.startsWith('_') || !Array.isArray(rows) || key === 'basic') continue;
      for (const row of rows) {
        const time = Object.entries(row).find(([k, v]) => /时间$|日期$/.test(k) && v);
        if (time)
          events.push({
            date: time[1],
            label: cfg[key]?.[0] || key,
            row,
            source: cfg[key]?.[1] || ds.object,
          });
      }
    }
    events.sort((a, b) => new Date(a.date) - new Date(b.date));
    body = panel(
      '已登记业务进展',
      events.length
        ? `<div class="timeline">${events.map((e) => `<div class="timeline-item">${esc(e.label)}<time>${dateText(e.date)}</time>${badge(e.row['状态'] || e.row['处理状态'] || '已登记')}<span class="secondary">来源 ${esc(e.source)}</span></div>`).join('')}</div>`
        : empty('尚无带日期的关联事件')
    );
  }
  if (drawerTab === 'files') {
    const files = [];
    for (const [section, rows] of Object.entries(d)) {
      if (section.startsWith('_') || !Array.isArray(rows)) continue;
      for (const row of rows)
        for (const [key, value] of Object.entries(row))
          if (
            value &&
            !hiddenIdentityField(key) &&
            /路径|依据|证据|校验值|文件名|说明|原话/.test(key)
          )
            files.push({ key, value });
    }
    body = panel(
      '文件与依据',
      files.length
        ? files
            .map(
              (f) =>
                `<div class="file-card"><strong>${esc(f.key)}</strong><p>${esc(f.value)}</p><button class="text-button" data-copy="${esc(f.value)}">复制内容</button></div>`
            )
            .join('')
        : empty('N/A文件或依据')
    );
  }
  $('#drawer-content').innerHTML =
    `<div class="drawer-header"><button class="icon-button drawer-close" data-close aria-label="关闭详情">×</button><nav class="breadcrumb breadcrumb-drawer" aria-label="详情分级导航"><ol data-drawer-breadcrumbs></ol></nav><span class="standard-tag">${ds.kind === 'record' ? '主录追溯' : { order: '订单详情', workorder: '工单详情', fund: '资金结算详情' }[ds.kind]}</span><h2>${esc(title)}</h2><p>${esc(ds.key)}<br>来源 ${esc(object)} · ${state.mode === 'demo' ? '演示数据' : '正式数据'}</p><div class="drawer-tabs" role="tablist">${[
      ['basic', '基本信息'],
      ['related', '关联明细'],
      ['progress', '业务进展'],
      ['files', '文件与依据'],
    ]
      .map(
        ([key, label]) =>
          `<button role="tab" aria-selected="${drawerTab === key}" class="${drawerTab === key ? 'active' : ''}" data-tab="${key}">${label}</button>`
      )
      .join('')}</div></div><div class="drawer-body">${body}</div>`;
  window.easyerpManual?.decorateDrawer(object, base);
  renderBreadcrumbs();
}

async function openDetail(kind, key, object = '', history = null) {
  const token = ++detailSequence;
  if (object === 'sales.销售订单登记表') kind = 'order';
  if (object === 'production.生产工单表') kind = 'workorder';
  if (object === 'finance.资金流水表') kind = 'fund';
  object = object || detailSections[kind]?.basic || '';
  let parents = history ?? (drawerState && !$('#drawer').hidden ? drawerTrail : []);
  const previous = parents.findIndex(
    (item) => item.kind === kind && item.key === key && item.object === object
  );
  if (previous >= 0) parents = parents.slice(0, previous);
  $('#drawer').hidden = false;
  $('#drawer-backdrop').hidden = false;
  document.body.style.overflow = 'hidden';
  $('.shell').inert = true;
  $('#drawer-content').innerHTML = '<div class="loading">正在追溯关联记录…</div>';
  drawerTab = 'basic';
  try {
    const data =
      kind === 'record'
        ? await api('record', { object, id: key })
        : await api('detail', { kind, id: key });
    if (token !== detailSequence) return;
    const base = data.basic?.[0] || {},
      label = detailTitle(base, key, object);
    drawerState = { kind, key, object, data };
    drawerTrail = [...parents, { kind, key, object, label }];
    renderDrawer();
    $('#drawer').scrollTop = 0;
    $('#drawer .drawer-close')?.focus();
  } catch (err) {
    $('#drawer-content').innerHTML =
      `<div class="drawer-header"><button class="icon-button drawer-close" data-close>×</button><h2>暂时无法查看详情</h2><p>${esc(err.message)}</p></div>`;
  }
}

function closeDrawer() {
  detailSequence++;
  $('.shell').inert = false;
  drawerState = null;
  drawerTrail = [];
  $('#drawer').hidden = true;
  $('#drawer-backdrop').hidden = true;
  document.body.style.overflow = '';
  renderBreadcrumbs();
  $('#refresh').focus();
}

async function exportData() {
  if (!lastList) return;
  try {
    const r = await window.easyerpFetch('/api/export?' + params(window.easyerpTableTools?.augmentParams('export', lastList) || lastList));
    if (!r.ok) {
      const d = await r.json();
      throw new Error(d.error);
    }
    const blob = await r.blob(),
      a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'easyerp-' + (lastList.kind || 'records') + '.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    const total = Number(r.headers.get('X-Total-Rows')),
      n = Number(r.headers.get('X-Exported-Rows'));
    toast(
      n < total
        ? `已导出前 ${n} 条，当前共有 ${total} 条；请缩小筛选范围。`
        : `已导出 ${n} 条记录；N/A值使用 \\N 标记。`
    );
  } catch (err) {
    toast(err.message);
  }
}

document.addEventListener('click', async (e) => {
  const el = e.target.closest('button');
  if (!el) return;
  if (el.hasAttribute('data-page')) {
    state.scope = el.dataset.scope || '';
    move(el.dataset.page, el.dataset.object || '');
  } else if (el.dataset.detail) openDetail(el.dataset.detail, el.dataset.id);
  else if (el.dataset.record) openDetail('record', el.dataset.id, el.dataset.record);
  else if (el.dataset.task) {
    const r = JSON.parse(el.dataset.task);
    if (r['来源'] === 'workspace') {
      await window.easyerpWorkspace.openItem(r['编号']);
      return;
    }
    openDetail(r['入口'] === 'record' ? 'record' : r['入口'], r['入口ID'], r['来源']);
  } else if (el.dataset.tab) {
    drawerTab = el.dataset.tab;
    renderDrawer();
  } else if (el.hasAttribute('data-close')) closeDrawer();
  else if (el.dataset.copy) {
    try {
      await navigator.clipboard.writeText(el.dataset.copy);
      toast('已复制');
    } catch {
      toast('请选中文字后复制');
    }
  } else if (el.dataset.paging) {
    state.offset = Math.max(0, state.offset + Number(el.dataset.paging) * state.limit);
    render();
  } else if (el.hasAttribute('data-clear-scope')) {
    state.scope = '';
    move(route, exploreObject);
  } else if (el.hasAttribute('data-retry')) render();
});

function applyQuery(start = state.start, end = state.end) {
  if (!start || !end || start > end) return toast('请选择有效的起止日期');
  state.start = start;
  state.end = end;
  state.search = $('#search').value;
  state.offset = 0;
  dateRangePopover.close();
  render();
}
$('#search').onkeydown = (event) => {
  if (event.key === 'Enter' && !event.isComposing) {
    event.preventDefault();
    applyQuery();
  }
};
$('#search').addEventListener('input', () => {
  if (!$('#search').value && state.search) applyQuery();
});
$('#refresh').onclick = () => render();
$('#export').onclick = exportData;
$('#drawer-backdrop').onclick = closeDrawer;
document.addEventListener('keydown', (e) => {
  if (
    e.key === 'Escape' &&
    !document.querySelector('#manual-entry')?.open &&
    !document.querySelector('#import-interface')?.open &&
    !document.querySelector('#company-details')?.open
  )
    closeDrawer();
});
$('#menu').onclick = () => $('#sidebar').classList.toggle('open');
async function changeMode(mode) {
  if (changeMode.busy) return;
  changeMode.busy = true;
  $('#source-toggle').disabled = true;
  try {
    await window.easyerpDatabaseSource.switch('active-' + mode);
  } catch (err) {
    toast(err.message);
  } finally {
    changeMode.busy = false;
    $('#source-toggle').disabled = false;
  }
}

$('#source-toggle').onclick = () => toggleSourceMenu();
$('#back-live').onclick = () => changeMode('live');
window.addEventListener('hashchange', () => {
  if (!$('#drawer').hidden) closeDrawer();
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  exploreObject = q.get('object') || '';
  state.scope = q.get('scope') || '';
  state.offset = history.state?.easyerpView?.offset || 0;
  render();
});
window.addEventListener('popstate', () => {
  restoreNavigationState();
  if (location.hash === renderedNavigationHash) render();
});
(async () => {
  restoreNavigationState();
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  exploreObject = q.get('object') || '';
  state.scope = q.get('scope') || '';
  sync();
  try {
    meta = await api('meta');
    updateAccess(meta);
    sync();
    await render();
  } catch (err) {
    $('#content').innerHTML =
      `<div class="error-panel">${esc(err.message)}<br>请确认前端服务和数据库已经启动。<br><button class="button" data-retry>重新读取</button></div>`;
  }
})();

window.addEventListener('erp:data-changed', (event) => {
  if (event.detail.mode === state.mode) {
    meta = null;
    render();
  }
});

function accessLabel(capabilities) {
  const read = capabilities?.query_read_only === true || capabilities?.read_only === true;
  const write = capabilities?.manual_entry === true && capabilities?.read_only === false;
  return read && write ? 'R&W' : read ? 'Read' : write ? 'Write' : '—';
}
function updateAccess(capabilities) {
  $('#access-level').textContent = accessLabel(capabilities);
}
const dateRangePopover = window.easyerpQueryPopover.bind(
  $('#date-range-popover'), $('#date-range-trigger'), () => {
    for (const id of ['start', 'end']) $('#' + id).value = state[id];
    validateDateRange();
  }
);
function validateDateRange() {
  const start = $('#start'), end = $('#end');
  end.setCustomValidity(start.value && end.value && start.value > end.value
    ? (window.ERPUI?.t('请选择有效的起止日期') || '请选择有效的起止日期') : '');
  $('#date-range-apply').disabled = !start.value || !end.value || !start.validity.valid || !end.validity.valid;
}
for (const id of ['start', 'end']) {
  $('#' + id).addEventListener('input', validateDateRange);
  $('#' + id).addEventListener('change', validateDateRange);
}
$('#date-range-form').addEventListener('submit', (event) => {
  event.preventDefault();
  validateDateRange();
  if (!$('#date-range-form').reportValidity()) return;
  dateRangePopover.close(true);
  applyQuery($('#start').value, $('#end').value);
});
document.querySelectorAll('[data-date-cancel]').forEach(button => {
  button.addEventListener('click', () => dateRangePopover.close(true));
});
function syncQueryDates() {
  $('#date-range-text').textContent = `${state.start.replaceAll('-', ':')} -> ${state.end.replaceAll('-', ':')}`;
  $('#date-range-trigger').disabled = $('#start').disabled || $('#end').disabled;
}
document.addEventListener('easyerp:database-label', () => {
  $('#connection').textContent = window.easyerpDatabaseSource.label;
});
function syncSourceMenu() {
  document.querySelectorAll('[data-source-value]').forEach((button) => {
    const selected = 'active-' + button.dataset.sourceValue === window.easyerpDatabaseSource.id;
    button.setAttribute('aria-checked', String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
}
function closeSourceMenu(restoreFocus = false) {
  $('#source-menu').hidden = true;
  $('#source-toggle').setAttribute('aria-expanded', 'false');
  if (restoreFocus) $('#source-toggle').focus({ preventScroll: true });
}
function toggleSourceMenu() {
  const menu = $('#source-menu'),
    trigger = $('#source-toggle');
  if (!menu.hidden) {
    closeSourceMenu();
    return;
  }
  syncSourceMenu();
  menu.hidden = false;
  const anchor = trigger.getBoundingClientRect(),
    width = menu.offsetWidth,
    height = menu.offsetHeight;
  menu.style.left = Math.max(8, Math.min(anchor.left, window.innerWidth - width - 8)) + 'px';
  menu.style.top =
    Math.max(
      8,
      anchor.top >= height + 16
        ? anchor.top - height - 8
        : Math.min(anchor.bottom + 8, window.innerHeight - height - 8)
    ) + 'px';
  trigger.setAttribute('aria-expanded', 'true');
  (menu.querySelector('[aria-checked="true"]') || $('#database-manager-open')).focus({ preventScroll: true });
}
$('#source-menu').addEventListener('click', (event) => {
  const button = event.target.closest('[data-source-value]');
  if (!button) return;
  const mode = button.dataset.sourceValue;
  closeSourceMenu(true);
  if ('active-' + mode !== window.easyerpDatabaseSource.id) changeMode(mode);
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('#source-menu,#source-toggle')) closeSourceMenu();
});
document.addEventListener('keydown', (event) => {
  const menu = $('#source-menu');
  if (menu.hidden) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    closeSourceMenu(true);
  } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    const items = [...menu.querySelectorAll('[data-source-value],#database-manager-open')];
    let index = items.indexOf(document.activeElement);
    index =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? items.length - 1
          : (index + (event.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length;
    items[index].focus({ preventScroll: true });
  } else if (event.key === 'Tab') closeSourceMenu();
});
$('#source-toggle').addEventListener('keydown', (event) => {
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    if ($('#source-menu').hidden) toggleSourceMenu();
  }
});
window.addEventListener('resize', () => closeSourceMenu());

window.renderWorkspacePage = render;


document.addEventListener('click', (event) => {
  if (!event.target.closest('[data-supplier-items]')) return;
  move('archive', 'production.供应物品明细表', { department: 'production' });
});
