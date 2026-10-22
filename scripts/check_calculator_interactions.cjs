const fs=require('fs');const path=require('path');const assert=require('node:assert/strict');const{chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character');
 const pairs=JSON.parse(fs.readFileSync(path.join(out,'review-sessions.json'),'utf8'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const ctx=await browser.newContext({viewport:{width:844,height:390},reducedMotion:'reduce'});
 const arena=await ctx.newPage(),classic=await ctx.newPage();
 const errors=[];for(const p of [arena,classic])p.on('pageerror',e=>errors.push(String(e)));
 const checks=[];
 const open=async(p,i,newUi=true)=>p.goto('http://127.0.0.1:8767'+pairs[i][newUi?'character':'classic'],{waitUntil:'networkidle'});
 const state=async(p)=>p.evaluate(async()=>{const c=window.v2BattleConfig;const response=await fetch(c.stateUrl+'?control_token='+c.controlToken);const text=await response.text();if(!response.ok)throw Error('state HTTP '+response.status+' '+(text.match(/<title>([\s\S]*?)<\/title>/)?.[1]||text.slice(0,80)));const result=JSON.parse(text);return result.state||result});
 const wait=async(fn,msg)=>{for(let n=0;n<60;n++){if(await fn())return;await new Promise(r=>setTimeout(r,200));}throw Error(msg)};
 for(const item of pairs){
  await arena.goto('http://127.0.0.1:8767'+item.character,{waitUntil:'networkidle'});
  await arena.evaluate(async()=>{const c=window.v2BattleConfig;const csrf=document.querySelector('input[name="csrfmiddlewaretoken"]').value;await fetch(c.actionUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({action:'reset_session',control_token:c.controlToken})})});
 }
 await open(arena,0);await open(classic,0,false);
 let initial=(await state(arena)).players.p1.hp;
 await arena.evaluate(()=>{for(const step of [-100,-100,100])document.querySelector(`[data-hp-target="p1"][data-hp-step="${step}"]`).click()});
 await wait(async()=>Number(await arena.locator('[data-player-hp="p1"]').textContent())===initial-100,'arena HP queue');
 await wait(async()=>Number(await classic.locator('[data-player-hp="p1"]').textContent())===initial-100,'classic realtime parity');
 checks.push('Rapid mixed HP input and classic/character realtime parity');
 await arena.locator('[data-battle-action="undo"]').click();
 await wait(async()=>Number(await arena.locator('[data-player-hp="p1"]').textContent())===initial,'undo');
 checks.push('Undo restores HP without replacing the session');
 await arena.locator('[data-control-key="root_charge"]').click();
 await wait(async()=>!!(await state(arena)).players.p1.passive_state.root_charge?.value,'charge');
 assert.equal(await arena.locator('[data-control-key="root_charge"]').getAttribute('aria-pressed'),'true');
 checks.push('Root charge core follows existing passive state');
 for(const counter of ['yang','yin']) for(let i=1;i<=4;i++){
  await arena.locator(`[data-tao-counter="${counter}"][aria-pressed="false"]`).first().click();
  await wait(async()=>Number((await state(arena)).players.p2.passive_state[counter+'_counter']?.value)===i,counter+' counter');
 }
 await wait(async()=>!!(await state(arena)).players.p2.passive_state.harmony?.value,'harmony activation');
 await arena.locator('[data-tao-effect="damage_100"]').click();
 await wait(async()=>(await state(arena)).players.p2.passive_state.harmony_effect?.value==='damage_100','harmony effect');
 await arena.screenshot({path:path.join(out,'web-tao-harmony.png'),fullPage:true});
 await arena.locator('[data-tao-counter="yang"][aria-pressed="true"]').first().click();
 await wait(async()=>Number((await state(arena)).players.p2.passive_state.yang_counter?.value)===3,'harmony retains 3');
 assert.equal((await state(arena)).players.p2.passive_state.harmony.value,true);
 await arena.locator('[data-tao-counter="yang"][aria-pressed="true"]').first().click();
 await wait(async()=>(await state(arena)).players.p2.passive_state.harmony?.value===false,'harmony clears');
 checks.push('Tao 4/4 activation, 3/4 retention, below-three clearing and effect selection');
 await open(arena,1);
 let before=(await state(arena)).players.p2.hp;
 const damage=before-2500;
 await arena.evaluate(async(damage)=>{const c=window.v2BattleConfig;const csrf=document.querySelector('input[name="csrfmiddlewaretoken"]').value;const r=await fetch(c.actionUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({action:'hp',target:'p2',amount:-damage,control_token:c.controlToken})});if(!r.ok)throw Error(await r.text())},damage);
 await wait(async()=>await arena.locator('[data-control-key="blue_flame"]').getAttribute('aria-pressed').then(v=>v==='true'),'blue flame boundary');
 await arena.screenshot({path:path.join(out,'web-muyeong-blue-flame.png'),fullPage:true});
 checks.push('Muyeong blue flame boundary at 2500 HP');
 await open(arena,2);
 for(let i=1;i<=5;i++){
  await arena.locator('[data-control-key="howling_counter"] .visual-token[aria-pressed="false"]').last().click();
  await wait(async()=>Number((await state(arena)).players.p1.passive_state.howling_counter?.value)===i,'howling counter');
 }
 await arena.locator('[data-control-key="pressure"]').click();
 await wait(async()=>Number((await state(arena)).players.p1.passive_state.howling_counter?.value)===0,'pressure reset');
 await arena.locator('[data-control-key="rita_role"] button').nth(1).click();
 await wait(async()=>(await state(arena)).players.p2.passive_state.rita_role?.value==='assassin','rita role');
 await arena.screenshot({path:path.join(out,'web-wolf-rita-active.png'),fullPage:true});
 checks.push('Wolf pressure reset and Rita single-role selection');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'web-interaction-report.json'),JSON.stringify({checks,errors},null,2));
 console.log(JSON.stringify({checks,errors},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
