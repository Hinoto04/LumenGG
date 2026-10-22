// Focused regressions for the October 19 artwork/state revision.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character');
 const pairs=JSON.parse(fs.readFileSync(path.join(out,'visual-review-sessions.json')));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:740,height:360},reducedMotion:'reduce'});
 const errors=[],checks=[];page.on('pageerror',e=>errors.push(String(e)));
 async function visit(theme){
  const pair=pairs.find(p=>p.characters.includes({keith:'키스',rev:'레브',yohan:'요한',iomong:'이오몽',cmyk:'CMYK'}[theme]));
  assert(pair,'fixture for '+theme);
  await page.goto('http://127.0.0.1:8767'+pair.character,{waitUntil:'networkidle'});
  return page.locator('[data-theme="'+theme+'"] [data-player-passives]');
 }
 async function toggle(panel,key){
  const b=panel.locator('[data-control-key="'+key+'"]');
  const old=await b.getAttribute('aria-pressed');await b.click();
  for(let i=0;i<70;i++){if(await b.getAttribute('aria-pressed')!==old)return;await page.waitForTimeout(100)}
  throw Error(key+' failed to synchronize');
 }
 const notice=await visit('keith');
 assert((await notice.locator('img').getAttribute('src')).endsWith('notice-cutout-v3.png'));
 assert.deepEqual(await notice.locator('img').evaluate(i=>[i.naturalWidth,i.naturalHeight,getComputedStyle(i).objectFit]),[384,512,'contain']);
 await toggle(notice,'notice');await toggle(notice,'notice');
 checks.push('Notice: entire portrait card with transparent surround, contain rendering, live on/off');
 const rev=await visit('rev');
 assert((await rev.locator('[data-control-key="dark_night"] img').getAttribute('src')).endsWith('veil-night-v3.png'));
 await toggle(rev,'dark_night');await toggle(rev,'dark_night');
 checks.push('Dark Night: separate moon/cloak image with original toggle');
 const yohan=await visit('yohan');
 assert.equal(await yohan.locator('img[src$="foresight-coin-v3.png"]').count(),10);
 assert.equal(await yohan.locator('img[src$="foresight-painted-v2.png"]').count(),1);
 assert.equal(await yohan.locator('.foresight-eye').count(),0);
 const coins=yohan.locator('[data-control-key="foresight_counter"]');
 // The full-state suite leaves all coins filled: turn one off and back on.
 await coins.locator('.visual-token.is-on').last().click();
 for(let i=0;i<70;i++){if(await coins.locator('.visual-token.is-on').count()===9)break;await page.waitForTimeout(100)}
 assert.equal(await coins.locator('.visual-token.is-on').count(),9);
 await coins.locator('.visual-token:not(.is-on)').last().click();
 for(let i=0;i<70;i++){if(await coins.locator('.visual-token.is-on').count()===10)break;await page.waitForTimeout(100)}
 assert.equal(await coins.locator('.visual-token.is-on').count(),10);
 await toggle(yohan,'disaster_one');await toggle(yohan,'disaster_one');
 checks.push('Yohan: ten coin slots; old red eye only on independent Disaster One; counter decrement/increment and toggle synchronize');
 const iomong=await visit('iomong');
 assert.equal(await iomong.locator('button,img,[data-ambient],.ambient-effect').count(),0);
 const legacy=await page.evaluate(async()=>{const c=window.v2BattleConfig;const s=await(await fetch(c.stateUrl+'?control_token='+c.controlToken)).json();const p=Object.values(s.players).find(p=>p.character.calculator_ui?.theme_key==='iomong'||p.character.name==='이오몽');return p?.passive_state});
 assert.equal(legacy?.['364']?.value,3,'restored legacy data remains untouched');
 checks.push('Iomong: zero controls/images/effects, including existing stored legacy state');
 const jam=await visit('cmyk');
 assert.equal(await jam.locator('img[src$="wave-group-v3.png"]').count(),1);
 assert.equal(await jam.locator('img').evaluate(i=>getComputedStyle(i).objectFit),'contain');
 checks.push('Jam Day: full four-character artwork packaged with contain crop');
 await page.goto('http://127.0.0.1:8767'+pairs[0].classic,{waitUntil:'networkidle'});
 assert.equal(await page.locator('script[src*="calculator-character"],link[href*="calculator-character"],img[src*="calculator-character/symbols/"]').count(),0);
 checks.push('Classic entry loads no character UI script/style/symbols');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(out,'oct19-web-report.json'),JSON.stringify({checks,legacyIomongState:legacy??null,errors},null,2));
 console.log(JSON.stringify({checks,errors}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
