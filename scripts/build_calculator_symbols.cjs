/* Package authored raster masters and unchanged original-card crops.
 * Run with sharp from the workspace dependency runtime via NODE_PATH.
 * The only SVG below is a rounded crop mask; it never draws an ability icon. */
const fs=require("fs"),path=require("path"),sharp=require("sharp");
const root=path.resolve(__dirname,"..");
const manifest=require(path.join(root,"LumenGG/content/calculator-symbol-art.json"));
const out=path.join(root,"LumenGG/static/v2/calculator-character/symbols");
fs.mkdirSync(out,{recursive:true});
(async()=>{
 for(const [key,asset] of Object.entries(manifest)){
  let image=sharp(path.join(root,asset.source));
  if(asset.kind==="card"){
   const [left,top,width,height]=asset.crop;
   image=image.extract({left,top,width,height}).resize(480,480,{fit:asset.fit||"cover",background:{r:0,g:0,b:0,alpha:0}});
   const mask=Buffer.from('<svg width="480" height="480"><rect width="480" height="480" rx="42" fill="white"/></svg>');
   const clipped=await image.ensureAlpha().composite([{input:mask,blend:"dest-in"}]).png().toBuffer();
   image=sharp(clipped).extend({top:16,bottom:16,left:16,right:16,background:{r:0,g:0,b:0,alpha:0}});
  }else{
   const meta=await image.metadata();
   if(!meta.hasAlpha)throw Error(key+" must preserve generated transparency");
   const [width,height]=asset.canvas||[512,512];
   if(asset.trim_alpha)image=image.trim({background:{r:0,g:0,b:0,alpha:0},threshold:1});
   image=image.resize(width-48,height-48,{fit:"contain",background:{r:0,g:0,b:0,alpha:0}}).extend({top:24,bottom:24,left:24,right:24,background:{r:0,g:0,b:0,alpha:0}});
  }
  await image.png({compressionLevel:9}).toFile(path.join(out,asset.file));
 }
 console.log(Object.keys(manifest).length+" raster icons packaged: generated illustration + original card crop.");
})().catch(e=>{console.error(e);process.exit(1)});
