'use strict';
window.easyerpCalculations = (() => {
  let listing, active, manager, openId = '';
  const drafts = new Map();
  const tr = text => window.ERPUI.t(text);
  const scope = () => ({ mode: state.mode, db: window.easyerpDatabaseSource.id });
  const draftKey = (source, id) => JSON.stringify([source.db, source.mode, id]);
  async function request(source, payload, action = '/save') {
    const response = await window.easyerpFetch('/api/calculations' + (payload ? action : '') + '?' + new URLSearchParams(source), payload ? {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-EasyERP-Token': listing.token }, body: JSON.stringify(payload),
    } : undefined);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || tr('无法保存计算记录'));
    return data;
  }
  function close(force = false) {
    if (!active || (active.busy && !force)) return;
    const session = active;
    if (session.editor && !session.busy) drafts.set(draftKey(session.source, session.item.id), { remarks: session.form.elements.remarks.value, board: session.editor.value(), version: session.item.version });
    session.region.remove(); session.row.classList.remove('row-details-open');
    session.row.setAttribute('aria-expanded', 'false'); session.row.removeAttribute('aria-controls');
    active = null; openId = '';
  }
  async function render() {
    close(true);
    closeManager(true);
    const source = scope();
    const response = await window.easyerpFetch('/api/calculations?' + new URLSearchParams({ ...source, search: state.search }));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    listing = { ...data, source };
    return { html: `<section class="panel calculation-list"><div class="panel-head"><h2 data-ui-label>量化计算</h2><div class="calculation-list-actions"><button class="button" data-formula-manage aria-expanded="false" data-ui-label>修改已保存的公式</button><button class="button primary" data-calculation-new data-ui-label>＋ 新建条目</button></div></div><div class="table-wrap"><table><thead><tr><th>ID</th><th data-ui-label>备注</th></tr></thead><tbody>${data.rows.map(item => `<tr data-calculation-id="${esc(item.id)}" tabindex="0" aria-expanded="false"><td><button type="button" class="table-button" data-calculation-open="${esc(item.id)}" data-i18n-ignore>${esc(item.id)}</button></td><td class="calculation-remarks" data-i18n-ignore>${esc(item.remarks) || '<span class="muted">N/A</span>'}</td></tr>`).join('') || '<tr><td colspan="2" class="muted">N/A</td></tr>'}</tbody></table></div></section>` };
  }
  function open(row) {
    if (active?.busy || manager?.busy) return;
    closeManager();
    if (active?.row === row) { close(); return; }
    close();
    const item = listing.rows.find(item => item.id === row.dataset.calculationId);
    if (!item) return;
    const source = { ...listing.source }, key = draftKey(source, item.id);
    const savedDraft = drafts.get(key), draft = savedDraft?.version === item.version ? savedDraft : item;
    const region = document.createElement('tr'); region.className = 'table-record-details'; region.id = 'calculation-' + item.id;
    region.insertCell().colSpan = 2;
    region.firstElementChild.innerHTML = `<section class="record-inline-panel calculation-board" role="region" aria-label="${tr('计算台')}"><div class="record-inline-head"><div><h3 data-ui-label>计算台</h3><span data-i18n-ignore>${esc(item.id)}</span><span class="record-inline-mode" data-ui-label>${state.mode === 'demo' ? '演示数据' : '正式数据'}</span></div><button type="button" class="button small" data-calculation-close data-ui-label>收起详情</button></div><form><fieldset><div class="calculation-layout"><div class="calculation-left"><section class="calculation-section calculation-note" aria-label="${tr('备注')}"><h4><label for="calculation-remarks-${esc(item.id)}" data-ui-label>备注</label></h4><textarea id="calculation-remarks-${esc(item.id)}" name="remarks" rows="8" maxlength="20000" aria-label="${tr('备注')}"></textarea></section><section class="calculation-section calculation-library" aria-label="${tr('备选公式')}"><h4 data-ui-label>备选公式</h4><div class="calculation-scroll calculation-library-body" data-formula-library tabindex="0" aria-label="${tr('备选公式')}"></div></section></div><div data-calculation-editor></div></div><p class="entry-error" data-error role="alert" hidden></p><div class="calculation-actions"><span data-saved data-ui-label role="status"></span><button type="submit" class="button" name="write_result" value="1" data-ui-label>结果写入备注并保存</button><button type="submit" class="button primary" data-ui-label>保存</button></div></fieldset></form></section>`;
    row.after(region); row.classList.add('row-details-open'); row.setAttribute('aria-expanded', 'true'); row.setAttribute('aria-controls', region.id);
    const form = region.querySelector('form'); form.elements.remarks.value = draft.remarks;
    const session = { row, region, form, source, item, busy: false, pending: null };
    active = session; openId = item.id;
    session.editor = window.easyerpCalculator.mount(region.querySelector('[data-calculation-editor]'), draft.board, { host: region.querySelector('[data-formula-library]'), formulas: listing.formulas });
    form.addEventListener('input', () => { region.querySelector('[data-saved]').textContent = tr('尚未保存'); });
    form.addEventListener('calculation-change', () => { region.querySelector('[data-saved]').textContent = tr('尚未保存'); });
    region.querySelector('[data-calculation-close]').onclick = () => close();
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (session.busy) return;
      const content = { id: session.item.id, version: session.item.version, remarks: form.elements.remarks.value, board: session.editor.value(), write_result: event.submitter?.name === 'write_result', save_formula: event.submitter?.name === 'save_formula' };
      const signature = JSON.stringify(content);
      if (session.pending?.signature !== signature) session.pending = { signature, payload: { ...content, request_id: crypto.randomUUID() } };
      session.busy = true; form.querySelector('fieldset').disabled = true; region.querySelector('[data-calculation-close]').disabled = true;
      region.querySelector('[data-saved]').textContent = tr('正在保存');
      const error = region.querySelector('[data-error]'); error.hidden = true;
      try {
        const data = await request(source, session.pending.payload);
        session.item = data.item; drafts.delete(key); session.pending = null;
        if (active !== session || !region.isConnected) return;
        const index = listing.rows.findIndex(row => row.id === data.item.id); listing.rows[index] = data.item;
        form.elements.remarks.value = data.item.remarks;
        listing.formulas = data.formulas || [];
        session.editor.setFormulas(listing.formulas);
        row.querySelector('.calculation-remarks').textContent = data.item.remarks || 'N/A';
        region.querySelector('[data-saved]').textContent = tr('已保存');
      } catch (failure) {
        if (active === session) { error.textContent = failure.message; error.hidden = false; region.querySelector('[data-saved]').textContent = tr('尚未保存'); }
      } finally {
        session.busy = false; form.querySelector('fieldset').disabled = false; region.querySelector('[data-calculation-close]').disabled = false;
      }
    });
    form.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!session.busy) close(); }
    });
  }
  function closeManager(force = false) {
    if (!manager || (manager.busy && !force)) return;
    manager.region.remove(); manager = null;
    document.querySelector('[data-formula-manage]')?.setAttribute('aria-expanded', 'false');
  }
  async function manageFormulas() {
    if (active?.busy || manager?.busy) return;
    if (manager) { closeManager(); return; }
    close();
    const source = { ...listing.source }, response = await request(source);
    if (JSON.stringify(scope()) !== JSON.stringify(source) || route !== 'calculations') return;
    listing.formulas = response.formulas;
    const region = document.createElement('section'); region.className = 'calculation-formula-manager';
    region.setAttribute('aria-label', tr('修改已保存的公式'));
    region.innerHTML = `<div class="panel-head"><h3 data-ui-label>修改已保存的公式</h3><button type="button" class="button small" data-manager-close data-ui-label>关闭</button></div><div class="calculation-manager-layout"><div class="calculation-scroll" data-manager-library tabindex="0" aria-label="${tr('备选公式')}"></div><form><fieldset><div data-template-editor></div><p class="entry-error" data-template-error role="alert" hidden></p><div class="calculation-actions"><span data-template-status data-ui-label role="status"></span><button class="button primary" type="submit" data-template-save data-ui-label>保存公式修改</button></div></fieldset></form></div>`;
    document.querySelector('.calculation-list > .table-wrap').before(region);
    document.querySelector('[data-formula-manage]').setAttribute('aria-expanded', 'true');
    const session = { region, source, busy: false, pending: null, selected: null, editor: null, drafts: new Map() };
    manager = session;
    const form = region.querySelector('form'), library = region.querySelector('[data-manager-library]');
    function select(formula) {
      if (session.busy) return;
      if (session.selected) session.drafts.set(session.selected.id, session.editor.value());
      session.selected = formula;
      session.editor = window.easyerpCalculator.mountFormulaEditor(region.querySelector('[data-template-editor]'), { ...formula, ...session.drafts.get(formula.id) });
      region.querySelector('[data-template-status]').textContent = '';
      region.querySelector('[data-template-error]').hidden = true;
      showLibrary();
    }
    function showLibrary() {
      window.easyerpCalculator.renderLibrary(library, listing.formulas, formula => formula.id === session.selected?.id, select);
    }
    showLibrary();
    if (listing.formulas.length) select(listing.formulas[0]);
    else { form.hidden = true; library.classList.add('calculation-manager-empty'); }
    region.querySelector('[data-manager-close]').onclick = () => closeManager();
    form.addEventListener('input', () => { region.querySelector('[data-template-status]').textContent = tr('尚未保存'); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (session.busy || !session.selected) return;
      const content = { id: session.selected.id, version: session.selected.version, ...session.editor.value() };
      const signature = JSON.stringify(content);
      if (session.pending?.signature !== signature) session.pending = { signature, payload: { ...content, request_id: crypto.randomUUID() } };
      session.busy = true; form.querySelector('fieldset').disabled = true; library.inert = true;
      region.querySelector('[data-manager-close]').disabled = true;
      const status = region.querySelector('[data-template-status]'), error = region.querySelector('[data-template-error]');
      status.textContent = tr('正在保存'); error.hidden = true;
      try {
        const result = await request(source, session.pending.payload, '/formulas/save');
        if (manager !== session) return;
        listing.formulas = result.formulas; session.selected = result.formula; session.pending = null;
        session.drafts.delete(result.formula.id); showLibrary();
        status.textContent = tr('已保存');
      } catch (failure) {
        if (manager === session) { error.textContent = failure.message; error.hidden = false; status.textContent = tr('尚未保存'); }
      } finally {
        session.busy = false; form.querySelector('fieldset').disabled = false; library.inert = false;
        region.querySelector('[data-manager-close]').disabled = false;
      }
    });
  }
  let creating, createPending;
  async function create() {
    if (!listing || creating || manager?.busy) return;
    const source = { ...listing.source };
    const button = document.querySelector('[data-calculation-new]');
    creating = true; if (button) button.disabled = true;
    try {
      if (createPending?.source !== JSON.stringify(source)) createPending = { source: JSON.stringify(source), payload: { request_id: crypto.randomUUID(), remarks: '', board: {} } };
      const data = await request(source, createPending.payload);
      createPending = null;
      if (route !== 'calculations' || state.mode !== source.mode) return;
      state.search = ''; $('#search').value = ''; sync();
      await window.render();
      const row = document.querySelector(`[data-calculation-id="${data.item.id}"]`);
      if (row) { open(row); row.nextElementSibling.querySelector('textarea').focus(); }
    } catch (error) { toast(error.message); }
    finally { creating = false; if (button?.isConnected) button.disabled = false; }
  }
  document.addEventListener('click', event => {
    if (event.target.closest('[data-formula-manage]')) { manageFormulas().catch(error => toast(error.message)); return; }
    if (event.target.closest('[data-calculation-new]')) { create(); return; }
    const row = event.target.closest('[data-calculation-id]');
    if (row) open(row);
  });
  document.addEventListener('keydown', event => {
    if (event.target.matches('[data-calculation-id]') && ['Enter', ' '].includes(event.key)) { event.preventDefault(); open(event.target); }
  });
  return { render, create, close, get openId() { return openId; } };
})();
Object.assign(window.ERP_MESSAGES, {
  '量化计算': ['Quantitative calculations', 'Quantitative Berechnungen'], '计算台': ['Calculation board', 'Rechenblatt'],
  '＋ 新建条目': ['＋ New entry', '＋ Neuer Eintrag'], '结果写入备注并保存': ['Write result to remarks and save', 'Ergebnis in Bemerkung speichern'],
  '尚未保存': ['Unsaved', 'Nicht gespeichert'], '已保存': ['Saved', 'Gespeichert'],
  '正在保存': ['Saving', 'Wird gespeichert'],
  '修改已保存的公式': ['Edit saved formulas', 'Gespeicherte Formeln bearbeiten'],
  '保存公式修改': ['Save formula changes', 'Formeländerungen speichern'],
  '无法保存计算记录': ['Cannot save calculation', 'Berechnung kann nicht gespeichert werden'],
});
