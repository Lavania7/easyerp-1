'use strict';
(function (root) {
  const MAX_EXPRESSION = 512;
  const MAX_DIGITS = 120;
  const MAX_VALUE_DIGITS = 768;
  const DISPLAY_DIGITS = 20;
  const abs = (value) => value < 0n ? -value : value;
  const fail = (code) => { throw new Error(code); };

  function fraction(numerator, denominator = 1n) {
    if (denominator === 0n) fail('division');
    if (denominator < 0n) { numerator = -numerator; denominator = -denominator; }
    let a = abs(numerator), b = denominator;
    while (b) { const remainder = a % b; a = b; b = remainder; }
    numerator /= a;
    denominator /= a;
    if (abs(numerator).toString().length > MAX_VALUE_DIGITS || denominator.toString().length > MAX_VALUE_DIGITS) fail('limit');
    return { numerator, denominator };
  }

  function evaluate(expression) {
    const source = String(expression ?? '').trim().replace(/×/g, '*').replace(/[÷:]/g, '/').replace(/−/g, '-').replace(/,/g, '.');
    if (!source) fail('empty');
    if (source.length > MAX_EXPRESSION) fail('limit');
    if (/[^\d\s.+*/()\-]/.test(source)) fail('syntax');
    let position = 0;
    function space() { while (/\s/.test(source[position] || '') && position < source.length) position++; }
    function atom(depth) {
      if (depth > 32) fail('limit');
      space();
      const sign = source[position];
      if (sign === '+' || sign === '-') {
        position++;
        const value = atom(depth + 1);
        return sign === '-' ? fraction(-value.numerator, value.denominator) : value;
      }
      if (sign === '(') {
        position++;
        const value = sum(depth + 1);
        space();
        if (source[position++] !== ')') fail('syntax');
        return value;
      }
      const match = /^(?:\d+(?:\.\d*)?|\.\d+)/.exec(source.slice(position));
      if (!match) fail('syntax');
      const value = match[0], digits = value.replace('.', '');
      if (digits.length > MAX_DIGITS) fail('limit');
      position += value.length;
      const scale = value.includes('.') ? value.length - value.indexOf('.') - 1 : 0;
      return fraction(BigInt(digits), 10n ** BigInt(scale));
    }
    function product(depth) {
      let left = atom(depth);
      for (;;) {
        space();
        const operator = source[position];
        if (operator !== '*' && operator !== '/') return left;
        position++;
        const right = atom(depth);
        left = operator === '*'
          ? fraction(left.numerator * right.numerator, left.denominator * right.denominator)
          : fraction(left.numerator * right.denominator, left.denominator * right.numerator);
      }
    }
    function sum(depth) {
      let left = product(depth);
      for (;;) {
        space();
        const operator = source[position];
        if (operator !== '+' && operator !== '-') return left;
        position++;
        const right = product(depth);
        left = fraction(left.numerator * right.denominator + (operator === '+' ? 1n : -1n) * right.numerator * left.denominator, left.denominator * right.denominator);
      }
    }
    const result = sum(0);
    space();
    if (position !== source.length) fail('syntax');
    const negative = result.numerator < 0n, numerator = abs(result.numerator);
    let integer = numerator / result.denominator, remainder = numerator % result.denominator;
    let decimals = '';
    for (let index = 0; remainder && index < DISPLAY_DIGITS; index++) {
      remainder *= 10n;
      decimals += String(remainder / result.denominator);
      remainder %= result.denominator;
    }
    const exact = remainder === 0n;
    if (!exact && remainder * 2n >= result.denominator) {
      const rounded = BigInt(decimals) + 1n;
      if (rounded.toString().length > DISPLAY_DIGITS) { integer++; decimals = ''; }
      else decimals = rounded.toString().padStart(DISPLAY_DIGITS, '0');
    }
    decimals = decimals.replace(/0+$/, '');
    const value = (negative && (integer || /[1-9]/.test(decimals)) ? '-' : '') + integer + (decimals ? '.' + decimals : '');
    return { value, exact };
  }

  if (typeof module === 'object' && module.exports) module.exports = { evaluate };
  if (!root?.document) return;
  const document = root.document;
  const messages = {
    zh: {
      title: '计算器', close: '关闭计算器', move: '拖动计算器，或用方向键移动',
      expression: '表达式', result: '结果', clear: '清除', backspace: '退格', calculate: '计算',
      hint: 'Enter 计算 · Esc 关闭 · 支持小数点或逗号', approximate: '≈ 已四舍五入至 20 位小数',
      empty: '请输入表达式', syntax: '请检查数字、运算符和括号', division: '不能除以零', limit: '表达式过长或数值超出范围',
      decimal: '小数点', plus: '加', minus: '减', times: '乘', divide: '除', left: '左括号', right: '右括号',
    },
    en: {
      title: 'Calculator', close: 'Close calculator', move: 'Drag calculator, or move with arrow keys',
      expression: 'Expression', result: 'Result', clear: 'Clear', backspace: 'Backspace', calculate: 'Calculate',
      hint: 'Enter to calculate · Esc to close · Decimal point or comma', approximate: '≈ Rounded to 20 decimal places',
      empty: 'Enter an expression', syntax: 'Check numbers, operators and parentheses', division: 'Cannot divide by zero', limit: 'Expression or value is too large',
      decimal: 'Decimal point', plus: 'Add', minus: 'Subtract', times: 'Multiply', divide: 'Divide', left: 'Left parenthesis', right: 'Right parenthesis',
    },
    de: {
      title: 'Rechner', close: 'Rechner schließen', move: 'Rechner ziehen oder mit Pfeiltasten bewegen',
      expression: 'Ausdruck', result: 'Ergebnis', clear: 'Löschen', backspace: 'Rücktaste', calculate: 'Berechnen',
      hint: 'Enter berechnet · Esc schließt · Dezimalpunkt oder Komma', approximate: '≈ Auf 20 Nachkommastellen gerundet',
      empty: 'Ausdruck eingeben', syntax: 'Zahlen, Operatoren und Klammern prüfen', division: 'Division durch null ist nicht möglich', limit: 'Ausdruck oder Wert ist zu groß',
      decimal: 'Dezimalpunkt', plus: 'Addieren', minus: 'Subtrahieren', times: 'Multiplizieren', divide: 'Dividieren', left: 'Öffnende Klammer', right: 'Schließende Klammer',
    },
  };
  const keys = [
    ['C', 'clear'], ['(', 'left'], [')', 'right'], ['⌫', 'backspace'],
    ['7'], ['8'], ['9'], ['÷', 'divide'],
    ['4'], ['5'], ['6'], ['×', 'times'],
    ['1'], ['2'], ['3'], ['−', 'minus'],
    ['0'], ['.', 'decimal'], ['=', 'calculate'], ['+', 'plus'],
  ];
  let trigger, panel, input, result, status, controller, mountController, drag;
  let last = null, errorCode = '', position = null, evaluated = false;
  const text = () => messages[root.ERPPreferences?.language] || messages[document.documentElement.lang.slice(0, 2)] || messages.zh;

  function viewport() {
    const view = root.visualViewport;
    return { x: view?.offsetLeft || 0, y: view?.offsetTop || 0, width: view?.width || root.innerWidth, height: view?.height || root.innerHeight };
  }
  function topBoundary(view, margin) {
    const topbar = trigger?.closest('.topbar');
    if (!topbar || (view.width > 700 && view.height > 500)) return view.y + margin;
    return Math.max(view.y + margin, Math.min(topbar.getBoundingClientRect().bottom + margin, view.y + view.height - 70));
  }
  function place(x, y) {
    if (!panel) return;
    const view = viewport(), bounds = panel.getBoundingClientRect();
    const margin = Math.min(10, view.width / 20, view.height / 20);
    position = {
      x: Math.max(view.x + margin, Math.min(x, view.x + view.width - bounds.width - margin)),
      y: Math.max(topBoundary(view, margin), Math.min(y, view.y + view.height - bounds.height - margin)),
    };
    panel.style.left = position.x + 'px';
    panel.style.top = position.y + 'px';
  }
  function fit() {
    if (!panel) return;
    const view = viewport();
    panel.style.maxWidth = Math.max(1, view.width - 20) + 'px';
    panel.style.maxHeight = Math.max(1, view.y + view.height - topBoundary(view, 10) - 10) + 'px';
    const bounds = panel.getBoundingClientRect();
    place(position?.x ?? view.x + view.width - bounds.width - 22, position?.y ?? view.y + 100);
  }
  function paint() {
    const labels = text();
    if (trigger) {
      trigger.querySelector('span').textContent = labels.title;
      trigger.title = labels.title;
      trigger.setAttribute('aria-label', labels.title);
    }
    if (!panel) return;
    panel.querySelectorAll('[data-calculator-label]').forEach((node) => { node.textContent = labels[node.dataset.calculatorLabel]; });
    panel.querySelectorAll('[data-calculator-aria]').forEach((node) => {
      node.setAttribute('aria-label', labels[node.dataset.calculatorAria]);
      node.title = labels[node.dataset.calculatorAria];
    });
    status.textContent = errorCode ? labels[errorCode] : last && !last.exact ? labels.approximate : '';
    fit();
  }
  function resetResult() {
    last = null;
    errorCode = '';
    evaluated = false;
    result.textContent = '—';
    status.textContent = '';
    input.removeAttribute('aria-invalid');
  }
  function calculate() {
    try {
      last = { ...evaluate(input.value), expression: input.value };
      evaluated = true;
      errorCode = '';
      result.textContent = (last.exact ? '' : '≈ ') + last.value;
      input.removeAttribute('aria-invalid');
    } catch (error) {
      last = null;
      evaluated = false;
      errorCode = Object.hasOwn(messages.zh, error.message) ? error.message : 'syntax';
      result.textContent = '—';
      input.setAttribute('aria-invalid', 'true');
    }
    paint();
  }
  function insert(value) {
    if (evaluated) {
      if (/^[+−×÷*/\-]$/.test(value)) input.value = last.exact ? last.value : '(' + last.expression + ')';
      else input.value = '';
      input.setSelectionRange(input.value.length, input.value.length);
    }
    const start = input.selectionStart, end = input.selectionEnd;
    if (input.value.length - (end - start) + value.length > MAX_EXPRESSION) return;
    input.setRangeText(value, start, end, 'end');
    resetResult();
  }
  function act(key) {
    if (key === 'calculate') calculate();
    else if (key === 'clear') { input.value = ''; resetResult(); }
    else if (key === 'backspace') {
      const start = input.selectionStart, end = input.selectionEnd;
      input.setRangeText('', start === end ? Math.max(0, start - 1) : start, end, 'end');
      resetResult();
    } else insert(key);
    input.focus({ preventScroll: true });
  }
  function stopDrag(event) {
    if (drag) {
      const handle = panel?.querySelector('.calculator-drag');
      if (event?.type !== 'pointerup' && handle?.hasPointerCapture(drag.id)) handle.releasePointerCapture(drag.id);
      drag = null;
    }
    panel?.classList.remove('is-dragging');
  }
  function close(restoreFocus = true) {
    if (!panel) return;
    const returnFocus = panel.contains(document.activeElement);
    stopDrag();
    controller.abort();
    panel.remove();
    panel = input = result = status = controller = null;
    position = null;
    last = null;
    errorCode = '';
    evaluated = false;
    trigger?.setAttribute('aria-expanded', 'false');
    trigger?.setAttribute('aria-pressed', 'false');
    if (restoreFocus && returnFocus) trigger?.focus({ preventScroll: true });
  }
  function open() {
    if (panel) { input.focus({ preventScroll: true }); return; }
    if (!trigger) mount();
    if (!trigger) return;
    controller = new root.AbortController();
    const options = { signal: controller.signal };
    panel = document.createElement('section');
    panel.id = 'easyerp-calculator';
    panel.className = 'calculator-panel';
    panel.dataset.i18nIgnore = '';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'false');
    panel.setAttribute('aria-labelledby', 'calculator-title');
    panel.innerHTML = `<header class="calculator-head"><h2><button type="button" class="calculator-drag" data-calculator-aria="move"><span class="calculator-grip" aria-hidden="true">⠿</span><span id="calculator-title" data-calculator-label="title"></span></button></h2><button type="button" class="calculator-close" data-calculator-aria="close">×</button></header><div class="calculator-body"><div class="calculator-screen"><label for="calculator-expression" data-calculator-label="expression"></label><input id="calculator-expression" type="text" inputmode="text" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="${MAX_EXPRESSION}" aria-describedby="calculator-hint calculator-status" dir="ltr"><span class="calculator-result-label" data-calculator-label="result"></span><output id="calculator-result" for="calculator-expression" aria-live="polite" aria-atomic="true" dir="ltr">—</output><p id="calculator-status" role="status" aria-live="polite"></p></div><div class="calculator-keys">${keys.map(([key, name]) => `<button type="button" data-calculator-key="${name === 'clear' || name === 'backspace' || name === 'calculate' ? name : key}"${name ? ` data-calculator-aria="${name}"` : ''} class="calculator-key${name === 'calculate' ? ' calculator-equals' : name && name !== 'decimal' ? ' calculator-operation' : ''}">${key}</button>`).join('')}</div><p id="calculator-hint" data-calculator-label="hint"></p></div>`;
    document.body.append(panel);
    input = panel.querySelector('input');
    result = panel.querySelector('output');
    status = panel.querySelector('#calculator-status');
    const closeButton = panel.querySelector('.calculator-close');
    let closeTouch;
    closeButton.addEventListener('click', () => close(), options);
    closeButton.addEventListener('pointerdown', (event) => {
      closeTouch = event.pointerType === 'touch' ? { id: event.pointerId, x: event.clientX, y: event.clientY } : null;
    }, options);
    closeButton.addEventListener('pointercancel', () => { closeTouch = null; }, options);
    closeButton.addEventListener('pointerup', (event) => {
      if (closeTouch?.id === event.pointerId && Math.hypot(event.clientX - closeTouch.x, event.clientY - closeTouch.y) < 10) close();
      closeTouch = null;
    }, options);
    panel.querySelector('.calculator-keys').addEventListener('click', (event) => {
      const key = event.target.closest('[data-calculator-key]');
      if (key) act(key.dataset.calculatorKey);
    }, options);
    input.addEventListener('input', resetResult, options);
    panel.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return; }
      if (event.target !== input || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === 'Enter' || event.key === '=') { event.preventDefault(); calculate(); }
      else if (evaluated && (/^[\d.,+\-*/×÷−(]$/.test(event.key))) { event.preventDefault(); insert(event.key); }
    }, options);
    const handle = panel.querySelector('.calculator-drag');
    handle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || !event.isPrimary) return;
      const bounds = panel.getBoundingClientRect();
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, left: bounds.left, top: bounds.top };
      handle.setPointerCapture(event.pointerId);
      panel.classList.add('is-dragging');
    }, options);
    handle.addEventListener('pointermove', (event) => {
      if (drag?.id === event.pointerId) place(drag.left + event.clientX - drag.x, drag.top + event.clientY - drag.y);
    }, options);
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) handle.addEventListener(name, stopDrag, options);
    handle.addEventListener('keydown', (event) => {
      const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (delta) { event.preventDefault(); const step = event.shiftKey ? 48 : 16; place(position.x + delta[0] * step, position.y + delta[1] * step); }
      if (event.key === 'Home') { event.preventDefault(); position = null; fit(); }
    }, options);
    root.addEventListener('resize', fit, options);
    root.visualViewport?.addEventListener('resize', fit, options);
    root.visualViewport?.addEventListener('scroll', fit, options);
    trigger.setAttribute('aria-expanded', 'true');
    trigger.setAttribute('aria-pressed', 'true');
    paint();
    input.focus({ preventScroll: true });
  }
  function toggle() { if (panel) close(); else open(); }
  function mount(container = document.querySelector('.top-actions')) {
    if (trigger?.isConnected) return trigger;
    if (!container) return null;
    mountController?.abort();
    mountController = new root.AbortController();
    const options = { signal: mountController.signal };
    trigger = document.createElement('button');
    trigger.id = 'calculator-toggle';
    trigger.type = 'button';
    trigger.className = 'calculator-toggle';
    trigger.dataset.i18nIgnore = '';
    trigger.setAttribute('aria-controls', 'easyerp-calculator');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-pressed', 'false');
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 6h8M8 10h2m4 0h2M8 14h2m4 0h2M8 18h2m4 0h2"/></svg><span></span>';
    const appearance = container.querySelector('#appearance-controls');
    container.insertBefore(trigger, appearance);
    trigger.addEventListener('click', toggle, options);
    root.addEventListener('erp:language-changed', paint, options);
    root.addEventListener('pagehide', () => close(false), options);
    paint();
    return trigger;
  }
  function destroy() {
    close(false);
    mountController?.abort();
    trigger?.remove();
    trigger = mountController = null;
    document.removeEventListener('DOMContentLoaded', ready);
  }
  function ready() { mount(); }
  root.easyerpCalculator = { evaluate, mount, open, close, toggle, destroy };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, { once: true });
  else ready();
})(typeof window === 'undefined' ? null : window);
