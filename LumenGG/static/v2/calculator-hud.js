/* 통합 계산기 HUD: 캐릭터 테마, 화면 설정, HP 버튼 방식, 패시브. 상태 변경은 battle-calculator.js가 맡는다. */
(function () {
    const root = document.querySelector('.lc[data-battle-session]');
    const tray = window.CalculatorPassiveTray;
    const layout = window.CalculatorLayout;
    if (!root || !tray || !layout) return;
    const language = window.v2BattleConfig?.language || 'ko';
    const words = {
        ko: {settings: '화면 설정', style: '배경', illustrated: '일러스트', clean: '단색', brightness: '일러스트 밝기', reset: '권장값', close: '닫기', local: '이 기기에만 저장됩니다.', passive: '패시브', none: '조작할 패시브가 없습니다.', on: 'ON', off: 'OFF', use: '발동', using: '발동 중', ready: '사용 가능', resetCount: '눌러서 초기화', hpButtons: 'HP 버튼', four: '4버튼', eight: '8버튼', chooseTitle: 'HP 버튼 방식', chooseNote: '처음 한 번만 묻습니다. 나중에 화면 설정에서 바꿀 수 있습니다.', shieldNote: '4버튼은 두 번째 줄에 보호막 버튼이 들어갑니다. 보호막 특성(핀프 등)은 8버튼이어도 4버튼 + 보호막 줄입니다.'},
        en: {settings: 'Display', style: 'Background', illustrated: 'Illustrated', clean: 'Solid', brightness: 'Illustration brightness', reset: 'Default', close: 'Close', local: 'Saved on this device only.', passive: 'Passive', none: 'No passive to track.', on: 'ON', off: 'OFF', use: 'Use', using: 'Active', ready: 'Ready', resetCount: 'tap to reset', hpButtons: 'HP buttons', four: '4 buttons', eight: '8 buttons', chooseTitle: 'HP button layout', chooseNote: 'Asked once. You can change it later in Display.', shieldNote: '4 buttons put the shield controls on the second row. Shield traits (such as Finf) always use 4 buttons and a shield row.'},
        ja: {settings: '表示設定', style: '背景', illustrated: 'イラスト', clean: '単色', brightness: 'イラストの明るさ', reset: '推奨値', close: '閉じる', local: 'この端末にのみ保存されます。', passive: 'パッシブ', none: '操作するパッシブはありません。', on: 'ON', off: 'OFF', use: '発動', using: '発動中', ready: '使用可', resetCount: 'タップでリセット', hpButtons: 'HPボタン', four: '4ボタン', eight: '8ボタン', chooseTitle: 'HPボタンの配置', chooseNote: '最初の一度だけ確認します。後で表示設定から変更できます。', shieldNote: '4ボタンでは2列目にシールドボタンが入ります。シールド特性(フィンフなど)は8ボタンでも4ボタンとシールド列です。'},
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
        if (label) { node.setAttribute('aria-label', label); node.title = label; }
        node.addEventListener('click', onClick);
        return node;
    }

    /* ---------- 화면 설정 · HP 버튼 방식 ---------- */
    const appearance = window.CalculatorAppearanceModel;
    let display = appearance ? appearance.defaultAppearance : {style: 'illustrated', brightness: 35, hpButtons: null};
    try { if (appearance) display = appearance.calculatorAppearance(JSON.parse(localStorage.getItem(appearance.appearanceKey))); } catch (error) { /* 기본값 */ }
    const apis = new Map();
    function save() {
        if (!appearance) return;
        try { localStorage.setItem(appearance.appearanceKey, JSON.stringify(display)); } catch (error) { /* 저장 불가 */ }
    }
    function applyDisplay(persist) {
        root.dataset.calculatorStyle = display.style;
        root.dataset.hpButtons = display.hpButtons || '4';
        root.style.setProperty('--lc-shade', String(1 - display.brightness / 100));
        if (persist) save();
        apis.forEach(render);
    }
    function segment(label, options, current, onPick) {
        const group = el('div', 'lc-segment');
        group.setAttribute('role', 'radiogroup');
        group.setAttribute('aria-label', label);
        const buttons = options.map(([value, text]) => {
            const option = button('', text, () => onPick(value));
            option.textContent = text;
            option.setAttribute('role', 'radio');
            option.dataset.value = value;
            return option;
        });
        group.append(...buttons);
        group.sync = (value) => buttons.forEach((option) => option.setAttribute('aria-checked', String(option.dataset.value === value)));
        group.sync(current);
        return group;
    }
    const dialog = el('dialog', 'lc-dialog');
    dialog.setAttribute('aria-label', w('settings'));
    dialog.append(el('h2', '', w('settings')));
    const styleGroup = segment(w('style'), [['illustrated', w('illustrated')], ['clean', w('clean')]], display.style, (style) => { display = {...display, style}; sync(); applyDisplay(true); });
    const hpGroup = segment(w('hpButtons'), [['4', w('four')], ['8', w('eight')]], display.hpButtons || '4', (hpButtons) => { display = {...display, hpButtons}; sync(); applyDisplay(true); });
    const brightness = el('label', 'lc-range');
    const brightnessValue = el('output');
    const slider = el('input');
    Object.assign(slider, {type: 'range', min: '0', max: '100', step: '5'});
    slider.addEventListener('input', () => { display = {...display, brightness: Number(slider.value)}; sync(); applyDisplay(true); });
    brightness.append(el('span', '', w('brightness')), brightnessValue, slider);
    const actions = el('div', 'lc-dialog-actions');
    const resetButton = button('lc-chip', w('reset'), () => { display = {...display, brightness: 35}; sync(); applyDisplay(true); });
    resetButton.textContent = w('reset') + ' 35%';
    const closeButton = button('lc-chip is-primary', w('close'), () => dialog.close());
    closeButton.textContent = w('close');
    actions.append(resetButton, closeButton);
    dialog.append(el('p', 'lc-dialog-label', w('hpButtons')), hpGroup, el('p', 'lc-dialog-label', w('style')), styleGroup, brightness, el('p', 'lc-dialog-note', w('local')), actions);
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    root.append(dialog);
    function sync() {
        styleGroup.sync(display.style);
        hpGroup.sync(display.hpButtons || '4');
        slider.value = String(display.brightness);
        brightnessValue.textContent = display.brightness + '%';
        brightness.hidden = display.style === 'clean';
        resetButton.hidden = display.style === 'clean';
    }
    sync();
    root.querySelectorAll('[data-display-open]').forEach((open) => open.addEventListener('click', () => dialog.showModal()));
    window.addEventListener('storage', (event) => {
        if (!appearance || event.key !== appearance.appearanceKey) return;
        try { display = appearance.calculatorAppearance(JSON.parse(event.newValue)); } catch (error) { display = appearance.defaultAppearance; }
        sync(); applyDisplay(false);
    });

    /* 처음 접속한 조작자에게 HP 버튼 방식을 한 번 묻는다. 관전자는 묻지 않는다. */
    function preview(steps) {
        const rows = el('span', 'lc-choose-preview');
        for (const row of steps) {
            const line = el('span', 'lc-choose-row');
            for (const value of row) line.append(el('i', value < 0 ? 'is-damage' : 'is-heal', (value > 0 ? '+' : '−') + Math.abs(value)));
            rows.append(line);
        }
        return rows;
    }
    let asked = false;
    function askHpButtons(state) {
        if (asked || display.hpButtons || !state.can_control) return;
        asked = true;
        const chooser = el('dialog', 'lc-dialog lc-choose');
        chooser.setAttribute('aria-label', w('chooseTitle'));
        const options = el('div', 'lc-choose-options');
        for (const [mode, rows] of [['4', [layout.HP_STEPS_4]], ['8', [layout.HP_STEPS_8.slice(0, 4), layout.HP_STEPS_8.slice(4)]]]) {
            const option = button('lc-choose-option', w(mode === '4' ? 'four' : 'eight'), () => {
                display = {...display, hpButtons: mode};
                sync(); applyDisplay(true); chooser.close(); chooser.remove();
            });
            option.append(el('strong', '', w(mode === '4' ? 'four' : 'eight')), preview(rows));
            options.append(option);
        }
        chooser.append(el('h2', '', w('chooseTitle')), el('p', 'lc-dialog-note', w('chooseNote')), options, el('p', 'lc-dialog-note', w('shieldNote')));
        root.append(chooser);
        chooser.showModal();
    }

    /* ---------- 캐릭터 테마 · HP 바 ---------- */
    const cssUrl = (value) => `url("${String(value).replaceAll('"', '%22')}")`;
    const shieldModel = window.CalculatorShieldModel;
    window.addEventListener('lumen-calculator-state', (event) => {
        const state = event.detail;
        for (const target of ['p1', 'p2']) {
            const panel = root.querySelector(`[data-player-panel="${target}"]`);
            const player = state.players?.[target];
            const character = player?.character;
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
            root.style.setProperty(`--lc-${target}`, theme.accent || character?.color || (target === 'p1' ? '#45d0a0' : '#b892ff'));
            // 보호막 특성은 8버튼 설정이어도 4버튼 + 보호막 줄. 보호막 양은 HP 바 끝에 파란 구간
            const hasShield = !!(player && shieldModel?.prefersShieldRow(player));
            const shield = player && shieldModel ? shieldModel.shieldAmount(player) : 0;
            const bar = layout.hpBar(player?.hp || 0, player?.initial_hp || 0, shield);
            panel.classList.toggle('has-shield', hasShield);
            panel.style.setProperty('--lc-bar-hp', bar.hp.toFixed(4));
            panel.style.setProperty('--lc-bar-shield', bar.shield.toFixed(4));
            panel.classList.toggle('is-low', bar.ratio <= 0.3);
            panel.classList.toggle('is-down', !!player && player.hp <= 0);
        }
        askHpButtons(state);
    });

    /* ---------- 패시브: 카드 그림 · 불빛 · ± ---------- */
    function crop(api, key, index, cls) {
        const tile = el('span', 'lc-crop' + (cls ? ' ' + cls : ''));
        tile.setAttribute('aria-hidden', 'true');
        const image = layout.passiveCardImage(api.player.character);
        if (image) {
            const area = layout.cropBackground(layout.cardCrop(api.player.character?.calculator_ui?.theme_key || '', key, index));
            tile.style.backgroundImage = cssUrl(image);
            tile.style.backgroundSize = area.size;
            tile.style.backgroundPosition = area.position;
        }
        return tile;
    }
    function artTile(name, cls) {
        const file = name && tray.artFile(name);
        if (!file) return null;
        const tile = el('span', 'lc-crop is-art' + (cls ? ' ' + cls : ''));
        tile.setAttribute('aria-hidden', 'true');
        tile.style.backgroundImage = cssUrl(`/static/v2/calculator-character/clean/${file}`);
        return tile;
    }
    /* 카드 그림 크롭이 기본, 카드 그림이 없을 때만 패시브 아이콘 그림 */
    function picture(api, item, index, cls) {
        if (item.token) {
            // 토큰 카운터는 그 토큰 카드의 그림을 쓴다.
            const tile = el('span', 'lc-crop is-token' + (cls ? ' ' + cls : ''));
            tile.setAttribute('aria-hidden', 'true');
            const area = layout.cropBackground(layout.TOKEN_CROP);
            tile.style.backgroundImage = cssUrl(item.token);
            tile.style.backgroundSize = area.size;
            tile.style.backgroundPosition = area.position;
            return tile;
        }
        if (layout.passiveCardImage(api.player.character)) return crop(api, item.key, index, cls);
        return artTile(item.art, cls) || crop(api, item.key, index, cls);
    }
    // 개수 표시(불빛·×N). 누르는 곳은 이걸 담은 박스 전체다(resettable).
    function lights(api, item) {
        const value = Number(item.value) || 0;
        if (!item.max || item.max > 12) return el('span', 'lc-lights lc-count', `×${value}`);
        const node = el('span', 'lc-lights');
        for (let index = 0; index < item.max; index += 1) node.append(el('span', 'lc-light' + (index < value ? ' is-on' : '')));
        return node;
    }
    // 카운터 박스 전체를 누르면 0으로 초기화한다. ± 버튼과 그 주변(버튼의 넓힌 누름 영역)은 ±로 동작한다.
    function resettable(node, item, send, blocked) {
        const value = Number(item.value) || 0;
        const off = blocked || value <= 0;
        node.classList.add('lc-resettable');
        node.setAttribute('role', 'button');
        node.setAttribute('aria-label', `${item.label} ${value} · ${w('resetCount')}`);
        node.setAttribute('aria-disabled', String(off));
        node.tabIndex = off ? -1 : 0;
        const reset = () => { if (!off) send(item.key, 0); };
        node.addEventListener('click', reset);
        node.addEventListener('keydown', (event) => {
            if (event.target !== node || (event.key !== 'Enter' && event.key !== ' ')) return;
            event.preventDefault();
            reset();
        });
        return node;
    }
    function stepButton(item, delta, send, blocked) {
        const value = Number(item.value) || 0;
        const disabled = blocked || (delta < 0 ? value <= 0 : item.max != null && value >= item.max);
        const node = button('lc-pstep', `${item.label} ${delta < 0 ? '−1' : '+1'}`, (event) => { event.stopPropagation(); send(item.key, value + delta); }, disabled);
        node.textContent = delta < 0 ? '−' : '+';
        return node;
    }
    function stateText(item) {
        if (item.kind === 'trigger') return item.active ? w('using') : item.ready ? w('ready') : w('use');
        return item.active ? w('on') : w('off');
    }
    function classes(item) {
        return (item.active ? ' is-active' : '') + (item.enabled ? '' : ' is-blocked') + (item.attention ? ' is-ready' : '') + (item.kind === 'status' ? ' is-status' : '');
    }

    /* 토글·발동·상태: 카드 그림 자체가 버튼(상태는 읽기 전용) */
    function pressTile(api, item, index, send, locked, size) {
        const label = `${item.label} ${stateText(item)}` + (item.hint ? ` · ${item.hint}` : '');
        const node = item.kind === 'status'
            ? el('div', `lc-tile lc-tile-${size}` + classes(item))
            : button(`lc-tile lc-tile-${size}` + classes(item), label, () => send(item.key, !item.active), locked || !item.enabled);
        if (item.kind === 'status') { node.setAttribute('role', 'status'); node.title = label; node.setAttribute('aria-label', label); }
        else if (item.kind === 'toggle') { node.setAttribute('role', 'switch'); node.setAttribute('aria-checked', String(item.active)); }
        node.dataset.controlKey = item.key;
        node.append(picture(api, item, index, 'is-fill'));
        node.append(el('span', 'lc-tile-name', item.label), el('span', 'lc-pill', stateText(item)));
        return node;
    }
    /* 카운터: 그림 위 불빛, 양옆(또는 아래) ± */
    function counterTile(api, item, index, send, locked, size) {
        const blocked = locked || !item.enabled;
        const box = el('div', `lc-counter-tile lc-tile-${size}` + classes(item));
        box.dataset.controlKey = item.key;
        box.title = item.label + (item.hint ? ` · ${item.hint}` : '');
        const face = el('div', 'lc-tile lc-tile-face');
        face.append(picture(api, item, index, 'is-fill'), el('span', 'lc-tile-name', item.label), lights(api, item));
        resettable(face, item, send, blocked);
        if (size === 'split') {
            const steps = el('div', 'lc-pstep-bar');
            steps.append(stepButton(item, -1, send, blocked), stepButton(item, 1, send, blocked));
            box.append(face, steps);
        } else box.append(stepButton(item, -1, send, blocked), face, stepButton(item, 1, send, blocked));
        return box;
    }
    function choiceTile(api, item, index, send, locked, size) {
        const box = el('div', `lc-choice-tile lc-tile-${size}` + classes(item));
        box.dataset.controlKey = item.key;
        box.setAttribute('role', 'radiogroup');
        box.setAttribute('aria-label', item.label);
        box.title = item.label + (item.hint ? ` · ${item.hint}` : '');
        (item.choices || []).forEach((choice, choiceIndex) => {
            const option = button('lc-tile lc-choice' + (choice.selected ? ' is-active' : ''), `${item.label} ${choice.label}`, () => send(item.key, choice.value), locked || !item.enabled);
            option.setAttribute('role', 'radio');
            option.setAttribute('aria-checked', String(choice.selected));
            option.append(artTile(choice.art, 'is-fill') || crop(api, item.key + ':' + choice.value, index + choiceIndex, 'is-fill'), el('span', 'lc-tile-name', choice.label));
            box.append(option);
        });
        return box;
    }
    function tile(api, item, index, send, locked, size) {
        if (item.kind === 'counter') return counterTile(api, item, index, send, locked, size);
        if (item.kind === 'choice') return choiceTile(api, item, index, send, locked, size);
        if (item.kind === 'text') {
            const input = el('input', 'lc-text');
            input.value = String(item.value ?? '');
            input.disabled = locked || !item.enabled;
            input.setAttribute('aria-label', item.label);
            input.placeholder = item.label;
            input.addEventListener('change', () => send(item.key, input.value));
            return input;
        }
        return pressTile(api, item, index, send, locked, size);
    }

    /* 목록(3개 이상): 한 줄씩. 작은 카운터 둘은 반씩, 상태 + 선택지는 한 줄로 */
    function listRow(api, group, indexOf, send, locked) {
        const row = el('div', 'lc-row');
        const counterHalf = (item) => {
            const blocked = locked || !item.enabled;
            const half = el('div', 'lc-row-part' + classes(item));
            half.dataset.controlKey = item.key;
            half.title = item.label + (item.hint ? ` · ${item.hint}` : '');
            half.append(picture(api, item, indexOf(item), 'is-thumb'), el('span', 'lc-row-name', item.label), stepButton(item, -1, send, blocked), lights(api, item), stepButton(item, 1, send, blocked));
            return resettable(half, item, send, blocked);
        };
        if (group.kind === 'pair') { row.classList.add('is-pair'); row.append(counterHalf(group.items[0]), counterHalf(group.items[1])); return row; }
        if (group.kind === 'status-choice') {
            const {status, choice} = group;
            const part = el('div', 'lc-row-part is-wide' + classes(choice) + (status.active ? ' is-status-on' : ''));
            part.dataset.controlKey = choice.key;
            part.title = `${status.label} ${stateText(status)} · ${status.hint}` + (choice.hint ? ` · ${choice.hint}` : '');
            const lamp = el('span', 'lc-row-lamp' + (status.active ? ' is-on' : ''));
            lamp.setAttribute('aria-hidden', 'true');
            const options = el('span', 'lc-row-choices');
            options.setAttribute('role', 'radiogroup');
            options.setAttribute('aria-label', choice.label);
            for (const option of choice.choices || []) {
                const node = button('lc-row-choice' + (option.selected ? ' is-active' : ''), `${choice.label} ${option.label}`, () => send(choice.key, option.value), locked || !choice.enabled);
                node.textContent = option.label;
                node.setAttribute('role', 'radio');
                node.setAttribute('aria-checked', String(option.selected));
                options.append(node);
            }
            part.append(lamp, el('span', 'lc-row-name', status.label), options);
            row.append(part);
            return row;
        }
        const item = group.item;
        if (item.kind === 'counter') { row.append(counterHalf(item)); row.firstChild.classList.add('is-wide'); return row; }
        const node = tile(api, item, indexOf(item), send, locked, 'row');
        row.append(node);
        return row;
    }

    function render(api) {
        apis.set(api.target, api);
        const definition = api.player.character?.passive || {};
        const items = api.player.character ? tray.passiveTray(api.player, definition, language) : [];
        const send = (key, value) => {
            const action = tray.trayAction(api.player, definition, api.target, key, value, language);
            if (action) api.dispatch(action);
        };
        const locked = !api.canControl;
        const mode = layout.passiveLayout(items);
        const list = el('div', `lc-tray is-${mode}`);
        list.setAttribute('role', 'group');
        list.setAttribute('aria-label', w('passive'));
        const indexOf = (item) => items.indexOf(item);
        if (mode === 'list') {
            // 목록형은 한 장의 카드 틀 안에 줄을 쌓는다. 배경은 패시브 카드 그림을 흐리게 깐다.
            if (layout.passiveCardImage(api.player.character)) list.append(crop(api, items[0]?.key || 'list', 0, 'is-backdrop'));
            for (const group of layout.passiveGroups(items)) list.append(listRow(api, group, indexOf, send, locked));
        } else {
            for (const group of layout.passiveGroups(items)) {
                const groupItems = group.kind === 'single' ? [group.item] : group.kind === 'pair' ? group.items : [group.status, group.choice];
                for (const item of groupItems) list.append(tile(api, item, indexOf(item), send, locked, mode));
            }
        }
        api.root.replaceChildren();
        if (items.length) api.root.append(list);
        setTimeout(() => fit(api.root), 0);
        if (sizes && !observed.has(api.root)) { observed.add(api.root); sizes.observe(api.root); }
    }
    const observed = new WeakSet();
    const sizes = 'ResizeObserver' in window ? new ResizeObserver((entries) => entries.forEach((entry) => fit(entry.target))) : null;

    /* 패시브 칸은 최대 높이가 정해져 있다. 넘치면 이름 → 그림 순으로 줄인다. */
    function overflowing(holder) {
        if (holder.scrollHeight > holder.clientHeight + 1) return true;
        const list = holder.querySelector('.lc-tray');
        return !!list && (list.scrollHeight > list.clientHeight + 1 || list.scrollWidth > list.clientWidth + 1);
    }
    const LEVELS = ['', 'is-tight', 'is-tighter'];
    function fit(holder) {
        for (const level of LEVELS) {
            holder.classList.remove('is-tight', 'is-tighter');
            if (level === 'is-tight') holder.classList.add('is-tight');
            if (level === 'is-tighter') holder.classList.add('is-tight', 'is-tighter');
            if (!overflowing(holder)) return;
        }
    }
    window.addEventListener('resize', () => apis.forEach((api) => fit(api.root)));

    window.calculatorTray = {render};
    applyDisplay(false);
})();
