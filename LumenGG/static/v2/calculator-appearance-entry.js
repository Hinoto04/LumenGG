/* Entry selections only change a device preference; the session stays unchanged. */
(function(){
 const model=window.CalculatorAppearanceModel;if(!model)return;
 const read=()=>{try{return model.calculatorAppearance(JSON.parse(localStorage.getItem(model.appearanceKey)))}catch{return model.defaultAppearance}};
 function save(style){try{localStorage.setItem(model.appearanceKey,JSON.stringify({...read(),style}))}catch{}}
 document.querySelectorAll('[data-calculator-style]').forEach(choice=>{
  choice.addEventListener(choice.tagName==='INPUT'?'change':'click',()=>save(choice.dataset.calculatorStyle));
 });
 const selected=document.querySelector('input[name="ui"]:checked');
 if(selected?.value==='character'){
  const target=document.querySelector('input[data-calculator-style="'+read().style+'"]');
  if(target)target.checked=true;
 }
})();
