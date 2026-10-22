const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character'),pairs=require(path.join(out,'passive-input-sessions.json'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const ctx=await browser.newContext({viewport:{width:740,height:360},reducedMotion:'reduce'});
 await ctx.addInitScript(()=>{
  localStorage.setItem('lumengg-calculator-appearance-v1',JSON.stringify({style:'clean',brightness:35}));
  window.inputFrames=[];const send=WebSocket.prototype.send;
  WebSocket.prototype.send=function(data){try{const msg=JSON.parse(data);if(msg.type==='action')window.inputFrames.push({at:performance.now(),payload:msg.payload});}catch{}return send.call(this,data)};
 });
 const page=await ctx.newPage(),errors=[],report=[];page.on('pageerror',e=>errors.push(String(e)));
 async function state(){return page.evaluate(async()=>{const c=window.v2BattleConfig;return (await fetch(c.stateUrl+'?control_token='+c.controlToken)).json()})}
 async function waitForFrames(count){await page.waitForFunction(n=>window.inputFrames.length>=n,count);await page.waitForTimeout(150);}
 for(const pair of pairs){
  await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
  const before=await state();
  const click=await page.evaluate(()=>{
   const targets=[...document.querySelectorAll('[data-player-panel]')].map(p=>({target:p.dataset.playerPanel,theme:p.dataset.theme}));
   let inputs=0;
   const hit=b=>{if(b&&!b.disabled){b.click();inputs++;return true}return false};
   for(const {target,theme} of targets){
    const holder=document.querySelector(`[data-player-passives="${target}"]`);
    if(theme==='tao'){
     for(const key of ['yang_counter','yin_counter'])for(let n=0;n<4;n++)hit(holder.querySelector(`[data-control-key="${key}"] .tao-cell:not(.is-on)`));
     if(!holder.querySelector('.visual-tao.is-choosing'))throw Error('Tao must lock for choice before commit');
     hit(holder.querySelector('[data-tao-effect="damage_100"]'));
     hit(holder.querySelector('[data-control-key=yin_counter] .tao-cell.is-on'));
     if(!holder.querySelector('.tao-sigil.is-harmony'))throw Error('Tao harmony must remain at 4/3');
     continue;
    }
    const spec=window.CalculatorVisualModel.visualDefinition(theme);
    for(const c of spec.controls){
     if(c.type==='counter'){
      if(c.max)for(let n=0;n<c.max;n++)hit(holder.querySelector(`[data-control-key="${c.key}"] .visual-token:not(.is-on)`));
      else for(let n=0;n<3;n++){const row=holder.querySelector(`[data-control-key="${c.key}"]`);hit(row?.querySelectorAll('.visual-step')[1]);}
     }
    }
    for(const c of spec.controls){
     if(['toggle','thresholdAction'].includes(c.type)){
      const b=holder.querySelector(`[data-control-key="${c.key}"]`);if(b?.getAttribute('aria-pressed')!=='true')hit(b);
     }else if(c.type==='choice')for(const role of ['guardian','assassin','paladin'])hit(holder.querySelector(`[data-role="${role}"]`));
    }
   }
   return {targets,inputs,last:performance.now()};
  });
  if(click.inputs){
   await waitForFrames(1);
   const frames=await page.evaluate(()=>window.inputFrames);
   assert.equal(frames.length,1,JSON.stringify(click.targets));
   assert(frames[0].at-click.last>=865,'900ms debounce must not send immediately');
   const actions=frames[0].payload.actions||[frames[0].payload];
   const keys=actions.map(a=>a.target+':'+a.key);assert.equal(new Set(keys).size,keys.length,'one final value per passive');
   let after;
   for(let n=0;n<60;n++){after=await state();if(after.version>before.version)break;await page.waitForTimeout(100)}
   assert(after.version>before.version);
   for(const action of actions){const entry=after.players[action.target].passive_state[action.key];assert.deepEqual(entry?.value??entry?.count,action.value,action.key);}
   report.push({themes:click.targets.map(t=>t.theme),inputs:click.inputs,stored_actions:actions.length,transport_batches:frames.length});
  }else report.push({themes:click.targets.map(t=>t.theme),inputs:0,transport_batches:0});
  assert(await page.locator('[data-player-passives]').evaluateAll(ps=>ps.every(p=>p.scrollHeight<=p.clientHeight+1&&p.scrollWidth<=p.clientWidth+1)));
  await page.screenshot({path:path.join(out,'passive-input-web-'+click.targets.map(t=>t.theme).join('-')+'.png')});
  if(click.targets.some(t=>t.theme==='tao')){
   await page.evaluate(()=>{document.querySelector('[data-control-key=yin_counter] .tao-cell.is-on').click()});
   await waitForFrames(2);
   for(let n=0;n<60;n++){const s=await state();const target=click.targets.find(t=>t.theme==='tao').target;const p=s.players[target].passive_state;if(p.harmony?.value===false&&p.harmony_effect?.value==='')break;if(n===59)throw Error('Tao harmony did not clear');await page.waitForTimeout(100)}
  }
 }
 // Classic Tao also applies counter + latch + effect changes in one window.
 const classic=pairs.find(p=>p.characters.includes('타오'));
 await page.goto('http://127.0.0.1:8767'+classic.classic,{waitUntil:'networkidle'});
 await page.evaluate(async()=>{const c=window.v2BattleConfig;await fetch(c.actionUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('input[name=csrfmiddlewaretoken]').value},body:JSON.stringify({action:'reset_session',control_token:c.controlToken})})});
 await page.reload({waitUntil:'networkidle'});
 await page.evaluate(()=>{for(const counter of ['yang','yin'])for(let n=0;n<4;n++)document.querySelector(`[data-tao-counter="${counter}"][data-tao-delta="1"]`).click();document.querySelector('[data-tao-effect="damage_100"]').click()});
 await waitForFrames(1);assert.equal(await page.evaluate(()=>window.inputFrames.length),1);
 const tao=(await state()).players.p2.passive_state;assert.equal(tao.harmony?.value,true);assert.equal(tao.harmony_effect?.value,'damage_100');
 await page.screenshot({path:path.join(out,'passive-input-web-classic.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'passive-input-web-report.json'),JSON.stringify({themes:19,report,classic_tao:true,checks:['immediate visual preview','900ms transport window','one final set per key','all theme input controls','Tao lock/retention/clear','Wolf activation consumes tokens','classic Tao atomic dependencies','no character passive scrolling'],errors},null,2));
 await browser.close();console.log('19 themes: 900ms coalescing, final values, conditional passives and classic Tao passed.');
})().catch(e=>{console.error(e);process.exit(1)});
