'use strict';
(() => {
  const root=document.documentElement,system=matchMedia('(prefers-color-scheme: dark)');
  const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
  const write=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
  let theme=read('easyerp.theme','system'),language=read('easyerp.language','zh');
  if(!['light','dark','system'].includes(theme))theme='system';
  if(!['zh','en','de'].includes(language))language='zh';
  function paint(){
    root.dataset.theme=theme==='system'?(system.matches?'dark':'light'):theme;
    root.dataset.themePreference=theme;root.style.colorScheme=root.dataset.theme;
    root.lang={zh:'zh-CN',en:'en',de:'de'}[language];
    document.querySelectorAll('[data-theme-value]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.themeValue===theme)));
    document.querySelectorAll('[data-language-value]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.languageValue===language)));
  }
  window.ERPPreferences={get theme(){return theme;},get language(){return language;}};
  paint();system.addEventListener('change',()=>{if(theme==='system')paint();});
  document.addEventListener('DOMContentLoaded',()=>{
    paint();
    document.querySelector('#appearance-controls').addEventListener('click',event=>{
      const button=event.target.closest('button');if(!button)return;
      if(button.dataset.themeValue){theme=button.dataset.themeValue;write('easyerp.theme',theme);paint();}
      if(button.dataset.languageValue&&button.dataset.languageValue!==language){
        language=button.dataset.languageValue;write('easyerp.language',language);paint();
        window.dispatchEvent(new CustomEvent('erp:language-changed',{detail:{language}}));
      }
    });
  });
  window.addEventListener('storage',event=>{
    if(event.key==='easyerp.theme'){theme=['light','dark','system'].includes(event.newValue)?event.newValue:'system';paint();}
    if(event.key==='easyerp.language'){language=['zh','en','de'].includes(event.newValue)?event.newValue:'zh';paint();window.dispatchEvent(new CustomEvent('erp:language-changed',{detail:{language}}));}
  });
})();
