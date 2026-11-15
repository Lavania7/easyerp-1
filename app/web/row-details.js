'use strict';
window.easyerpRowDetails = (() => {
  let current = null, serial = 0;
  const key = (object, id) => JSON.stringify([object, String(id)]);
  const alive = session => current === session && session.row.isConnected && state.mode === session.mode;
  async function request(session, path, extra = {}) {
    const response = await window.easyerpFetch('/api/' + path + '?' + new URLSearchParams({ mode: session.mode, ...extra }), { signal: session.controller.signal });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '无法读取记录信息');
    return result;
  }
  async function each(items, callback) {
    let index = 0;
    await Promise.all(Array.from({ length: Math.min(3, items.length) }, async () => {
      while (index < items.length) await callback(items[index++]);
    }));
  }
  function close(focus = false) {
    if (!current) return;
    const session = current;
    current = null;
    session.controller.abort();
    session.region.remove();
    session.row.classList.remove('row-details-open');
    session.row.setAttribute('aria-expanded', 'false');
    session.row.removeAttribute('aria-controls');
    if (focus && session.row.isConnected) session.row.focus({ preventScroll: true });
  }
  function fields(session, frame) {
    const definition = session.objects.get(frame.object);
    return `<dl class="record-inline-fields">${(definition?.columns || Object.keys(frame.values).map(name => ({ name }))).filter(column => !hiddenIdentityField(column.name)).map(column => {
      const value = frame.values[column.name];
      let text = value == null ? '<span class="muted">N/A</span>' : esc(typeof value === 'object' ? JSON.stringify(value) : value === '' ? '""' : String(value));
      if (column.reference && value != null && value !== '') {
        const label = session.labels.get(key(column.reference.target, value));
        text = `<span>${esc(label || ERPUI.t('关联记录未找到'))}</span><small class="record-inline-id">${esc(value)}</small>`;
      }
      return `<div><dt data-ui-label>${esc(column.name)}</dt><dd data-i18n-ignore>${text}</dd></div>`;
    }).join('')}</dl>`;
  }
  function render(session, root, children, references) {
    if (!alive(session)) return;
    const object = session.objects.get(root.object);
    session.region.firstElementChild.innerHTML = `<section class="record-inline-panel" role="region" aria-label="记录详情"><div class="record-inline-head"><div><h3 data-ui-label>记录详情</h3><span data-ui-label>${esc(object?.label || object?.name || root.object)}</span><span class="record-inline-mode" data-ui-label>${session.mode === 'demo' ? '演示数据' : '正式数据'}</span></div><button type="button" class="button small" data-row-details-close data-ui-label>收起详情</button></div><section><h4 data-ui-label>完整字段</h4>${fields(session, root)}</section>${children.map((frame, index) => `<section class="record-inline-related"><h4 data-ui-label>${esc(session.objects.get(frame.object)?.label || frame.object)} · ${index + 1}</h4>${fields(session, frame)}</section>`).join('')}${references.length ? `<section class="record-inline-references"><h4 data-ui-label>关联记录信息</h4>${references.map(frame => `<section class="record-inline-related"><h5 data-ui-label>${esc(session.objects.get(frame.object)?.label || frame.object)}</h5>${frame.error ? `<p class="muted">${esc(frame.error)}</p>` : fields(session, frame)}</section>`).join('')}</section>` : ''}</section>`;
  }
  async function open(row) {
    close();
    const region = document.createElement('tr');
    region.className = 'table-record-details';
    region.id = 'record-inline-' + (++serial);
    region.insertCell().colSpan = [...row.cells].reduce((total, cell) => total + cell.colSpan, 0);
    region.firstElementChild.innerHTML = '<div class="record-inline-panel" role="status" data-ui-label>正在读取完整记录与关联信息…</div>';
    row.after(region);
    row.classList.add('row-details-open');
    row.setAttribute('aria-expanded', 'true');
    row.setAttribute('aria-controls', region.id);
    const session = { row, region, mode: state.mode, object: row.dataset.rowObject, id: row.dataset.rowId, controller: new AbortController(), labels: new Map() };
    current = session;
    try {
      const [metadata, record] = await Promise.all([
        request(session, 'entry/meta'),
        request(session, 'entry/record', { object: session.object, id: session.id }),
      ]);
      if (!alive(session)) return;
      session.objects = new Map(metadata.objects.map(object => [object.key, object]));
      const root = { object: session.object, id: session.id, values: record.values };
      const children = (record.children || []).map(child => ({ object: child.object, id: child.id, values: child.values }));
      const owned = new Set([root, ...children].map(frame => key(frame.object, frame.id)));
      const references = new Map();
      for (const frame of [root, ...children]) {
        for (const column of session.objects.get(frame.object)?.columns || []) {
          const value = frame.values[column.name], reference = column.reference;
          if (!reference || value == null || value === '' || owned.has(key(reference.target, value))) continue;
          references.set(key(reference.target, value), { object: reference.target, id: value });
        }
      }
      await each([...references.values()], async frame => {
        try { frame.values = (await request(session, 'entry/record', { object: frame.object, id: frame.id, include_children: '0' })).values; }
        catch (error) { if (error.name === 'AbortError') throw error; frame.error = error.message; }
      });
      if (!alive(session)) return;
      const names = new Map();
      for (const frame of [root, ...children, ...references.values()].filter(frame => frame.values)) {
        for (const column of session.objects.get(frame.object)?.columns || []) {
          const value = frame.values[column.name];
          if (column.reference && value != null && value !== '') names.set(key(column.reference.target, value), { object: column.reference.target, id: value });
        }
      }
      await each([...names.entries()], async ([identity, reference]) => {
        try {
          const result = await request(session, 'entry/choices', { object: reference.object, selected: reference.id });
          const choice = result.rows.find(row => row.value === reference.id);
          if (choice) session.labels.set(identity, choice.label);
        } catch (error) { if (error.name === 'AbortError') throw error; }
      });
      render(session, root, children, [...references.values()]);
    } catch (error) {
      if (error.name === 'AbortError' || !alive(session)) return;
      region.firstElementChild.innerHTML = `<div class="record-inline-panel"><p role="alert">${esc(error.message)}</p><button type="button" class="button small" data-row-details-close data-ui-label>收起详情</button></div>`;
    }
  }
  function toggle(row) { current?.row === row ? close() : open(row); }
  document.addEventListener('click', event => {
    if (event.target.closest('[data-row-details-close]')) { event.preventDefault(); close(true); return; }
    if (event.target.closest('[data-row-edit]')) { close(); return; }
    const row = event.target.closest('#content tr[data-row-object][data-row-id]');
    if (!row || event.target.closest('input,select,textarea,a,summary,[contenteditable]')) return;
    const button = event.target.closest('button');
    // ID buttons in a saved row follow the row; explicit Edit/View actions retain their own behavior.
    if (button && !button.hasAttribute('data-record')) return;
    if (getSelection()?.isCollapsed === false) return;
    event.preventDefault(); event.stopPropagation(); toggle(row);
  }, true);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && current && (current.row.contains(event.target) || current.region.contains(event.target))) { event.preventDefault(); event.stopPropagation(); close(true); return; }
    const row = event.target.closest('#content tr[data-row-object][data-row-id]');
    if (row && event.target === row && ['Enter', ' '].includes(event.key)) { event.preventDefault(); toggle(row); }
  });
  window.addEventListener('hashchange', () => close());
  window.addEventListener('erp:data-changed', () => close());
  Object.assign(window.ERP_MESSAGES, {
    '记录详情': ['Record details', 'Datensatzdetails'], '收起详情': ['Collapse details', 'Details schließen'],
    '完整字段': ['All fields', 'Alle Felder'], '关联记录信息': ['Linked record information', 'Verknüpfte Datensatzinformationen'],
    '正在读取完整记录与关联信息…': ['Loading full record and linked information…', 'Datensatz und verknüpfte Informationen werden geladen…'],
    '无法读取记录信息': ['Could not load record information', 'Datensatzinformationen konnten nicht geladen werden'],
    '关联记录未找到': ['Linked record not found', 'Verknüpfter Datensatz nicht gefunden'],
    '展开或收起记录详情': ['Expand or collapse record details', 'Datensatzdetails ein- oder ausblenden'],
  });
  return { mount() { if (current && (!current.row.isConnected || current.mode !== state.mode)) close(); } };
})();
