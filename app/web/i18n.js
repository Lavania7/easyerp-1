'use strict';
(() => {
  const messages = window.ERP_MESSAGES || {},
    patterns = window.ERP_PATTERNS || [];
  const language = () => window.ERPPreferences.language;
  const locale = () => ({ zh: 'zh-CN', en: 'en-GB', de: 'de-DE' })[language()];
  const literal = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const compiled = patterns.map(([source, en, de]) => {
    const names = [];
    let last = 0,
      regex = '';
    for (const match of source.matchAll(/\{(\w+)\}/g)) {
      regex += literal(source.slice(last, match.index)) + '(.+?)';
      names.push(match[1]);
      last = match.index + match[0].length;
    }
    return { regex: new RegExp('^' + regex + literal(source.slice(last)) + '$'), names, en, de };
  });
  function t(value) {
    const source = String(value ?? ''),
      lang = language();
    if (lang === 'zh' || !source) return source;
    const trim = source.trim(),
      direct = messages[trim];
    let result = direct?.[lang === 'en' ? 0 : 1];
    if (result === undefined && trim.includes('；')) result = trim.split('；').map(t).join('; ');
    if (result === undefined) {
      for (const pattern of compiled) {
        const match = trim.match(pattern.regex);
        if (!match) continue;
        result = pattern[lang].replace(/\{(\w+)\}/g, (_, name) =>
          t(match[pattern.names.indexOf(name) + 1])
        );
        break;
      }
    }
    if (result === undefined) {
      // Composite labels retain IDs and SQL schema prefixes, while translating UI names.
      const pieces = trim.split(/( · | \/ | ↗| →|、|\r?\n)/);
      if (pieces.length > 1)
        result = pieces.map((piece) => (piece === '、' ? ', ' : t(piece))).join('');
      else if (/^(sales|production|rd|finance|legal|analysis)\./.test(trim)) {
        const dot = trim.indexOf('.');
        result =
          trim.slice(0, dot + 1) +
          (messages[trim.slice(dot + 1)]?.[lang === 'en' ? 0 : 1] ?? trim.slice(dot + 1));
      }
    }
    return result === undefined ? source : source.replace(trim, result);
  }
  window.ERPUI = { t, locale };
  const originals = new WeakMap(),
    attributes = new WeakMap();
  function ignored(element) {
    if (
      !element ||
      (element.closest('script,style,textarea,[data-i18n-ignore]') &&
        !element.closest('[data-ui-label]'))
    )
      return true;
    // Business values and reference labels remain verbatim in every language.
    const cell = element.closest(
      '#content td,#drawer dd,button[data-record],button[data-task],.entry-ref option[value]:not([value=""]),.entry-saved-id'
    );
    return !!cell && !element.closest('.badge,.muted,button[data-detail],[data-ui-label]');
  }
  function text(node) {
    if (ignored(node.parentElement)) return;
    const current = node.nodeValue;
    let saved = originals.get(node);
    if (!saved || current !== saved.output) saved = { source: current, output: current };
    const output = t(saved.source);
    saved.output = output;
    originals.set(node, saved);
    if (output !== current) node.nodeValue = output;
  }
  function attribute(element, name) {
    if (ignored(element)) return;
    const current = element.getAttribute(name);
    if (current === null) return;
    let saved = attributes.get(element);
    if (!saved) {
      saved = {};
      attributes.set(element, saved);
    }
    let entry = saved[name];
    if (!entry || current !== entry.output) entry = { source: current, output: current };
    const output = t(entry.source);
    entry.output = output;
    saved[name] = entry;
    if (output !== current) element.setAttribute(name, output);
  }
  function translate() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) text(walker.currentNode);
    document.querySelectorAll('[title],[aria-label],[placeholder]').forEach((element) => {
      for (const name of ['title', 'aria-label', 'placeholder']) attribute(element, name);
    });
    document.title = t('easyERP · 经营工作台');
  }
  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      translate();
    });
  };
  new MutationObserver(schedule).observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['title', 'aria-label', 'placeholder'],
  });
  window.addEventListener('erp:language-changed', translate);
  translate();
})();
