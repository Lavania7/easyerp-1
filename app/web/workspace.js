'use strict';
window.easyerpWorkspace = (() => {
  let view = 'items',
    current = null,
    token = '',
    pending = null,
    returnFocus = null,
    lastPage = '';
  const dialog = document.createElement('dialog');
  dialog.className = 'entry-dialog workspace-dialog';
  dialog.id = 'workspace-dialog';
  dialog.setAttribute('aria-labelledby', 'workspace-dialog-title');
  dialog.setAttribute('aria-modal', 'false');
  document.body.append(dialog);
  const departments = [
    ['finance', '财务'],
    ['legal', '法务'],
    ['production', '生产'],
    ['rd', '研发'],
    ['sales', '销售'],
    ['analysis', '分析'],
  ];
  const groups = [
    ['sales', '销售'],
    ['inventory', '采购与库存'],
    ['production', '生产实绩'],
    ['rd', '研发'],
    ['finance', '财务'],
    ['legal', '法务'],
    ['analysis', '分析报告'],
  ];
  const pageTabs = {
    workflow: [
      ['items', '办理事项'],
      ['production', '生产执行'],
    ],
    audit: [],
  };
  const reportPeriod = (item) => (item.values.start || '—') + ' – ' + (item.values.due || '—');
  const descriptions = {
    sales: '订单、发货与售后',
    inventory: '采购订单、到货与库存盘点',
    production: '领退料、完工与质量记录',
    rd: '项目、设计与发布记录',
    finance: '资金、发票与会计记录',
    legal: '合同审阅与业务交付',
    analysis: '数据集、指标与分析报告',
  };
  const transitions = {
    '草稿': ['已发布', '已取消'],
    '已发布': ['已完成', '已取消'],
    '待采纳': ['待执行', '已取消'],
    '待执行': ['处理中', '已取消'],
    '处理中': ['待复核', '已取消'],
    '待复核': ['已完成', '处理中', '已取消'],
    '已完成': [],
    '已取消': [],
    '待接续': ['待采纳', '待执行', '处理中', '待复核', '已完成', '已取消'],
    '历史归档': [],
  };
  const kindFor = () => (route === 'plans' ? 'plan' : route === 'audit' ? 'report' : 'workflow');
  const frozen = (item) =>
    ['已完成', '已取消', '历史归档'].includes(item.status) ||
    (item.kind === 'report' && item.status === '已发布');
  async function request(kind, extra = {}) {
    const response = await window.easyerpFetch('/api/workspace?' + params({ kind, ...extra }));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    token = data.token;
    return data;
  }
  function tabs(items) {
    return `<div class="workspace-tabs" role="group">${items.map(([key, label]) => `<button class="button ${view === key ? 'primary' : ''}" data-ws-view="${key}" aria-pressed="${view === key}">${esc(label)}</button>`).join('')}</div>`;
  }
  function dataHome() {
    return {
      html: `<p class="workspace-intro">按业务部门查看已经发生的事实。基础资料集中在档案馆，计划与办理过程各有独立入口。</p><div class="workspace-grid">${groups.map(([key, label]) => `<button class="panel workspace-card" data-page="${key}">${icon(key === 'inventory' ? 'inventory' : key)}<h2>${esc(label)}</h2><p>${esc(descriptions[key])}</p><span>查看记录 ↗</span></button>`).join('')}</div>`,
    };
  }
  async function render(page) {
    const requestedView = new URLSearchParams(location.hash.split('?')[1] || '').get('view');
    view = pageTabs[page]?.some(([key]) => key === requestedView) ? requestedView : 'items';
    if (page === 'workflow' && state.department !== 'production') view = 'items';
    lastPage = page;
    if (page === 'data') {
      $('#export').hidden = false;
      $('#export').disabled = false;
      return explorer();
    }
    if (page === 'archive' || page === 'delivery') {
      $('#export').hidden = false;
      $('#export').disabled = false;
      return explorer();
    }
    if (page === 'audit' && state.department) {
      const objects = deptObjects();
      const selected = objects.find((o) => o.schema + '.' + o.name === exploreObject) || chooseObject(objects);
      if (selected && selected.schema !== 'workspace') {
        $('#export').hidden = false;
        $('#export').disabled = false;
        return explorer();
      }
      exploreObject = 'workspace.report';
    }
    if (page === 'workflow' && state.scope === 'pending' && state.department === 'production')
      view = 'production';
    if (
      ['workflow', 'tasks'].includes(page) &&
      view === 'production' &&
      state.department === 'production'
    ) {
      const d = await list('workorders', '');
      return {
        html:
          tabs(pageTabs.workflow) +
          `<div class="workspace-actions"><button class="button primary" data-ws-entry="production.生产工单表">＋ 登记生产执行</button></div>` +
          d.html,
      };
    }
    const kind = page === 'plans' ? 'plan' : page === 'audit' ? 'report' : 'workflow';
    const d = await request(kind, kind === 'report' ? { department: state.department } : {});
    const rows =
      kind === 'report'
        ? d.rows.filter((item) => (!state.department || matchesDepartment(item.values.department)))
        : d.rows.filter((item) => matchesDepartment(item.values.department));
    const counts = rows.reduce((a, r) => ((a[r.status] = (a[r.status] || 0) + 1), a), {});
    let prefix =
      page === 'audit'
        ? (state.department ? '<div class="table-toolbar">' + objectControls(deptObjects(), deptObjects().find((o) => o.schema === 'workspace')) + '</div>' : '')
        : ['workflow', 'tasks'].includes(page) && state.department === 'production'
          ? tabs(pageTabs.workflow)
          : '';
    const heading = kind === 'plan' ? '计划清单' : kind === 'report' ? '审计记录' : '事项清单';
    const body = `<div class="table-wrap"><table><thead><tr><th>标题</th><th>责任部门 / 负责人</th><th>${kind === 'report' ? '审计期间' : '截止日期'}</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows.map((item) => `<tr><td><button class="table-button" data-ws-open="${esc(item.id)}" data-i18n-ignore>${esc(item.values.title)}</button><span class="secondary"><span ${kind === 'report' ? 'data-ui-label' : 'data-i18n-ignore'}>${esc(kind === 'report' ? '' : item.values.type || '')}</span> <span data-i18n-ignore>${esc(item.values.plan_id || '')}</span></span></td><td data-i18n-ignore>${esc(item.values.department || '—')} / ${esc(item.values.owner || '待指定')}</td><td>${esc(kind === 'report' ? reportPeriod(item) : item.values.due || '未设期限')}</td><td>${badge(item.status)}</td><td><button class="button small" data-ws-open="${esc(item.id)}">${frozen(item) ? '查看' : '办理'}</button>${kind === 'plan' && item.status === '已发布' ? ` <button class="button small" data-ws-start="${esc(item.id)}">发起执行</button>` : ''}${kind === 'report' && item.status === '已发布' ? ` <button class="button small" data-ws-revise="${esc(item.id)}">新建修订版</button>` : ''}</td></tr>`).join('') || `<tr><td colspan="5">${empty(kind === 'report' ? '尚无审计报告' : kind === 'plan' ? '尚无企业计划' : '尚无办理事项')}</td></tr>`}</tbody></table></div>`;
    current = { kind, rows, mode: state.mode };
    return {
      html:
        prefix +
        `<div class="workspace-stats">${Object.entries(counts)
          .map(([label, n]) => `<span>${esc(label)} <strong>${n}</strong></span>`)
          .join(
            ''
          )}</div><section class="panel"><div class="panel-head"><h2>${heading}</h2><button class="button primary" data-ws-new>＋ 新建${kind === 'report' ? '记录' : kind === 'plan' ? '计划' : '事项'}</button></div>${body}</section>`,
    };
  }
  function matchesDepartment(value) {
    const aliases = {
      finance: ['finance', '财务', '财务部', 'FIN'],
      legal: ['legal', '法务', '法务部', 'LEG'],
      production: ['production', '生产', '生产部', '采购与库存', '生产实绩', 'PRD'],
      rd: ['rd', '研发', '研发部', 'R&D', 'RND'],
      sales: ['sales', '销售', '销售部', 'SAL'],
      analysis: ['analysis', '分析', '分析部', '数据分析', '分析报告', 'ANA'],
    };
    return (aliases[state.department] || []).some(
      (alias) =>
        alias.toLocaleLowerCase() ===
        String(value || '')
          .trim()
          .toLocaleLowerCase()
    );
  }
  const fields = {
    title: '标题',
    type: '事项类型',
    department: '责任部门',
    owner: '负责人',
    start: '开始日期',
    due: '截止日期',
    description: '内容与目标',
    decision: '采纳决定',
    result: '实际结果 / 整改结果',
    evidence: '证据路径或说明',
    links: '关联记录',
    plan_id: '关联计划',
    scope: '审计范围',
    conclusion: '审计结论',
    unresolved: '未核事项',
  };
  function positionPanel() {
    if (!dialog.open) return;
    if (dialog.classList.contains('plan-dialog')) {
      dialog.style.removeProperty('left');
      dialog.style.removeProperty('top');
      return;
    }
    const anchor = returnFocus?.isConnected ? returnFocus.getBoundingClientRect() : null;
    const topbar = document.querySelector('.topbar')?.getBoundingClientRect();
    const left = anchor && anchor.width ? anchor.left : (innerWidth - dialog.offsetWidth) / 2;
    const top = anchor && anchor.height ? anchor.bottom + 8 : (topbar?.bottom || 12) + 8;
    dialog.style.left = Math.max(12, Math.min(left, innerWidth - dialog.offsetWidth - 12)) + 'px';
    dialog.style.top = Math.max(12, Math.min(top, innerHeight - dialog.offsetHeight - 12)) + 'px';
  }
  function closePanel() {
    if (pending?.busy) return;
    dialog.close();
    pending = null;
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  }
  window.addEventListener('resize', positionPanel);
  function edit(item = null, defaults = {}, kindOverride = null) {
    // Keep the current input when another page action opens the same floating editor.
    if (dialog.open) {
      (
        dialog.querySelector('input:not([type=hidden]):enabled') || dialog.querySelector('button')
      )?.focus();
      return;
    }
    returnFocus = document.activeElement;
    if (!item && !Object.hasOwn(defaults, 'department'))
      defaults = {
        department: departments.find(([key]) => key === state.department)?.[1] || '',
        ...defaults,
      };
    const kind = kindOverride || item?.kind || kindFor(),
      values = { ...(item?.values || {}), ...defaults };
    const keys =
      kind === 'report'
        ? ['title', 'department', 'start', 'due', 'owner', 'scope', 'conclusion', 'unresolved', 'evidence', 'links']
        : kind === 'plan'
          ? ['title', 'department', 'owner', 'start', 'due', 'description', 'links']
          : [
              'title',
              'type',
              'department',
              'owner',
              'start',
              'due',
              'description',
              'decision',
              'result',
              'evidence',
              'links',
              'plan_id',
            ];
    const locked = item && frozen(item),
      status = item?.status || (kind === 'workflow' ? '待采纳' : '草稿');
    pending = { item, kind, mode: state.mode, requestId: crypto.randomUUID() };
    const statuses =
      kind === 'report'
        ? ['草稿', '已发布']
        : item
          ? [status, ...(transitions[status] || [])]
          : kind === 'workflow'
            ? ['待采纳', '待执行']
            : ['草稿'];
    dialog.classList.toggle('plan-dialog', kind === 'plan');
    dialog.setAttribute('aria-modal', String(kind === 'plan'));
    dialog.innerHTML = `<div class="entry-head"><div><span class="entry-mode">${state.mode === 'demo' ? '演示数据' : '正式数据'}</span><h2 id="workspace-dialog-title">${item ? '查看与办理' : '新建'}${kind === 'plan' ? '企业计划' : kind === 'report' ? '审计报告' : '工作流事项'}</h2></div><button type="button" class="icon-button" data-ws-close aria-label="关闭">×</button></div><form id="workspace-form"><div class="entry-content workspace-body"><p class="entry-error" role="alert" hidden></p><div class="entry-grid">${keys
      .map((key) => {
        if (kind === 'report' && key === 'department') {
          const labels = departments.map(([, label]) => label);
          const selected = values.department || '';
          return `<label class="entry-field"><span>责任部门</span><select name="department" ${locked ? 'disabled' : ''}><option value="">未指定部门</option>${[...labels, ...(selected && !labels.includes(selected) ? [selected] : [])].map((label) => `<option value="${esc(label)}" ${selected === label ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label>`;
        }
        if (['links', 'plan_id'].includes(key))
          return `<label class="entry-field wide"><span>${fields[key]}</span><div data-ws-reference="${key}">正在读取关联名称…</div></label>`;
        const multiline = [
          'description',
          'decision',
          'result',
          'evidence',
          'scope',
          'conclusion',
          'unresolved',
          'links',
        ].includes(key);
        const label = kind === 'report' && key === 'owner' ? '复核人' : kind === 'report' && key === 'start' ? '起始日期' : kind === 'report' && key === 'due' ? '截止日期' : fields[key];
        return `<label class="entry-field ${multiline || key === 'title' ? 'wide' : ''}"><span>${label}${key === 'title' || (kind === 'report' && ['start', 'due'].includes(key)) ? ' *' : ''}</span>${multiline ? `<textarea name="${key}" rows="3" data-i18n-ignore ${locked ? 'disabled' : ''}>${esc(values[key] || '')}</textarea>` : `<input name="${key}" type="${['start', 'due'].includes(key) ? 'date' : 'text'}" value="${esc(values[key] || '')}" ${key === 'title' || (kind === 'report' && ['start', 'due'].includes(key)) ? 'required' : ''} ${locked ? 'disabled' : ''} data-i18n-ignore>`}</label>`;
      })
      .join(
        ''
      )}<label class="entry-field"><span>当前状态</span><select name="status" ${locked ? 'disabled' : ''}>${statuses.map((s) => `<option ${status === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select></label><label class="entry-field wide"><span>本次处理说明</span><textarea name="note" rows="2" ${locked ? 'disabled' : ''}></textarea></label></div>${item ? `<details class="workspace-history"><summary>处理历史 · ${item.history.length} 次</summary>${item.history.map((event) => `<div class="file-card"><strong>${esc(event.from || '新建')} → ${esc(event.to)}</strong><time>${dateText(event.at)}</time><p data-i18n-ignore>${esc(event.note || '')}</p><details><summary>当次记录</summary><pre data-i18n-ignore>${esc(JSON.stringify(event.after, null, 2))}</pre></details></div>`).join('')}</details>` : ''}</div><div class="entry-footer"><button type="button" class="button" data-ws-close>关闭</button>${locked ? '' : '<button class="button primary" type="submit" data-ws-save disabled>保存</button>'}</div></form>`;
    if (kind === 'plan' && (state.department === 'production' || ['production', '生产', '生产部', 'PRD'].includes(values.department)))
      window.easyerpPlanVisual.mount(dialog);
    if (item?.legacy) {
      const box = document.createElement('details');
      box.className = 'workspace-history';
      box.innerHTML = `<summary>历史来源快照</summary><pre data-i18n-ignore>${esc(JSON.stringify(item.legacy, null, 2))}</pre>`;
      dialog.querySelector('.workspace-body').append(box);
    }
    if (kind === 'plan') dialog.showModal();
    else dialog.show();
    positionPanel();
    (
      dialog.querySelector('input:not([type=hidden]):enabled') || dialog.querySelector('button')
    )?.focus({ preventScroll: true });
    const referenceSession = pending;
    prepareNamedReferences(values, locked)
      .then(() => {
        if (pending === referenceSession && dialog.open)
          dialog.querySelector('[data-ws-save]')?.removeAttribute('disabled');
      })
      .catch((error) => {
        if (pending !== referenceSession) return;
        const box = dialog.querySelector('.entry-error');
        if (box) {
          box.hidden = false;
          box.textContent = error.message;
        }
      });
    dialog.querySelector('form').addEventListener('submit', save);
    dialog.querySelector('form').addEventListener('input', () => {
      pending.requestId = crypto.randomUUID();
    });
  }
  async function prepareNamedReferences(values, locked) {
    const session = pending;
    const fetchJSON = async (path) => {
      const response = await window.easyerpFetch(path);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '无法读取关联名称');
      return data;
    };
    const api = (path, params = {}) =>
      fetchJSON('/api/' + path + '?' + new URLSearchParams({ mode: session.mode, ...params }));
    const title = (text) => {
      try {
        const value = JSON.parse(text);
        return value['产品名称'] || value['项目名称'] || text;
      } catch {
        return text;
      }
    };
    const planBox = dialog.querySelector('[data-ws-reference="plan_id"]');
    if (planBox) {
      const result = await api('workspace', { kind: 'plan' });
      if (pending !== session) return;
      planBox.innerHTML = `<select name="plan_id" aria-describedby="workspace-plan-source" ${locked ? 'disabled' : ''}><option value="">请选择关联计划</option>${result.rows.map((row) => `<option value="${esc(row.id)}" ${row.id === values.plan_id ? 'selected' : ''} data-i18n-ignore>${esc(title(row.values.title))}</option>`).join('')}</select>${referenceSourceHint('workspace.plan', [], 'workspace-plan-source')}`;
    }
    const box = dialog.querySelector('[data-ws-reference="links"]');
    if (!box) return;
    const meta = await api('entry/meta');
    if (pending !== session) return;
    const objects = meta.objects.filter((o) => !o.retired),
      links = String(values.links || '')
        .split(/\n/)
        .filter(Boolean)
        .map((raw) => {
          const split = raw.indexOf(':');
          return {
            raw,
            object: raw.slice(0, split),
            id: raw.slice(split + 1),
            label: '已有关联（保留）',
          };
        });
    for (const link of links) {
      if (!objects.some((o) => o.key === link.object)) continue;
      const result = await api('entry/choices', { object: link.object, selected: link.id });
      link.label = result.rows.find((r) => r.value === link.id)?.label || '已有关联（保留）';
    }
    if (pending !== session) return;
    box.innerHTML = `<input type="hidden" name="links"><ul data-ws-linked></ul>${locked ? '' : `<div class="entry-ref"><select data-ws-link-object aria-label="关联记录类型">${objects.map((o) => `<option value="${esc(o.key)}">${esc(o.label || o.name)}</option>`).join('')}</select><input type="search" data-ws-link-search placeholder="搜索名称" aria-label="搜索关联名称"><select data-ws-link-choice aria-label="选择关联记录"><option value="">请选择关联记录</option></select><button type="button" data-ws-link-add>添加关联</button></div>`}`;
    const paint = () => {
      box.querySelector('[name=links]').value = links.map((l) => l.raw).join('\n');
      box.querySelector('[data-ws-linked]').innerHTML = links
        .map(
          (l, i) =>
            `<li><span data-i18n-ignore>${esc(l.label)}</span>${referenceSourceHint(l.object || l.raw.slice(0, l.raw.indexOf(':')), objects)}${locked ? '' : ` <button type="button" data-ws-unlink="${i}">移除</button>`}</li>`
        )
        .join('');
    };
    paint();
    if (locked) return;
    let serial = 0;
    const select = box.querySelector('[data-ws-link-choice]'),
      object = box.querySelector('[data-ws-link-object]'),
      search = box.querySelector('[data-ws-link-search]');
    const load = async () => {
      const token = ++serial;
      box.querySelector('[data-ws-source]')?.remove();
      const source = document.createElement('div');
      source.dataset.wsSource = '';
      source.innerHTML = referenceSourceHint(object.value, objects, 'workspace-link-source');
      box.append(source);
      select.setAttribute('aria-describedby', 'workspace-link-source');
      select.disabled = true;
      try {
        const result = await api('entry/choices', { object: object.value, q: search.value });
        if (pending !== session || token !== serial) return;
        select.innerHTML =
          '<option value="">请选择关联记录</option>' +
          result.rows
            .map((r) => `<option value="${esc(r.value)}" data-i18n-ignore>${esc(r.label)}</option>`)
            .join('');
      } finally {
        if (token === serial) select.disabled = false;
      }
    };
    object.addEventListener('change', () => {
      search.value = '';
      load().catch((error) => toast(error.message));
    });
    search.addEventListener('input', () => {
      clearTimeout(search._timer);
      search._timer = setTimeout(() => load().catch((error) => toast(error.message)), 220);
    });
    box.addEventListener('click', (event) => {
      const add = event.target.closest('[data-ws-link-add]'),
        remove = event.target.closest('[data-ws-unlink]');
      if (add && select.value) {
        const raw = object.value + ':' + select.value;
        if (!links.some((l) => l.raw === raw))
          links.push({ raw, label: select.selectedOptions[0].textContent });
        paint();
        session.requestId = crypto.randomUUID();
      }
      if (remove) {
        links.splice(Number(remove.dataset.wsUnlink), 1);
        paint();
        session.requestId = crypto.randomUUID();
      }
    });
    await load();
  }
  async function save(event) {
    event.preventDefault();
    const session = pending,
      form = event.target,
      error = form.querySelector('.entry-error'),
      button = form.querySelector('[type=submit]');
    button.disabled = true;
    error.hidden = true;
    const data = new FormData(form),
      values = {};
    for (const key of Object.keys(fields)) if (data.has(key)) values[key] = String(data.get(key));
    session.busy = true;
    const payload = {
      request_id: session.requestId,
      kind: session.kind,
      values,
      status: data.get('status'),
      note: data.get('note'),
    };
    if (session.item)
      Object.assign(payload, { id: session.item.id, version: session.item.version });
    try {
      const fetchToken = await window.easyerpFetch(
        '/api/workspace?' + new URLSearchParams({ kind: session.kind, mode: session.mode })
      );
      const meta = await fetchToken.json();
      if (!fetchToken.ok) throw new Error(meta.error);
      const response = await window.easyerpFetch(
        '/api/workspace/save?' + new URLSearchParams({ mode: session.mode }),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-EasyERP-Token': meta.token },
          body: JSON.stringify(payload),
        }
      );
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      dialog.close();
      pending = null;
      toast('已保存');
      if (state.mode === session.mode) {
        if (session.kind === 'workflow' && route === 'plans') move('workflow');
        else await window.renderWorkspacePage();
      }
    } catch (err) {
      session.busy = false;
      error.textContent = err.message;
      error.hidden = false;
      button.disabled = false;
      form.querySelector('.workspace-body').scrollTop = 0;
    }
  }
  document.addEventListener('click', (e) => {
    const button = e.target.closest('button');
    if (!button) return;
    if (button.hasAttribute('data-ws-new')) edit();
    if (button.dataset.wsView) {
      state.scope = '';
      move(route, '', { view: button.dataset.wsView });
    }
    if (button.dataset.wsOpen) {
      const item = current?.rows.find((x) => x.id === button.dataset.wsOpen);
      if (item) edit(item);
    }
    if (button.dataset.wsStart) {
      const item = current?.rows.find((x) => x.id === button.dataset.wsStart);
      if (item) {
        edit(
          null,
          {
            title: item.values.title,
            description: item.values.description || '',
            plan_id: item.id,
            department: item.values.department || '',
            owner: item.values.owner || '',
          },
          'workflow'
        );
      }
    }
    if (button.dataset.wsRevise) {
      const item = current?.rows.find((x) => x.id === button.dataset.wsRevise);
      if (item)
        edit(null, {
          ...item.values,
          title: item.values.title + '（修订）',
          links: (item.values.links || '') + '\n审计报告ID:' + item.id,
        });
    }
    if (button.dataset.wsEntry) window.easyerpManual.open(button.dataset.wsEntry);
    if (button.hasAttribute('data-ws-close')) closePanel();
  });
  dialog.addEventListener('cancel', (e) => {
    if (pending?.busy) e.preventDefault();
  });
  dialog.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closePanel();
    }
  });
  async function openItem(id) {
    const data = await request('workflow', { start: '', end: '' });
    const item = data.rows.find((x) => x.id === id);
    if (item) edit(item);
    else toast('事项已不在当前来源中');
  }
  return {
    navigation: () => ({ groups, departments, tabs: pageTabs, view, page: lastPage }),
    render,
    create: () => route === 'calculations' ? window.easyerpCalculations.create() : (['data', 'archive', 'delivery'].includes(route) || (route === 'audit' && exploreObject !== 'workspace.report' && state.department) ? window.easyerpManual.open() : edit()),
    openItem,
    mounted() {},
    edit,
  };
})();

Object.assign(window.ERP_MESSAGES, {
  '活动数据': ['Active data', 'Aktive Daten'],
  '静态数据': ['Static data', 'Statische Daten'],
  '部门交付': ['Department deliveries', 'Abteilungslieferungen'],
  '矩阵关系图': ['Relationship matrix', 'Beziehungsmatrix'],
  '审计记录': ['Audit records', 'Prüfaufzeichnungen'],
  '来源位置': ['Source location', 'Quellpfad'],
  '审计报告': ['Audit reports', 'Prüfberichte'],
  '审计期间': ['Audit period', 'Prüfzeitraum'],
  '审计期间 *': ['Audit period *', 'Prüfzeitraum *'],
  '未指定部门': ['Department unspecified', 'Abteilung nicht angegeben'],
  '审计记录': ['Audit report list', 'Liste der Prüfberichte'],
  '尚无审计报告': ['No audit reports yet', 'Noch keine Prüfberichte'],
  '＋ 新建报告': ['＋ New report', '＋ Neuer Bericht'],
  '新建审计报告': ['New audit report', 'Neuer Prüfbericht'],
  '查看与办理审计报告': ['Review audit report', 'Prüfbericht ansehen'],
  '月度报告使用所选月份；季度报告覆盖该月份所在季度；年度报告覆盖该月份所在年度。': [
    'Monthly reports use the selected month; quarterly reports cover its quarter; annual reports cover its year.',
    'Monatsberichte gelten für den gewählten Monat, Quartalsberichte für dessen Quartal und Jahresberichte für dessen Jahr.',
  ],
  '按起止日期登记审计范围、结论和未核事项。全年、季度和自定义日期使用上方统一筛选；部门选择仅显示该部门的记录。': [
    'Record monthly, quarterly or annual audit scope, conclusions and unresolved matters. Select a department to filter its reports; deselect it to view all reports.',
    'Prüfumfang, Ergebnisse und offene Punkte monatlich, quartalsweise oder jährlich erfassen. Eine Abteilung wählen, um deren Berichte zu filtern; abwählen, um alle Berichte zu sehen.',
  ],
  '企业计划': ['Company plans', 'Unternehmenspläne'],
  '工作流': ['Workflows', 'Arbeitsabläufe'],
  '数据中心': ['Data center', 'Datenzentrum'],
  '档案馆': ['Archive', 'Archiv'],
  '审计': ['Audit', 'Prüfung'],
  '生产实绩': ['Production records', 'Produktionsdaten'],
  '生产执行': ['Production execution', 'Produktionsausführung'],
  '月度审计报告': ['Monthly audit reports', 'Monatliche Prüfberichte'],
  '办理事项': ['Workflow items', 'Vorgänge'],
  '计划清单': ['Plans', 'Pläne'],
  '月报清单': ['Monthly reports', 'Monatsberichte'],
  '事项清单': ['Items', 'Vorgänge'],
  '标题': ['Title', 'Titel'],
  '责任部门 / 负责人': ['Department / owner', 'Abteilung / Verantwortlicher'],
  '审计月份': ['Audit month', 'Prüfmonat'],
  '截止日期': ['Due date', 'Frist'],
  '状态': ['Status', 'Status'],
  '操作': ['Actions', 'Aktionen'],
  '办理': ['Process', 'Bearbeiten'],
  '发起执行': ['Start execution', 'Ausführung starten'],
  '新建修订版': ['Create revision', 'Revision erstellen'],
  '新建月报': ['New report', 'Neuer Bericht'],
  '新建计划': ['New plan', 'Neuer Plan'],
  '新建事项': ['New item', 'Neuer Vorgang'],
  '＋ 新建月报': ['＋ New report', '＋ Neuer Bericht'],
  '＋ 新建计划': ['＋ New plan', '＋ Neuer Plan'],
  '＋ 新建事项': ['＋ New item', '＋ Neuer Vorgang'],
  '待指定': ['Unassigned', 'Nicht zugewiesen'],
  '未设期限': ['No due date', 'Keine Frist'],
  '查看与办理工作流事项': ['Process workflow item', 'Vorgang bearbeiten'],
  '查看与办理企业计划': ['Review company plan', 'Unternehmensplan prüfen'],
  '查看与办理审计月报': ['Review audit report', 'Prüfbericht ansehen'],
  '新建企业计划': ['New company plan', 'Neuer Unternehmensplan'],
  '新建工作流事项': ['New workflow item', 'Neuer Vorgang'],
  '新建审计月报': ['New audit report', 'Neuer Prüfbericht'],
  '事项类型': ['Item type', 'Vorgangsart'],
  '开始日期': ['Start date', 'Anfangsdatum'],
  '内容与目标': ['Description and objective', 'Inhalt und Ziel'],
  '采纳决定': ['Adoption decision', 'Annahmeentscheidung'],
  '实际结果 / 整改结果': ['Outcome / correction result', 'Ergebnis / Korrektur'],
  '证据路径或说明': ['Evidence path or description', 'Nachweis oder Beschreibung'],
  '关联记录ID': ['Related record IDs', 'Verknüpfte Datensatz-IDs'],
  '关联计划ID': ['Related plan ID', 'Verknüpfte Plan-ID'],
  '审计范围': ['Audit scope', 'Prüfumfang'],
  '审计结论': ['Audit conclusion', 'Prüfergebnis'],
  '本次处理说明': ['Processing note', 'Bearbeitungsnotiz'],
  '待采纳': ['Awaiting decision', 'Entscheidung ausstehend'],
  '待执行': ['Ready to execute', 'Bereit zur Ausführung'],
  '待复核': ['Awaiting review', 'Prüfung ausstehend'],
  '待接续': ['Awaiting handoff', 'Übernahme ausstehend'],
  '历史归档': ['Historical archive', 'Historisches Archiv'],
  '处理历史': ['Processing history', 'Bearbeitungsverlauf'],
  '当次记录': ['Saved snapshot', 'Gespeicherter Stand'],
  '历史来源快照': ['Legacy source snapshot', 'Historischer Quellstand'],
  '＋ 登记生产执行': ['＋ Record production execution', '＋ Produktionsausführung erfassen'],
  '库存盘点与余额': ['Inventory count and balance', 'Inventur und Bestand'],
  '仓储地点': ['Storage locations', 'Lagerorte'],
  '地点标识': ['Location code', 'Ortskennung'],
  '采购内容': ['Purchase items', 'Bestellpositionen'],
  '账面数量': ['Book quantity', 'Buchbestand'],
  '余额说明': ['Balance notes', 'Bestandsnotiz'],
  '尚无企业计划': ['No company plans yet', 'Noch keine Unternehmenspläne'],
  '尚无办理事项': ['No workflow items yet', 'Noch keine Vorgänge'],
  '尚无审计月报': ['No audit reports yet', 'Noch keine Prüfberichte'],
  '按业务部门查看已经发生的事实。基础资料集中在档案馆，计划与办理过程各有独立入口。': [
    'Browse actual business records by department. Master data lives in the archive; plans and workflows have their own pages.',
    'Geschäftsdaten nach Abteilung ansehen. Stammdaten liegen im Archiv; Pläne und Abläufe haben eigene Seiten.',
  ],
  '企业目标与生产计划集中登记，发布后可发起执行事项。': [
    'Record company objectives and production plans; start linked execution after publication.',
    'Unternehmensziele und Produktionspläne erfassen; nach Veröffentlichung verknüpfte Vorgänge starten.',
  ],
  '一个事项串联采纳、执行、整改和复核；处理过程与证据保留在同一条记录。': [
    'One item tracks decision, execution, correction and review, with its history and evidence.',
    'Ein Vorgang verbindet Entscheidung, Ausführung, Korrektur und Prüfung mit Verlauf und Nachweisen.',
  ],
  '每月集中记录审计范围、结论和未核事项。发布前由复核人明确确认，报告按版本保留。': [
    'Record monthly scope, conclusions and unresolved matters. A reviewer confirms publication; report versions are retained.',
    'Monatlich Umfang, Ergebnisse und offene Punkte festhalten. Veröffentlichung wird geprüft; Versionen bleiben erhalten.',
  ],
  '订单、发货与售后': ['Orders, shipments and after-sales', 'Aufträge, Versand und Kundendienst'],
  '采购订单、到货与库存盘点': [
    'Purchases, deliveries and inventory counts',
    'Bestellungen, Wareneingang und Inventur',
  ],
  '领退料、完工与质量记录': [
    'Materials, completion and quality',
    'Materialbewegungen, Fertigstellung und Qualität',
  ],
  '项目、设计与发布记录': [
    'Projects, designs and releases',
    'Projekte, Konstruktion und Freigaben',
  ],
  '资金、发票与会计记录': [
    'Funds, invoices and accounting',
    'Zahlungen, Rechnungen und Buchhaltung',
  ],
  '合同审阅与业务交付': ['Contract reviews and deliveries', 'Vertragsprüfungen und Übergaben'],
  '数据集、指标与分析报告': [
    'Datasets, metrics and reports',
    'Datensätze, Kennzahlen und Berichte',
  ],
});

Object.assign(window.ERP_MESSAGES, {
  '逐项明细（可选）': ['Item details (optional)', 'Positionen (optional)'],
  '更多地点标识（可选）': [
    'Additional location codes (optional)',
    'Weitere Ortskennungen (optional)',
  ],
  '采购说明': ['Purchase description', 'Bestellbeschreibung'],
  '订单金额': ['Order amount', 'Bestellbetrag'],
  '订单文件路径': ['Original order file', 'Originalbestellung'],
});
Object.assign(window.ERP_MESSAGES, {
  '查看记录': ['View records', 'Datensätze ansehen'],
  '截止日期': ['End date', 'Enddatum'],
  '标题 *': ['Title *', 'Titel *'],
  '审计月份 *': ['Audit month *', 'Prüfmonat *'],
});

Object.assign(window.ERP_MESSAGES, {
  '计划': ['Plans', 'Pläne'],
  '数据库': ['Database', 'Datenbank'],
  '归档': ['Archive', 'Archiv'],
  '分析': ['Analysis', 'Analyse'],
  '选择部门': ['Select a department', 'Abteilung auswählen'],
  '选择审阅内容': ['Select content to review', 'Inhalt zur Prüfung auswählen'],
  '左侧栏': ['Left sidebar', 'Linke Seitenleiste'],
  '上方栏': ['Department bar', 'Abteilungsleiste'],
  '查看经营概况': ['View the dashboard', 'Übersicht ansehen'],
  '工作空间白板': ['Empty workspace', 'Leerer Arbeitsbereich'],
});
