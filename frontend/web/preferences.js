'use strict';
window.ERPDefaults=Object.freeze({currency:'CNY',timeZone:'Asia/Shanghai',utcOffset:'+08:00'});
(() => {
  const root=document.documentElement,system=matchMedia('(prefers-color-scheme: dark)');
  const themes=['light','dark','system'],languages=['zh','en','de'];
  const icons={
    light:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    dark:'<path d="M20.5 14.1A8.5 8.5 0 0 1 9.9 3.5 8.5 8.5 0 1 0 20.5 14.1Z"/>',
    system:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>'
  };
  const labels={zh:{theme:'主题',language:'语言',light:'浅色',dark:'深色',system:'跟随系统',zh:'中文',en:'英文',de:'德文',next:'点击切换为'},en:{theme:'Theme',language:'Language',light:'Light',dark:'Dark',system:'System',zh:'Chinese',en:'English',de:'German',next:'Click for'},de:{theme:'Design',language:'Sprache',light:'Hell',dark:'Dunkel',system:'System',zh:'Chinesisch',en:'Englisch',de:'Deutsch',next:'Weiter zu'}};
  const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
  const write=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
  let theme=read('easyerp.theme','system'),language=read('easyerp.language','zh');
  if(!themes.includes(theme))theme='system';
  if(!languages.includes(language))language='zh';
  const next=(items,current)=>items[(items.indexOf(current)+1)%items.length];
  function paint(){
    root.dataset.theme=theme==='system'?(system.matches?'dark':'light'):theme;
    root.dataset.themePreference=theme;root.style.colorScheme=root.dataset.theme;
    root.lang={zh:'zh-CN',en:'en',de:'de'}[language];
    const themeButton=document.querySelector('#theme-toggle'),languageButton=document.querySelector('#language-toggle'),text=labels[language];
    if(themeButton){
      themeButton.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+icons[theme]+'</svg>';
      themeButton.title=text.theme+': '+text[theme]+'; '+text.next+' '+text[next(themes,theme)];
      themeButton.setAttribute('aria-label',themeButton.title);
    }
    if(languageButton){
      languageButton.textContent=language.toUpperCase();
      languageButton.title=text.language+': '+text[language]+'; '+text.next+' '+text[next(languages,language)];
      languageButton.setAttribute('aria-label',languageButton.title);
    }
  }
  function cycleTheme(){theme=next(themes,theme);write('easyerp.theme',theme);paint();}
  function cycleLanguage(){language=next(languages,language);write('easyerp.language',language);paint();window.dispatchEvent(new CustomEvent('erp:language-changed',{detail:{language}}));}
  window.ERPPreferences={get theme(){return theme;},get language(){return language;}};
  paint();system.addEventListener('change',()=>{if(theme==='system')paint();});
  document.addEventListener('DOMContentLoaded',()=>{
    paint();
    document.querySelector('#theme-toggle').addEventListener('click',cycleTheme);
    document.querySelector('#language-toggle').addEventListener('click',cycleLanguage);
    const clock=document.querySelector('#rtc-clock');
    const formatter=new Intl.DateTimeFormat('en-GB',{timeZone:window.ERPDefaults.timeZone,hourCycle:'h23',hour:'2-digit',minute:'2-digit',second:'2-digit'});
    const tick=()=>{clock.textContent=formatter.format(new Date());};
    tick();setInterval(tick,1000);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
  });
  window.addEventListener('storage',event=>{
    if(event.key==='easyerp.theme'){theme=themes.includes(event.newValue)?event.newValue:'system';paint();}
    if(event.key==='easyerp.language'){language=languages.includes(event.newValue)?event.newValue:'zh';paint();window.dispatchEvent(new CustomEvent('erp:language-changed',{detail:{language}}));}
  });
})();
