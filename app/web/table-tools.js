'use strict';
(() => {
  const preferences = new Map(), results = new Map(), uncertain = new Map(), requestContexts = new WeakMap();
  let current = null, selected = new Map(), fingerprint = '', generation = 0;
  const labels = {
    '字段筛选与排序': ['Field filters and sorting', 'Feldfilter und Sortierung'],
    '应用于全部匹配记录；分页、条数与导出使用同一条件。': ['Applies to every matching record; pages, counts and export use the same conditions.', 'Gilt für alle Treffer; Seiten, Anzahl und Export verwenden dieselben Bedingungen.'],
    '字段': ['Field', 'Feld'], '条件': ['Condition', 'Bedingung'], '筛选值': ['Filter value', 'Filterwert'],
    '增加筛选': ['Add filter', 'Filter hinzufügen'], '移除筛选': ['Remove filter', 'Filter entfernen'],
    '应用筛选与排序': ['Apply filters and sort', 'Filter und Sortierung anwenden'], '重置表格查询': ['Reset table query', 'Tabellenabfrage zurücksetzen'],
    '排序字段': ['Sort field', 'Sortierfeld'], '默认排序': ['Default order', 'Standardsortierung'],
    '升序': ['Ascending', 'Aufsteigend'], '降序': ['Descending', 'Absteigend'],
    '等于': ['Equals', 'Gleich'], '不等于': ['Does not equal', 'Ungleich'], '包含': ['Contains', 'Enthält'],
    '开头为': ['Starts with', 'Beginnt mit'], '小于': ['Less than', 'Kleiner als'], '不大于': ['At most', 'Höchstens'],
    '大于': ['Greater than', 'Größer als'], '不小于': ['At least', 'Mindestens'],
    '为空值 NULL': ['Is NULL', 'Ist NULL'], '非空值 NULL': ['Is not NULL', 'Ist nicht NULL'],
    '为空文本': ['Is empty text', 'Ist leerer Text'], '非空文本': ['Is not empty text', 'Ist kein leerer Text'],
    '勾选本页': ['Select this page', 'Diese Seite auswählen'], '选择记录': ['Select record', 'Datensatz auswählen'],
    '仅勾选本页显示记录，可跨页保留已选；改变查询或来源会清空选择。': ['Selects displayed rows only. Explicit selections persist across pages and clear when the query or source changes.', 'Wählt nur angezeigte Zeilen. Die Auswahl bleibt beim Blättern erhalten und wird bei Abfrage- oder Quellenwechsel gelöscht.'],
    '已选': ['Selected', 'Ausgewählt'], '清除选择': ['Clear selection', 'Auswahl löschen'],
    '批量修改字段': ['Batch edit a field', 'Feld gesammelt ändern'], '批量修改': ['Batch edit', 'Sammeländerung'],
    '取消批量修改': ['Cancel batch edit', 'Sammeländerung abbrechen'], '设置内容': ['Set value', 'Wert setzen'],
    '设为空值 NULL': ['Set to NULL', 'Auf NULL setzen'], '新内容': ['New value', 'Neuer Wert'],
    '保存整批': ['Save batch', 'Gesamte Auswahl speichern'], '重试原批次': ['Retry original batch', 'Ursprüngliche Anfrage wiederholen'],
    '保存中…': ['Saving…', 'Wird gespeichert…'], '演示库': ['Demo database', 'Demodatenbank'], '正式库': ['Live database', 'Echtdatenbank'],
    '所有选中记录改为同一内容；任一冲突或失败，整批回滚。': ['All selected records receive the same value. Any conflict or failure rolls back the entire batch.', 'Alle ausgewählten Datensätze erhalten denselben Wert. Bei Konflikt oder Fehler wird alles zurückgerollt.'],
    '结果尚未确认，重试会使用原请求标识与原内容。': ['The result is unconfirmed. Retry uses the original request ID and content.', 'Das Ergebnis ist unbestätigt. Wiederholen verwendet die ursprüngliche Anfrage-ID und den ursprünglichen Inhalt.'],
    '原版本缺失，请刷新列表后重新选择。': ['The original version is missing. Refresh and select again.', 'Die Originalversion fehlt. Aktualisieren und erneut auswählen.'],
    '一次最多选择 100 条记录。': ['Select at most 100 records per batch.', 'Höchstens 100 Datensätze pro Änderung auswählen.'],
    '最多同时使用 8 项字段筛选。': ['Use at most 8 field filters.', 'Höchstens 8 Feldfilter verwenden.'],
    '请先选择记录。': ['Select records first.', 'Zuerst Datensätze auswählen.'],
    '请在当前主录中选择记录。': ['Select records from the current authoritative table.', 'Datensätze aus der aktuellen Haupttabelle auswählen.'],
    '此字段受保护，不能批量修改。': ['This field is protected from batch edits.', 'Dieses Feld ist vor Sammeländerungen geschützt.'],
    '会话已失效，请刷新后重试。': ['The session expired. Refresh and retry.', 'Die Sitzung ist abgelaufen. Aktualisieren und erneut versuchen.'],
    '服务未返回有效结果，请重试原批次。': ['The server returned no valid result. Retry the original batch.', 'Keine gültige Serverantwort. Ursprüngliche Anfrage wiederholen.'],
    '整批已保存': ['Batch saved', 'Gesamte Auswahl gespeichert'],
    '此列表未提供全范围字段查询。': ['Whole-result field queries are unavailable for this list.', 'Feldabfragen über alle Treffer sind für diese Liste nicht verfügbar.'],
    '必填字段不能清空。': ['A required field cannot be cleared.', 'Ein Pflichtfeld darf nicht geleert werden.'],
    '关联记录名称搜索': ['Search linked record names', 'Verknüpfte Datensatznamen suchen'],
    '请选择': ['Please select', 'Bitte auswählen'], '全部匹配': ['All matches', 'Alle Treffer'],
    '保存期间请稍候。': ['Please wait while saving.', 'Bitte während des Speicherns warten.'],
    '请填写有效时间。': ['Enter a valid time.', 'Eine gültige Zeit eingeben.'],
  };
  Object.assign(window.ERP_MESSAGES || (window.ERP_MESSAGES = {}), labels);
  const t = text => window.ERPUI?.t(text) || text;
  const h = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const uiOriginals = new WeakMap();
  function paintLanguage(root) {
    if (!root) return;
    const sources = new Map();
    for (const [source, translations] of Object.entries(window.ERP_MESSAGES)) {
      sources.set(source, source);
      if (Array.isArray(translations)) translations.forEach(value => sources.set(value, source));
    }
    const original = value => {
      if (sources.has(value)) return sources.get(value);
      const count = value.match(/^(已选|Selected|Ausgewählt)( \d+ \/ 100)$/);
      if (count) return '已选' + count[2];
      return value.split(' · ').map(part => sources.get(part) || part).join(' · ');
    };
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement.closest('input,textarea,[data-i18n-ignore]')) continue;
      const value = node.nodeValue, saved = uiOriginals.get(node);
      const source = saved && saved.output === value ? saved.source : original(value);
      const output = source.startsWith('已选 ') ? t('已选') + source.slice(2) : source.split(' · ').map(t).join(' · ');
      uiOriginals.set(node, { source, output });
      if (value !== output) node.nodeValue = output;
    }
    root.querySelectorAll('[aria-label],[placeholder]').forEach(element => {
      for (const name of ['aria-label', 'placeholder']) {
        const value = element.getAttribute(name);
        if (value) element.setAttribute(name, t(original(value)));
      }
    });
  }
  const opLabels = { eq: '等于', ne: '不等于', contains: '包含', starts_with: '开头为', lt: '小于', lte: '不大于', gt: '大于', gte: '不小于', is_null: '为空值 NULL', not_null: '非空值 NULL', is_empty: '为空文本', not_empty: '非空文本' };
  const noValue = op => ['is_null', 'not_null', 'is_empty', 'not_empty'].includes(op);
  const source = extra => extra?.object ? 'object:' + extra.object : extra?.kind ? 'kind:' + extra.kind : '';
  const keyOf = extra => JSON.stringify([state.mode, source(extra)]);
  function setting(extra) {
    const key = keyOf(extra);
    if (!preferences.has(key)) preferences.set(key, { filters: [], sort: {} });
    return preferences.get(key);
  }
  function augmentParams(path, extra = {}) {
    if (!['list', 'explore', 'export'].includes(path) || !source(extra)) return extra;
    const value = setting(extra);
    const augmented = { ...extra, table_filters: JSON.stringify(value.filters), table_sort: JSON.stringify(value.sort) };
    if (path !== 'export') requestContexts.set(extra, { key: keyOf(extra), fingerprint: fingerprintFrom(extra, augmented) });
    return augmented;
  }
  function fingerprintFrom(extra, value) {
    return JSON.stringify([state.mode, source(extra), state.start, state.end, state.search, state.scope, state.status, state.person, state.subject, extra.date_filter ?? '1', value.table_filters, value.table_sort]);
  }
  function queryFingerprint(extra) {
    const value = augmentParams('export', extra);
    return fingerprintFrom(extra, value);
  }
  function rememberResult(path, extra, body) {
    if (!['list', 'explore'].includes(path) || !source(extra)) return;
    const request = requestContexts.get(extra) || { key: keyOf(extra), fingerprint: queryFingerprint(extra) };
    results.set(request.key, { body, fingerprint: request.fingerprint });
  }
  function refresh() { state.offset = 0; render(); }
  function options(columns, chosen = '') {
    return columns.map(col => `<option value="${h(col.name)}" ${col.name === chosen ? 'selected' : ''}>${h(t(col.name))}</option>`).join('');
  }
  function filterRow(session, value = {}) {
    const col = session.info.columns.find(col => col.name === value.field) || session.info.columns[0];
    const row = document.createElement('div');
    row.className = 'table-tools-filter';
    row.innerHTML = `<select data-tool-filter-field aria-label="${h(t('字段'))}">${options(session.info.columns, col.name)}</select><select data-tool-filter-op aria-label="${h(t('条件'))}">${col.operations.map(op => `<option value="${op}" ${op === value.op ? 'selected' : ''}>${h(t(opLabels[op]))}</option>`).join('')}</select><input data-tool-filter-value type="text" maxlength="500" aria-label="${h(t('筛选值'))}" value="${h(value.value)}"><button type="button" class="button small" data-tool-filter-remove aria-label="${h(t('移除筛选'))}">×</button>`;
    const op = row.querySelector('[data-tool-filter-op]'), input = row.querySelector('input');
    const sync = () => { input.hidden = noValue(op.value); input.required = !input.hidden; };
    row.querySelector('[data-tool-filter-field]').addEventListener('change', event => {
      const column = session.info.columns.find(col => col.name === event.target.value);
      op.innerHTML = column.operations.map(operation => `<option value="${operation}">${h(t(opLabels[operation]))}</option>`).join('');
      input.value = ''; sync();
    });
    op.addEventListener('change', sync);
    row.querySelector('button').addEventListener('click', () => row.remove());
    sync();
    return row;
  }
  function queryPanel(session) {
    const value = setting(session.extra), region = document.createElement('details');
    region.className = 'table-tools-query';
    region.innerHTML = `<summary>${h(t('字段筛选与排序'))}${value.filters.length ? ' · ' + value.filters.length : ''}</summary><form><p>${h(t('应用于全部匹配记录；分页、条数与导出使用同一条件。'))}</p><div data-tool-filters></div><div class="table-tools-query-actions"><button type="button" class="button small" data-tool-add-filter>${h(t('增加筛选'))}</button><label>${h(t('排序字段'))}<select data-tool-sort><option value="">${h(t('默认排序'))}</option>${options(session.info.columns, value.sort.field)}</select></label><select data-tool-direction aria-label="${h(t('条件'))}"><option value="asc">${h(t('升序'))}</option><option value="desc" ${value.sort.direction === 'desc' ? 'selected' : ''}>${h(t('降序'))}</option></select><button type="submit" class="button primary">${h(t('应用筛选与排序'))}</button><button type="button" class="button small" data-tool-reset>${h(t('重置表格查询'))}</button></div></form>`;
    const filters = region.querySelector('[data-tool-filters]');
    value.filters.forEach(item => filters.append(filterRow(session, item)));
    region.querySelector('[data-tool-add-filter]').addEventListener('click', () => {
      if (filters.children.length >= 8) return toast(t('最多同时使用 8 项字段筛选。'));
      filters.append(filterRow(session));
    });
    region.querySelector('form').addEventListener('submit', event => {
      event.preventDefault();
      if (session.batch?.pending) return toast(t('保存期间请稍候。'));
      value.filters = [...filters.children].map(row => ({ field: row.querySelector('select').value, op: row.querySelector('[data-tool-filter-op]').value, ...(!noValue(row.querySelector('[data-tool-filter-op]').value) ? { value: row.querySelector('input').value } : {}) }));
      const field = region.querySelector('[data-tool-sort]').value;
      value.sort = field ? { field, direction: region.querySelector('[data-tool-direction]').value } : {};
      refresh();
    });
    region.querySelector('[data-tool-reset]').addEventListener('click', () => {
      if (session.batch?.pending) return toast(t('保存期间请稍候。'));
      value.filters = []; value.sort = {}; refresh();
    });
    session.panel.querySelector('.table-wrap').before(region);
  }
  function updateSelection(session) {
    session.panel.querySelectorAll('[data-tool-row-select]').forEach(input => { input.checked = selected.has(input.dataset.id); input.disabled = !!session.batch?.pending; });
    const boxes = [...session.panel.querySelectorAll('[data-tool-row-select]')], all = session.panel.querySelector('[data-tool-select-page]');
    if (all) { all.checked = boxes.length > 0 && boxes.every(input => input.checked); all.indeterminate = boxes.some(input => input.checked) && !all.checked; all.disabled = !!session.batch?.pending || !boxes.length; }
    session.bar.querySelector('[data-tool-selected]').textContent = `${t('已选')} ${selected.size} / 100`;
    session.bar.querySelector('[data-tool-bulk-open]').disabled = !selected.size || !!session.batch?.pending;
    session.bar.querySelector('[data-tool-clear]').disabled = !selected.size || !!session.batch?.pending;
    paintLanguage(session.bar);
  }
  function selectRows(session) {
    const table = session.panel.querySelector('.table-wrap table'), header = table.tHead.rows[0];
    const th = document.createElement('th'); th.className = 'table-tools-select';
    th.innerHTML = `<input type="checkbox" data-tool-select-page aria-label="${h(t('勾选本页'))}">`; header.prepend(th);
    const versions = new Map(session.body.rows.map(row => [String(row[session.info.pk]), row._table_version]));
    table.querySelectorAll('tbody > tr').forEach(row => {
      if (!row.dataset.rowId) { if (row.cells[0]) row.cells[0].colSpan++; return; }
      const cell = row.insertCell(0); cell.className = 'table-tools-select';
      if (row.dataset.rowObject !== session.info.object) return;
      cell.innerHTML = `<input type="checkbox" data-tool-row-select data-id="${h(row.dataset.rowId)}" aria-label="${h(t('选择记录'))} ${h(row.dataset.rowId)}">`;
      cell.querySelector('input').addEventListener('change', event => {
        const id = event.target.dataset.id, version = versions.get(id);
        if (!version) { event.target.checked = false; return toast(t('原版本缺失，请刷新列表后重新选择。')); }
        if (event.target.checked && !selected.has(id) && selected.size >= 100) { event.target.checked = false; return toast(t('一次最多选择 100 条记录。')); }
        if (event.target.checked) selected.set(id, { id, version: String(version) }); else selected.delete(id);
        closeBatch(session); updateSelection(session);
      });
    });
    th.querySelector('input').addEventListener('change', event => {
      const boxes = [...session.panel.querySelectorAll('[data-tool-row-select]')];
      if (event.target.checked && new Set([...selected.keys(), ...boxes.map(box => box.dataset.id)]).size > 100) { toast(t('一次最多选择 100 条记录。')); updateSelection(session); return; }
      for (const box of boxes) {
        const id = box.dataset.id, version = versions.get(id);
        if (event.target.checked && version) selected.set(id, { id, version: String(version) }); else selected.delete(id);
      }
      closeBatch(session); updateSelection(session);
    });
    session.bar = document.createElement('div'); session.bar.className = 'table-tools-bulk-bar';
    session.bar.innerHTML = `<span data-tool-selected role="status"></span><button type="button" class="button primary" data-tool-bulk-open>${h(t('批量修改字段'))}</button><button type="button" class="button small" data-tool-clear>${h(t('清除选择'))}</button><small>${h(t('仅勾选本页显示记录，可跨页保留已选；改变查询或来源会清空选择。'))}</small>`;
    session.panel.querySelector('.table-wrap').before(session.bar);
    session.bar.querySelector('[data-tool-clear]').addEventListener('click', () => { selected.clear(); closeBatch(session); updateSelection(session); });
    session.bar.querySelector('[data-tool-bulk-open]').addEventListener('click', () => openBatch(session));
    updateSelection(session);
  }
  function closeBatch(session) {
    if (session.batch?.pending) return;
    session.batch?.region.remove(); session.batch = null;
  }
  async function entryRequest(session, path, options = {}, extra = {}) {
    const response = await fetch('/api/entry/' + path + '?' + new URLSearchParams({ mode: session.mode, ...extra }), options);
    let result;
    try { result = await response.json(); } catch { throw new Error(t('服务未返回有效结果，请重试原批次。')); }
    if (!response.ok) { const error = new Error(result.error || t('会话已失效，请刷新后重试。')); error.status = response.status; throw error; }
    return result;
  }
  function alive(session) { return current === session && session.panel.isConnected && state.mode === session.mode; }
  function modeText(session) { return t(session.mode === 'demo' ? '演示库' : '正式库'); }
  async function openBatch(session, retry = null) {
    if (!selected.size && !retry) return toast(t('请先选择记录。'));
    closeBatch(session);
    const batch = { region: document.createElement('div'), pending: false, payload: retry?.payload || null };
    batch.region.className = 'table-tools-batch'; session.batch = batch;
    session.bar.after(batch.region);
    batch.region.innerHTML = `<p role="status">${h(t('保存中…'))}</p>`;
    try {
      const metadata = await entryRequest(session, 'meta');
      if (!alive(session) || session.batch !== batch) return;
      const obj = metadata.objects.find(obj => obj.key === session.info.object);
      if (!obj || obj.retired) throw new Error(t('请在当前主录中选择记录。'));
      const protectedSet = new Set(session.info.protected_fields);
      const fields = obj.columns.filter(col => !protectedSet.has(col.name) && !col.automatic && !col.retired_reference && !hiddenIdentityField(col.name));
      if (!fields.length) throw new Error(t('此字段受保护，不能批量修改。'));
      batch.region.innerHTML = `<form><strong>${h(t('批量修改'))} · ${h(modeText(session))} · ${retry?.payload.records.length || selected.size}</strong><p>${h(t('所有选中记录改为同一内容；任一冲突或失败，整批回滚。'))}</p><div data-tool-batch-error role="alert" tabindex="-1" hidden></div><fieldset><div class="table-tools-batch-fields"><label>${h(t('字段'))}<select data-tool-batch-field>${options(fields, retry?.payload.field)}</select></label><label>${h(t('设置内容'))}<select data-tool-batch-null><option value="value">${h(t('设置内容'))}</option><option value="null">${h(t('设为空值 NULL'))}</option></select></label><div data-tool-batch-value></div></div><div class="table-tools-batch-actions"><button type="button" class="button" data-tool-batch-cancel>${h(t('取消批量修改'))}</button><button type="submit" class="button primary" data-tool-batch-save>${h(t('保存整批'))} · ${h(modeText(session))}</button></div></fieldset></form>`;
      batch.metadata = metadata; batch.obj = obj;
      const form = batch.region.querySelector('form'), field = form.querySelector('[data-tool-batch-field]'), nullMode = form.querySelector('[data-tool-batch-null]');
      const drawValue = () => {
        const col = fields.find(col => col.name === field.value), holder = form.querySelector('[data-tool-batch-value]');
        nullMode.querySelector('[value=null]').disabled = !!col.required;
        if (col.required) nullMode.value = 'value';
        if (nullMode.value === 'null') { holder.innerHTML = '<span>N/A · NULL</span>'; return; }
        let control;
        if (col.reference) control = `<input type="search" data-tool-batch-ref placeholder="${h(t('关联记录名称搜索'))}"><select data-tool-batch-input><option value="">${h(t('请选择'))}</option></select>${referenceSourceHint(col.reference.target, metadata.objects)}`;
        else if (col.type === 'boolean' || col.options.length) control = `<select data-tool-batch-input>${(col.type === 'boolean' ? ['true', 'false'] : col.options).map(value => `<option value="${h(value)}">${h(value)}</option>`).join('')}</select>`;
        else if (col.type === 'date') control = '<input type="date" data-tool-batch-input>';
        else if (col.type === 'timestamp with time zone') control = '<input type="datetime-local" step="1" data-tool-batch-input><small>UTC+8</small>';
        else control = `<textarea rows="2" maxlength="20000" data-tool-batch-input ${col.type.startsWith('numeric') || col.type === 'integer' ? 'inputmode="decimal"' : ''}></textarea>`;
        holder.innerHTML = `<label>${h(t('新内容'))}${control}</label>`;
        const input = holder.querySelector('[data-tool-batch-input]');
        input.required = !!col.required || !!col.reference || !(col.type === 'text' || col.type.startsWith('character'));
        if (col.reference) {
          let serial = 0;
          const load = async () => {
            const version = ++serial, search = holder.querySelector('[data-tool-batch-ref]').value;
            try {
              const result = await entryRequest(session, 'options', {}, { object: obj.key, field: col.name, q: search, selected: input.value });
              if (!alive(session) || session.batch !== batch || !input.isConnected || version !== serial) return;
              const selectedValue = input.value;
              input.innerHTML = `<option value="">${h(t('请选择'))}</option>` + result.rows.map(row => `<option value="${h(row.value)}" ${row.value === selectedValue ? 'selected' : ''}>${h(row.label)}</option>`).join('');
            } catch (error) { showBatchError(batch, error); }
          };
          holder.querySelector('[data-tool-batch-ref]').addEventListener('input', event => { clearTimeout(batch.timer); batch.timer = setTimeout(load, 220); });
          load();
        }
      };
      field.addEventListener('change', drawValue); nullMode.addEventListener('change', drawValue); drawValue();
      form.querySelector('[data-tool-batch-cancel]').addEventListener('click', () => closeBatch(session));
      form.addEventListener('submit', event => { event.preventDefault(); saveBatch(session, batch, fields); });
      if (retry) {
        nullMode.value = retry.payload.value === null ? 'null' : 'value'; drawValue();
        const input = form.querySelector('[data-tool-batch-input]');
        if (input) {
          if (input.tagName === 'SELECT' && ![...input.options].some(opt => opt.value === String(retry.payload.value))) input.add(new Option(String(retry.payload.value), String(retry.payload.value)));
          input.value = String(retry.payload.value);
        }
        lockPending(session, batch, false);
        showBatchError(batch, new Error(t('结果尚未确认，重试会使用原请求标识与原内容。')));
      }
      paintLanguage(batch.region);
    } catch (error) { if (alive(session)) batch.region.textContent = error.message; }
  }
  function showBatchError(batch, error) {
    const element = batch.region.querySelector('[data-tool-batch-error]');
    if (element) { element.hidden = false; element.textContent = error.message; element.focus(); }
  }
  function lockPending(session, batch, saving) {
    batch.pending = true;
    const form = batch.region.querySelector('form');
    form.querySelectorAll('input,select,textarea,[data-tool-batch-cancel]').forEach(input => { input.disabled = true; });
    const button = form.querySelector('[data-tool-batch-save]'); button.disabled = saving;
    button.textContent = t(saving ? '保存中…' : '重试原批次') + ' · ' + modeText(session);
    updateSelection(session);
  }
  async function saveBatch(session, batch, fields) {
    if (!alive(session) || batch.saving) return;
    const form = batch.region.querySelector('form');
    if (!batch.payload && !form.reportValidity()) return;
    if (!batch.payload) {
      const field = form.querySelector('[data-tool-batch-field]').value, col = fields.find(col => col.name === field), input = form.querySelector('[data-tool-batch-input]');
      let value = form.querySelector('[data-tool-batch-null]').value === 'null' ? null : input.value;
      if (value !== null && col.type === 'timestamp with time zone') {
        const parsed = new Date(value + window.ERPDefaults.utcOffset);
        if (Number.isNaN(parsed.getTime())) return showBatchError(batch, new Error(t('请填写有效时间。')));
        value = parsed.toISOString();
      }
      if (value !== null && col.type === 'boolean') value = value === 'true';
      batch.payload = { request_id: crypto.randomUUID(), object: session.info.object, field, value, records: [...selected.values()] };
    }
    batch.saving = true; uncertain.set(session.fingerprint, { payload: batch.payload }); lockPending(session, batch, true);
    try {
      const send = () => entryRequest(session, 'bulk', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-EasyERP-Token': batch.metadata.token }, body: JSON.stringify(batch.payload) });
      let result;
      try { result = await send(); } catch (error) {
        if (error.status !== 403) throw error;
        batch.metadata = await entryRequest(session, 'meta');
        if (!alive(session)) throw error;
        result = await send();
      }
      uncertain.delete(session.fingerprint); batch.pending = false;
      if (alive(session)) { selected.clear(); closeBatch(session); updateSelection(session); toast(`${t('整批已保存')} · ${modeText(session)} · ${result.count}`); }
      window.dispatchEvent(new CustomEvent('erp:data-changed', { detail: { mode: session.mode } }));
    } catch (error) {
      if (error.status && error.status < 500) {
        uncertain.delete(session.fingerprint); batch.pending = false; batch.payload = null;
        if (alive(session)) { form.querySelectorAll('input,select,textarea,button').forEach(input => { input.disabled = false; }); form.querySelector('[data-tool-batch-save]').textContent = t('保存整批') + ' · ' + modeText(session); updateSelection(session); }
      } else if (alive(session)) lockPending(session, batch, false);
      if (alive(session)) showBatchError(batch, error);
    } finally { batch.saving = false; }
  }
  function mount() {
    const panel = document.querySelector('#content .table-edit-panel');
    if (!panel) { current = null; selected.clear(); fingerprint = ''; return; }
    if (panel.dataset.tableToolsMounted) return;
    if (typeof lastList === 'undefined' || !source(lastList)) return;
    const extra = { ...lastList }, remembered = results.get(keyOf(extra)), fp = queryFingerprint(extra);
    if (!remembered || remembered.fingerprint !== fp || !remembered.body._table_tools) return;
    panel.dataset.tableToolsMounted = 'true';
    if (fp !== fingerprint) { selected.clear(); fingerprint = fp; }
    const session = { panel, extra, body: remembered.body, info: remembered.body._table_tools, mode: state.mode, fingerprint: fp, generation: ++generation };
    current = session; queryPanel(session);
    if (session.info.writable && panel.querySelector('[data-table-edit-toggle]:not(:disabled)')) selectRows(session);
    const retry = uncertain.get(fp);
    if (retry && session.bar) {
      retry.payload.records.forEach(record => selected.set(record.id, record));
      updateSelection(session); openBatch(session, retry);
    }
  }
  window.addEventListener('erp:language-changed', () => {
    if (!current) return;
    current.panel.querySelectorAll('.table-tools-query,.table-tools-bulk-bar,.table-tools-batch').forEach(paintLanguage);
    current.panel.querySelector('[data-tool-select-page]')?.setAttribute('aria-label', t('勾选本页'));
    current.panel.querySelectorAll('[data-tool-row-select]').forEach(input => input.setAttribute('aria-label', t('选择记录') + ' ' + input.dataset.id));
  });
  window.addEventListener('beforeunload', event => { if (uncertain.size) { event.preventDefault(); event.returnValue = ''; } });
  window.easyerpTableTools = { augmentParams, rememberResult, mount };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else queueMicrotask(mount);
})();
