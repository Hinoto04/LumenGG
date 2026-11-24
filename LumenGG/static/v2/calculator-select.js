// 대전 계산기 시작: 격투게임식 캐릭터·패시브 선택.
// 로스터 칸을 누르면 지금 고르는 쪽(1P/2P)에 들어가고, 상대가 아직 비어 있으면 그쪽으로 넘어간다.
// 패시브(특성)는 카드 그림으로 고른다. 하나뿐이면 자동으로 고른다.
(() => {
    const form = document.querySelector('[data-fighter-select]');
    if (!form) return;
    const label = (key) => form.dataset[`label${key[0].toUpperCase()}${key.slice(1)}`] || '';
    const fighters = [...form.querySelectorAll('[data-fighter]')];
    const cells = [...form.querySelectorAll('.fs-cell')];
    const submit = form.querySelector('.fs-start');
    const hint = form.querySelector('[data-fighter-hint]');
    const picked = new Map(); // fighter → 사용자가 직접 고른 적이 있는가
    let traits = null;
    let active = fighters[0];

    const characterOf = (fighter) => fighter.querySelector('[data-fighter-character]').value;
    const cellOf = (id) => cells.find((cell) => cell.dataset.character === String(id));

    function setActive(fighter) {
        active = fighter;
        fighters.forEach((item) => item.classList.toggle('is-active', item === fighter));
        form.dataset.picking = fighter.dataset.fighter;
    }

    function showPortrait(fighter, cell) {
        const img = fighter.querySelector('[data-fighter-portrait]');
        const name = fighter.querySelector('[data-fighter-name]');
        fighter.querySelector('[data-fighter-empty]').hidden = !!cell;
        name.textContent = cell ? cell.dataset.name : label('pick');
        fighter.style.setProperty('--fs-color', cell ? cell.style.getPropertyValue('--fs-color') : 'transparent');
        if (!cell) { img.hidden = true; img.removeAttribute('src'); return; }
        if (img.getAttribute('src') !== cell.dataset.portrait) {
            img.hidden = true;
            img.onload = () => { img.hidden = false; };
            img.onerror = () => { img.hidden = true; };
            img.src = cell.dataset.portrait;
        } else img.hidden = false;
    }

    function renderTraits(fighter) {
        const holder = fighter.querySelector('[data-fighter-traits]');
        const input = fighter.querySelector('[data-fighter-trait]');
        const id = Number(characterOf(fighter));
        holder.replaceChildren();
        if (!id || !traits) return;
        const choices = traits.filter((trait) => trait.character_id === id);
        if (choices.length === 1) input.value = String(choices[0].id);
        if (!choices.some((trait) => String(trait.id) === input.value)) input.value = '';
        for (const trait of choices) {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = 'fs-trait';
            option.setAttribute('role', 'radio');
            const selected = input.value === String(trait.id);
            option.setAttribute('aria-checked', String(selected));
            option.classList.toggle('is-selected', selected);
            option.title = trait.name;
            // 카드 가운데 일러스트 일부를 정사각형 아이콘으로 쓴다.
            const art = document.createElement('span');
            art.className = 'fs-trait-art';
            art.style.backgroundImage = `url("${String(trait.img).replace(/"/g, '%22')}")`;
            const name = document.createElement('span');
            name.className = 'fs-trait-name';
            name.textContent = trait.name;
            option.append(art, name);
            option.addEventListener('click', () => { input.value = String(trait.id); renderTraits(fighter); update(); });
            holder.append(option);
        }
    }

    function choose(fighter, cell) {
        fighter.querySelector('[data-fighter-character]').value = cell.dataset.character;
        if (fighter.dataset.lastCharacter !== cell.dataset.character) fighter.querySelector('[data-fighter-trait]').value = '';
        fighter.dataset.lastCharacter = cell.dataset.character;
        picked.set(fighter, true);
        showPortrait(fighter, cell);
        renderTraits(fighter);
        const other = fighters.find((item) => item !== fighter);
        if (other && !picked.get(other)) setActive(other);
        update();
    }

    function update() {
        for (const cell of cells) {
            cell.classList.toggle('is-p1', characterOf(fighters[0]) === cell.dataset.character);
            cell.classList.toggle('is-p2', characterOf(fighters[1]) === cell.dataset.character);
        }
        const ready = !!traits && fighters.every((fighter) => characterOf(fighter) && fighter.querySelector('[data-fighter-trait]').value);
        submit.disabled = !ready;
        hint.textContent = ready ? '' : traits ? label('need') : '';
    }

    for (const fighter of fighters) {
        fighter.addEventListener('click', (event) => {
            if (event.target.closest('.fs-trait, .fs-name')) return;
            setActive(fighter);
        });
        fighter.querySelector('.fs-name').addEventListener('focus', () => setActive(fighter));
        showPortrait(fighter, null);
    }
    for (const cell of cells) {
        cell.addEventListener('click', () => choose(active, cell));
        // 마우스를 올리면 지금 고르는 쪽에 미리 보여 준다.
        cell.addEventListener('mouseenter', () => showPortrait(active, cell));
        cell.addEventListener('mouseleave', () => showPortrait(active, cellOf(characterOf(active)) || null));
    }
    setActive(fighters[0]);
    update();

    // 휴대폰: 선택 화면이 한 화면에 다 들어오도록 로스터 칸 크기를 화면 높이에 맞추고, 들어오자마자 그쪽으로 스크롤한다.
    const roster = form.querySelector('.fs-roster');
    const narrow = window.matchMedia('(max-width: 760px)');
    function fitRoster() {
        if (!narrow.matches) { roster.style.removeProperty('--fs-cell'); roster.style.removeProperty('--fs-cols'); return; }
        const count = cells.length;
        const width = roster.clientWidth;
        const gap = 6, nameHeight = 16;
        // 로스터가 쓸 수 있는 높이: 폼 높이에서 플레이어 칸 최소 높이와 시작 버튼을 뺀 나머지.
        // 로스터는 화면의 절반까지만 써서 초상화가 충분히 보이게 한다.
        const available = Math.min(form.clientHeight - 210 - (form.querySelector('.fs-actions').offsetHeight + 8) - 24, form.clientHeight * 0.48);
        let best = {cell: 0, cols: 5};
        for (let cols = 4; cols <= 10; cols += 1) {
            const rows = Math.ceil(count / cols);
            const byWidth = (width - gap * (cols - 1)) / cols;
            const byHeight = (available - gap * (rows - 1)) / rows - nameHeight;
            const cell = Math.floor(Math.min(byWidth, byHeight, 76));
            if (cell > best.cell) best = {cell, cols};
        }
        roster.style.setProperty('--fs-cols', String(best.cols));
        roster.style.setProperty('--fs-cell', `${Math.max(34, best.cell)}px`);
    }
    fitRoster();
    window.addEventListener('resize', fitRoster);
    if (narrow.matches) {
        requestAnimationFrame(() => {
            fitRoster();
            form.scrollIntoView({block: 'start', behavior: 'instant'});
        });
    }

    const language = document.documentElement.lang || 'ko';
    fetch(`/deck/options?lang=${encodeURIComponent(language)}`)
        .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
        .then((data) => {
            traits = (data.traits || []).map((trait) => ({ id: trait.id, character_id: trait.character_id, name: trait.name, img: trait.img }));
            fighters.forEach(renderTraits);
            update();
        })
        .catch(() => { hint.textContent = label('error'); });
})();
