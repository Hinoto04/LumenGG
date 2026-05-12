const zoneLabels = {
    list: "리스트",
    hand: "손패",
    side: "사이드",
};

const zoneElements = {
    list: document.getElementById("v2ZoneList"),
    hand: document.getElementById("v2ZoneHand"),
    side: document.getElementById("v2ZoneSide"),
};

const zoneCountElements = {
    list: document.getElementById("v2ListCount"),
    hand: document.getElementById("v2HandZoneCount"),
    side: document.getElementById("v2SideZoneCount"),
};

const config = window.v2DeckBuilderConfig || {};
const exceptList = config.exceptList || {};
const cardStore = new Map();
const deckEntries = [];
const touchOnly = window.matchMedia("(pointer: coarse)").matches;
let nextEntryId = 1;
let maxDeckSize = 21;

function isUltimateCard(card) {
    return card && (card.ultimate === true || card.ultimate === "true" || card.ultimate === 1 || card.ultimate === "1");
}

function countUltimateEntries() {
    return deckEntries.filter((entry) => isUltimateCard(cardStore.get(String(entry.pk)))).length;
}

function ToggleDesc() {
    const description = document.getElementById("DescriptionInput");
    const button = document.getElementById("DescToggleBtn");
    if (!description || !button) return;
    const isHidden = description.classList.toggle("is-hidden");
    button.textContent = isHidden ? "덱 설명 열기" : "덱 설명 닫기";
}

function getSelectedCharacterId() {
    const selected = document.querySelector('input[name="char"]:checked');
    return selected ? selected.value : "";
}

function setMaxDeckSize(characterId) {
    if (characterId === "5") maxDeckSize = 24;
    else if (characterId === "15") maxDeckSize = 33;
    else if (characterId === "16") maxDeckSize = 26;
    else if (characterId === "17") maxDeckSize = 25;
    else maxDeckSize = 21;
}

function syncSearchCharacter(pruneCards = false) {
    const characterId = getSelectedCharacterId();
    const searchCharacter = document.getElementById("v2_search_char");
    if (searchCharacter) searchCharacter.value = characterId;
    setMaxDeckSize(characterId);

    if (pruneCards) {
        for (let i = deckEntries.length - 1; i >= 0; i--) {
            const card = cardStore.get(String(deckEntries[i].pk));
            if (card && String(card.character) !== "1" && String(card.character) !== String(characterId)) {
                deckEntries.splice(i, 1);
            }
        }
        renderDeck();
    }
}

function countEntries(zone = null) {
    return deckEntries.filter((entry) => !zone || entry.zone === zone).length;
}

function countCard(pk) {
    return deckEntries.filter((entry) => String(entry.pk) === String(pk)).length;
}

function canAddCard(card, zone) {
    if (countEntries() >= maxDeckSize) {
        alert(`덱 매수는 최대 ${maxDeckSize}장입니다.`);
        return false;
    }
    if (isUltimateCard(card) && countUltimateEntries() >= 1) {
        alert("얼티밋 카드는 1장까지만 넣을 수 있습니다.");
        return false;
    }
    if (zone === "hand" && countEntries("hand") >= 5) {
        alert("손패 매수는 최대 5장입니다.");
        return false;
    }

    const cardCount = countCard(card.pk);
    if (cardCount === 0) return true;

    const limit = exceptList[String(card.pk)];
    if (!limit || cardCount >= Number(limit)) {
        alert("이 카드는 더 넣을 수 없습니다.");
        return false;
    }
    return true;
}

function addCard(card, zone = "list") {
    cardStore.set(String(card.pk), card);
    if (isUltimateCard(card)) zone = "list";
    if (!canAddCard(card, zone)) return;
    deckEntries.push({
        entryId: nextEntryId++,
        pk: String(card.pk),
        zone,
    });
    renderDeck();
}

function moveEntry(entryId, zone) {
    const entry = deckEntries.find((item) => item.entryId === Number(entryId));
    if (!entry || entry.zone === zone) return;
    const card = cardStore.get(String(entry.pk));
    if (isUltimateCard(card) && zone !== "list") {
        alert("얼티밋 카드는 얼티밋 영역에 별도로 표시됩니다.");
        return;
    }
    if (zone === "hand" && countEntries("hand") >= 5) {
        alert("손패 매수는 최대 5장입니다.");
        return;
    }
    entry.zone = zone;
    renderDeck();
}

function removeEntry(entryId) {
    const index = deckEntries.findIndex((item) => item.entryId === Number(entryId));
    if (index >= 0) {
        deckEntries.splice(index, 1);
        renderDeck();
    }
}

function sortEntries(entries) {
    return [...entries].sort((a, b) => {
        const cardA = cardStore.get(String(a.pk)) || {};
        const cardB = cardStore.get(String(b.pk)) || {};
        const frameA = cardA.frame ?? 999;
        const frameB = cardB.frame ?? 999;
        if (frameA !== frameB) return frameA - frameB;
        return String(cardA.name || "").localeCompare(String(cardB.name || ""), "ko");
    });
}

function makeDeckCard(entry) {
    const card = cardStore.get(String(entry.pk));
    const tile = document.createElement("article");
    tile.className = "v2-builder-card";
    if (isUltimateCard(card)) tile.classList.add("is-ultimate");
    tile.dataset.entryId = entry.entryId;
    if (!touchOnly) {
        tile.draggable = true;
        tile.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", `entry:${entry.entryId}`);
        });
    }

    const image = document.createElement("img");
    image.src = card.img_sm || card.img || "";
    image.alt = card.name || "";
    tile.appendChild(image);

    const removeButton = document.createElement("button");
    removeButton.className = "v2-builder-remove";
    removeButton.type = "button";
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => removeEntry(entry.entryId));
    tile.appendChild(removeButton);

    const controls = document.createElement("div");
    controls.className = "v2-builder-card-actions";
    if (isUltimateCard(card)) {
        const badge = document.createElement("span");
        badge.className = "v2-builder-ultimate-badge";
        badge.textContent = "얼티밋";
        controls.appendChild(badge);
    } else {
        Object.keys(zoneLabels).forEach((zone) => {
            if (zone === entry.zone) return;
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = zoneLabels[zone];
            button.addEventListener("click", () => moveEntry(entry.entryId, zone));
            controls.appendChild(button);
        });
    }
    tile.appendChild(controls);

    return tile;
}

function renderDeck() {
    Object.values(zoneElements).forEach((element) => {
        if (element) element.replaceChildren();
    });

    Object.keys(zoneElements).forEach((zone) => {
        const zoneEntries = sortEntries(deckEntries.filter((entry) => entry.zone === zone));
        zoneEntries.forEach((entry) => zoneElements[zone].appendChild(makeDeckCard(entry)));
        if (zoneCountElements[zone]) zoneCountElements[zone].textContent = zoneEntries.length;
    });

    document.getElementById("CardCount").textContent = countEntries();
    document.getElementById("HandCount").textContent = countEntries("hand");
    document.getElementById("SideCount").textContent = countEntries("side");
}

function makeSearchCard(card) {
    const tile = document.createElement("article");
    tile.className = "v2-search-card";
    if (!touchOnly) {
        tile.draggable = true;
        tile.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", `search:${card.pk}`);
        });
    }

    const image = document.createElement("img");
    image.src = card.img_sm || "";
    image.alt = card.name || "";
    tile.appendChild(image);

    const body = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = card.name;
    body.append(name);
    tile.appendChild(body);

    tile.addEventListener("click", () => addCard(card, "list"));
    return tile;
}

function renderSearchResults(cards) {
    const results = document.getElementById("v2DeckSearchResults");
    if (!results) return;
    results.replaceChildren();
    cards.forEach((card) => {
        cardStore.set(String(card.pk), card);
        results.appendChild(makeSearchCard(card));
    });
}

function searchCards() {
    const form = document.getElementById("v2DeckSearchForm");
    if (!form) return;
    syncSearchCharacter(false);
    const params = new URLSearchParams(new FormData(form));
    fetch(`${config.createSearchUrl}?${params.toString()}`)
        .then((response) => response.json())
        .then((cards) => {
            cards.sort((a, b) => (a.frame ?? 999) - (b.frame ?? 999));
            renderSearchResults(cards);
        });
}

function setupDropZones() {
    Object.entries(zoneElements).forEach(([zone, element]) => {
        if (!element || touchOnly) return;
        const wrapper = element.closest(".v2-deck-builder-zone");
        wrapper.addEventListener("dragover", (event) => {
            event.preventDefault();
            wrapper.classList.add("is-drag-over");
        });
        wrapper.addEventListener("dragleave", () => {
            wrapper.classList.remove("is-drag-over");
        });
        wrapper.addEventListener("drop", (event) => {
            event.preventDefault();
            wrapper.classList.remove("is-drag-over");
            const data = event.dataTransfer.getData("text/plain");
            if (data.startsWith("entry:")) {
                moveEntry(data.replace("entry:", ""), zone);
            } else if (data.startsWith("search:")) {
                const pk = data.replace("search:", "");
                const card = cardStore.get(String(pk));
                if (card) addCard(card, zone);
            }
        });
    });
}

function aggregateDeck() {
    const aggregate = {};
    deckEntries.forEach((entry) => {
        if (!aggregate[entry.pk]) {
            aggregate[entry.pk] = { count: 0, hand: 0, side: 0 };
        }
        aggregate[entry.pk].count += 1;
        if (entry.zone === "hand") aggregate[entry.pk].hand += 1;
        if (entry.zone === "side") aggregate[entry.pk].side += 1;
    });
    return Object.keys(aggregate).map((pk) => [pk, aggregate[pk]]);
}

function submitDeck() {
    const form = document.getElementById("submitForm");
    if (!form) return;
    const formData = new FormData(form);
    const payload = {};
    formData.forEach((value, key) => {
        payload[key] = value;
    });

    if (window.jQuery && jQuery.fn.summernote) {
        payload.description = jQuery("#id_description").summernote("code");
    }

    payload.deck = aggregateDeck();
    fetch(form.action, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": payload.csrfmiddlewaretoken,
        },
        body: JSON.stringify(payload),
    })
        .then((response) => response.json())
        .then((response) => {
            if (response.status === 100) {
                window.location.href = response.url;
            } else {
                alert(response.msg);
            }
        });
}

function loadInitialDeck() {
    const data = document.getElementById("v2InitialDeck");
    if (!data) return;
    const cards = JSON.parse(data.textContent);
    cards.forEach((card) => {
        cardStore.set(String(card.pk), card);
        if (isUltimateCard(card)) {
            if (card.count > 0 && countUltimateEntries() === 0) addInitialEntry(card.pk, "list");
            return;
        }
        for (let i = 0; i < card.hand; i++) addInitialEntry(card.pk, "hand");
        for (let i = 0; i < card.side; i++) addInitialEntry(card.pk, "side");
        for (let i = 0; i < card.count - card.hand - card.side; i++) addInitialEntry(card.pk, "list");
    });
}

function addInitialEntry(pk, zone) {
    deckEntries.push({
        entryId: nextEntryId++,
        pk: String(pk),
        zone,
    });
}

function selectInitialCharacter() {
    if (!config.selectedCharacterId) return;
    const input = document.querySelector(`input[name="char"][value="${config.selectedCharacterId}"]`);
    if (input) input.checked = true;
}

function setupEvents() {
    document.querySelectorAll('input[name="char"]').forEach((input) => {
        input.addEventListener("change", () => syncSearchCharacter(true));
    });
    document.getElementById("v2DeckSearchButton").addEventListener("click", searchCards);
    document.getElementById("v2DeckSubmit").addEventListener("click", submitDeck);
    document.getElementById("v2DeckSearchForm").addEventListener("submit", (event) => {
        event.preventDefault();
        searchCards();
    });
}

selectInitialCharacter();
syncSearchCharacter(false);
loadInitialDeck();
setupEvents();
setupDropZones();
renderDeck();
window.deckSubmit = submitDeck;
