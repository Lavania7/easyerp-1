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

  function normalizeLatex(expression) {
    let source = String(expression ?? '').trim();
    if (!source) fail('empty');
    if (source.length > MAX_EXPRESSION) fail('limit');
    source = source.replace(/\\(?:left|right)\b/g, '').replace(/\\(?:cdot|times)\b/g, '*')
      .replace(/\\div\b/g, '/').replace(/\\[,;!]/g, '').replace(/×/g, '*')
      .replace(/[÷:]/g, '/').replace(/−/g, '-').replace(/η/g, 'eta')
      .replace(/\\(?:mathrm|operatorname)\{([A-Za-z]+)\}/g, '$1')
      .replace(/_\{([A-Za-z0-9]+)\}/g, '_$1')
      .replace(/\\(eta|alpha|beta|gamma|theta|max|min)\b/g, '$1');
    source = source.replace(/,/g, /\b(?:max|min)\s*\(/.test(source) ? ';' : '.');
    let position = 0;
    function group(depth) {
      if (depth > 32) fail('limit');
      let output = '';
      while (position < source.length && source[position] !== '}') {
        if (source.startsWith('\\frac', position)) {
          position += 5;
          const parts = [];
          for (let i = 0; i < 2; i++) {
            while (/\s/.test(source[position] || '') && position < source.length) position++;
            if (source[position++] !== '{') fail('syntax');
            parts.push(group(depth + 1));
            if (source[position++] !== '}') fail('syntax');
          }
          output += '((' + parts[0] + ')/(' + parts[1] + '))';
        } else if (source[position] === '{') {
          position++;
          output += '(' + group(depth + 1) + ')';
          if (source[position++] !== '}') fail('syntax');
        } else output += source[position++];
      }
      return output;
    }
    const normalized = group(0);
    if (position !== source.length) fail('syntax');
    const assignment = normalized.split('=');
    if (assignment.length > 2 || (assignment.length === 2 && !/^[A-Za-z][A-Za-z0-9_]*\s*$/.test(assignment[0]))) fail('syntax');
    const result = assignment.at(-1).trim();
    if (/[^A-Za-z0-9_\s.+*/()^;\-]/.test(result)) fail('syntax');
    return result;
  }
  function parameters(expression) {
    return [...new Set(normalizeLatex(expression).match(/[A-Za-z][A-Za-z0-9_]*/g) || [])].filter(name => !['max', 'min'].includes(name));
  }
  function evaluate(expression, values = {}) {
    const source = normalizeLatex(expression);
    let position = 0;
    function space() { while (/\s/.test(source[position] || '') && position < source.length) position++; }
    function atom(depth) {
      if (depth > 32) fail('limit');
      space();
      if (source[position] === '(') {
        position++;
        const value = sum(depth + 1);
        space();
        if (source[position++] !== ')') fail('syntax');
        return value;
      }
      const name = /^[A-Za-z][A-Za-z0-9_]*/.exec(source.slice(position));
      if (name) {
        position += name[0].length;
        if (['max', 'min'].includes(name[0])) {
          space();
          if (source[position++] !== '(') fail('syntax');
          const args = [sum(depth + 1)];
          space();
          while (source[position] === ';') { position++; args.push(sum(depth + 1)); space(); }
          if (source[position++] !== ')' || args.length < 2) fail('syntax');
          return args.reduce((a, b) => {
            const greater = a.numerator * b.denominator > b.numerator * a.denominator;
            return (name[0] === 'max' ? greater : !greater) ? a : b;
          });
        }
        if (!Object.hasOwn(values, name[0])) fail('parameter');
        const raw = String(values[name[0]]).trim().replace(',', '.');
        if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw)) fail('parameter');
        return decimal(raw);
      }
      const match = /^(?:\d+(?:\.\d*)?|\.\d+)/.exec(source.slice(position));
      if (!match) fail('syntax');
      position += match[0].length;
      return decimal(match[0]);
    }
    function decimal(raw) {
      const digits = raw.replace('.', '');
      if (digits.replace(/[+-]/, '').length > MAX_DIGITS) fail('limit');
      const scale = raw.includes('.') ? raw.length - raw.indexOf('.') - 1 : 0;
      return fraction(BigInt(digits), 10n ** BigInt(scale));
    }
    function power(depth) {
      let left = atom(depth);
      space();
      if (source[position] === '^') {
        position++;
        const right = unary(depth + 1);
        if (right.denominator !== 1n || abs(right.numerator) > 100n) fail('exponent');
        const exponent = abs(right.numerator);
        if (Math.max(abs(left.numerator).toString().length, left.denominator.toString().length) * Number(exponent) > 4000) fail('limit');
        left = right.numerator < 0n
          ? fraction(left.denominator ** exponent, left.numerator ** exponent)
          : fraction(left.numerator ** exponent, left.denominator ** exponent);
      }
      return left;
    }
    function unary(depth) {
      if (depth > 32) fail('limit');
      space();
      if (source[position] === '+' || source[position] === '-') {
        const sign = source[position++], value = unary(depth + 1);
        return sign === '-' ? fraction(-value.numerator, value.denominator) : value;
      }
      return power(depth);
    }
    function product(depth) {
      let left = unary(depth);
      for (;;) {
        space();
        let operator = source[position];
        if (operator === '*' || operator === '/') position++;
        else if (/[A-Za-z(]/.test(operator || '')) operator = '*';
        else return left;
        const right = unary(depth);
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

  const engine = { evaluate, parameters, normalizeLatex };
  if (typeof module === 'object' && module.exports) module.exports = engine;
  if (!root?.document) return;
  let renderer;
  const labels = {
    '金额': ['Amount', 'Betrag'], '比率': ['Ratio', 'Verhältnis'],
    '含损耗需求': ['Quantity with loss', 'Bedarf mit Verlust'], '复利': ['Compound interest', 'Zinseszins'],
    '净生产量': ['Net production quantity', 'Nettoproduktionsmenge'], '物料需求': ['Material requirements', 'Materialbedarf'],
    '预计工期': ['Estimated duration', 'Voraussichtliche Dauer'],
    '搜索ID或备注': ['Search ID or remarks', 'ID oder Bemerkung suchen'],
    '历史计划': ['Legacy plans', 'Bisherige Pläne'],
    'D 需求量 · S 目标安全库存 · I 可用库存 · W 在制可交付量': ['D Demand · S Target safety stock · I Available stock · W Deliverable work in progress', 'D Bedarf · S Zielsicherheitsbestand · I Verfügbarer Bestand · W Lieferbare laufende Produktion'],
    'Q_plan 净生产量 · b_j 单位产品物料用量': ['Q_plan Net production · b_j Material per unit', 'Q_plan Nettoproduktion · b_j Material je Einheit'],
    'Q_plan 净生产量 · t_u 单件标准工时 · n 并行资源数 · eta 有效产能系数': ['Q_plan Net production · t_u Standard time per unit · n Parallel resources · eta Effective capacity factor', 'Q_plan Nettoproduktion · t_u Standardzeit je Einheit · n Parallele Ressourcen · eta Effektiver Kapazitätsfaktor'],
    '公式名称': ['Formula name', 'Formelname'],
    '未命名公式': ['Unnamed formula', 'Unbenannte Formel'],
    '暂无已保存的公式': ['No saved formulas', 'Keine gespeicherten Formeln'],
    '参数含义（可选）': ['Parameter meaning (optional)', 'Parameterbedeutung (optional)'],
    '参数含义': ['Parameter meanings', 'Parameterbedeutungen'],
    'LaTeX 代码': ['LaTeX code', 'LaTeX-Code'],
    '公式与结果': ['Formula and result', 'Formel und Ergebnis'],
    '参数值': ['Parameter values', 'Parameterwerte'],
    '备选公式': ['Formula library', 'Formelbibliothek'],
    '已保存公式': ['Saved formula', 'Gespeicherte Formel'],
    '当前公式无需参数': ['No parameters in this formula', 'Diese Formel hat keine Parameter'],
    '将当前LaTeX公式保存': ['Save current LaTeX formula', 'Aktuelle LaTeX-Formel speichern'],
    '公式预设': ['Formula preset', 'Formelvorlage'], '自定义': ['Custom', 'Benutzerdefiniert'],
    'LaTeX 公式': ['LaTeX formula', 'LaTeX-Formel'], '参数': ['Parameters', 'Parameter'],
    '公式预览': ['Formula preview', 'Formelvorschau'], '计算结果': ['Calculated result', 'Berechnetes Ergebnis'],
    '四舍五入至20位小数': ['Rounded to 20 decimal places', 'Auf 20 Nachkommastellen gerundet'],
    '请输入公式': ['Enter a formula', 'Formel eingeben'],
    '请填写全部参数': ['Enter every parameter', 'Alle Parameter eingeben'],
    '公式格式有误': ['Invalid formula', 'Ungültige Formel'],
    '不能除以零': ['Cannot divide by zero', 'Division durch null nicht möglich'],
    '指数须为−100至100的整数': ['Exponent must be an integer from −100 to 100', 'Exponent muss ganzzahlig zwischen −100 und 100 sein'],
    '公式或数值超出范围': ['Formula or value exceeds limits', 'Formel oder Wert außerhalb des Bereichs'],
    '支持四则、分式、括号、整数幂、max/min。函数参数用逗号，函数内小数用小数点；不支持根式、求和或脚本。': ['Supports arithmetic, fractions, parentheses, integer powers and max/min. Separate function arguments with commas and use decimal points inside functions. Roots, sums and scripts are unsupported.', 'Unterstützt Grundrechenarten, Brüche, Klammern, ganzzahlige Potenzen und max/min. Funktionsargumente mit Komma trennen, Dezimalpunkt in Funktionen verwenden. Keine Wurzeln, Summen oder Skripte.'],
  };
  Object.assign(root.ERP_MESSAGES, labels);
  const tr = text => root.ERPUI.t(text);
  function loadRenderer() {
    if (root.katex) return Promise.resolve(root.katex);
    if (!renderer) renderer = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/vendor/katex/katex.min.js';
      script.onload = () => resolve(root.katex);
      script.onerror = () => { script.remove(); renderer = null; reject(new Error('renderer')); };
      document.head.append(script);
    });
    return renderer;
  }
  function renderFormula(node, formula) {
    try {
      if (root.katex) root.katex.render(formula || '\\;', node, { displayMode: true, throwOnError: true, trust: false, strict: 'error', maxExpand: 100, maxSize: 10 });
      else node.textContent = formula;
    } catch { node.textContent = formula; }
  }
  function renderLibrary(host, formulas, selected, onSelect) {
    host.replaceChildren();
    if (!formulas.length) {
      const empty = document.createElement('p'); empty.className = 'calculation-empty'; empty.dataset.uiLabel = '';
      empty.textContent = tr('暂无已保存的公式'); host.append(empty);
    }
    for (const formula of formulas) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'calculation-formula-card';
      button.dataset.formulaOption = formula.expression; button.dataset.formulaId = formula.id;
      button.setAttribute('aria-pressed', String(selected(formula)));
      const title = document.createElement('span'); title.className = 'calculation-formula-card-name';
      if (formula.name) { title.dataset.i18nIgnore = ''; title.textContent = formula.name; }
      else { title.dataset.uiLabel = ''; title.textContent = tr('未命名公式'); }
      const node = document.createElement('span'); node.className = 'calculation-formula-card-preview'; node.dataset.i18nIgnore = '';
      renderFormula(node, formula.expression);
      button.append(title, node); button.onclick = () => onSelect(formula); host.append(button);
    }
    loadRenderer().then(() => {
      if (host.isConnected) for (const button of host.querySelectorAll('[data-formula-option]')) renderFormula(button.querySelector('.calculation-formula-card-preview'), button.dataset.formulaOption);
    }).catch(() => {});
  }
  function nameInput() {
    return `<label class="calculation-formula-name"><span data-ui-label>公式名称</span><input type="text" data-formula-name maxlength="120" aria-label="${tr('公式名称')}" autocomplete="off"></label>`;
  }
  function mount(host, board = {}, library) {
    host.innerHTML = `<div class="calculation-formula">
      <section class="calculation-section calculation-code" aria-label="${tr('LaTeX 代码')}">
        <h4 data-ui-label>LaTeX 代码</h4>
        <textarea data-expression rows="5" maxlength="512" spellcheck="false" dir="ltr" aria-label="${tr('LaTeX 公式')}"></textarea>
        <div class="calculation-formula-save">${nameInput()}<button type="submit" class="button" name="save_formula" value="1" data-save-formula data-ui-label>将当前LaTeX公式保存</button></div>
        <small data-ui-label>支持四则、分式、括号、整数幂、max/min。函数参数用逗号，函数内小数用小数点；不支持根式、求和或脚本。</small>
      </section>
      <section class="calculation-section calculation-preview-section" aria-label="${tr('公式与结果')}">
        <h4 data-ui-label>公式与结果</h4>
        <div class="calculation-scroll calculation-preview-body" tabindex="0" aria-label="${tr('公式与结果')}">
          <div class="calculator-preview" data-preview data-i18n-ignore aria-label="${tr('公式预览')}"></div>
          <div class="calculation-result"><span data-ui-label>计算结果</span><output aria-live="polite" dir="ltr">—</output></div>
          <p data-status data-ui-label role="status"></p>
        </div>
      </section>
      <section class="calculation-section calculation-parameter-section" aria-label="${tr('参数值')}">
        <h4 data-ui-label>参数值</h4>
        <div class="calculation-scroll calculation-parameter-body" tabindex="0" aria-label="${tr('参数值')}">
          <div class="calculator-parameters" data-parameters></div>
          <p class="calculation-empty" data-no-parameters data-ui-label>当前公式无需参数</p>
        </div>
      </section>
    </div>`;
    const input = host.querySelector('[data-expression]'), box = host.querySelector('[data-parameters]');
    const title = host.querySelector('[data-formula-name]'); title.value = board.formula_name || '';
    const output = host.querySelector('output'), status = host.querySelector('[data-status]');
    const gallery = library.host;
    input.value = board.expression || '';
    let values = { ...board.parameters }, notes = { ...board.parameter_notes }, last = null, savedFormulas = [...(library.formulas || [])];
    const errors = { empty: '请输入公式', parameter: '请填写全部参数', syntax: '公式格式有误', division: '不能除以零', exponent: '指数须为−100至100的整数', limit: '公式或数值超出范围' };
    const selected = formula => formula.expression === input.value.trim() && formula.name === title.value.trim();
    function updateSelection() {
      for (const card of gallery.querySelectorAll('[data-formula-id]')) card.setAttribute('aria-pressed', String(selected(savedFormulas.find(formula => formula.id === card.dataset.formulaId))));
    }
    function showLibrary() {
      renderLibrary(gallery, savedFormulas, selected, formula => {
        input.value = formula.expression; title.value = formula.name; notes = { ...formula.parameter_notes }; refresh();
      });
    }
    function preview() { renderFormula(host.querySelector('[data-preview]'), input.value); }
    function calculate() {
      values = Object.fromEntries([...box.querySelectorAll('input')].map(field => [field.dataset.formulaParam, field.value]));
      try {
        last = evaluate(input.value, values);
        output.textContent = (last.exact ? '' : '≈ ') + last.value;
        status.textContent = last.exact ? '' : tr('四舍五入至20位小数');
        input.removeAttribute('aria-invalid');
      } catch (error) {
        last = null; output.textContent = '—';
        status.textContent = tr(errors[error.message] || errors.syntax);
        input.setAttribute('aria-invalid', 'true');
      }
      host.querySelector('[data-save-formula]').disabled = !input.value.trim();
      host.dispatchEvent(new CustomEvent('calculation-change', { bubbles: true }));
    }
    function refresh() {
      for (const field of box.querySelectorAll('input')) values[field.dataset.formulaParam] = field.value;
      box.replaceChildren();
      try {
        for (const name of parameters(input.value)) {
          const label = document.createElement('label'), field = document.createElement('input'); label.dataset.i18nIgnore = '';
          const heading = document.createElement('span'); heading.className = 'calculation-parameter-heading';
          const symbol = document.createElement('span'); symbol.textContent = name; heading.append(symbol);
          if (notes[name]?.trim()) {
            const meaning = document.createElement('span'); meaning.className = 'calculation-parameter-meaning';
            meaning.dataset.parameterMeaning = name; meaning.textContent = notes[name]; heading.append(meaning);
          }
          label.append(heading);
          field.dataset.formulaParam = name; field.setAttribute('aria-label', name);
          field.type = 'text'; field.inputMode = 'decimal'; field.maxLength = 123;
          field.value = values[name] ?? ''; field.autocomplete = 'off';
          label.append(field); box.append(label);
        }
      } catch {}
      host.querySelector('[data-no-parameters]').hidden = box.childElementCount > 0;
      updateSelection(); preview(); calculate();
    }
    input.addEventListener('input', refresh);
    title.addEventListener('input', updateSelection);
    box.addEventListener('input', calculate);
    host.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.isComposing && event.target.matches('input')) { event.preventDefault(); calculate(); }
    });
    showLibrary(); refresh();
    loadRenderer().then(() => { if (host.isConnected) preview(); }).catch(() => {});
    return {
      value: () => ({ expression: input.value, parameters: { ...values }, formula_name: title.value, parameter_notes: Object.fromEntries(Object.keys(values).filter(name => notes[name]).map(name => [name, notes[name]])) }),
      result: () => last,
      setFormulas: formulas => { savedFormulas = [...formulas]; showLibrary(); },
    };
  }
  function mountFormulaEditor(host, formula) {
    host.innerHTML = `<div class="calculation-template-editor">${nameInput()}
      <label><span data-ui-label>LaTeX 代码</span><textarea data-template-expression rows="5" maxlength="512" spellcheck="false" dir="ltr" aria-label="${tr('LaTeX 公式')}"></textarea></label>
      <div class="calculator-preview" data-template-preview data-i18n-ignore aria-label="${tr('公式预览')}"></div>
      <section><h4 data-ui-label>参数含义</h4><div data-template-notes></div><p data-no-template-parameters data-ui-label>当前公式无需参数</p></section>
    </div>`;
    const input = host.querySelector('[data-template-expression]'), title = host.querySelector('[data-formula-name]'), box = host.querySelector('[data-template-notes]');
    input.value = formula.expression; title.value = formula.name;
    const notes = { ...formula.parameter_notes };
    function values() { return Object.fromEntries([...box.querySelectorAll('input')].map(field => [field.dataset.parameterNote, field.value])); }
    function preview() { renderFormula(host.querySelector('[data-template-preview]'), input.value); }
    function refresh() {
      Object.assign(notes, values()); box.replaceChildren();
      try {
        for (const name of parameters(input.value)) {
          const label = document.createElement('label'); label.className = 'calculation-template-note';
          const symbol = document.createElement('span'); symbol.textContent = name; symbol.dataset.i18nIgnore = '';
          const field = document.createElement('input'); field.type = 'text'; field.maxLength = 300; field.value = notes[name] || '';
          field.dataset.parameterNote = name; field.setAttribute('aria-label', name + ' · ' + tr('参数含义')); field.placeholder = tr('参数含义（可选）');
          label.append(symbol, field); box.append(label);
        }
      } catch {}
      host.querySelector('[data-no-template-parameters]').hidden = box.childElementCount > 0; preview();
    }
    input.addEventListener('input', refresh);
    refresh(); loadRenderer().then(() => { if (host.isConnected) preview(); }).catch(() => {});
    return { value: () => ({ name: title.value, expression: input.value, parameter_notes: values() }) };
  }
  root.easyerpCalculator = { ...engine, mount, mountFormulaEditor, renderLibrary };
})(typeof window === 'undefined' ? null : window);
