const fs=require("fs"),path=require("path"),assert=require("node:assert/strict");
const {chromium}=require("playwright");
(async()=>{
 const out=path.resolve("artifacts/calculator-character");
 const pairs=JSON.parse(fs.readFileSync(path.join(out,"visual-review-sessions.json"),"utf8"));
 const browser=await chromium.launch({channel:"msedge",headless:true});
 const page=await browser.newPage({viewport:{width:740,height:360},reducedMotion:"reduce"});
 const errors=[];page.on("pageerror",e=>errors.push(String(e)));
 const report=[];
 for(const pair of pairs){
  await page.goto("http://127.0.0.1:8767"+pair.character,{waitUntil:"networkidle"});
  report.push(await page.evaluate(()=>({
   themes:[...document.querySelectorAll("[data-player-panel]")].map(p=>p.dataset.theme),
   overflow:document.documentElement.scrollWidth>innerWidth,
   panels:[...document.querySelectorAll("[data-player-passives]")].map(p=>{
    const r=p.getBoundingClientRect();
    return {theme:p.closest("[data-player-panel]").dataset.theme,height:p.clientHeight,content:p.scrollHeight,scrollWidth:p.scrollWidth,width:p.clientWidth,
     outside:[...p.querySelectorAll("button")].filter(b=>{const q=b.getBoundingClientRect();if(!q.width||!q.height)return false;return q.left<r.left-1||q.top<r.top-1||q.right>r.right+1||q.bottom>r.bottom+1}).length,
     small:[...p.querySelectorAll("button")].filter(b=>{const q=b.getBoundingClientRect();if(!q.width||!q.height)return false;return q.width<43||q.height<43}).length};
   }),
   headers:document.querySelectorAll(".v2-battle-player-head,.arena-character-name,.arena-emblem").length,
   handInHp:[...document.querySelectorAll("[data-player-hand]")].every(p=>p.parentElement.matches(".v2-battle-hp>div")),
   mirror:getComputedStyle(document.querySelector("[data-player-panel='p1'] .arena-background")).transform
  })));
  if(pair.characters.includes("타오")||pair.characters.includes("비올라")||pair.characters.includes("리타"))
   await page.screenshot({path:path.join(out,"visual-"+pair.characters.join("-")+".png")});
 }
 const viewports=[];
 const special=pairs.find(p=>p.characters.includes("비올라"));
 for(const [width,height] of [[844,390],[1024,768],[1440,900],[390,844]]){
  await page.setViewportSize({width,height});
  await page.goto("http://127.0.0.1:8767"+special.character,{waitUntil:"networkidle"});
  viewports.push(await page.evaluate(()=>({
    viewport:[innerWidth,innerHeight],overflow:document.documentElement.scrollWidth>innerWidth,
    passives:[...document.querySelectorAll("[data-player-passives]")].map(p=>({height:p.clientHeight,content:p.scrollHeight,width:p.clientWidth,scrollWidth:p.scrollWidth}))
  })));
  await page.screenshot({path:path.join(out,"visual-"+width+"x"+height+".png"),fullPage:true});
 }
 fs.writeFileSync(path.join(out,"visual-layout-report.json"),JSON.stringify({report,viewports,errors},null,2));
 console.log(JSON.stringify({pairs:report.length,errors,problems:report.filter(r=>r.overflow||r.panels.some(p=>p.content>p.height+1||p.outside||p.small))},null,2));
 assert.equal(errors.length,0);
 assert(viewports.every(v=>!v.overflow&&v.passives.every(p=>p.content<=p.height+1&&p.scrollWidth<=p.width+1)));
 assert(report.every(r=>!r.overflow&&r.headers===0&&r.handInHp));
 assert(report.every(r=>r.panels.every(p=>p.content<=p.height+1&&p.scrollWidth<=p.width+1&&p.outside===0&&p.small===0)));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
