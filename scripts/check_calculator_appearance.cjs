const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character');
 const prefix=process.env.CALCULATOR_REVIEW_PREFIX||'appearance';
 const cleanFiles=new Set(Object.values(require('../LumenGG/content/calculator-clean-icons.json')).map(a=>a.file));
 const pairs=JSON.parse(fs.readFileSync(path.join(out,'visual-review-sessions.json')));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:740,height:360},reducedMotion:'reduce'});
 const page=await context.newPage();
 const errors=[],report=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>localStorage.setItem('lumengg-calculator-appearance-v1',JSON.stringify({style:'clean',brightness:35})));
 for(const pair of pairs){
  await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
  const geometry=await page.evaluate(files=>[...document.querySelectorAll('[data-player-panel]')].map(p=>{
   const passive=p.querySelector('[data-player-passives]'),buttons=[...passive.querySelectorAll('button')],r=passive.getBoundingClientRect();
   const bad=buttons.filter(b=>{const q=b.getBoundingClientRect();if(!q.width||!q.height)return false;return q.width<43||q.height<43||q.left<r.left-1||q.right>r.right+1||q.top<r.top-1||q.bottom>r.bottom+1});
   return {theme:p.dataset.theme,scroll:passive.scrollHeight>passive.clientHeight+1,bad:bad.length,
    illustratedImages:passive.querySelectorAll('img:not([src*="/clean/"])').length,
    missing:[...passive.querySelectorAll('img')].filter(i=>!i.complete||!i.naturalWidth).length,
    obsolete:[...passive.querySelectorAll('img')].filter(i=>!files.includes(i.src.split('/').pop())).length,
    effects:passive.querySelectorAll('.ambient-effect').length,
    sceneHidden:getComputedStyle(p.querySelector('.arena-background')).display==='none',
    portraitHidden:getComputedStyle(p,'::before').display==='none'};
  }),[...cleanFiles]);
  assert(geometry.every(g=>!g.scroll&&!g.bad&&!g.illustratedImages&&!g.missing&&!g.obsolete&&!g.effects&&g.sceneHidden&&g.portraitHidden),JSON.stringify(geometry));
  await page.screenshot({path:path.join(out,prefix+'-clean-web-'+geometry.map(g=>g.theme).join('-')+'.png')});
  report.push(geometry);
 }
 const rootPair=pairs.find(p=>p.characters.includes('루트'));
 await page.goto('http://127.0.0.1:8767'+rootPair.character,{waitUntil:'networkidle'});
 const charge=page.getByRole('button',{name:'차지',exact:true});
 assert.equal(await charge.isEnabled(),true,'review session must permit live input');
 const active=await charge.getAttribute('aria-pressed');
 await charge.click();
 await page.waitForFunction(old=>document.querySelector('[data-control-key="root_charge"]').getAttribute('aria-pressed')!==old,active);
 await charge.click();
 await page.waitForFunction(old=>document.querySelector('[data-control-key="root_charge"]').getAttribute('aria-pressed')===old,active);
 const pair=pairs.find(p=>p.characters.includes('키스'));
 await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
 async function quantities(){return page.evaluate(async()=>{const c=window.v2BattleConfig;const s=await(await fetch(c.stateUrl+'?control_token='+c.controlToken)).json();return {p1:s.players.p1,p2:s.players.p2,events:s.events}})}
 const before=await quantities();
 await page.getByRole('button',{name:'화면 설정',exact:true}).click();
 assert(await page.getByRole('dialog').isVisible());
 await page.getByRole('radio',{name:'일러스트',exact:true}).check();
 await page.evaluate(async()=>{
  await Promise.all([...document.querySelectorAll('[data-player-panel]')].map(async panel=>{
   const url=getComputedStyle(panel,'::before').backgroundImage;
   if(!url.startsWith('url('))return;
   const image=new Image();image.src=url.slice(5,-2);await image.decode();
  }));
 });
 for(const brightness of [0,35,70,100]){
  await page.locator('#arena-brightness').fill(String(brightness));
  assert.equal(await page.locator('body').evaluate(el=>Number(el.style.getPropertyValue('--arena-shade'))),1-brightness/100);
  await page.getByRole('button',{name:'닫기',exact:true}).click();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(200);
  await page.screenshot({path:path.join(out,'appearance-illustrated-web-'+brightness+'.png')});
  await page.getByRole('button',{name:'화면 설정',exact:true}).click();
 }
 await page.getByRole('button',{name:'권장 밝기 · 35%',exact:true}).click();
 await page.getByRole('button',{name:'닫기',exact:true}).click();
 assert.deepEqual(await quantities(),before,'display settings must not change HP, FP, passives or history');
 // A second page without the test init script reads the persisted preference.
 const restored=await page.context().newPage();
 await restored.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
 assert.equal(await restored.locator('body').getAttribute('data-calculator-style'),'illustrated');
 assert.equal(await restored.locator('body').evaluate(el=>Number(el.style.getPropertyValue('--arena-shade'))),.65);
 await restored.close();
 const entry=await context.newPage();
 await entry.goto('http://127.0.0.1:8767'+pair.classic+'?choose_ui=1',{waitUntil:'networkidle'});
 await entry.getByRole('link',{name:/깔끔한 UI 계산기/}).click();
 await entry.waitForLoadState('networkidle');
 assert.equal(await entry.locator('body').getAttribute('data-calculator-style'),'clean');
 await entry.close();
 await page.getByRole('button',{name:'화면 설정',exact:true}).click();
 await page.getByRole('radio',{name:'깔끔하게',exact:true}).check();
 await page.keyboard.press('Escape');
 assert.equal(await page.locator('dialog:visible').count(),0);
 assert.equal(await page.getByRole('button',{name:'화면 설정',exact:true}).evaluate(el=>el===document.activeElement),true);
 for(const [width,height] of [[844,390],[1024,768],[1440,900],[390,844]]){
  await page.setViewportSize({width,height});
  for(const pair of pairs){
   await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
   assert(await page.locator('[data-player-passives]').evaluateAll(ps=>ps.every(p=>p.scrollHeight<=p.clientHeight+1&&p.scrollWidth<=p.clientWidth+1)));
  }
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,prefix+'-web-report.json'),JSON.stringify({themes:19,sizes:5,report,checks:['versioned clean raster assets only','no passive scrolling','44px touch bounds','live Root charge on/off','brightness 0/35/70/100','unchanged session and history','saved settings restore','dialog Escape and focus restore'],errors},null,2));
 console.log('19 clean themes / 5 sizes, brightness, state preservation and saved preferences passed.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
