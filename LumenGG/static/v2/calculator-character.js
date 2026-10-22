/* Independent character HUD. Only state actions are shared with the classic UI. */
(function () {
    const root = document.querySelector('[data-battle-session]');
    const model = window.CalculatorVisualModel;
    if (!root || !model) return;
    const language = window.v2BattleConfig?.language || 'ko';
    const displayModel=window.CalculatorAppearanceModel;
    let display=displayModel.defaultAppearance;
    try{display=displayModel.calculatorAppearance(JSON.parse(localStorage.getItem(displayModel.appearanceKey)))}catch{}
    const passiveApis=new Map();
    const displayLabels={
        ko:{settings:'화면 설정',style:'화면 스타일',illustrated:'일러스트',clean:'깔끔하게',brightness:'배경 밝기',reset:'권장 밝기',close:'닫기',local:'화면 설정은 이 기기에만 저장됩니다.'},
        en:{settings:'Display settings',style:'Display style',illustrated:'Illustrated',clean:'Clean',brightness:'Background brightness',reset:'Recommended',close:'Close',local:'Display settings are saved on this device only.'},
        ja:{settings:'表示設定',style:'表示スタイル',illustrated:'イラスト',clean:'シンプル',brightness:'背景の明るさ',reset:'推奨値',close:'閉じる',local:'表示設定はこの端末にのみ保存されます。'},
    }[language]||{};
    const previous = new Map();
    const intents = new Map();
    let suppress = true;
    const get = (player,key,fallback=0) => (player.passive_state?.[key]?.value ?? player.passive_state?.[key]?.count ?? fallback);
    const themeKey = player => player.character?.calculator_ui?.theme_key || 'default';
    const labels = {
        ko: {choose:'조화 효과 선택', hand:'손패'},
        en: {choose:'Choose harmony effect',hand:'Hand'},
        ja: {choose:'調和効果を選択',hand:'手札'},
    }[language] || {choose:'조화 효과 선택',hand:'손패'};
    function node(tag, cls, text) {
        const result=document.createElement(tag);
        if (cls) result.className=cls;
        if (text !== undefined) result.textContent=text;
        return result;
    }
    function glyph(theme) {
        if(display.style==='clean')return symbol('seal',true);
        if (theme==='default') return node('span','visual-emblem');
        const img=node('img','visual-emblem');
        img.src='/static/v2/calculator-character/'+theme+'/emblem.png';
        img.alt=''; img.setAttribute('aria-hidden','true');
        img.addEventListener('error',()=>img.hidden=true);
        return img;
    }
    function crop(name) {
        if(display.style==='clean')return symbol(name,true);
        const info=model.passiveArt[name];
        const holder=node('span','visual-crop');
        holder.setAttribute('aria-hidden','true');
        if (!info) return holder;
        const [x,y,w,h]=info.crop;
        const img=node('img');
        img.alt=''; img.draggable=false;
        img.src='/static/v2/calculator-character/passives/'+info.file;
        Object.assign(img.style,{width:(info.width/w*100)+'%',height:(info.height/h*100)+'%',left:(-x/w*100)+'%',top:(-y/h*100)+'%'});
        img.addEventListener('error',()=>img.hidden=true);
        holder.append(img);
        return holder;
    }
    function symbol(name,active) {
        const clean=display.style==='clean';
        const info=(clean?model.passiveCleanArt:model.passiveSymbolArt)[name];
        const img=node('img','passive-symbol'+(active?'':' is-idle')+(info?.kind==='card'?' is-card-art':''));
        img.src='/static/v2/calculator-character/'+(clean?'clean/':'symbols/')+(info?.file||name+'.png');
        img.alt='';img.draggable=false;img.setAttribute('aria-hidden','true');
        img.addEventListener('error',()=>img.hidden=true);
        return img;
    }
    function aura(host,api,key,active) {
        if(display.style==='clean')return;
        const p=model.visualPresentation(themeKey(api.player),key);
        if(!active || !p.effect)return;
        const effect=node('span','ambient-effect ambient-'+p.effect);
        effect.setAttribute('aria-hidden','true');effect.dataset.ambient=key;
        if(p.color) effect.style.setProperty('--effect-color',p.color);
        for(let i=0;i<3;i++)effect.append(node('i'));
        host.append(effect);
    }
    function artwork(api,key,active) {
        const p=model.visualPresentation(themeKey(api.player),key);
        return p.symbol?symbol(p.symbol,active):glyph(themeKey(api.player));
    }
    function moving(target) {
        return display.style!=='clean' && !suppress && (intents.get(target)||0)>Date.now() && !matchMedia('(prefers-reduced-motion:reduce)').matches;
    }
    function flashClass(api,key,value) {
        if (!moving(api.target)) return '';
        const before=previous.get(api.target);
        if (!before || before.character!==api.player.character?.id) return '';
        const old=get(before.player,key);
        return old===value ? '' : model.passiveActive(value) ? ' just-lit' : ' just-unlit';
    }
    function makeButton(api,cls,label,selected,onClick,disabled=false) {
        const b=node('button',cls);
        b.type='button'; b.title=label; b.setAttribute('aria-label',label);
        b.setAttribute('aria-pressed',String(!!selected));
        b.disabled=!api.canControl || disabled;
        b.addEventListener('click',onClick);
        return b;
    }
    function send(api,key,value) {
        const action=model.visualAction(themeKey(api.player),api.player,api.target,key,value,language);
        if (action) return api.dispatch(action);
    }
    function countCells(api,control,viola=false) {
        const value=Number(model.visualValue(api.player,control));
        const label=model.visualLabel(control,language);
        const row=node('div','visual-token-row'+(viola?' visual-viola':''));
        row.dataset.controlKey=control.key;
        const positions=model.visualTokenPositions(themeKey(api.player));
        if(positions)row.classList.add('visual-token-stage');
        else if ((control.max||0)>=6) row.classList.add('visual-token-grid');
        for (let i=0;i<control.max;i++) {
            const filled=i<value;
            const before=previous.get(api.target);
            const wasFilled=before && i<Number(get(before.player,control.key,control.default||0));
            const changed=before?.character===api.player.character?.id && moving(api.target) && filled!==wasFilled;
            const cell=makeButton(api,'visual-token'+(filled?' is-on':'')+(changed?(filled?' just-lit':' just-unlit'):''),
                label+' '+value+'/'+control.max+(filled?' −1':' +1'),filled,
                ()=>send(api,control.key,model.steppedCounter(api.player,control,filled)),!model.visualEnabled(api.player,control));
            cell.dataset.tokenIndex=i;
            if(positions){
                const pos=positions[i];
                cell.style.left=(pos.x*100)+'%';cell.style.top=(pos.y*100)+'%';
                cell.style.setProperty('--token-angle',pos.rotation+'deg');
            }
            cell.append(viola ? crop('viola') : artwork(api,control.key,filled));
            aura(cell,api,control.key,filled);
            row.append(cell);
        }
        return row;
    }
    function taoPanel(api) {
        const player=api.player;
        const harmony=model.harmonyState(player);
        const locked=model.taoInputLocked(player);
        const effect=String(get(player,'harmony_effect',''));
        const panel=node('div','visual-tao'+(locked?' is-choosing':''));
        const spec=model.visualDefinition('tao');
        function bar(key,shade) {
            const c=spec.controls.find(c=>c.key===key);
            const value=Number(get(player,key));
            const stack=node('div','tao-bar tao-bar-'+shade);
            stack.dataset.controlKey=key;
            for(let i=0;i<4;i++) {
                const filled=i<value;
                const b=makeButton(api,'tao-cell'+(filled?' is-on':''),model.visualLabel(c,language)+' '+value+'/4'+(filled?' −1':' +1'),filled,
                    ()=>send(api,key,model.steppedCounter(player,c,filled)),locked);
                b.dataset.taoCounter=shade==='white'?'yang':'yin';
                b.dataset.tokenIndex=i;
                b.append(node('span','tao-cell-core'));
                aura(b,api,key,filled);
                stack.append(b);
            }
            return stack;
        }
        panel.append(bar('yang_counter','white'));
        const center=node('div','tao-center');
        const old=previous.get(api.target);
        const wasHarmony=old && model.harmonyState(old.player);
        const animate=moving(api.target) && old?.character===player.character?.id;
        const transition=animate && harmony!==wasHarmony ? (harmony?' is-forming':' is-leaving') : '';
        const caption=node('span','tao-effect-caption',harmony && effect ? (effect==='fp_1'?'+1FP':'+100DMG') : '');
        caption.setAttribute('aria-live','polite');
        center.append(caption);
        const sigil=node('div','tao-sigil'+(harmony?' is-harmony':' is-idle')+transition);
        sigil.setAttribute('aria-label',labels.choose);
        const yin=makeButton(api,'tao-half tao-yin'+(effect==='fp_1'?' is-selected':''),'+1FP',effect==='fp_1',
            ()=>send(api,'harmony_effect','fp_1'),!harmony);
        const yang=makeButton(api,'tao-half tao-yang'+(effect==='damage_100'?' is-selected':''),'+100DMG',effect==='damage_100',
            ()=>send(api,'harmony_effect','damage_100'),!harmony);
        yin.dataset.taoEffect='fp_1'; yang.dataset.taoEffect='damage_100';
        if (locked) {yin.append(node('span','tao-choice-hint','+1FP'));yang.append(node('span','tao-choice-hint','+100DMG'));}
        sigil.append(node('span','tao-black-half'),node('span','tao-black-orb'),node('span','tao-white-orb'),node('span','tao-dot tao-dot-white'),node('span','tao-dot tao-dot-black'),yin,yang);
        center.append(sigil);
        aura(sigil,api,'harmony',harmony);
        panel.append(center,bar('yin_counter','black'));
        return panel;
    }
    function ritaPanel(api) {
        const player=api.player;
        const panel=node('div','visual-rita');
        const light=model.passiveActive(get(player,'light_lumen',false));
        const spec=model.visualDefinition('rita');
        const lumen=spec.controls.find(c=>c.key==='light_lumen');
        const button=makeButton(api,'lumen-switch'+(light?' is-on':'')+flashClass(api,'light_lumen',light),
            model.visualLabel(lumen,language),light,()=>send(api,'light_lumen',!light));
        button.dataset.controlKey='light_lumen';
        button.append(crop('condenser'));
        aura(button,api,'light_lumen',light);
        panel.append(button);
        const roles=node('div','legion-row');
        roles.dataset.controlKey='rita_role';
        const choice=spec.controls.find(c=>c.key==='rita_role');
        for (const item of choice.choices) {
            const selected=get(player,'rita_role','')===item.value;
            const name=item.labels?.[language]||item.label;
            const before=previous.get(api.target);
            const changed=before?.character===player.character?.id && moving(api.target) && (get(before.player,'rita_role','')===item.value)!==selected;
            const diamond=makeButton(api,'legion-diamond'+(selected?' is-on':'')+(changed?(selected?' just-lit':' just-unlit'):''),
                name,selected,()=>send(api,'rita_role',selected?'':item.value));
            diamond.dataset.role=item.value;
            diamond.append(crop(item.value));
            aura(diamond,api,'rita_role',selected);
            roles.append(diamond);
        }
        panel.append(roles);
        return panel;
    }
    function genericPanel(api) {
        const theme=themeKey(api.player);
        const spec=model.visualDefinition(theme);
        const panel=node('div','visual-generic passive-layout-'+model.visualLayout(theme));
        if(model.visualLayout(theme)==='empty')return panel;
        let stage=null;
        if (!spec.controls.length) {
            const decoration=node('span','visual-static');
            decoration.setAttribute('aria-hidden','true');
            decoration.append(symbol('seal',true));
            panel.append(decoration);
        }
        for (const control of spec.controls) {
            const label=model.visualLabel(control,language);
            const raw=model.visualValue(api.player,control);
            if(control.type==='counter' && control.max && control.max<=12) {
                const cells=countCells(api,control,theme==='viola');
                panel.append(cells);
                if(cells.classList.contains('visual-token-stage'))stage=cells;
            } else if(control.type==='counter') {
                const row=node('div','visual-free-counter');
                row.dataset.controlKey=control.key;
                const minus=makeButton(api,'visual-step',label+' −1',false,()=>send(api,control.key,Number(raw)-1),Number(raw)<=0);
                const plus=makeButton(api,'visual-step',label+' +1',false,()=>send(api,control.key,Number(raw)+1));
                minus.append(node('span','','−')); plus.append(node('span','','+'));
                const count=node('span','visual-count',String(raw));
                count.setAttribute('aria-label',label+' '+raw);
                const image=node('span','visual-counter-image'+flashClass(api,control.key,Number(raw)));
                image.append(artwork(api,control.key,Number(raw)>0),count);
                aura(image,api,control.key,Number(raw)>0);
                row.append(minus,image,plus);panel.append(row);
            } else if(['toggle','thresholdAction','status'].includes(control.type)) {
                const selected=model.visualActive(api.player,control);
                const b=makeButton(api,'visual-switch'+(selected?' is-on':'')+(model.visualEnabled(api.player,control)?' is-ready':'')+flashClass(api,control.key,selected),
                    label,selected,()=>send(api,control.key,!selected),control.type==='status'||!model.visualEnabled(api.player,control));
                b.dataset.controlKey=control.key;
                if(control.type==='status') b.setAttribute('role','img');
                b.append(artwork(api,control.key,selected));
                aura(b,api,control.key,selected);
                if(control.type==='status')b.classList.add('passive-readonly');
                if(stage){
                    b.classList.add('stage-switch');stage.append(b);
                }else panel.append(b);
            }
        }
        return panel;
    }
    root.querySelectorAll('[data-player-panel]').forEach(panel=>{
        const target=panel.dataset.playerPanel;
        const hand=panel.querySelector('[data-player-hand]');
        const hp=panel.querySelector('.v2-battle-hp>div');
        if (hand && hp) {hand.className='arena-hand'; hp.append(hand);}
        panel.querySelector('.v2-battle-player-head')?.remove();
        const scene=node('div','arena-background');scene.setAttribute('aria-hidden','true');panel.prepend(scene);
        panel.setAttribute('aria-label',target.toUpperCase());
    });
    const partyBar=root.querySelector('.party-calculator-bar');
    if(partyBar){
        const counter=partyBar.querySelector('[data-party-exchanges]');
        const complete=partyBar.querySelector('[data-party-exchange]');
        partyBar.replaceChildren(...[counter,complete].filter(Boolean));
        partyBar.classList.add('arena-party-tools');
        root.querySelector('.v2-battle-center')?.append(partyBar);
    }
    const back=root.querySelector('[data-battle-back]');
    if(back){const url=new URL(back.href);url.searchParams.set('ui','character');back.href=url.toString();}
    root.querySelectorAll('[data-hp-step]').forEach(b=>{
        const amount=Number(b.dataset.hpStep);
        b.dataset.queueLabel=(amount>0?'+':'−')+Math.abs(amount);b.textContent=b.dataset.queueLabel;
        b.setAttribute('aria-label',b.dataset.hpTarget.toUpperCase()+' HP '+(amount>0?'+':'')+amount);
    });
    root.querySelectorAll('.v2-battle-center button,.v2-battle-center a').forEach(b=>{
        if(!b.hasAttribute('aria-label'))b.setAttribute('aria-label',b.textContent.trim());
        b.title=b.getAttribute('aria-label');
    });
    function recordIntent(event) {
        const b=event.target.closest('button');
        const panel=b?.closest('[data-player-panel]');
        if(panel && b.closest('[data-player-passives]') && !b.disabled)intents.set(panel.dataset.playerPanel,Date.now()+5000);
    }
    root.addEventListener('pointerdown',recordIntent,true);
    root.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')recordIntent(e);},true);
    function visibility(){root.dataset.effectsPaused=String(document.hidden);}
    document.addEventListener('visibilitychange',visibility);visibility();
    function drawPassives(api){
        const theme=themeKey(api.player);
        api.root.replaceChildren(theme==='tao'?taoPanel(api):theme==='rita'?ritaPanel(api):genericPanel(api));
        api.renderShieldControls?.();
    }
    function applyDisplay(save=false){
        document.body.dataset.calculatorStyle=display.style;
        document.body.style.setProperty('--arena-shade',String(1-display.brightness/100));
        if(save)try{localStorage.setItem(displayModel.appearanceKey,JSON.stringify(display))}catch{}
        for(const api of passiveApis.values())drawPassives(api);
    }
    applyDisplay();
    const dialog=node('dialog','arena-display-dialog');dialog.setAttribute('aria-label',displayLabels.settings);
    const heading=node('h2','',displayLabels.settings);dialog.append(heading);
    const choices=node('fieldset','arena-display-choices');choices.append(node('legend','',displayLabels.style));
    for(const style of ['illustrated','clean']){
        const label=node('label');const radio=node('input');radio.type='radio';radio.name='calculator-style';radio.value=style;radio.checked=display.style===style;
        radio.addEventListener('change',()=>{display={...display,style};applyDisplay(true);brightnessGroup.hidden=style==='clean'});
        label.append(radio,node('span','',displayLabels[style]));choices.append(label);
    }
    dialog.append(choices);
    const brightnessGroup=node('div','arena-display-brightness');brightnessGroup.hidden=display.style==='clean';
    const brightnessLabel=node('label','',displayLabels.brightness);brightnessLabel.htmlFor='arena-brightness';
    const output=node('output','',display.brightness+'%');output.htmlFor='arena-brightness';
    const slider=node('input');slider.type='range';slider.id='arena-brightness';slider.min='0';slider.max='100';slider.step='5';slider.value=String(display.brightness);
    slider.addEventListener('input',()=>{display={...display,brightness:Number(slider.value)};output.textContent=display.brightness+'%';applyDisplay(true)});
    const reset=node('button','v2-button',displayLabels.reset+' · 35%');reset.type='button';reset.addEventListener('click',()=>{slider.value='35';slider.dispatchEvent(new Event('input'))});
    brightnessGroup.append(brightnessLabel,output,slider,reset);dialog.append(brightnessGroup,node('p','',displayLabels.local));
    const close=node('button','v2-button',displayLabels.close);close.type='button';close.addEventListener('click',()=>dialog.close());dialog.append(close);root.append(dialog);
    dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close()}});
    const clock=root.querySelector('.v2-battle-round-clock');
    if(clock){
        const settings=node('button',clock.className+' arena-display-open');settings.type='button';settings.title=displayLabels.settings;settings.setAttribute('aria-label',displayLabels.settings);settings.setAttribute('aria-haspopup','dialog');
        settings.append(...clock.childNodes);clock.replaceWith(settings);settings.addEventListener('click',()=>dialog.showModal());
    }
    window.addEventListener('storage',event=>{if(event.key!==displayModel.appearanceKey)return;try{display=displayModel.calculatorAppearance(JSON.parse(event.newValue))}catch{display=displayModel.defaultAppearance}applyDisplay();slider.value=String(display.brightness);output.textContent=display.brightness+'%';brightnessGroup.hidden=display.style==='clean';choices.querySelectorAll('input').forEach(r=>r.checked=r.value===display.style)});
    window.characterCalculator={
        suppressMotion(){suppress=true;intents.clear();},
        renderPassives(api){
            passiveApis.set(api.target,api);
            drawPassives(api);
            return true;
        },
        render(state){
            for(const target of ['p1','p2']){
                const player=state.players[target],panel=root.querySelector('[data-player-panel='+target+']');
                if(!panel || !player)continue;
                const theme=player.character?.calculator_ui||{};
                panel.dataset.theme=theme.theme_key||'default';
                panel.style.setProperty('--arena-accent',theme.accent||'#a6b8d4');
                panel.style.setProperty('--arena-secondary',theme.secondary||'#e8eff9');
                if(theme.background)panel.style.setProperty('--arena-scene','url("'+String(theme.background).replaceAll('"','%22')+'")');
                else panel.style.removeProperty('--arena-scene');
                const old=previous.get(target);
                if(old && JSON.stringify(old.player.passive_state)!==JSON.stringify(player.passive_state))intents.delete(target);
                previous.set(target,{character:player.character?.id,player:JSON.parse(JSON.stringify(player))});
            }
            if(state.type!=='tournament'){
                const clock=root.querySelector('.v2-battle-round-clock');
                if(clock)clock.dataset.arena=String(!state.sudden_death);
                if(clock && !state.sudden_death){clock.querySelector('span').textContent='CHARACTER';clock.querySelector('strong').textContent='ARENA';}
            }
            suppress=false;
        },
    };
})();
