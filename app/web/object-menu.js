'use strict';
window.easyerpObjectMenu = (() => {
  const escape = (text) => String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  // First matching business family wins; every available object remains a leaf.
  const families = [
    ['交付', /^交付/], ['BOM', /^BOM/], ['产品', /^产品/], ['物料', /^物料/],
    ['生产', /^(生产|工单)/], ['库存', /^库存/], ['采购', /^采购/],
    ['仓储', /^(仓库|仓储|库位|保管方)/], ['供应商', /^供应商/],
    ['销售订单', /^销售订单/], ['销售', /^(销售|合同订单)/],
    ['客户', /^客户/], ['商品', /^(商品|组合商品|订单组合)/],
    ['平台与渠道', /^(平台|渠道|订单导出)/], ['售后', /^售后/],
    ['项目', /^项目/], ['研发', /^研发/], ['发布', /^发布/], ['设计', /^设计/],
    ['计量', /^(计量|单位)/], ['利润表', /^利润表/], ['现金流量表', /^现金流量表/],
    ['资产负债表', /^资产负债表/], ['会计', /^会计/], ['发票', /^发票/],
    ['资金', /^(资金|流水|内部划转|重复记录)/], ['账户', /^账户/],
    ['税务', /^(税款|纳税)/], ['财务报表', /^报表/], ['资产', /^资产/],
    ['分析报告', /^(分析报告|报告)/], ['意见', /^意见/], ['指标', /^指标/],
    ['数据', /^数据/], ['法律与规则', /^(法律|法规|适用规则|合同审阅)/],
  ];
  function groupName(object) {
    const name = object.label || object.name;
    return families.find(([, pattern]) => pattern.test(object.name))?.[0] || name.replace(/(登记表|记录表|档案表|明细表|对应表|表)$/, '');
  }
  function render(objects, current) {
    const groups = new Map();
    for (const object of objects) {
      const group = groupName(object);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(object);
    }
    const selected = current.schema + '.' + current.name;
    return `<div class="object-picker"><button id="object-filter" type="button" class="object-select object-picker-trigger" value="${escape(selected)}" aria-label="选择主录" aria-haspopup="menu" aria-expanded="false" aria-controls="object-picker-menu"><span>${escape(current.label || current.name)}</span><span class="object-chevron" aria-hidden="true">▾</span></button><div id="object-picker-menu" class="object-picker-menu" role="menu" aria-label="业务分类" hidden><div class="object-group-list" role="none">${[...groups].map(([label, members], index) => `<button type="button" role="menuitem" class="object-group ${members.includes(current) ? 'is-current' : ''}" data-object-group="${index}" aria-haspopup="menu" aria-expanded="false" aria-controls="object-submenu-${index}"><span>${escape(label)}</span><span aria-hidden="true">▸</span></button>`).join('')}</div>${[...groups].map(([label, members], index) => `<div id="object-submenu-${index}" class="object-submenu" role="menu" aria-label="${escape(label)}" data-object-submenu="${index}" hidden>${members.map((object) => { const value = object.schema + '.' + object.name; return `<button type="button" role="menuitemradio" aria-checked="${value === selected}" data-object-value="${escape(value)}"><span>${escape(object.label || object.name)}</span><span class="object-menu-check" aria-hidden="true">${value === selected ? '✓' : ''}</span></button>`; }).join('')}</div>`).join('')}</div></div>`;
  }
  let active = null, anchor = null;
  function close(focus = false) {
    if (!active) return;
    const trigger = active.querySelector('.object-picker-trigger');
    active.querySelector('.object-picker-menu').hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (focus && trigger.isConnected) trigger.focus();
    active = null;
    anchor = null;
  }
  function showGroup(button) {
    const picker = button.closest('.object-picker');
    picker.querySelectorAll('[data-object-group]').forEach((el) => el.setAttribute('aria-expanded', String(el === button)));
    picker.querySelectorAll('[data-object-submenu]').forEach((el) => { el.hidden = el.dataset.objectSubmenu !== button.dataset.objectGroup; });
  }
  function revealInColumn(element) {
    if (!element) return;
    const column = element.parentElement, item = element.getBoundingClientRect(), bounds = column.getBoundingClientRect();
    // Scroll only this column; scrollIntoView can also move the page and close the menu.
    if (item.top < bounds.top + 3) column.scrollTop -= bounds.top + 3 - item.top;
    else if (item.bottom > bounds.bottom - 3) column.scrollTop += item.bottom - bounds.bottom + 3;
  }
  function open(picker) {
    close();
    active = picker;
    const trigger = picker.querySelector('.object-picker-trigger'), menu = picker.querySelector('.object-picker-menu');
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    const current = picker.querySelector('.object-group.is-current') || picker.querySelector('.object-group');
    showGroup(current);
    const rect = trigger.getBoundingClientRect();
    anchor = { left: rect.left, top: rect.top };
    // Both columns share one floating surface, so the pointer never crosses a gap.
    menu.style.width = Math.min(560, innerWidth - 24) + 'px';
    menu.style.left = Math.max(12, Math.min(rect.left, innerWidth - menu.offsetWidth - 12)) + 'px';
    // A definite height constrains the grid row, giving each column its own scrollport.
    menu.style.height = 'auto';
    menu.style.maxHeight = 'none';
    const naturalHeight = Math.max(160, menu.scrollHeight + 2);
    const below = Math.max(0, innerHeight - rect.bottom - 18), above = Math.max(0, rect.top - 18);
    const upwards = below < Math.min(240, naturalHeight) && above > below;
    menu.style.height = Math.min(440, naturalHeight, upwards ? above : below) + 'px';
    menu.style.top = (upwards ? rect.top - menu.offsetHeight - 6 : rect.bottom + 6) + 'px';
    revealInColumn(current);
    revealInColumn(picker.querySelector('[data-object-value][aria-checked="true"]'));
  }
  document.addEventListener('click', (event) => {
    const trigger = event.target.closest('.object-picker-trigger');
    if (trigger) { active === trigger.closest('.object-picker') ? close() : open(trigger.closest('.object-picker')); return; }
    const group = event.target.closest('[data-object-group]');
    if (group) { showGroup(group); return; }
    const leaf = event.target.closest('[data-object-value]');
    if (leaf) {
      const input = leaf.closest('.object-picker').querySelector('.object-picker-trigger');
      input.value = leaf.dataset.objectValue;
      close(true);
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return;
    }
    close();
  });
  document.addEventListener('pointerover', (event) => {
    const group = event.target.closest('[data-object-group]');
    if (group && group.closest('.object-picker') === active) showGroup(group);
  });
  document.addEventListener('focusin', (event) => {
    const group = event.target.closest('[data-object-group]');
    if (group && group.closest('.object-picker') === active) showGroup(group);
    if (active && !active.contains(event.target)) close();
  });
  document.addEventListener('keydown', (event) => {
    const picker = event.target.closest('.object-picker');
    if (!picker) return;
    const trigger = picker.querySelector('.object-picker-trigger');
    if (event.key === 'Escape' && active === picker) { event.preventDefault(); close(true); return; }
    if (event.key === 'Tab') { close(); return; }
    if (event.target === trigger && ['ArrowDown', 'ArrowUp', 'ArrowRight'].includes(event.key)) {
      event.preventDefault(); open(picker); (picker.querySelector('.object-group.is-current') || picker.querySelector('.object-group')).focus(); return;
    }
    if (!active) return;
    const group = event.target.closest('[data-object-group]');
    if (event.key === 'ArrowRight' && group) { event.preventDefault(); showGroup(group); picker.querySelector('.object-submenu:not([hidden]) button')?.focus(); return; }
    if (event.key === 'ArrowLeft' && event.target.closest('.object-submenu')) { event.preventDefault(); picker.querySelector('[data-object-group][aria-expanded="true"]').focus(); return; }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const buttons = [...event.target.parentElement.querySelectorAll('button')], index = buttons.indexOf(event.target);
      buttons[event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    }
  });
  window.addEventListener('resize', () => close());
  window.addEventListener('scroll', (event) => {
    if (!active || (event.target instanceof Node && active.contains(event.target))) return;
    const rect = active.querySelector('.object-picker-trigger').getBoundingClientRect();
    // A queued scroll from bringing the trigger into view must not close the newly opened menu.
    if (Math.abs(rect.left - anchor.left) > .5 || Math.abs(rect.top - anchor.top) > .5) close();
  }, true);
  window.addEventListener('hashchange', () => close());
  Object.assign(window.ERP_MESSAGES, {
    '业务分类': ['Business categories', 'Geschäftskategorien'], '交付': ['Delivery', 'Lieferung'],
    '产品': ['Products', 'Produkte'], '物料': ['Materials', 'Materialien'], '采购': ['Purchasing', 'Einkauf'],
    '仓储': ['Warehousing', 'Lagerhaltung'], '供应商': ['Suppliers', 'Lieferanten'],
    '客户': ['Customers', 'Kunden'], '商品': ['Merchandise', 'Waren'],
    '平台与渠道': ['Platforms and channels', 'Plattformen und Kanäle'], '售后': ['After-sales', 'Kundendienst'],
    '项目': ['Projects', 'Projekte'], '发布': ['Releases', 'Freigaben'], '设计': ['Design', 'Entwicklung'],
    '计量': ['Measurement', 'Maßeinheiten'], '会计': ['Accounting', 'Buchhaltung'], '发票': ['Invoices', 'Rechnungen'],
    '资金': ['Funds', 'Zahlungsmittel'], '账户': ['Accounts', 'Konten'], '税务': ['Tax', 'Steuern'],
    '财务报表': ['Financial statements', 'Finanzberichte'], '资产': ['Assets', 'Vermögenswerte'],
    '意见': ['Recommendations', 'Empfehlungen'], '指标': ['Metrics', 'Kennzahlen'], '数据': ['Data', 'Daten'],
    '法律与规则': ['Law and rules', 'Recht und Regeln'],
    '人员': ['People', 'Personal'], '往来未结': ['Open balances', 'Offene Posten'],
    '收入成本确认': ['Revenue and cost recognition', 'Erlös- und Kostenerfassung'],
    '费用归属': ['Expense allocation', 'Kostenzuordnung'], '公司主体': ['Company entities', 'Unternehmen'],
    '到货': ['Arrivals', 'Wareneingang'], '发货': ['Dispatch', 'Versand'],
    '委外物料流转': ['Subcontracted material movements', 'Materialfluss bei Fremdfertigung'],
    '完工': ['Completion', 'Fertigstellung'], '报废': ['Scrap', 'Ausschuss'],
    '设备': ['Equipment', 'Anlagen'], '质量检验': ['Quality checks', 'Qualitätsprüfung'],
    '验收': ['Acceptance', 'Abnahme'], '库存': ['Inventory', 'Bestand'],
    '销售订单': ['Sales orders', 'Verkaufsaufträge'],
  });
  return { render, groupName };
})();
