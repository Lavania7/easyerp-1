'use strict';
window.easyerpPlanVisual = (() => {
  let renderer;
  const formulas = [
    { title: '净生产量', tex: String.raw`Q_{\mathrm{plan}}=\max\!\left(0,\,D+S-I-W\right)`, note: 'D 需求量 · S 目标安全库存 · I 可用库存 · W 在制可交付量' },
    { title: '物料需求', tex: String.raw`M_j=Q_{\mathrm{plan}}\times b_j`, note: 'bⱼ 单位产品的物料用量 · Mⱼ 第 j 项物料需求量' },
    { title: '预计工期', tex: String.raw`T=\frac{Q_{\mathrm{plan}}\times t_u}{n\times\eta}`, note: 'tᵤ 单件标准工时 · n 并行资源数 · η 有效产能系数' },
  ];
  function loadRenderer() {
    if (window.katex) return Promise.resolve(window.katex);
    if (!renderer) renderer = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/vendor/katex/katex.min.js';
      script.onload = () => resolve(window.katex);
      script.onerror = () => { script.remove(); renderer = null; reject(new Error('公式渲染器未能加载')); };
      document.head.append(script);
    });
    return renderer;
  }
  function mount(dialog) {
    const grid = dialog.querySelector('.entry-grid'), layout = document.createElement('div');
    layout.className = 'plan-layout';
    grid.before(layout);
    layout.append(grid);
    const panel = document.createElement('aside');
    panel.className = 'plan-calculation';
    panel.setAttribute('aria-labelledby', 'plan-calculation-title');
    panel.innerHTML = `<div class="plan-calculation-heading"><h3 id="plan-calculation-title">量化计算</h3><span class="plan-preview-tag">公式预览</span></div><p class="plan-calculation-intro">从生产目标到物料与工期，先明确计划的计算关系。</p>${formulas.map((formula, index) => `<section class="plan-formula-card"><h4><span class="plan-formula-number" aria-hidden="true">0${index + 1}</span><span>${formula.title}</span></h4><div class="plan-formula" data-plan-formula="${index}" data-i18n-ignore></div><p>${formula.note}</p></section>`).join('')}<p class="plan-calculation-footnote">测算前需确认需求、库存、BOM、单位与产能口径。当前展示公式，待补参数。</p>`;
    layout.append(panel);
    loadRenderer().then((katex) => {
      if (!panel.isConnected) return;
      panel.querySelectorAll('[data-plan-formula]').forEach((element, index) => {
        katex.render(formulas[index].tex, element, { displayMode: true, throwOnError: false, trust: false, output: 'htmlAndMathml' });
      });
    }).catch((error) => {
      if (!panel.isConnected) return;
      panel.querySelector('[data-plan-formula]').textContent = window.ERPUI.t(error.message);
    });
  }
  Object.assign(window.ERP_MESSAGES, {
    '量化计算': ['Quantitative planning', 'Quantitative Planung'], '公式预览': ['Formula preview', 'Formelvorschau'],
    '从生产目标到物料与工期，先明确计划的计算关系。': ['Connect production targets with material needs and lead time.', 'Produktionsziele mit Materialbedarf und Durchlaufzeit verbinden.'],
    '净生产量': ['Net production quantity', 'Nettoproduktionsmenge'], '物料需求': ['Material requirements', 'Materialbedarf'],
    '预计工期': ['Estimated duration', 'Voraussichtliche Dauer'],
    'D 需求量 · S 目标安全库存 · I 可用库存 · W 在制可交付量': ['D Demand · S Target safety stock · I Available stock · W Deliverable work in progress', 'D Bedarf · S Zielsicherheitsbestand · I Verfügbarer Bestand · W Lieferbare laufende Produktion'],
    'bⱼ 单位产品的物料用量 · Mⱼ 第 j 项物料需求量': ['bⱼ Material per product · Mⱼ Requirement for material j', 'bⱼ Material je Produkt · Mⱼ Bedarf für Material j'],
    'tᵤ 单件标准工时 · n 并行资源数 · η 有效产能系数': ['tᵤ Standard time per unit · n Parallel resources · η Effective capacity factor', 'tᵤ Standardzeit je Einheit · n Parallele Ressourcen · η Effektiver Kapazitätsfaktor'],
    '测算前需确认需求、库存、BOM、单位与产能口径。当前展示公式，待补参数。': ['Confirm demand, stock, BOM, units and capacity before estimating. Formulas are shown here; parameters are pending.', 'Vor der Berechnung Bedarf, Bestand, Stückliste, Einheiten und Kapazität bestätigen. Formeln werden angezeigt; Parameter stehen noch aus.'],
    '公式渲染器未能加载': ['Could not load the formula renderer', 'Formeldarstellung konnte nicht geladen werden'],
  });
  return { mount };
})();
