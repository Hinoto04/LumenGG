const config = window.v2DeckBuilderConfig || {};
const translations = config.translations || {};

function t(key, fallback, params = {}) {
    let value = translations[key] || fallback;
    Object.entries(params).forEach(([name, replacement]) => {
        value = value.replace(`{${name}}`, replacement);
    });
    return value;
}

const zoneLabels = {
    list: t("list", "리스트"),
    hand: t("hand", "손패"),
    side: t("side", "사이드"),
};

const mobileZoneButtonLabels = {
    list: "L",
    hand: "H",
    side: "S",
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

const exceptList = config.exceptList || {};
const cardStore = new Map();
const deckEntries = [];
let nextEntryId = 1;
let maxDeckSize = 21;
let dragState = null;
let suppressClickUntil = 0;
const LONG_PRESS_DRAG_DELAY = 300;
const LONG_PRESS_MOVE_TOLERANCE = 10;
const KIMERA_CHARACTER_ID = "15";
const NEUTRAL_CHARACTER_ID = "1";

function isUltimateCard(card) {
    return card && (card.ultimate === true || card.ultimate === "true" || card.ultimate === 1 || card.ultimate === "1");
}

function isAttackOrDefenseCard(card) {
    const type = String(card?.type || "");
    return type.includes("공격") || type.includes("수비");
}

function canUseCardForCharacter(card, characterId) {
    if (!card) return false;
    if (String(card.character) === NEUTRAL_CHARACTER_ID || String(card.character) === String(characterId)) return true;
    return String(characterId) === KIMERA_CHARACTER_ID && !isUltimateCard(card) && isAttackOrDefenseCard(card);
}

function isForcedSideCard(card) {
    return !!(card && !isUltimateCard(card) && String(card.type || "").includes("특수"));
}

function getDefaultZone(card) {
    if (isUltimateCard(card)) return "list";
    if (isForcedSideCard(card)) return "side";
    return "list";
}

function getAllowedZones(card) {
    if (isUltimateCard(card)) return ["list"];
    if (isForcedSideCard(card)) return ["side"];
    return ["list", "hand", "side"];
}

function countEntries(zone = null) {
    return deckEntries.filter((entry) => !zone || entry.zone === zone).length;
}

function countDeckSizeEntries(zone = null) {
    return deckEntries.filter((entry) => {
        if (zone && entry.zone !== zone) return false;
        return !isUltimateCard(cardStore.get(String(entry.pk)));
    }).length;
}

function countCard(pk) {
    return deckEntries.filter((entry) => String(entry.pk) === String(pk)).length;
}

function countUltimateEntries() {
    return deckEntries.filter((entry) => isUltimateCard(cardStore.get(String(entry.pk)))).length;
}

function getSelectedCharacterId() {
    const select = document.querySelector('select[name="char"]');
    if (select) return select.value;
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

    if (!pruneCards) return;
    for (let i = deckEntries.length - 1; i >= 0; i--) {
        const card = cardStore.get(String(deckEntries[i].pk));
        if (card && !canUseCardForCharacter(card, characterId)) {
            deckEntries.splice(i, 1);
        }
    }
    renderDeck();
}

function canAddCard(card, zone) {
    if (isUltimateCard(card) && countUltimateEntries() >= 1) {
        alert(t("maxUltimate", "얼티밋 카드는 1장까지만 넣을 수 있습니다."));
        return false;
    }
    if (zone === "hand" && countEntries("hand") >= 5) {
        alert(t("maxHand", "손패 매수는 최대 5장입니다."));
        return false;
    }

    const cardCount = countCard(card.pk);
    if (cardCount === 0) return true;

    const limit = exceptList[String(card.pk)];
    if (!limit || cardCount >= Number(limit)) {
        alert(t("cannotAdd", "이 카드는 더 넣을 수 없습니다."));
        return false;
    }
    return true;
}

function addCard(card, zone = "list") {
    cardStore.set(String(card.pk), card);
    if (!getAllowedZones(card).includes(zone)) zone = getDefaultZone(card);
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
    if (!getAllowedZones(card).includes(zone)) {
        alert(isUltimateCard(card)
            ? t("ultimateNotice", "얼티밋 카드는 얼티밋 영역에 별도로 표시됩니다.")
            : t("specialSideOnly", "특수 타입 카드는 사이드 덱에만 넣을 수 있습니다."));
        return;
    }
    if (zone === "hand" && countEntries("hand") >= 5) {
        alert(t("maxHand", "손패 매수는 최대 5장입니다."));
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
        const ultimateA = isUltimateCard(cardA);
        const ultimateB = isUltimateCard(cardB);
        if (ultimateA !== ultimateB) return ultimateA ? -1 : 1;
        const frameA = cardA.frame ?? 999;
        const frameB = cardB.frame ?? 999;
        if (frameA !== frameB) return frameA - frameB;
        return String(cardA.name || "").localeCompare(String(cardB.name || ""), "ko");
    });
}

function bindPointerDrag(element, getPayload, sourceElement = null) {
    element.addEventListener("contextmenu", (event) => {
        event.preventDefault();
    });

    element.addEventListener("pointerdown", (event) => {
        if (event.pointerType === "touch") return;
        if (event.button && event.button !== 0) return;
        if (event.target.closest("button, input, select, textarea, a")) return;
        const source = sourceElement || element;
        dragState = {
            pointerId: event.pointerId,
            inputType: "pointer",
            payload: getPayload(),
            source,
            handle: element,
            startX: event.clientX,
            startY: event.clientY,
            currentX: event.clientX,
            currentY: event.clientY,
            active: false,
            ghost: null,
            longPressTimer: null,
        };
        dragState.longPressTimer = window.setTimeout(startPointerDrag, LONG_PRESS_DRAG_DELAY);
    });

    element.addEventListener("touchstart", (event) => {
        if (event.touches.length !== 1) return;
        if (event.target.closest("button, input, select, textarea, a")) return;
        const touch = event.changedTouches[0];
        const source = sourceElement || element;
        dragState = {
            pointerId: touch.identifier,
            inputType: "touch",
            payload: getPayload(),
            source,
            handle: element,
            startX: touch.clientX,
            startY: touch.clientY,
            currentX: touch.clientX,
            currentY: touch.clientY,
            active: false,
            ghost: null,
            longPressTimer: null,
        };
        registerTouchDragListeners();
        dragState.longPressTimer = window.setTimeout(startPointerDrag, LONG_PRESS_DRAG_DELAY);
    }, { passive: true });

    element.addEventListener("pointermove", (event) => {
        if (!dragState || dragState.inputType !== "pointer" || dragState.pointerId !== event.pointerId) return;
        dragState.currentX = event.clientX;
        dragState.currentY = event.clientY;
        const moved = Math.hypot(event.clientX - dragState.startX, event.clientY - dragState.startY);
        if (!dragState.active) {
            if (moved > LONG_PRESS_MOVE_TOLERANCE) cleanupPointerDrag();
            return;
        }
        event.preventDefault();
        movePointerGhost(event);
    });

    element.addEventListener("pointerup", finishPointerDrag);
    element.addEventListener("pointercancel", cancelPointerDrag);
}

function startPointerDrag(event) {
    if (!dragState) return;
    window.clearTimeout(dragState.longPressTimer);
    dragState.longPressTimer = null;
    if (dragState.inputType === "pointer") {
        dragState.handle?.setPointerCapture?.(dragState.pointerId);
    }
    const rect = dragState.source.getBoundingClientRect();
    const ghost = createPointerGhost();
    ghost.classList.add("v2-mobile-drag-ghost");
    if (dragState.payload.type === "search") {
        ghost.style.width = getComputedStyle(document.querySelector("[data-mobile-deck-builder]"))
            .getPropertyValue("--mobile-deck-card-width")
            .trim() || "66px";
    } else {
        ghost.style.width = `${rect.width}px`;
        ghost.style.height = `${rect.height}px`;
    }
    document.body.appendChild(ghost);
    dragState.source.classList.add("is-drag-source");
    dragState.active = true;
    dragState.ghost = ghost;
    movePointerGhost(event || { clientX: dragState.currentX, clientY: dragState.currentY });
}

function registerTouchDragListeners() {
    document.addEventListener("touchmove", handleTouchDragMove, { passive: false });
    document.addEventListener("touchend", finishTouchDrag, { passive: false });
    document.addEventListener("touchcancel", cancelTouchDrag, { passive: true });
}

function unregisterTouchDragListeners() {
    document.removeEventListener("touchmove", handleTouchDragMove);
    document.removeEventListener("touchend", finishTouchDrag);
    document.removeEventListener("touchcancel", cancelTouchDrag);
}

function getDragTouch(touches) {
    if (!dragState || dragState.inputType !== "touch") return null;
    return Array.from(touches).find((touch) => touch.identifier === dragState.pointerId) || null;
}

function handleTouchDragMove(event) {
    const touch = getDragTouch(event.touches);
    if (!touch) return;
    dragState.currentX = touch.clientX;
    dragState.currentY = touch.clientY;
    const moved = Math.hypot(touch.clientX - dragState.startX, touch.clientY - dragState.startY);
    if (!dragState.active) {
        if (moved > LONG_PRESS_MOVE_TOLERANCE) cleanupPointerDrag();
        return;
    }
    event.preventDefault();
    movePointerGhost(touch);
}

function finishTouchDrag(event) {
    const touch = getDragTouch(event.changedTouches);
    if (!touch) return;
    if (dragState.active) {
        event.preventDefault();
        const zone = findDropZone(touch);
        if (zone) applyDrop(dragState.payload, zone);
        suppressClickUntil = Date.now() + 350;
    }
    cleanupPointerDrag();
}

function cancelTouchDrag(event) {
    if (!getDragTouch(event.changedTouches)) return;
    cleanupPointerDrag();
}

function createPointerGhost() {
    if (dragState?.payload.type !== "search") {
        return dragState.source.cloneNode(true);
    }
    const card = cardStore.get(String(dragState.payload.pk));
    const ghost = document.createElement("article");
    ghost.className = "v2-mobile-drag-ghost-card";
    const image = document.createElement("img");
    image.src = card?.img_sm || card?.img || "";
    image.alt = card?.name || "";
    image.draggable = false;
    ghost.appendChild(image);
    return ghost;
}

function movePointerGhost(event) {
    if (!dragState?.ghost) return;
    dragState.ghost.style.transform = `translate(${event.clientX}px, ${event.clientY}px) translate(-50%, -50%)`;
    document.querySelectorAll(".v2-deck-mobile-zone.is-drag-over").forEach((zone) => {
        zone.classList.remove("is-drag-over");
    });
    const zone = findDropZone(event);
    if (zone) {
        document.querySelector(`.v2-deck-mobile-zone[data-zone="${zone}"]`)?.classList.add("is-drag-over");
    }
}

function findDropZone(event) {
    if (!dragState) return null;
    const ghost = dragState.ghost;
    if (ghost) ghost.style.pointerEvents = "none";
    const target = document.elementFromPoint(event.clientX, event.clientY);
    if (ghost) ghost.style.pointerEvents = "";
    return target?.closest("[data-zone]")?.dataset.zone || null;
}

function finishPointerDrag(event) {
    if (!dragState || dragState.inputType !== "pointer" || dragState.pointerId !== event.pointerId) return;
    if (dragState.active) {
        event.preventDefault();
        const zone = findDropZone(event);
        if (zone) applyDrop(dragState.payload, zone);
        suppressClickUntil = Date.now() + 350;
    }
    cleanupPointerDrag();
}

function cancelPointerDrag(event) {
    if (!dragState || dragState.inputType !== "pointer" || dragState.pointerId !== event.pointerId) return;
    cleanupPointerDrag();
}

function cleanupPointerDrag() {
    if (dragState?.longPressTimer) window.clearTimeout(dragState.longPressTimer);
    if (dragState?.inputType === "touch") unregisterTouchDragListeners();
    if (dragState?.inputType === "pointer" && dragState?.handle?.hasPointerCapture?.(dragState.pointerId)) {
        dragState.handle.releasePointerCapture?.(dragState.pointerId);
    }
    dragState?.ghost?.remove();
    dragState?.source?.classList.remove("is-drag-source");
    document.querySelectorAll(".v2-deck-mobile-zone.is-drag-over").forEach((zone) => {
        zone.classList.remove("is-drag-over");
    });
    dragState = null;
}

function applyDrop(payload, zone) {
    if (!payload) return;
    if (payload.type === "entry") {
        moveEntry(payload.entryId, zone);
        return;
    }
    if (payload.type === "search") {
        const card = cardStore.get(String(payload.pk));
        if (card) addCard(card, zone);
    }
}

function makeDeckCard(entry) {
    const card = cardStore.get(String(entry.pk));
    const tile = document.createElement("article");
    tile.className = "v2-mobile-builder-card";
    if (isUltimateCard(card)) tile.classList.add("is-ultimate");
    tile.dataset.entryId = entry.entryId;

    const image = document.createElement("img");
    image.src = card.img_sm || card.img || "";
    image.alt = card.name || "";
    image.draggable = false;
    tile.appendChild(image);

    const removeButton = document.createElement("button");
    removeButton.className = "v2-mobile-card-remove";
    removeButton.type = "button";
    removeButton.textContent = "x";
    removeButton.ariaLabel = t("remove", "삭제");
    removeButton.addEventListener("click", () => removeEntry(entry.entryId));
    tile.appendChild(removeButton);

    const controls = document.createElement("div");
    controls.className = "v2-mobile-card-actions";
    if (isUltimateCard(card)) {
        const badge = document.createElement("span");
        badge.className = "v2-mobile-card-badge";
        badge.textContent = t("ultimate", "얼티밋");
        controls.appendChild(badge);
    } else if (isForcedSideCard(card)) {
        const badge = document.createElement("span");
        badge.className = "v2-mobile-card-badge";
        badge.textContent = zoneLabels.side;
        controls.appendChild(badge);
    } else {
        Object.keys(zoneLabels).forEach((zone) => {
            if (zone === entry.zone) return;
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = mobileZoneButtonLabels[zone];
            button.addEventListener("click", () => moveEntry(entry.entryId, zone));
            controls.appendChild(button);
        });
    }
    tile.appendChild(controls);
    bindPointerDrag(tile, () => ({ type: "entry", entryId: entry.entryId }));
    return tile;
}

function renderDeck() {
    Object.values(zoneElements).forEach((element) => {
        if (element) element.replaceChildren();
    });

    Object.keys(zoneElements).forEach((zone) => {
        const zoneEntries = sortEntries(deckEntries.filter((entry) => entry.zone === zone));
        zoneEntries.forEach((entry) => zoneElements[zone]?.appendChild(makeDeckCard(entry)));
        if (zoneCountElements[zone]) zoneCountElements[zone].textContent = countDeckSizeEntries(zone);
    });

    document.getElementById("CardCount").textContent = countDeckSizeEntries();
    const handCount = document.getElementById("HandCount");
    const sideCount = document.getElementById("SideCount");
    if (handCount) handCount.textContent = countDeckSizeEntries("hand");
    if (sideCount) sideCount.textContent = countDeckSizeEntries("side");
}

function makeSearchCard(card) {
    const tile = document.createElement("article");
    tile.className = "v2-mobile-search-card";

    const image = document.createElement("img");
    image.src = card.img_sm || "";
    image.alt = card.name || "";
    image.draggable = false;
    tile.appendChild(image);

    const body = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = card.name;
    body.appendChild(name);

    const actions = document.createElement("div");
    actions.className = "v2-mobile-search-actions";
    getAllowedZones(card).forEach((zone) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = zoneLabels[zone];
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            addCard(card, zone);
        });
        actions.appendChild(button);
    });
    body.appendChild(actions);
    tile.appendChild(body);

    tile.addEventListener("click", (event) => {
        if (Date.now() < suppressClickUntil) {
            event.preventDefault();
            event.stopPropagation();
            return;
        }
        addCard(card, getDefaultZone(card));
    });
    bindPointerDrag(image, () => ({ type: "search", pk: card.pk }), tile);
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
    Object.entries(aggregate).forEach(([pk, values]) => {
        if (isForcedSideCard(cardStore.get(String(pk)))) {
            values.hand = 0;
            values.side = values.count;
        }
    });
    return Object.keys(aggregate).map((pk) => [pk, aggregate[pk]]);
}

function submitDeck() {
    const form = document.getElementById("submitForm");
    if (!form) return;
    if (countDeckSizeEntries() > maxDeckSize) {
        alert(t("maxDeckSize", "덱 매수는 최대 {count}장입니다.", { count: maxDeckSize }));
        return;
    }
    const formData = new FormData(form);
    const payload = {};
    formData.forEach((value, key) => {
        payload[key] = value;
    });
    payload.description = payload.description || "";
    payload.keyword = payload.keyword || "";
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

function addInitialEntry(pk, zone) {
    deckEntries.push({
        entryId: nextEntryId++,
        pk: String(pk),
        zone,
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
        if (isForcedSideCard(card)) {
            for (let i = 0; i < card.count; i++) addInitialEntry(card.pk, "side");
            return;
        }
        for (let i = 0; i < card.hand; i++) addInitialEntry(card.pk, "hand");
        for (let i = 0; i < card.side; i++) addInitialEntry(card.pk, "side");
        for (let i = 0; i < card.count - card.hand - card.side; i++) addInitialEntry(card.pk, "list");
    });
}

function selectInitialCharacter() {
    if (!config.selectedCharacterId) return;
    const select = document.querySelector('select[name="char"]');
    if (select) {
        select.value = String(config.selectedCharacterId);
        return;
    }
    const input = document.querySelector(`input[name="char"][value="${config.selectedCharacterId}"]`);
    if (input) input.checked = true;
}

function setupEvents() {
    document.querySelectorAll('select[name="char"], input[name="char"]').forEach((input) => {
        input.addEventListener("change", () => syncSearchCharacter(true));
    });
    document.getElementById("v2DeckSearchButton")?.addEventListener("click", searchCards);
    document.getElementById("v2DeckSubmit")?.addEventListener("click", submitDeck);
    document.getElementById("v2DeckSearchForm")?.addEventListener("submit", (event) => {
        event.preventDefault();
        searchCards();
    });
    document.getElementById("submitForm")?.addEventListener("submit", (event) => {
        event.preventDefault();
        submitDeck();
    });
    document.querySelector("[data-mobile-deck-fullscreen]")?.addEventListener("click", () => {
        const root = document.querySelector("[data-mobile-deck-builder]") || document.documentElement;
        if (document.fullscreenElement) document.exitFullscreen?.();
        else root.requestFullscreen?.();
    });
    document.querySelector("[data-mobile-deck-meta-open]")?.addEventListener("click", openDeckMetaModal);
    document.querySelectorAll("[data-mobile-deck-meta-close]").forEach((button) => {
        button.addEventListener("click", closeDeckMetaModal);
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeDeckMetaModal();
    });
}

function openDeckMetaModal() {
    const modal = document.querySelector("[data-mobile-deck-meta-modal]");
    if (!modal) return;
    modal.hidden = false;
    modal.querySelector("#submitForm input, #submitForm select, #submitForm textarea")?.focus();
}

function closeDeckMetaModal() {
    const modal = document.querySelector("[data-mobile-deck-meta-modal]");
    if (!modal || modal.hidden) return;
    modal.hidden = true;
}

selectInitialCharacter();
syncSearchCharacter(false);
loadInitialDeck();
setupEvents();
renderDeck();
window.deckSubmit = submitDeck;
