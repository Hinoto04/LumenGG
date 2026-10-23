(() => {
  const form = document.querySelector('.v2-battle-start'); if (!form) return;
  const hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.name = 'schema_version'; hidden.value = '2'; form.append(hidden);
  const submit = form.querySelector('[type="submit"]'); submit.disabled = true;
  fetch('/deck/options').then(r => r.json()).then(data => {
    for (const prefix of ['player1', 'player2']) {
      const character = form.querySelector(`[name="${prefix}_character"]`), label = document.createElement('label'), select = document.createElement('select');
      label.textContent = '특성 '; select.name = `${prefix}_trait_card_id`; select.required = true; label.append(select); character.parentElement.append(label);
      const update = () => { select.replaceChildren(); const choices = data.traits.filter(t => t.character_id === Number(character.value)); const empty = document.createElement('option'); empty.value = ''; empty.textContent = '특성을 선택해주세요'; select.append(empty); choices.forEach(t => { const o = document.createElement('option'); o.value = t.id; o.textContent = t.name; select.append(o); }); if (choices.length === 1) select.value = choices[0].id; };
      character.addEventListener('change', update); update();
    } submit.disabled = false;
  }).catch(() => { const message = document.createElement('p'); message.textContent = '특성 정보를 불러오지 못했습니다. 새로고침해주세요.'; form.append(message); });
})();
