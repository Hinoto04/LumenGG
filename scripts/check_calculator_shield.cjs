const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character'),fixture=require(path.join(out,'shield-review-session.json'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const ctx=await browser.newContext({viewport:{width:740,height:360},reducedMotion:'reduce'});
 await ctx.addInitScript(()=>localStorage.setItem('lumengg-calculator-appearance-v1',JSON.stringify({style:'clean',brightness:35})));
 const p=await ctx.newPage(),errors=[];p.on('pageerror',e=>errors.push(String(e)));
 await p.goto('http://127.0.0.1:8767'+fixture.character,{waitUntil:'networkidle'});
 const state=()=>p.evaluate(async()=>{const c=window.v2BattleConfig;return (await fetch(c.stateUrl+'?control_token='+c.controlToken)).json()});
 const api=body=>p.evaluate(async body=>{const c=window.v2BattleConfig;const r=await fetch(c.actionUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('input[name=csrfmiddlewaretoken]').value},body:JSON.stringify({...body,control_token:c.controlToken})});if(!r.ok)throw Error(await r.text());},body);
 const shield=(s,target='p1')=>s.players[target].passive_state.finf_shield?.value||0;
 async function wait(hp,value,target='p1'){for(let i=0;i<100;i++){const s=await state();if(s.players[target].hp===hp&&shield(s,target)===value)return;await p.waitForTimeout(100)}const s=await state();throw Error('Expected HP/shield '+hp+'/'+value+' got '+s.players[target].hp+'/'+shield(s,target));}
 const initial=(await state()).players.p1.initial_hp;
 await api({action:'reset_session'});await p.reload({waitUntil:'networkidle'});
 const plus=(target='p1')=>p.locator(`[data-shield-target="${target}"][data-shield-step="100"]`);
 await plus().click({clickCount:3});
 assert((await plus().textContent()).includes('+300'),'pending sum');
 await wait(initial,300);
 assert.equal(await p.locator('[data-player-hp=p1] .v2-battle-shield-value').textContent(),'+300');
 await p.screenshot({path:path.join(out,'shield-web-clean-active.png')});
 const spectator=await ctx.newPage();await spectator.goto('http://127.0.0.1:8767'+fixture.view+'?ui=character',{waitUntil:'networkidle'});
 assert.equal(await spectator.locator('.v2-shield-button').count(),6);
 assert.equal(await spectator.locator('.v2-shield-button:enabled').count(),0);
 assert.equal(await spectator.locator('[data-player-hp=p1] .v2-battle-shield-value').textContent(),'+300');
 await p.locator('[data-hp-target=p1][data-hp-step="-500"]').click();await wait(initial-200,0);
 await p.screenshot({path:path.join(out,'shield-web-clean-overflow.png')});
 await p.locator('[data-battle-action=undo]').click();await wait(initial,300);
 await plus().click();await p.locator('[data-shield-reset=p1]').click();await wait(initial,0);
 await p.waitForTimeout(2300);await wait(initial,0);
 await p.locator('[data-shield-target=p1][data-shield-step="-100"]').click();await wait(initial,0);
 await p.waitForTimeout(1900);
 // A dependent sequence must not merge HP edits across a shield gain.
 await plus().click({clickCount:3});
 await p.locator('[data-hp-target=p1][data-hp-step="-500"]').click();
 await plus().click({clickCount:2});
 await p.locator('[data-hp-target=p1][data-hp-step="-100"]').click();await wait(initial-200,100);
 // Character display changes rebuild the passive panel but keep its controls.
 await p.getByRole('button',{name:'화면 설정',exact:true}).click();
 await p.getByRole('radio',{name:'일러스트',exact:true}).check();
 await p.getByRole('button',{name:'닫기',exact:true}).click();
 assert.equal(await p.locator('.v2-shield-button').count(),6);
 await p.screenshot({path:path.join(out,'shield-web-illustrated.png')});
 const classic=await ctx.newPage();await classic.goto('http://127.0.0.1:8767'+fixture.classic,{waitUntil:'networkidle'});
 assert.equal(await classic.locator('.v2-shield-button').count(),6);
 await classic.screenshot({path:path.join(out,'shield-web-classic.png')});
 await classic.close();await spectator.close();
 await p.waitForTimeout(1000);
 await api({action:'shield',target:'p1',amount:50000});
 await p.reload({waitUntil:'networkidle'});
 await p.getByRole('button',{name:'화면 설정',exact:true}).click();await p.getByRole('radio',{name:'깔끔하게',exact:true}).check();await p.getByRole('button',{name:'닫기',exact:true}).click();
 const sizes=[];
 for(const [width,height] of [[740,360],[844,390],[1024,768],[1440,900],[390,844]]){
  await p.setViewportSize({width,height});
  const geometry=await p.locator('[data-player-passives]').evaluateAll(ps=>ps.map(e=>({scroll:e.scrollHeight>e.clientHeight+1||e.scrollWidth>e.clientWidth+1,buttons:[...e.querySelectorAll('.v2-shield-button')].map(b=>{const r=b.getBoundingClientRect();const p=e.getBoundingClientRect();return {w:r.width,h:r.height,inside:r.top>=p.top-1&&r.bottom<=p.bottom+1&&r.left>=p.left-1&&r.right<=p.right+1}})})));
  assert(geometry.every(g=>!g.scroll&&g.buttons.length===3&&g.buttons.every(b=>b.w>=44&&b.h>=44&&b.inside)),JSON.stringify({width,height,geometry}));
  assert(await p.locator('[data-player-hp=p1]').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'HP + shield must fit');
  sizes.push([width,height]);
 }
 for(const [lang,label] of [['en','Shield'],['ja','シールド']]){
  await ctx.addCookies([{name:'lumengg_language',value:lang,url:'http://127.0.0.1:8767'}]);
  await p.goto('http://127.0.0.1:8767'+fixture.character,{waitUntil:'networkidle'});
  assert((await plus().textContent()).startsWith(label));
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'shield-web-report.json'),JSON.stringify({checks:['300 shield queued in one change','overflow reaches HP','undo restores shield','reset flush leaves no later gain','negative floor','HP/shield input ordering','spectator read-only and shared state','classic/illustrated/clean controls','style switch preserves buttons','English/Japanese labels'],sizes,errors},null,2));
 await browser.close();console.log('Shield web: batching, damage, undo, reset, sharing, 3 skins, 5 sizes, 3 languages passed.');
})().catch(e=>{console.error(e);process.exit(1)});
