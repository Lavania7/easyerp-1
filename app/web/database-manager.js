'use strict';
(() => {
  Object.assign(window.ERP_MESSAGES ||= {}, {
    '数据库管理': ['Database manager', 'Datenbankverwaltung'],
    '新建数据库': ['New database', 'Neue Datenbank'],
    '版本关系': ['Version graph', 'Versionsgraph'],
    '选择文件夹': ['Choose folder', 'Ordner auswählen'],
    '数据库名称': ['Database name', 'Datenbankname'],
    '父版本': ['Parent version', 'Übergeordnete Version'],
    '关联版本（仅逻辑）': ['Related version (logical only)', 'Verknüpfte Version (nur logisch)'],
    '结构模板': ['Schema template', 'Schemavorlage'],
    '逻辑关联': ['Logical relation', 'Logische Verknüpfung'],
    '预览新建': ['Preview creation', 'Erstellung prüfen'],
    '创建空数据库': ['Create empty database', 'Leere Datenbank erstellen'],
    '迁移预览': ['Migration preview', 'Migrationsvorschau'],
    '当前空白结构模板': ['Current empty schema template', 'Aktuelle leere Schemavorlage'],
    '当前正式数据库': ['Current live database', 'Aktuelle produktive Datenbank'],
    '保留的旧正式库': ['Retained previous live database', 'Beibehaltene frühere Produktivdatenbank'],
    '旧源保留': ['Previous source retained', 'Bisherige Quelle beibehalten'],
    '完整备份恢复': ['Restored from full backup', 'Aus vollständiger Sicherung wiederhergestellt'],
    '恢复来源': ['Restore source', 'Wiederherstellungsquelle'],
    '迁移记录': ['Migration record', 'Migrationsprotokoll'],
    '正式数据已迁移，旧源保留。': ['Live data migrated; the previous source is retained.', 'Produktivdaten migriert; die bisherige Quelle bleibt erhalten.'],
    '正式数据库已恢复并切换，旧源完整保留。': ['The live database has been restored and switched; the previous source is fully retained.', 'Die Produktivdatenbank wurde wiederhergestellt und umgestellt; die bisherige Quelle bleibt vollständig erhalten.'],
    '已核对全部业务及运维表、结构、工作空间和正式导入历史。': ['All business and operations tables, schema, workspace and live import history were compared.', 'Alle Geschäfts- und Betriebstabellen, das Schema, der Arbeitsbereich und der produktive Importverlauf wurden verglichen.'],
    '备份恢复验证通过，未执行旧源清理。': ['Backup restore verification passed; the previous source was not removed.', 'Die Wiederherstellungsprüfung war erfolgreich; die bisherige Quelle wurde nicht entfernt.'],
    '项目演示数据库': ['Project demo database', 'Projekt Demodatenbank'],
    '未登记派生关系': ['Lineage not recorded', 'Abstammung nicht erfasst'],
    '空白结构派生': ['Empty schema derivation', 'Ableitung eines leeren Schemas'],
    '已配置': ['Configured', 'Konfiguriert'],
    '空库已就绪 · 已停止': ['Empty database ready · stopped', 'Leere Datenbank bereit · gestoppt'],
    '创建中': ['Creating', 'Wird erstellt'],
    '创建未完成': ['Creation incomplete', 'Erstellung unvollständig'],
    '选择版本查看目录与关系；创建新版本将生成空库。': [
      'Select a version to inspect its location and lineage; new versions contain no business records.',
      'Version für Speicherort und Abstammung auswählen; neue Versionen enthalten keine Geschäftsdaten.'],
    '创建只使用当前结构模板，不复制父版本的业务记录或工作空间。': [
      'Creation uses the current schema template without copying parent business records or workspace.',
      'Die Erstellung verwendet die aktuelle Schemavorlage ohne Geschäftsdaten oder Arbeitsbereich der Vorgängerversion.'],
    '目录': ['Directory', 'Verzeichnis'],
    '端口': ['Port', 'Port'],
    '工作空间': ['Workspace', 'Arbeitsbereich'],
    '模板指纹': ['Template fingerprint', 'Vorlagenfingerabdruck'],
    '数据库已创建，当前连接保持原配置。': ['Database created; the current connection configuration is retained.', 'Datenbank erstellt; die aktuelle Verbindungskonfiguration bleibt erhalten.'],
    '未选择文件夹': ['No folder selected', 'Kein Ordner ausgewählt'],
    '正式数据迁移尚未执行。': ['Live data migration has not been performed.', 'Produktivdaten wurden noch nicht migriert.'],
    '源目录': ['Source directory', 'Quellverzeichnis'],
    '目标目录': ['Target directory', 'Zielverzeichnis'],
    '待单独批准的操作': ['Operations requiring separate approval', 'Separat zu genehmigende Vorgänge'],
    '正在处理…': ['Processing…', 'Wird verarbeitet…'],
  });
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const dialog = document.createElement('dialog');
  dialog.id = 'database-manager';
  dialog.className = 'database-manager';
  dialog.setAttribute('aria-labelledby', 'database-manager-title');
  document.body.append(dialog);
  let catalog, token = '', folder = null, plan = null, busy = false, lastFocus;
  const status = value => ({configured:'已配置', retained:'旧源保留', ready:'空库已就绪 · 已停止', creating:'创建中', failed:'创建未完成'}[value] || '');

  async function request(path, payload) {
    const options = payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json', 'X-EasyERP-Token':token}, body:JSON.stringify(payload)};
    const response = await fetch('/api/databases' + path, {cache:'no-store', ...options});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || '数据库管理暂时不可用。');
    return body;
  }
  function notice(text, error = false) {
    const node = dialog.querySelector('[data-db-notice]');
    node.hidden = !text;
    node.textContent = text;
    node.classList.toggle('error', error);
  }
  async function action(task) {
    if (busy) return;
    notice('');
    busy = true;
    dialog.setAttribute('aria-busy', 'true');
    dialog.querySelectorAll('button').forEach(button => button.disabled = true);
    try { await task(); }
    catch (error) { notice(error.message, true); }
    finally {
      busy = false;
      dialog.removeAttribute('aria-busy');
      dialog.querySelectorAll('button').forEach(button => button.disabled = false);
    }
  }
  function renderGraph() {
    const nodes = catalog.nodes;
    const indices = new Map(nodes.map((node, index) => [node.id, index]));
    const lanes = nodes.map(node => node.kind === 'template' ? 0 : node.kind === 'live' ? 1 : node.kind === 'demo' ? 2 : 3);
    const height = Math.max(nodes.length * 66, 66);
    const lines = nodes.map((node, index) => [node.parent_id, node.logical_parent_id].map((parentId, relation) => {
      if (!parentId || !indices.has(parentId)) return '';
      const parent = indices.get(parentId);
      return `<path ${relation ? 'stroke-dasharray="3 3"' : ''} d="M${14 + lanes[parent] * 13} ${33 + parent * 66} C${14 + lanes[parent] * 13} ${33 + index * 66},${14 + lanes[index] * 13} ${33 + parent * 66},${14 + lanes[index] * 13} ${33 + index * 66}"/>`;
    }).join('')).join('');
    const circles = nodes.map((node, index) => `<circle cx="${14 + lanes[index] * 13}" cy="${33 + index * 66}" r="4" class="db-lane-${lanes[index]}"/>`).join('');
    dialog.querySelector('[data-db-graph]').innerHTML = `<div class="db-graph"><svg width="72" height="${height}" viewBox="0 0 72 ${height}" aria-hidden="true">${lines}${circles}</svg><div class="db-graph-rows">${nodes.map(node => `<button type="button" class="db-graph-row" data-db-node="${h(node.id)}"><strong ${node.kind === 'database' ? 'data-i18n-ignore' : ''}>${h(node.label)}</strong><span>${node.relation === 'restored-copy' ? '完整备份恢复' : node.parent_id ? '空白结构派生' : node.kind === 'template' ? '' : '未登记派生关系'}</span><small>${h(status(node.status))}</small></button>`).join('')}</div></div>`;
  }
  function showNode(id) {
    const node = catalog.nodes.find(item => item.id === id);
    if (!node) return;
    notice('');
    dialog.querySelectorAll('[data-db-node]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.dbNode === id)));
    dialog.querySelector('[data-db-detail]').innerHTML = `<h3 data-i18n-ignore>${h(node.label)}</h3><dl>${[
      ['目录',node.directory], ['端口',node.port], ['工作空间',node.workspace],
      ['模板指纹',node.template_sha256], [node.relation === 'restored-copy' ? '恢复来源' : '结构模板',catalog.nodes.find(item => item.id === node.parent_id)?.label],
      ['逻辑关联',catalog.nodes.find(item => item.id === node.logical_parent_id)?.label],
    ].filter(([,value]) => value !== undefined).map(([label,value]) => `<dt>${h(label)}</dt><dd data-i18n-ignore>${h(value)}</dd>`).join('')}</dl>`;
  }
  function newForm() {
    notice('');
    folder = null;
    plan = null;
    dialog.querySelector('[data-db-detail]').innerHTML = `<h3>新建数据库</h3><form data-db-form><label>数据库名称<input name="label" maxlength="80" required autocomplete="off"></label><label>关联版本（仅逻辑）<select name="parent_id">${catalog.nodes.filter(node => !['failed','creating'].includes(node.status)).map(node => `<option value="${h(node.id)}" ${node.kind === 'database' ? 'data-i18n-ignore' : ''}>${h(node.label)}</option>`).join('')}</select></label><div class="db-folder"><button type="button" class="button" data-db-folder>选择文件夹</button><output data-db-folder-label>未选择文件夹</output></div><p>创建只使用当前结构模板，不复制父版本的业务记录或工作空间。</p><button class="button primary" type="submit">预览新建</button></form><div data-db-preview></div>`;
  }
  async function load() {
    catalog = await request('');
    token = catalog.token;
    renderGraph();
    dialog.querySelector('footer span').textContent = catalog.source_retained ? '正式数据已迁移，旧源保留。' : '正式数据迁移尚未执行。';
    dialog.querySelector('[data-db-migration]').textContent = catalog.source_retained ? '迁移记录' : '迁移预览';
  }
  async function open() {
    if (dialog.open) { dialog.focus(); return; }
    lastFocus = document.activeElement;
    dialog.innerHTML = `<header><div><h2 id="database-manager-title">数据库管理</h2><p>选择版本查看目录与关系；创建新版本将生成空库。</p></div><button type="button" class="icon-button" data-db-close aria-label="关闭">×</button></header><div class="db-notice" data-db-notice role="status" hidden></div><nav><button type="button" class="button primary" data-db-new>新建数据库</button><button type="button" class="button" data-db-migration>迁移预览</button></nav><div class="db-manager-body"><section aria-label="版本关系" data-db-graph></section><section data-db-detail></section></div><footer><span>正式数据迁移尚未执行。</span><button type="button" class="button" data-db-close>关闭</button></footer>`;
    dialog.showModal();
    await action(async () => { await load(); showNode('active-live'); });
  }
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => { lastFocus?.focus(); });
  dialog.addEventListener('input', event => {
    if (!event.target.closest('[data-db-form]')) return;
    plan = null;
    const preview = dialog.querySelector('[data-db-preview]');
    if (preview) preview.textContent = '';
  });
  dialog.addEventListener('submit', event => {
    if (!event.target.matches('[data-db-form]')) return;
    event.preventDefault();
    action(async () => {
      if (!folder) throw new Error('请先选择文件夹。');
      const data = new FormData(event.target);
      plan = await request('/preview', {folder_ticket:folder.folder_ticket, label:data.get('label'), parent_id:data.get('parent_id')});
      dialog.querySelector('[data-db-preview]').innerHTML = `<dl><dt>目录</dt><dd data-i18n-ignore>${h(plan.directory)}</dd><dt>端口</dt><dd data-i18n-ignore>${h(plan.port)}</dd></dl><ul>${plan.effects.map(effect => `<li>${h(effect)}</li>`).join('')}</ul><button type="button" class="button primary" data-db-create>创建空数据库</button>`;
    });
  });
  dialog.addEventListener('click', event => {
    if (busy) return;
    const button = event.target.closest('button');
    if (!button) return;
    if (button.hasAttribute('data-db-close')) dialog.close();
    else if (button.hasAttribute('data-db-new')) newForm();
    else if (button.dataset.dbNode) showNode(button.dataset.dbNode);
    else if (button.hasAttribute('data-db-folder')) action(async () => {
      const result = await request('/folder', {});
      if (!result.cancelled) {
        folder = result; plan = null;
        dialog.querySelector('[data-db-folder-label]').textContent = folder.folder;
        dialog.querySelector('[data-db-folder-label]').setAttribute('data-i18n-ignore','');
        dialog.querySelector('[data-db-preview]').textContent = '';
      }
    });
    else if (button.hasAttribute('data-db-create')) action(async () => {
      if (!plan) return;
      const result = await request('/create', {plan_id:plan.plan_id});
      plan = null;
      await load(); showNode(result.node.id);
      notice('数据库已创建，当前连接保持原配置。');
    });
    else if (button.hasAttribute('data-db-migration')) action(async () => {
      const result = await request('/migration-preview');
      dialog.querySelector('[data-db-detail]').innerHTML = `<h3>${result.executed ? '迁移记录' : '迁移预览'}</h3><p>${result.executed ? '正式数据已迁移，旧源保留。' : '正式数据迁移尚未执行。'}</p><dl><dt>源目录</dt><dd data-i18n-ignore>${h(result.source.directory)}</dd><dt>目标目录</dt><dd data-i18n-ignore>${h(result.target.data_directory)}</dd></dl>${result.executed ? '' : `<h4>待单独批准的操作</h4><ul>${result.requires_separate_approval.map(text => `<li>${h(text)}</li>`).join('')}</ul>`}<ol>${result.steps.map(text => `<li>${h(text)}</li>`).join('')}</ol>`;
    });
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('#database-manager-open,[data-open-database-manager]')) return;
    document.querySelector('#source-menu')?.setAttribute('hidden','');
    document.querySelector('#source-toggle')?.setAttribute('aria-expanded','false');
    open();
  });
  window.easyerpDatabaseManager = {open};
})();
