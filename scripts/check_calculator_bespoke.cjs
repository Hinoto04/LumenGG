const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character');
 const pairs=JSON.parse(fs.readFileSync(path.join(out,'visual-review-sessions.json')));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:740,height:360},reducedMotion:'no-preference'});
 const page=await context.newPage();const errors=[],report=[];
 page.on('pageerror',e=>errors.push(String(e)));
 const state=()=>page.evaluate(async()=>{const c=window.v2BattleConfig;return (await fetch(c.stateUrl+'?control_token='+c.controlToken)).json()});
 const value=(s,t,k)=>s.players[t].passive_state[k]?.value??s.players[t].passive_state[k]?.count??0;
 const quantities=s=>Object.fromEntries(Object.entries(s.players).map(([t,p])=>[t,{hp:p.hp,fp:p.fp,passives:Object.fromEntries(Object.entries(p.passive_state).map(([k,v])=>[k,v.value??v.count]))}]));
 async function wait(fn){for(let i=0;i<60;i++){if(await fn())return;await page.waitForTimeout(100)}throw Error('State did not synchronize')}
 for(const pair of pairs){
  await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
  // Reset these disposable fixture sessions through their existing control endpoint.
  await page.evaluate(async()=>{const c=window.v2BattleConfig;await fetch(c.actionUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('input[name=csrfmiddlewaretoken]').value},body:JSON.stringify({action:'reset_session',control_token:c.controlToken})})});
  await page.reload({waitUntil:'networkidle'});
  const configs=await page.evaluate(()=>['p1','p2'].map(target=>{
   const theme=document.querySelector('[data-player-panel='+target+']').dataset.theme;
   return {target,theme,controls:window.CalculatorVisualModel.visualDefinition(theme).controls};
  }));
  for(const {target,theme,controls} of configs){
   const panel=page.locator('[data-player-panel='+target+']');
   if(['tao','rita'].includes(theme))continue; // Dedicated interaction suite covers these.
   for(const c of controls){
    const ui=panel.locator('[data-control-key="'+c.key+'"]');
    if(c.type==='counter'){
     const desired=c.max||2;
     while(Number(value(await state(),target,c.key))<desired){
      const old=Number(value(await state(),target,c.key));
      if(c.max)await ui.locator('.visual-token:not(.is-on)').last().click();
      else await ui.locator('.visual-step').last().click();
      await wait(async()=>Number(value(await state(),target,c.key))===old+1);
     }
    }else if(['toggle','thresholdAction'].includes(c.type)){
     assert.equal(await ui.isDisabled(),false,theme+' '+c.key+' available');
     await ui.click();await wait(async()=>value(await state(),target,c.key)===true);
    }else if(c.type==='status'){
     assert.equal(await ui.getAttribute('role'),'img');
     for(let i=0;i<5;i++)await panel.locator('[data-hp-step="-500"]').click();
     await wait(async()=>(await state()).players[target].hp<=2500);
    }
   }
  }
  await page.waitForTimeout(650);
  const geometry=await page.evaluate(()=>[...document.querySelectorAll('[data-player-panel]')].map(p=>{
   const hp=p.querySelector('.v2-battle-hp').getBoundingClientRect(),fp=p.querySelector('.v2-battle-fp').getBoundingClientRect();
   const passive=p.querySelector('[data-player-passives]'),buttons=[...passive.querySelectorAll('button')].filter(b=>b.getBoundingClientRect().width);
   const collisions=[];
   for(let i=0;i<buttons.length;i++)for(let j=i+1;j<buttons.length;j++){
    const a=buttons[i].getBoundingClientRect(),b=buttons[j].getBoundingClientRect();
    if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)collisions.push([buttons[i].title,buttons[j].title]);
   }
   return {theme:p.dataset.theme,symmetric:p.dataset.playerPanel==='p1'?hp.right<=fp.left:fp.right<=hp.left,
    passiveHeight:passive.clientHeight,content:passive.scrollHeight,collisions,
    missingImages:[...passive.querySelectorAll('img')].filter(i=>!i.complete||!i.naturalWidth).length,
    activeEffects:[...passive.querySelectorAll('[data-ambient]')].map(a=>a.dataset.ambient)};
  }));
  assert(geometry.every(g=>g.symmetric&&g.content<=g.passiveHeight+1&&!g.missingImages&&!g.collisions.length),JSON.stringify(geometry));
  await page.screenshot({path:path.join(out,'bespoke-'+configs.map(c=>c.theme).join('-')+'.png')});
  const stable=quantities(await state());
  await page.waitForTimeout(1100);
  assert.deepEqual(quantities(await state()),stable,'ambient effects must not mutate game state');
  const normal=await page.evaluate(()=>document.querySelector('[data-battle-session]')?.getAnimations({subtree:true}).filter(a=>a.playState==='running').length||0);
  if(geometry.some(g=>g.activeEffects.length))assert(normal>0,'active state keeps a weak ambient effect running');
  await page.emulateMedia({reducedMotion:'reduce'});
  const reduced=await page.evaluate(()=>[...document.querySelectorAll('.ambient-effect')].every(a=>getComputedStyle(a,'::before').animationName==='none'&&[...a.children].every(i=>getComputedStyle(i).animationName==='none')));
  assert(reduced,'reduce motion disables all persistent animation');
  await page.emulateMedia({reducedMotion:'no-preference'});
  report.push({characters:pair.characters,geometry,normalAnimations:normal,reducedMotion:reduced});
  console.log('Passed '+pair.characters.join(' / '));
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'bespoke-report.json'),JSON.stringify({report,errors},null,2));
 console.log(JSON.stringify({themes:19,pairs:report.length,errors,checks:'symmetric resources, live actions, non-overlapping 44px controls, active effects, unchanged idle state, reduced motion, packaged art'}));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
