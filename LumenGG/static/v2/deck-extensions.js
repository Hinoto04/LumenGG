(() => {
  const root = document.querySelector('[data-deck-extensions]');
  if (!root) return;
  const trait = root.querySelector('[data-trait-select]'), regulation = root.querySelector('[data-regulation-select]');
  const picker = root.querySelector('[data-reserve-picker]'), list = root.querySelector('[data-reserve-list]');
  const status = root.querySelector('[data-deck-diagnostics]');
  let data, reserve = [], loaded = false, timer, revision = 0;
  const characterId = () => Number(document.querySelector('[name="char"]:checked')?.value || document.querySelector('select[name="char"]')?.value);
  function option(select, value, text) { const o = document.createElement('option'); o.value = value; o.textContent = text; select.append(o); }
  function traits() {
    const old = trait.value; trait.replaceChildren(); option(trait, '', '특성을 선택해주세요');
    const choices = data.traits.filter(t => t.character_id === characterId());
    choices.forEach(t => option(trait, t.id, `${t.name} (${t.code || ''})`));
    trait.value = choices.some(t => String(t.id) === old) ? old : choices.length === 1 ? String(choices[0].id) : '';
  }
  function candidates() {
    const query = root.querySelector('[data-reserve-search]').value.toLowerCase();
    picker.replaceChildren();
    data.reserve_candidates.filter(c => `${c.name} ${c.code}`.toLowerCase().includes(query)).forEach(c => option(picker, c.id, `${c.name} (${c.code || ''})`));
  }
  function render() {
    list.replaceChildren();
    reserve.forEach(row => {
      const c = data.reserve_candidates.find(c => c.id === row.card_id), li = document.createElement('li');
      li.append(document.createTextNode(`${c?.name || row.card_id} × ${row.count} `));
      const button = document.createElement('button'); button.type = 'button'; button.className = 'v2-button'; button.textContent = '1장 빼기';
      button.addEventListener('click', () => { row.count--; reserve = reserve.filter(e => e.count > 0); render(); changed(); });
      li.append(button); list.append(li);
    });
    root.querySelector('[data-reserve-count]').textContent = reserve.reduce((n, e) => n + e.count, 0);
  }
  function fields() {
    if (!loaded) throw new Error('특성과 규정 정보를 불러온 뒤 저장해주세요.');
    return {schema_version: 2, trait_card_id: Number(trait.value) || null, regulation_version_id: Number(regulation.value) || null, reserve_cards: reserve};
  }
  function changed() {
    if (!loaded) return;
    clearTimeout(timer); const ticket = ++revision;
    timer = setTimeout(async () => {
      try {
        const cards = typeof aggregateDeck === 'function' ? aggregateDeck().map(([pk, v]) => ({card_id: Number(pk), ...v})) : [];
        const response = await fetch('/deck/validate', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value}, body: JSON.stringify({candidate: {deck_id:Number(root.dataset.deckId)||null,character_id: characterId(), cards, ...fields()}})});
        if (!response.ok) throw new Error('편성을 검사할 수 없습니다.');
        const report = await response.json(); if (ticket !== revision) return;
        status.replaceChildren();
        report.issues.forEach(i => { const p = document.createElement('p'); p.textContent = i.message; status.append(p); });
        if (!report.issues.length) status.textContent = '현재 규정에 맞는 구성입니다. 시작 배치는 게임 준비 시 확인합니다.';
        document.querySelectorAll('[data-card-id]').forEach(el => el.classList.toggle('has-rule-issue', report.issues.some(i => i.card_ids.includes(Number(el.dataset.cardId)))));
      } catch (e) { if (ticket === revision) status.textContent = e.message; }
    }, 250);
  }
  function includeForeign() {
    const selected = data?.traits.find(t => t.id === Number(trait.value));
    const rules = {...selected?.trait_config?.deck_rules, ...selected?.deck_rules};
    return !!(rules.other_character_cards || rules.allowed_character_ids?.some(id => ![1, characterId()].includes(id)) || rules.supplements?.some(s => s.allow_foreign_mark));
  }
  window.deckExtensions = {fields, changed, includeForeign};
  fetch(`/deck/options?deck_id=${root.dataset.deckId}`).then(r => { if (!r.ok) throw new Error('특성 정보를 불러올 수 없습니다.'); return r.json(); }).then(result => {
    data = result; reserve = data.selected.reserve_cards || []; traits(); trait.value = data.selected.trait_card_id || trait.value;
    option(regulation, '', '기본 규정'); data.versions.forEach(v => option(regulation, v.id, `${v.name} / ${v.version}`));
    regulation.value = data.selected.regulation_version_id || data.versions.find(v => !v.owner_id)?.id || '';
    candidates(); render(); loaded = true; changed();
    document.querySelectorAll('[name="char"]').forEach(input => input.addEventListener('change', () => { traits(); changed(); }));
  }).catch(e => { status.textContent = e.message; });
  root.querySelector('[data-reserve-search]').addEventListener('input', () => data && candidates());
  root.querySelector('[data-reserve-add]').addEventListener('click', () => {
    if (!loaded || !picker.value) return;
    const id = Number(picker.value), row = reserve.find(e => e.card_id === id);
    if (row) row.count++; else reserve.push({card_id: id, count: 1}); render(); changed();
  });
  trait.addEventListener('change', changed); regulation.addEventListener('change', changed);
})();
