'use strict';
window.easyerpMappingView = (() => {
  const axes = [['plans', '历史计划'], ['workflow', '工作流'], ['data', '活动数据'], ['archive', '静态数据'], ['audit', '审计'], ['delivery', '部门交付'], ['history', '历史来源']];
  const width = 220, height = 138;
  let model, controller, surfaces, selected = '', saved = { x: 0, y: 0 };
  const objectKey = (o) => o.schema + '.' + o.name;
  function cellFor(object) { return object && axes.some(([key]) => key === object.area) ? object.area + ':' + object.schema : ''; }
  async function render() {
    const departments = window.easyerpWorkspace.navigation().departments;
    const objects = new Map(meta.objects.map((o) => [objectKey(o), o]));
    const cells = new Map(axes.flatMap(([area]) => departments.map(([department]) => [area + ':' + department, { count: 0, objects: [] }])));
    for (const object of objects.values()) {
      const cell = cells.get(cellFor(object));
      if (cell) { cell.count++; cell.objects.push(object.label || object.name); }
    }
    const edges = new Map();
    function add(from, to, evidence) {
      if (from === to || !cells.has(from) || !cells.has(to)) return;
      const key = from + '>' + to;
      if (!edges.has(key)) edges.set(key, { from, to, evidence: [] });
      edges.get(key).evidence.push(evidence);
    }
    for (const reference of meta.references || []) {
      const from = reference.source_schema + '.' + reference.source_table;
      const to = reference.target_schema + '.' + reference.target_table;
      add(cellFor(objects.get(from)), cellFor(objects.get(to)), from + '.' + reference.source_column + ' → ' + to + '.' + reference.target_column + ' [FK]');
    }
    const aliases = { finance: ['finance', '财务', '财务部', 'fin'], legal: ['legal', '法务', '法务部', 'leg'], production: ['production', '生产', '生产部', '采购与库存', '生产实绩', 'prd'], rd: ['rd', '研发', '研发部', 'r&d', 'rnd'], sales: ['sales', '销售', '销售部', 'sal'], analysis: ['analysis', '分析', '分析部', '数据分析', '分析报告', 'ana'] };
    const departmentOf = (item) => departments.find(([key]) => aliases[key].includes(String(item.values.department || '').trim().toLowerCase()))?.[0];
    const payloads = await Promise.all(['plan', 'workflow', 'report'].map(async (kind) => {
      const response = await window.easyerpFetch('/api/workspace?' + new URLSearchParams({ mode: state.mode, kind, start: '', end: '' }));
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '无法读取矩阵来源');
      return data.rows;
    }));
    const items = payloads.flat(), byId = new Map(items.map((item) => [item.id, item]));
    const areaOf = { plan: 'plans', workflow: 'workflow', report: 'audit' };
    const itemCell = (item) => item && departmentOf(item) ? areaOf[item.kind] + ':' + departmentOf(item) : '';
    let unassigned = 0;
    for (const item of items) {
      const from = itemCell(item), cell = cells.get(from);
      if (cell) { cell.count++; cell.objects.push(item.values.title); } else unassigned++;
      if (item.values.plan_id && byId.has(item.values.plan_id)) add(from, itemCell(byId.get(item.values.plan_id)), item.id + ' → ' + item.values.plan_id + ' [plan_id]');
      for (const line of String(item.values.links || '').split('\n')) {
        const split = line.indexOf(':');
        if (split < 0) continue;
        const object = line.slice(0, split), id = line.slice(split + 1);
        if (id && objects.has(object)) add(from, cellFor(objects.get(object)), item.id + ' → ' + object + ':' + id + ' [links]');
      }
    }
    model = { departments, cells, edges: [...edges.values()] };
    return { html: `<section class="mapping-view" aria-label="矩阵关系图"><p class="mapping-hint">选择方格查看已知引用；再次选择取消。箭头：引用方 → 被引用主录。FK 表示外键结构，工作空间引用来自实际记录，不代表已发生交易。${unassigned ? ` ${unassigned} 条未指定部门的工作空间记录保留在原入口，不推定归属。` : ''}</p><div class="mapping-layout"><div class="mapping-corner">内容 / 部门</div><div class="mapping-top" tabindex="0" aria-label="部门横轴"><div style="width:${departments.length * width}px">${departments.map(([, label]) => `<div style="width:${width}px">${esc(label)}</div>`).join('')}</div></div><div class="mapping-left" tabindex="0" aria-label="内容纵轴"><div style="height:${axes.length * height}px">${axes.map(([, label]) => `<div style="height:${height}px">${esc(label)}</div>`).join('')}</div></div><div class="mapping-scroll" tabindex="0" aria-label="可拖动矩阵网格"><div class="mapping-canvas" style="width:${departments.length * width}px;height:${axes.length * height}px"><div class="mapping-cells">${axes.flatMap(([area, label]) => departments.map(([department, name]) => {
      const key = area + ':' + department, cell = cells.get(key);
      if (!cell.count) return `<div class="mapping-empty" data-mapping-empty="${key}" aria-hidden="true" style="width:${width}px;height:${height}px"></div>`;
      return `<button type="button" class="mapping-cell" data-mapping-cell="${key}" aria-pressed="false" style="width:${width}px;height:${height}px"><strong>${esc(name)} / ${esc(label)}</strong><span>${cell.count} 个已知主录 / 记录</span><small>${esc(cell.objects.slice(0, 3).join('、')) || '暂无已知来源'}</small></button>`;
    })).join('')}</div><svg class="mapping-arrows" width="${departments.length * width}" height="${axes.length * height}" aria-hidden="true"></svg></div></div></div><div class="mapping-evidence" aria-live="polite"></div></section>` };
  }
  function mounted() {
    const root = document.querySelector('.mapping-view');
    if (!root || !model) return;
    controller = new AbortController();
    const nav = document.getElementById('nav'), top = document.getElementById('department-bar');
    surfaces = { nav, top, navNodes: [...nav.childNodes], topNodes: [...top.childNodes] };
    nav.innerHTML = `<div class="mapping-navigation"><button type="button" class="nav-option nav-dashboard active" data-dashboard-toggle aria-pressed="true">${icon('overview')}<span>矩阵关系图</span></button></div><div class="mapping-external-left" tabindex="0" aria-label="内容纵轴"><div style="height:${axes.length * height}px">${axes.map(([key, label]) => `<button type="button" data-mapping-row="${key}" style="height:${height}px">${esc(label)}</button>`).join('')}</div></div>`;
    top.classList.add('mapping-external-top');
    top.innerHTML = `<div style="width:${model.departments.length * width}px">${model.departments.map(([key, label]) => `<button type="button" data-mapping-column="${key}" style="width:${width}px">${esc(label)}</button>`).join('')}</div>`;
    const options = { signal: controller.signal }, left = nav.querySelector('.mapping-external-left'), scroll = root.querySelector('.mapping-scroll');
    scroll.scrollLeft = saved.x; scroll.scrollTop = saved.y;
    const sync = () => { top.scrollLeft = scroll.scrollLeft; left.scrollTop = scroll.scrollTop; saved = { x: scroll.scrollLeft, y: scroll.scrollTop }; };
    const fitAxes = () => {
      top.firstElementChild.style.width = (model.departments.length * width + scroll.offsetWidth - scroll.clientWidth) + 'px';
      root.querySelector('.mapping-canvas').style.height = (axes.length * height + Math.max(0, scroll.clientHeight - left.clientHeight)) + 'px';
      left.firstElementChild.style.height = (axes.length * height) + 'px';
      sync();
    };
    window.addEventListener('resize', fitAxes, options);
    scroll.addEventListener('scroll', sync, options);
    top.addEventListener('scroll', () => { scroll.scrollLeft = top.scrollLeft; }, options);
    left.addEventListener('scroll', () => { scroll.scrollTop = left.scrollTop; }, options);
    top.addEventListener('wheel', (event) => { event.preventDefault(); scroll.scrollLeft += event.deltaX || event.deltaY; }, { ...options, passive: false });
    const position = (key) => {
      const [area, department] = key.split(':');
      return { column: model.departments.findIndex(([d]) => d === department), row: axes.findIndex(([a]) => a === area) };
    };
    const normals = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    function curvePaths(edges) {
      const ports = new Map();
      const curves = edges.map((edge) => {
        const from = position(edge.from), to = position(edge.to);
        const dx = to.column - from.column, dy = to.row - from.row;
        let startSide, endSide;
        if (!dy && Math.abs(dx) === 1) {
          startSide = from.row === 0 ? 'bottom' : from.row === axes.length - 1 ? 'top' : dx > 0 ? 'top' : 'bottom';
          endSide = startSide;
        } else if (!dx && Math.abs(dy) === 1) {
          startSide = from.column === 0 ? 'right' : from.column === model.departments.length - 1 ? 'left' : dy > 0 ? 'right' : 'left';
          endSide = startSide;
        } else if (Math.abs(dx) > Math.abs(dy)) {
          startSide = dx > 0 ? 'right' : 'left';
          endSide = dx > 0 ? 'left' : 'right';
        } else {
          startSide = dy > 0 ? 'bottom' : 'top';
          endSide = dy > 0 ? 'top' : 'bottom';
        }
        const curve = { edge, from, to, startSide, endSide };
        for (const [end, key, side, other] of [['start', edge.from, startSide, to], ['end', edge.to, endSide, from]]) {
          const group = key + ':' + side;
          if (!ports.has(group)) ports.set(group, []);
          ports.get(group).push({ curve, end, order: ['top', 'bottom'].includes(side) ? other.column * width : other.row * height });
        }
        return curve;
      });
      for (const entries of ports.values()) {
        entries.sort((a, b) => a.order - b.order || (a.curve.edge.from + '>' + a.curve.edge.to).localeCompare(b.curve.edge.from + '>' + b.curve.edge.to));
        entries.forEach(({ curve, end }, index) => {
          const cell = end === 'start' ? curve.from : curve.to;
          const side = end === 'start' ? curve.startSide : curve.endSide;
          const fraction = .2 + .6 * (index + 1) / (entries.length + 1);
          curve[end] = ['left', 'right'].includes(side)
            ? [(cell.column + (side === 'right' ? 1 : 0)) * width, (cell.row + fraction) * height]
            : [(cell.column + fraction) * width, (cell.row + (side === 'bottom' ? 1 : 0)) * height];
        });
      }
      return curves.map(({ edge, start, end, startSide, endSide }) => {
        const dx = end[0] - start[0], dy = end[1] - start[1];
        const distance = Math.hypot(dx, dy);
        const reach = clamp(distance * .42, 48, 200);
        const bow = startSide === endSide ? 0 : clamp(distance * .14, 22, 78);
        const bend = [-dy / distance * bow, dx / distance * bow];
        const control = (point, normal) => [
          clamp(point[0] + normal[0] * reach + bend[0], 4, model.departments.length * width - 4),
          clamp(point[1] + normal[1] * reach + bend[1], 4, axes.length * height - 4),
        ];
        const a = control(start, normals[startSide]), b = control(end, normals[endSide]);
        return `<path d="M${start} C${a} ${b} ${end}" data-mapping-from="${edge.from}" data-mapping-to="${edge.to}" data-start-side="${startSide}" data-end-side="${endSide}" marker-end="url(#mapping-arrow-tip)"><title>${esc(edge.evidence.join('\n'))}</title></path>`;
      }).join('');
    }
    let emphasized = '';
    function emphasize(key = '') {
      if (key === selected || !root.querySelector(`[data-mapping-cell="${key}"]`)?.classList.contains('is-related')) key = '';
      if (key === emphasized) return;
      emphasized = key;
      const svg = root.querySelector('.mapping-arrows');
      svg.classList.toggle('has-emphasis', Boolean(key));
      svg.querySelectorAll(':scope > path').forEach((path) => {
        path.classList.toggle('is-emphasized', path.dataset.mappingFrom === key || path.dataset.mappingTo === key);
      });
    }
    function paint() {
      if (!model.cells.get(selected)?.count) selected = '';
      root.classList.toggle('has-selection', Boolean(selected));
      const edges = selected ? model.edges.filter((edge) => edge.from === selected || edge.to === selected) : [];
      const related = new Set(edges.flatMap((edge) => [edge.from, edge.to]));
      root.querySelectorAll('[data-mapping-cell]').forEach((button) => {
        const active = button.dataset.mappingCell === selected;
        button.classList.toggle('is-selected', active);
        button.classList.toggle('is-related', !active && related.has(button.dataset.mappingCell));
        button.setAttribute('aria-pressed', String(active));
      });
      const svg = root.querySelector('.mapping-arrows');
      emphasized = '';
      svg.classList.remove('has-emphasis');
      svg.innerHTML = selected ? `<defs><marker id="mapping-arrow-tip" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="12" markerHeight="12" orient="auto"><path d="M0 0L10 5L0 10z"/></marker></defs>` + curvePaths(edges) : '';
      const evidence = root.querySelector('.mapping-evidence');
      evidence.innerHTML = selected ? `<p>${esc(selected)} · ${edges.length} 个已知引用方向</p>${edges.length ? '<details open><summary>引用依据</summary><ul>' + edges.flatMap((edge) => edge.evidence.map((value) => '<li data-i18n-ignore>' + esc(value) + '</li>')).join('') + '</ul></details>' : '<p>暂无已知引用，不推定其他流向。</p>'}` : '';
    }
    top.addEventListener('click', (event) => { const button = event.target.closest('[data-mapping-column]'); if (button) { selected = (selected.split(':')[0] || 'data') + ':' + button.dataset.mappingColumn; paint(); } }, options);
    left.addEventListener('click', (event) => { const button = event.target.closest('[data-mapping-row]'); if (button) { selected = button.dataset.mappingRow + ':' + (selected.split(':')[1] || model.departments[0][0]); paint(); } }, options);
    let drag = null, moved = false;
    scroll.addEventListener('pointerdown', (event) => { if (event.button !== 0 || !event.isPrimary) return; drag = { id: event.pointerId, x: event.clientX, y: event.clientY, left: scroll.scrollLeft, top: scroll.scrollTop }; moved = false; }, options);
    scroll.addEventListener('pointermove', (event) => {
      if (!drag || drag.id !== event.pointerId) return;
      if (!moved && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 5) return;
      moved = true; scroll.setPointerCapture(event.pointerId); root.classList.add('is-panning');
      scroll.scrollLeft = drag.left - (event.clientX - drag.x); scroll.scrollTop = drag.top - (event.clientY - drag.y);
    }, options);
    function stop(event) { if (drag?.id !== event.pointerId) return; if (scroll.hasPointerCapture(event.pointerId)) scroll.releasePointerCapture(event.pointerId); drag = null; root.classList.remove('is-panning'); }
    scroll.addEventListener('pointerup', stop, options); scroll.addEventListener('pointercancel', stop, options);
    scroll.addEventListener('click', (event) => { if (moved) { event.preventDefault(); event.stopPropagation(); moved = false; return; } const button = event.target.closest('[data-mapping-cell]'); selected = button && selected !== button.dataset.mappingCell ? button.dataset.mappingCell : ''; paint(); }, options);
    root.addEventListener('keydown', (event) => { if (event.key === 'Escape') { selected = ''; paint(); } }, options);
    root.addEventListener('pointerover', (event) => emphasize(event.target.closest('[data-mapping-cell]')?.dataset.mappingCell), options);
    root.addEventListener('pointerleave', () => emphasize(document.activeElement?.closest('[data-mapping-cell]')?.dataset.mappingCell), options);
    root.addEventListener('focusin', (event) => emphasize(event.target.closest('[data-mapping-cell]')?.dataset.mappingCell), options);
    root.addEventListener('focusout', (event) => emphasize(event.relatedTarget?.closest('[data-mapping-cell]')?.dataset.mappingCell), options);
    fitAxes(); paint();
  }
  function destroy() {
    controller?.abort(); controller = null;
    if (surfaces) {
      surfaces.nav.replaceChildren(...surfaces.navNodes);
      surfaces.top.replaceChildren(...surfaces.topNodes);
      surfaces.top.classList.remove('mapping-external-top');
      surfaces = null;
    }
    document.body.classList.remove('mapping-active');
  }
  return { render, mounted, destroy };
})();
