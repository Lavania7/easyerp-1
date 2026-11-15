'use strict';
(() => {
  const initial = new URL(location.href);
  const mode = initial.searchParams.get('mode') || 'live';
  const id = initial.searchParams.get('db') || 'active-' + mode;
  const custom = !['active-live', 'active-demo'].includes(id);
  let label = custom ? '所选数据库' : mode === 'demo' ? '演示数据' : '本机数据库';
  let switching = false;

  window.easyerpFetch = (input, options) => {
    const target = new URL(input, location.href);
    if (target.origin === location.origin && target.pathname.startsWith('/api/') &&
        !target.pathname.startsWith('/api/databases')) target.searchParams.set('db', id);
    return fetch(target, options);
  };

  async function switchDatabase(targetId, token) {
    if (switching || targetId === id) return;
    switching = true;
    try {
      if (!token) {
        const response = await fetch('/api/databases', {cache:'no-store'});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || '无法读取数据库目录。');
        token = result.token;
      }
      const response = await fetch('/api/databases/activate', {
        method:'POST', headers:{'Content-Type':'application/json', 'X-EasyERP-Token':token},
        body:JSON.stringify({id:targetId}),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '数据库切换失败。');
      const next = new URL(location.href);
      next.searchParams.set('db', result.id);
      next.searchParams.set('mode', result.mode);
      const [route, query = ''] = next.hash.split('?');
      const parameters = new URLSearchParams(query);
      parameters.delete('reference');
      next.hash = route + (parameters.size ? '?' + parameters : '');
      location.assign(next.href);
    } finally {
      switching = false;
    }
  }

  window.easyerpDatabaseSource = {
    id, custom, switch:switchDatabase,
    get label() { return label; },
    sourceLabel(sourceMode) { return custom ? label : sourceMode === 'demo' ? '演示数据' : '正式数据'; },
  };
  if (custom) fetch('/api/databases', {cache:'no-store'}).then(response => {
    if (!response.ok) throw new Error('无法读取数据库目录。');
    return response.json();
  }).then(catalog => {
    const selected = catalog.nodes.find(node => node.id === id);
    if (!selected?.switchable) return;
    label = selected.label;
    document.dispatchEvent(new Event('easyerp:database-label'));
  }).catch(() => {});
})();
