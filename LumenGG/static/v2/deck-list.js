const characterInputs = [...document.querySelectorAll('#v2DeckSearchCharacterPicker input[name="char"]')];
const traitField = document.querySelector('[data-trait-filter-field]');
const traitSelect = document.querySelector('[data-trait-filter]');
const regulationSelect = document.querySelector('[data-regulation-filter]');
const deckListScript = document.currentScript;

const selectedCharacterIds = () => new Set(
    characterInputs.filter((input) => input.checked).map((input) => Number(input.value)),
);

const renderTraits = (traits, preserveSelection = true) => {
    if (!traitField || !traitSelect) return;
    const characterIds = selectedCharacterIds();
    const previousValue = preserveSelection ? traitSelect.value || traitSelect.dataset.selectedTrait : '';
    traitField.hidden = characterIds.size === 0;
    traitSelect.replaceChildren(new Option(traitSelect.dataset.allLabel || '전체', ''));

    if (!characterIds.size) {
        traitSelect.value = '';
        return;
    }

    traits.filter((trait) => characterIds.has(Number(trait.character_id))).forEach((trait) => {
        traitSelect.add(new Option(trait.name, String(trait.id)));
    });
    traitSelect.value = [...traitSelect.options].some((option) => option.value === previousValue)
        ? previousValue
        : '';
};

fetch(deckListScript?.dataset.optionsUrl || '/deck/options')
    .then((response) => {
        if (!response.ok) throw new Error('덱 필터 정보를 불러오지 못했습니다.');
        return response.json();
    })
    .then((data) => {
        renderTraits(data.traits);
        if (regulationSelect) {
            const selectedValue = regulationSelect.dataset.selectedRegulation;
            data.versions.forEach((version) => {
                regulationSelect.add(new Option(version.name, String(version.id)));
            });
            regulationSelect.value = [...regulationSelect.options].some((option) => option.value === selectedValue)
                ? selectedValue
                : '';
        }
        characterInputs.forEach((input) => input.addEventListener('change', () => renderTraits(data.traits, false)));
    })
    .catch(() => {
        if (traitField) traitField.hidden = true;
    });
