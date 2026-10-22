const fs=require("fs"),{chromium}=require("playwright"),assert=require("node:assert/strict");
(async()=>{
 const pair=JSON.parse(fs.readFileSync("artifacts/calculator-character/review-sessions.json","utf8"))[0];
 const browser=await chromium.launch({channel:"msedge",headless:true});
 const page=await browser.newPage({viewport:{width:740,height:360},reducedMotion:"reduce"});
 await page.route(url=>url.pathname.includes("/control/")&&url.searchParams.get("ui")==="character",async route=>{
  const response=await route.fetch();let html=await response.text();
  const banner='<div class="party-calculator-bar"><a data-party-return href="/">파티 지도</a><p>교전 <strong data-party-exchanges>0/2</strong><span data-party-calculator-help>HP·FP 입력 후 공방 완료</span></p><button class="v2-button" data-party-exchange>공방 완료</button></div>';
  html=html.replace('<div class="v2-page-head">',banner+'<div class="v2-page-head">');
  html=html.replace(/<button[^>]+data-battle-action="sudden"[\s\S]*?<\/button>/,"");
  await route.fulfill({response,body:html});
 });
 await page.goto("http://127.0.0.1:8767"+pair.character,{waitUntil:"networkidle"});
 const report=await page.evaluate(()=>({
  center:!!document.querySelector(".v2-battle-center .arena-party-tools [data-party-exchange]"),
  passives:[...document.querySelectorAll("[data-player-passives]")].map(p=>({height:p.clientHeight,content:p.scrollHeight})),
  overflow:document.documentElement.scrollWidth>innerWidth
 }));
 assert(report.center&&!report.overflow&&report.passives.every(p=>p.content<=p.height+1&&p.height>=179));
 await page.screenshot({path:"artifacts/calculator-character/visual-party-layout.png"});
 fs.writeFileSync("artifacts/calculator-character/visual-party-layout-report.json",JSON.stringify(report,null,2));
 console.log(report);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
