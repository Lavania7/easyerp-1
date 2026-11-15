'use strict';
(() => {
  const h = (value) =>
    String(value ?? '').replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
    );
  const dialog = document.createElement('dialog');
  dialog.id = 'standard-templates';
  dialog.className = 'template-dialog';
  dialog.setAttribute('aria-label', '标准主录表下载');
  document.body.append(dialog);
  let catalog = null,
    mode = 'live',
    selected = '',
    department = '',
    filter = '',
    busy = false,
    lastFocus = null,
    job = 0;
  const current = () => catalog?.objects.find((obj) => obj.key === selected);

  function fieldType(type) {
    if (type === 'text' || type.startsWith('character')) return '文本';
    if (type === 'date') return '日期（YYYY-MM-DD）';
    if (type.startsWith('timestamp'))
      return '日期时间' + (type.includes('with time zone') ? '（含时区）' : '');
    if (['integer', 'bigint', 'smallint'].includes(type)) return '整数';
    const numeric = type.match(/^numeric\(\d+,(\d+)\)$/);
    if (numeric) return '数字，最多' + numeric[1] + '位小数';
    if (type.startsWith('numeric') || type === 'real' || type === 'double precision') return '数字';
    if (type === 'boolean') return '布尔值（true / false）';
    return type;
  }

  function notice(message, error = false) {
    const box = dialog.querySelector('#template-notice');
    box.hidden = !message;
    box.classList.toggle('error', error);
    box.textContent = message;
  }

  function shell() {
    dialog.innerHTML = `<div class="template-head"><div><span class="template-mode">${mode === 'demo' ? '演示表结构' : '正式表结构'}</span><h2>标准主录表下载</h2><p>选择一张主录表，下载空白CSV后填写。</p></div><button type="button" class="icon-button" data-template-close aria-label="关闭标准主录表下载">×</button></div>
      <div class="template-body"><div id="template-notice" class="template-notice" role="status" hidden></div><div id="template-chooser"><p class="template-loading">正在读取主录表字段…</p></div>
      <p class="template-format-note">CSV只保存表头和数据，不能保存行高、列宽或样式。用Excel打开后，可全选并自动调整列宽与行高；这些设置不会写入CSV。编号、账号等文本列请先设为文本格式。</p></div>
      <div class="template-footer"><span id="template-file-note" data-i18n-ignore>UTF-8中文CSV · 首行为原字段名</span><div><button type="button" class="button" data-template-close>关闭</button><button type="button" class="button primary" id="template-download" disabled>下载CSV</button></div></div>`;
  }

  function chooser() {
    const box = dialog.querySelector('#template-chooser');
    box.innerHTML = `<div class="template-tools"><label>部门<select id="template-department" aria-label="选择主录表部门"><option value="">全部部门</option>${catalog.departments.map((item) => `<option value="${h(item.id)}" ${department === item.id ? 'selected' : ''}>${h(item.name)}（${item.count}）</option>`).join('')}</select></label><label>查找主录表<input id="template-search" type="search" placeholder="搜索表名或字段" aria-label="搜索标准主录表"></label></div>
      <label class="template-select-label">主录表<select id="template-object" aria-label="选择标准主录表"></select></label><p id="template-count" class="template-count"></p><div id="template-preview"></div>`;
    updateList();
  }

  function updateList() {
    const needle = filter.trim().toLocaleLowerCase();
    const rows = catalog.objects.filter(
      (obj) =>
        (!department || obj.schema === department) &&
        (!needle ||
          [
            obj.name,
            obj.key,
            obj.department,
            window.ERPUI?.t(obj.name),
            ...obj.columns.map((c) => c.name),
          ]
            .join(' ')
            .toLocaleLowerCase()
            .includes(needle))
    );
    if (!rows.some((obj) => obj.key === selected)) selected = '';
    const select = dialog.querySelector('#template-object');
    select.innerHTML =
      '<option value="">' +
      (rows.length ? '请选择主录表' : '没有匹配的主录表') +
      '</option>' +
      rows
        .map(
          (obj) =>
            `<option value="${h(obj.key)}" ${selected === obj.key ? 'selected' : ''}>${h(obj.department)} · ${h(obj.name)}</option>`
        )
        .join('');
    select.disabled = !rows.length;
    dialog.querySelector('#template-count').textContent =
      `${rows.length}张主录表可选，共${catalog.objects.length}张`;
    preview();
  }

  function preview() {
    const obj = current();
    dialog.querySelector('#template-download').disabled = busy || !obj;
    const box = dialog.querySelector('#template-preview');
    if (!obj) {
      box.innerHTML = '<p class="template-empty">选择主录表后，可查看字段和填写要求。</p>';
      dialog.querySelector('#template-file-note').textContent = 'UTF-8中文CSV · 首行为原字段名';
      return;
    }
    dialog.querySelector('#template-file-note').textContent = obj.filename;
    box.innerHTML = `<div class="template-preview-head"><h3>${h(obj.name)}</h3><span>${obj.columns.length}个字段 · 按现有字段顺序</span></div>
      <div class="template-fields"><table><thead><tr><th>字段名</th><th>填写格式</th><th>填写要求</th></tr></thead><tbody>${obj.columns
        .map((column) => {
          const rules = [];
          if (column.primary) rules.push('记录编号；留空自动生成');
          if (column.automatic) rules.push('系统计算，留空');
          else if (!column.primary) rules.push('可留空，导入前确认空缺信息');
          if (column.reference)
            rules.push(
              '关联：' +
                column.reference.table.split('.').slice(1).join('.') +
                ' · ' +
                column.reference.field
            );
          if (column.options?.length) rules.push('可选：' + column.options.join('、'));
          return `<tr><td data-i18n-ignore>${h(column.name)}</td><td>${h(fieldType(column.type))}</td><td>${rules.map(h).join('<br>')}</td></tr>`;
        })
        .join('')}</tbody></table></div>
      ${obj.rules.length ? `<details class="template-rules"><summary>查看字段之间的填写规则</summary><ul>${obj.rules.map((rule) => `<li>${h(rule)}</li>`).join('')}</ul></details>` : ''}
      <p class="template-hint">CSV仅含原字段名表头。请保留表头名称和顺序，从第2行开始填写，每行一条记录。</p>`;
  }

  async function open() {
    lastFocus = document.activeElement;
    mode = state.mode;
    catalog = null;
    selected = '';
    filter = '';
    busy = false;
    const schema = {
      inventory: 'production',
      production: 'production',
      sales: 'sales',
      finance: 'finance',
      rd: 'rd',
      legal: 'legal',
      analysis: 'analysis',
    }[route];
    department = schema || '';
    const request = ++job;
    shell();
    if (!dialog.open) dialog.showModal();
    try {
      const response = await window.easyerpFetch('/api/templates/meta?' + new URLSearchParams({ mode }));
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || '暂时无法读取主录表字段。');
      if (request !== job || !dialog.open) return;
      catalog = body;
      chooser();
      dialog.querySelector('#template-object').focus();
    } catch (error) {
      if (request !== job || !dialog.open) return;
      dialog.querySelector('#template-chooser').innerHTML =
        '<button type="button" class="button" data-template-retry>重新读取</button>';
      notice(error.message, true);
    }
  }

  async function download() {
    const obj = current();
    if (!obj || busy) return;
    const request = job;
    busy = true;
    const button = dialog.querySelector('#template-download');
    button.disabled = true;
    button.textContent = '正在准备…';
    notice('');
    try {
      const response = await window.easyerpFetch(
        '/api/templates/download?' + new URLSearchParams({ mode, object: obj.key })
      );
      if (!response.ok) {
        let error;
        try {
          error = await response.json();
        } catch {}
        throw new Error(error?.error || '暂时无法下载，请重试。');
      }
      const blob = await response.blob();
      if (request !== job || !dialog.open) return;
      const url = URL.createObjectURL(blob),
        anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = obj.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notice('已下载：' + obj.filename);
    } catch (error) {
      if (request === job && dialog.open) notice(error.message, true);
    } finally {
      if (request === job && dialog.open) {
        busy = false;
        button.textContent = '下载CSV';
        preview();
      }
    }
  }

  function close() {
    job++;
    busy = false;
    dialog.close();
    lastFocus?.focus();
  }
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    close();
  });
  dialog.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') event.stopPropagation();
  });
  dialog.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.hasAttribute('data-template-close')) close();
    else if (button.hasAttribute('data-template-retry')) open();
    else if (button.id === 'template-download') download();
  });
  dialog.addEventListener('change', (event) => {
    if (event.target.id === 'template-department') {
      department = event.target.value;
      notice('');
      updateList();
    } else if (event.target.id === 'template-object') {
      selected = event.target.value;
      notice('');
      preview();
    }
  });
  dialog.addEventListener('input', (event) => {
    if (event.target.id === 'template-search') {
      filter = event.target.value;
      notice('');
      updateList();
    }
  });
  document.querySelector('#templates-open').addEventListener('click', open);
})();
