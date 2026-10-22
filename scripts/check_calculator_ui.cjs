const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');
(async()=>{
 const out=path.resolve('artifacts/calculator-character');
 const pairs=JSON.parse(fs.readFileSync(path.join(out,'review-sessions.json'),'utf8'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:844,height:390},reducedMotion:'reduce'});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const report=[];
 for (const [width,height] of [[740,360],[844,390],[1024,768],[1440,900],[390,844]]) {
  await page.setViewportSize({width,height});
  await page.goto('http://127.0.0.1:8767'+pairs[0].character,{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(out,`web-character-${width}x${height}.png`),fullPage:true});
  report.push(await page.evaluate(()=>({viewport:[innerWidth,innerHeight],overflow:document.documentElement.scrollWidth>innerWidth,players:[...document.querySelectorAll('[data-player-panel]')].map(p=>({rect:JSON.parse(JSON.stringify(p.getBoundingClientRect())),hp:p.querySelector('[data-player-hp]').textContent,passive:p.querySelector('[data-player-passives]').innerText})),assets:[...document.images].filter(i=>i.classList.contains('arena-emblem')).map(i=>({src:i.src,loaded:i.complete&&i.naturalWidth>0}))})));
 }
 await page.setViewportSize({width:844,height:390});
 for(let i=0;i<pairs.length;i++){
  await page.goto('http://127.0.0.1:8767'+pairs[i].character,{waitUntil:'networkidle'});
  await page.screenshot({path:path.join(out,`web-pair-${i+1}.png`),fullPage:true});
 }
 await page.goto('http://127.0.0.1:8767'+pairs[0].classic,{waitUntil:'networkidle'});
 await page.screenshot({path:path.join(out,'web-classic-844x390.png'),fullPage:true});
 report.push({classic:await page.evaluate(()=>({characterClass:document.body.classList.contains('v2-character-calculator'),newAssets:performance.getEntriesByType('resource').filter(r=>/calculator-character\//.test(r.name)).map(r=>r.name)}))});
 fs.writeFileSync(path.join(out,'web-layout-report.json'),JSON.stringify({report,errors},null,2));
 console.log(JSON.stringify({pages:report.length,errors,overflow:report.filter(r=>r.overflow).length},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1;});
