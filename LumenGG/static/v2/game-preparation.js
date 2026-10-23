(() => {
  const root = document.querySelector('[data-game-preparation]'); if (!root) return;
  const config = window.lumenSimulatorConfig || window.lumenSimulatorMobileConfig || window.v2BattleConfig;
  if (!config) return;
  const simulator = !!(window.lumenSimulatorConfig || window.lumenSimulatorMobileConfig);
  let envelope, version = -1, dirty = false, gameNumber;
  const editors = root.querySelector('[data-preparation-editors]'), status = root.querySelector('[data-preparation-status]');
  const isTrait = c => c && (c.type === '특성' || /(?:^|-)PS(?:-|$)/i.test(c.code || ''));
  function el(tag, text) { const e = document.createElement(tag); if (text != null) e.textContent = text; return e; }
  function button(text, callback, disabled = false) { const e = el('button', text); e.type = 'button'; e.className = 'v2-button'; e.disabled = disabled; e.addEventListener('click', callback); return e; }
  function candidate(section, row) {
    return {character_id: row.registered.character_id, trait_card_id: Number(section.querySelector('[data-selected-trait]').value) || null,
      cards: [...section.querySelectorAll('[data-prepared-card]')].map(tr => ({card_id: Number(tr.dataset.preparedCard), count: Number(tr.querySelector('[data-count]').value), hand: Number(tr.querySelector('[data-hand]').value), side: Number(tr.querySelector('[data-side]').value)})).filter(r => r.count > 0)};
  }
  async function send(side, action, active, submissionId) {
    try {
      const prep = envelope.preparation;
      const body = {action: 'preparation', target: side, request_id: crypto.randomUUID(), expected_version: simulator ? prep.version : envelope.version, preparation_version: prep.version, preparation_action: action, active, submission_id: submissionId,
        seat: config.seat, seat_token: config.seatToken, control_token: config.controlToken || ''};
      const url = simulator ? config.stateUrl.replace(/state\/$/, 'preparation/') : config.actionUrl;
      const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]')?.value || ''}, body: JSON.stringify(body)});
      const result = await response.json(); if (!response.ok || !result.ok) throw new Error(result.error || '준비 요청을 처리할 수 없습니다.');
      dirty = false; version = -1; update(result.state);
      if (simulator) window.dispatchEvent(new CustomEvent('lumen-simulator-apply-state', {detail: result.state}));
    } catch (error) { status.textContent = error.message; }
  }
  function update(next) {
    if (!next?.preparation) return;
    envelope = next; const wasHidden = root.hidden; root.hidden = false;
    const prep = next.preparation;
    if (prep.status === 'playing') root.open = false;
    else if (wasHidden || gameNumber !== prep.game_number) root.open = true;
    status.textContent = `게임 ${prep.game_number} · ${prep.status === 'playing' ? '진행 중' : '준비 중'} · P1 ${prep.players.p1.ready ? '준비 완료' : '편집 중'} / P2 ${prep.players.p2.ready ? '준비 완료' : '편집 중'}`;
    if (gameNumber !== prep.game_number) dirty = false;
    gameNumber = prep.game_number;
    if (version === prep.version || (dirty && prep.status === 'editing')) return;
    version = prep.version; editors.replaceChildren();
    for (const [side, row] of Object.entries(prep.players)) {
      if (!row.registered && !row.submissions) {
        if (row.public_catalog) { const section = el('section'); section.append(el('h3', side.toUpperCase() + ' · 공개 구성')); for (const entry of row.reserve_cards || []) section.append(el('p', '교체 덱: ' + row.public_catalog[entry.card_id].name + ' × ' + entry.count)); for (const entry of row.active?.cards || []) section.append(el('p', row.public_catalog[entry.card_id].name + ' × ' + entry.count)); editors.append(section); }
        continue;
      }
      const section = el('section'), title = el('h3', `${side.toUpperCase()} · ${row.registered?.name || '제출 덱 선택'}`); section.append(title);
      if (prep.status === 'playing') {
        section.append(el('p', '이번 게임 구성이 확정되었습니다.'));
        if (simulator && config.seat === side) section.append(button('다음 게임 준비', () => send(side, 'next_game')));
        editors.append(section); continue;
      }
      if (row.submissions?.length) {
        const select = el('select'); select.setAttribute('aria-label', '제출 덱');
        const blank = el('option', '제출 덱 선택'); blank.value = ''; select.append(blank);
        row.submissions.forEach(s => { const o = el('option', `${s.name} · ${s.trait_name || '특성 미지정'}`); o.value = s.id; select.append(o); });
        section.append(select, button('이 덱으로 준비', () => send(side, 'select_deck', undefined, Number(select.value)), row.ready));
      }
      if (!row.registered) { editors.append(section); continue; }
      const snapshot = row.registered, catalog = snapshot.catalog;
      const pool = new Map(); [...snapshot.cards, ...snapshot.reserve_cards, {card_id: snapshot.trait_card_id, count: 1}].forEach(e => { if (e.card_id) pool.set(e.card_id, (pool.get(e.card_id) || 0) + e.count); });
      const trait = el('select'); trait.dataset.selectedTrait = ''; trait.setAttribute('aria-label', '게임에 사용할 특성');
      [...pool.keys()].filter(pk => isTrait(catalog[pk])).forEach(pk => { const o = el('option', catalog[pk].name); o.value = pk; trait.append(o); });
      trait.value = row.active.trait_card_id || ''; trait.disabled = row.ready; trait.addEventListener('change', () => dirty = true);
      section.append(el('label', '특성 '), trait);
      const rules = snapshot.regulation_rules;
      section.append(el('p', `교체 한도 · 기술 ${rules.technique_swap_limit}장 / 특성 ${rules.trait_swap_limit}회 / 얼티밋 ${rules.ultimate_swap_limit}회`));
      const table = el('table'), head = el('tr'); ['카드', '등록 수량', '사용', '시작 패', '사이드'].forEach(t => head.append(el('th', t))); table.append(head);
      [...pool.entries()].filter(([pk]) => !isTrait(catalog[pk])).forEach(([pk, maximum]) => {
        const tr = el('tr'); tr.dataset.preparedCard = pk; tr.append(el('td', catalog[pk].name), el('td', maximum));
        const current = row.active.cards.find(e => e.card_id === pk) || {};
        for (const field of ['count', 'hand', 'side']) {
          const td = el('td'), input = el('input'); input.type = 'number'; input.min = '0'; input.max = maximum; input.value = current[field] || 0; input.dataset[field] = ''; input.style.width = '64px'; input.disabled = row.ready;
          input.setAttribute('aria-label', `${catalog[pk].name} ${field === 'count' ? '사용 매수' : field === 'hand' ? '시작 패' : '사이드'}`);
          input.addEventListener('input', () => dirty = true); td.append(input); tr.append(td);
        } table.append(tr);
      });
      section.append(table);
      if (row.ready) section.append(button('준비 완료 철회', () => send(side, 'cancel')));
      else section.append(button('배치 저장', () => send(side, 'save', candidate(section, row))), button('준비 완료', () => send(side, 'ready', candidate(section, row))));
      editors.append(section);
    }
  }
  const originalParent = root.parentElement;
  document.addEventListener('fullscreenchange', () => (document.fullscreenElement || originalParent).append(root));
  window.addEventListener('lumen-simulator-state', e => update(e.detail));
  window.addEventListener('lumen-calculator-state', e => update(e.detail));
  const initial = document.getElementById(simulator ? 'lumen-simulator-state' : 'battle-initial-state');
  if (initial) update(JSON.parse(initial.textContent));
})();
