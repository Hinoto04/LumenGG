(() => {
  const root = document.querySelector('[data-deck-extensions]');
  if (!root) return;

  const trait = root.querySelector('[data-trait-select]');
  const regulation = root.querySelector('[data-regulation-select]');
  const status = root.querySelector('[data-deck-diagnostics]');
  let data;
  let loaded = false;
  let timer;
  let revision = 0;

  const characterId = () => Number(
    document.querySelector('[name="char"]:checked')?.value
      || document.querySelector('select[name="char"]')?.value,
  );

  function option(select, value, text) {
    const item = document.createElement('option');
    item.value = value;
    item.textContent = text;
    select.append(item);
  }

  function renderTraits(preferredValue = trait.value) {
    trait.replaceChildren();
    const choices = data.traits.filter((item) => item.character_id === characterId());
    choices.forEach((item) => option(trait, item.id, `${item.name} (${item.code || ''})`));
    const preferred = String(preferredValue || '');
    const selected = choices.find((item) => String(item.id) === preferred) || choices[0];
    trait.value = selected ? String(selected.id) : '';
  }

  function fields() {
    if (!loaded) throw new Error('특성 정보를 불러온 뒤 저장해주세요.');
    return {
      schema_version: 2,
      trait_card_id: Number(trait.value) || null,
      regulation_version_id: Number(regulation.value) || null,
      reserve_cards: window.deckBuilderReserve?.fields() || [],
    };
  }

  function changed() {
    if (!loaded) return;
    clearTimeout(timer);
    revision += 1;
    if (!characterId()) {
      status.replaceChildren();
      document.querySelectorAll('[data-card-id]').forEach((element) => element.classList.remove('has-rule-issue'));
      return;
    }
    const ticket = revision;
    timer = setTimeout(async () => {
      try {
        const cards = typeof aggregateDeck === 'function'
          ? aggregateDeck().map(([pk, values]) => ({ card_id: Number(pk), ...values }))
          : [];
        const response = await fetch('/deck/validate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value,
          },
          body: JSON.stringify({
            candidate: {
              deck_id: Number(root.dataset.deckId) || null,
              character_id: characterId(),
              cards,
              ...fields(),
            },
          }),
        });
        if (!response.ok) throw new Error('편성을 검사할 수 없습니다.');
        const report = await response.json();
        if (ticket !== revision) return;
        status.replaceChildren();
        report.issues.forEach((issue) => {
          const paragraph = document.createElement('p');
          paragraph.textContent = issue.message;
          status.append(paragraph);
        });
        document.querySelectorAll('[data-card-id]').forEach((element) => {
          element.classList.toggle(
            'has-rule-issue',
            report.issues.some((issue) => issue.card_ids.includes(Number(element.dataset.cardId))),
          );
        });
      } catch (error) {
        if (ticket === revision) status.textContent = error.message;
      }
    }, 250);
  }

  function includeForeign() {
    const selected = data?.traits.find((item) => item.id === Number(trait.value));
    const rules = { ...selected?.trait_config?.deck_rules, ...selected?.deck_rules };
    return !!(
      rules.other_character_cards
      || rules.allowed_character_ids?.some((id) => ![1, characterId()].includes(id))
      || rules.supplements?.some((supplement) => supplement.allow_foreign_mark)
    );
  }

  window.deckExtensions = { fields, changed, includeForeign };

  fetch(`/deck/options?deck_id=${root.dataset.deckId}`)
    .then((response) => {
      if (!response.ok) throw new Error('특성 정보를 불러올 수 없습니다.');
      return response.json();
    })
    .then((result) => {
      data = result;
      renderTraits(data.selected.trait_card_id);
      regulation.replaceChildren();
      option(regulation, '', '무금제');
      data.versions.forEach((version) => option(regulation, version.id, version.name));
      regulation.value = data.selected.regulation_version_id
        ? String(data.selected.regulation_version_id)
        : '';
      window.deckBuilderReserve?.load(data.selected.reserve_cards || [], data.reserve_candidates || []);
      loaded = true;
      changed();
      document.querySelectorAll('[name="char"]').forEach((input) => {
        input.addEventListener('change', () => {
          renderTraits();
          changed();
        });
      });
    })
    .catch((error) => { status.textContent = error.message; });

  trait.addEventListener('change', changed);
  regulation.addEventListener('change', changed);
})();
