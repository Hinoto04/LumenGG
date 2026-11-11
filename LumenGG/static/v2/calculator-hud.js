/* 통합 계산기 HUD: 캐릭터 테마, 화면 설정, 패시브 트레이. 상태 변경은 battle-calculator.js가 맡는다. */
(function () {
    const root = document.querySelector('.lc[data-battle-session]');
    const tray = window.CalculatorPassiveTray;
    if (!root || !tray) return;
    const language = window.v2BattleConfig?.language || 'ko';
    const words = {
        ko: {settings: '화면 설정', style: '배경', illustrated: '일러스트', clean: '단색', brightness: '일러스트 밝기', reset: '권장값', close: '닫기', local: '이 기기에만 저장됩니다.', passive: '패시브', none: '조작할 패시브가 없습니다.', on: 'ON', off: 'OFF', use: '발동', using: '발동 중', ready: '사용 가능'},
        en: {settings: 'Display', style: 'Background', illustrated: 'Illustrated', clean: 'Solid', brightness: 'Illustration brightness', reset: 'Default', close: 'Close', local: 'Saved on this device only.', passive: 'Passive', none: 'No passive to track.', on: 'ON', off: 'OFF', use: 'Use', using: 'Active', ready: 'Ready'},
        ja: {settings: '表示設定', style: '背景', illustrated: 'イラスト', clean: '単色', brightness: 'イラストの明るさ', reset: '推奨値', close: '閉じる', local: 'この端末にのみ保存されます。', passive: 'パッシブ', none: '操作するパッシブはありません。', on: 'ON', off: 'OFF', use: '発動', using: '発動中', ready: '使用可'},
    }[language] || {};
    const w = (key) => words[key] || key;

    function el(tag, cls, text) {
        const node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }
    function button(cls, label, onClick, disabled) {
        const node = el('button', cls);
        node.type = 'button';
        node.disabled = !!disabled;
        if (label) node.setAttribute('aria-label', label);
        node.addEventListener('click', onClick);
        return node;
    }
    function icon(symbol) {
        if (!symbol) return null;
        const img = el('img', 'lc-passive-icon');
        img.src = `/static/v2/calculator-character/clean/${symbol}.png`;
        img.alt = ''; img.draggable = false;
        img.addEventListener('error', () => img.remove());
        return img;
    }

    /* ---------- 화면 설정 ---------- */
    const appearance = window.CalculatorAppearanceModel;
    let display = appearance ? appearance.defaultAppearance : {style: 'illustrated', brightness: 35};
    try { if (appearance) display = appearance.calculatorAppearance(JSON.parse(localStorage.getItem(appearance.appearanceKey))); } catch (error) { /* 기본값 */ }
    const apis = new Map();
    function applyDisplay(save) {
        root.dataset.calculatorStyle = display.style;
        root.style.setProperty('--lc-shade', String(1 - display.brightness / 100));
        if (save && appearance) { try { localStorage.setItem(appearance.appearanceKey, JSON.stringify(display)); } catch (error) { /* 저장 불가 */ } }
        apis.forEach(render);
    }
    const dialog = el('dialog', 'lc-dialog');
    dialog.setAttribute('aria-label', w('settings'));
    dialog.append(el('h2', '', w('settings')));
    const styleGroup = el('div', 'lc-segment');
    styleGroup.setAttribute('role', 'radiogroup');
    styleGroup.setAttribute('aria-label', w('style'));
    const styleButtons = ['illustrated', 'clean'].map((style) => {
        const option = button('', w(style), () => { display = {...display, style}; sync(); applyDisplay(true); });
        option.textContent = w(style);
        option.setAttribute('role', 'radio');
        option.dataset.style = style;
        return option;
    });
    styleGroup.append(...styleButtons);
    const brightness = el('label', 'lc-range');
    const brightnessText = el('span', '', w('brightness'));
    const brightnessValue = el('output');
    const slider = el('input');
    Object.assign(slider, {type: 'range', min: '0', max: '100', step: '5'});
    slider.addEventListener('input', () => { display = {...display, brightness: Number(slider.value)}; sync(); applyDisplay(true); });
    brightness.append(brightnessText, brightnessValue, slider);
    const actions = el('div', 'lc-dialog-actions');
    actions.append(
        button('lc-chip', w('reset'), () => { display = {...display, brightness: 35}; sync(); applyDisplay(true); }),
        button('lc-chip is-primary', w('close'), () => dialog.close()),
    );
    actions.children[0].textContent = w('reset') + ' 35%';
    actions.children[1].textContent = w('close');
    dialog.append(el('p', 'lc-dialog-label', w('style')), styleGroup, brightness, el('p', 'lc-dialog-note', w('local')), actions);
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    root.append(dialog);
    function sync() {
        styleButtons.forEach((option) => option.setAttribute('aria-checked', String(option.dataset.style === display.style)));
        slider.value = String(display.brightness);
        brightnessValue.textContent = display.brightness + '%';
        brightness.hidden = display.style === 'clean';
        actions.children[0].hidden = display.style === 'clean';
    }
    sync();
    root.querySelectorAll('[data-display-open]').forEach((open) => open.addEventListener('click', () => dialog.showModal()));
    window.addEventListener('storage', (event) => {
        if (!appearance || event.key !== appearance.appearanceKey) return;
        try { display = appearance.calculatorAppearance(JSON.parse(event.newValue)); } catch (error) { display = appearance.defaultAppearance; }
        sync(); applyDisplay(false);
    });

    /* ---------- 캐릭터 테마 ---------- */
    const cssUrl = (value) => `url("${String(value).replaceAll('"', '%22')}")`;
    window.addEventListener('lumen-calculator-state', (event) => {
        const state = event.detail;
        for (const target of ['p1', 'p2']) {
            const panel = root.querySelector(`[data-player-panel="${target}"]`);
            const character = state.players?.[target]?.character;
            if (!panel) continue;
            const theme = character?.calculator_ui || {};
            panel.dataset.theme = theme.theme_key || 'default';
            panel.style.setProperty('--lc-accent', theme.accent || character?.color || '#c9a45c');
            panel.style.setProperty('--lc-accent-2', theme.secondary || '#f1e7d2');
            if (character?.img) panel.style.setProperty('--lc-art', cssUrl(character.img));
            else panel.style.removeProperty('--lc-art');
            const label = panel.querySelector(`[data-player-character="${target}"]`);
            if (label) label.textContent = character?.name || '';
            const avatar = panel.querySelector(`[data-player-avatar="${target}"]`);
            if (avatar) {
                const src = character?.icon_img || theme.emblem || '';
                if (src && avatar.dataset.src !== src) {
                    avatar.dataset.src = src;
                    const img = el('img'); img.src = src; img.alt = ''; img.addEventListener('error', () => img.remove());
                    avatar.replaceChildren(img);
                } else if (!src) { avatar.dataset.src = ''; avatar.replaceChildren(); }
            }
            // 기록 패널의 플레이어 색
            root.style.setProperty(`--lc-${target}`, theme.accent || character?.color || (target === 'p1' ? '#45d0a0' : '#b892ff'));
            const player = state.players?.[target];
            const ratio = player && player.initial_hp ? player.hp / player.initial_hp : 1;
            panel.classList.toggle('is-low', ratio <= 0.3);
            panel.classList.toggle('is-down', !!player && player.hp <= 0);
        }
    });

    /* ---------- 패시브 트레이 ---------- */
    function render(api) {
        apis.set(api.target, api);
        const definition = api.player.character?.passive || {};
        const items = api.player.character ? tray.passiveTray(api.player, definition, language) : [];
        const send = (key, value) => {
            const action = tray.trayAction(api.player, definition, api.target, key, value, language);
            if (action) api.dispatch(action);
        };
        const locked = !api.canControl;
        const list = el('div', 'lc-tray');
        list.setAttribute('role', 'group');
        list.setAttribute('aria-label', w('passive'));
        for (const item of items) list.append(trayItem(item, send, locked));
        api.root.replaceChildren();
        if (items.length) api.root.append(list);
        else if (api.player.character) api.root.append(el('p', 'lc-tray-empty', w('none')));
        // 보호막 버튼은 엔진이 이어서 붙이므로 그 뒤에 맞춘다.
        setTimeout(() => fit(api.root), 0);
        if (sizes && !observed.has(api.root)) { observed.add(api.root); sizes.observe(api.root); }
    }
    const observed = new WeakSet();
    const sizes = 'ResizeObserver' in window ? new ResizeObserver((entries) => entries.forEach((entry) => fit(entry.target))) : null;

    /* 스크롤 없이 들어가도록 넘치면 안내 문구 → 아이콘·간격 순으로 줄인다. */
    function overflowing(holder) {
        if (holder.scrollHeight > holder.clientHeight + 1) return true;
        const list = holder.querySelector('.lc-tray');
        return !!list && list.scrollHeight > list.clientHeight + 1;
    }
    /* 들어가는 가장 큰 단계를 고른다: 여유가 있으면 누르는 칸을 키우고, 넘치면 줄인다. */
    const LEVELS = ['is-roomiest', 'is-roomy', '', 'is-tight', 'is-tighter', 'is-tightest'];
    function fit(holder) {
        for (const level of LEVELS) {
            const classes = level === 'is-roomiest' ? ['is-roomy', 'is-roomiest'] : level ? [level] : [];
            holder.classList.remove(...LEVELS.filter(Boolean));
            if (level === 'is-tighter') classes.unshift('is-tight');
            if (level === 'is-tightest') classes.unshift('is-tight', 'is-tighter');
            holder.classList.add(...classes);
            if (!overflowing(holder) || level === 'is-tightest') return;
        }
    }
    window.addEventListener('resize', () => apis.forEach((api) => fit(api.root)));

    /* 넉넉한 단계(is-roomy)에서만 보이는 패시브 그림. 버튼을 그림으로 구분하게 한다. */
    function art(name, cls) {
        const file = name && tray.artFile(name);
        if (!file) return null;
        const img = el('img', cls || 'lc-passive-art');
        img.src = `/static/v2/calculator-character/clean/${file}`;
        img.alt = ''; img.draggable = false; img.loading = 'lazy';
        img.addEventListener('error', () => img.remove());
        return img;
    }
    function head(item, extra) {
        const top = el('span', 'lc-passive-head');
        const picture = art(item.art);
        if (picture) top.append(picture);
        const ico = icon(item.symbol);
        if (ico) top.append(ico);
        const name = el('span', 'lc-passive-name', item.label);
        top.append(name);
        if (extra) top.append(extra);
        return top;
    }
    function hint(item) {
        return item.hint ? el('span', 'lc-passive-hint', item.hint) : null;
    }

    function trayItem(item, send, locked) {
        const card = el('div', `lc-passive is-${item.kind}` + (item.active ? ' is-active' : '') + (item.enabled ? '' : ' is-blocked'));
        card.dataset.controlKey = item.key;
        if (item.attention) card.classList.add('is-ready');
        if (item.kind === 'toggle' || item.kind === 'trigger') {
            const isTrigger = item.kind === 'trigger';
            const state = isTrigger
                ? (item.active ? w('using') : item.ready ? w('ready') : w('use'))
                : (item.active ? w('on') : w('off'));
            const pill = el('span', 'lc-pill', state);
            const press = button('lc-passive-press', `${item.label} ${state}`, () => send(item.key, !item.active), locked || !item.enabled);
            press.setAttribute(isTrigger ? 'aria-pressed' : 'role', isTrigger ? String(item.active) : 'switch');
            if (!isTrigger) press.setAttribute('aria-checked', String(item.active));
            press.append(head(item, pill));
            const note = hint(item);
            if (note) press.append(note);
            card.append(press);
            return card;
        }
        if (item.kind === 'status') {
            card.setAttribute('role', 'status');
            card.append(head(item, el('span', 'lc-pill', item.active ? w('on') : w('off'))));
            const note = hint(item);
            if (note) card.append(note);
            return card;
        }
        if (item.kind === 'counter') {
            const value = Number(item.value) || 0;
            const counted = el('span', 'lc-count', item.max ? `${value}/${item.max}` : `${value}${item.unit || ''}`);
            card.append(head(item, counted));
            const row = el('div', 'lc-counter');
            const blocked = locked || !item.enabled;
            const minus = button('lc-step', `${item.label} −1`, () => send(item.key, value - 1), blocked || value <= 0);
            minus.textContent = '−';
            row.append(minus);
            if (item.max && item.max <= 12) {
                const pips = el('div', 'lc-pips');
                pips.style.setProperty('--pips', String(item.max));
                for (let index = 0; index < item.max; index += 1) {
                    const pip = button('lc-pip' + (index < value ? ' is-on' : ''), `${item.label} ${tray.pipValue(value, index)}`, () => send(item.key, tray.pipValue(value, index)), blocked);
                    pips.append(pip);
                }
                row.append(pips);
            } else {
                row.append(el('span', 'lc-counter-value', String(value)));
            }
            const plus = button('lc-step', `${item.label} +1`, () => send(item.key, value + 1), blocked || (item.max != null && value >= item.max));
            plus.textContent = '+';
            row.append(plus);
            card.append(row);
            const note = hint(item);
            if (note) card.append(note);
            return card;
        }
        if (item.kind === 'choice') {
            card.append(head(item));
            const group = el('div', 'lc-choices');
            group.setAttribute('role', 'radiogroup');
            group.setAttribute('aria-label', item.label);
            for (const choice of item.choices || []) {
                const option = button('lc-choice' + (choice.selected ? ' is-on' : ''), `${item.label} ${choice.label}`, () => send(item.key, choice.value), locked || !item.enabled);
                const choiceArt = art(choice.art, 'lc-choice-art');
                if (choiceArt) option.append(choiceArt);
                option.append(el('span', '', choice.label));
                option.setAttribute('role', 'radio');
                option.setAttribute('aria-checked', String(choice.selected));
                group.append(option);
            }
            card.append(group);
            const note = hint(item);
            if (note) card.append(note);
            return card;
        }
        card.append(head(item));
        const input = el('input', 'lc-text');
        input.value = String(item.value ?? '');
        input.disabled = locked || !item.enabled;
        input.setAttribute('aria-label', item.label);
        input.addEventListener('change', () => send(item.key, input.value));
        card.append(input);
        return card;
    }

    window.calculatorTray = {render};
    applyDisplay(false);
})();
