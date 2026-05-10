document.querySelectorAll('[data-round-timer]').forEach((timer) => {
    const endsAt = new Date(timer.dataset.endsAt);

    const tick = () => {
        const remaining = endsAt.getTime() - Date.now();
        if (Number.isNaN(remaining)) {
            timer.textContent = '--:--';
            return;
        }
        if (remaining <= 0) {
            timer.textContent = '시간 초과';
            timer.classList.add('is-over');
            return;
        }
        const totalSeconds = Math.floor(remaining / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        timer.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    };

    tick();
    setInterval(tick, 1000);
});

const tournamentConfig = window.v2TournamentConfig || {};

function deckResultLabel(deck) {
    const ownerMark = deck.is_owner ? "내 덱" : deck.visibility;
    return `#${deck.id} ${deck.name} / ${deck.author} / ${deck.character} / ${ownerMark}`;
}

function selectTournamentDeck(picker, deck) {
    const hiddenInput = picker.querySelector('input[type="hidden"][name^="deck_"]');
    const selected = picker.querySelector("[data-deck-selected]");
    const results = picker.querySelector("[data-deck-search-results]");
    const searchInput = picker.querySelector("[data-deck-search-input]");
    if (!hiddenInput || !selected || !results) return;

    hiddenInput.value = deck.id;
    selected.innerHTML = "";

    const title = document.createElement("strong");
    title.textContent = `#${deck.id} ${deck.name}`;
    const meta = document.createElement("span");
    meta.textContent = `${deck.author} / ${deck.character} / ${deck.visibility}`;
    selected.append(title, meta);
    picker.dataset.selectedOwner = deck.is_owner ? "self" : "other";

    results.replaceChildren();
    if (searchInput) searchInput.value = "";
}

function renderTournamentDeckResults(picker, decks) {
    const results = picker.querySelector("[data-deck-search-results]");
    if (!results) return;
    results.replaceChildren();

    if (!decks.length) {
        const empty = document.createElement("div");
        empty.className = "v2-tournament-deck-result is-empty";
        empty.textContent = "검색 결과가 없습니다.";
        results.appendChild(empty);
        return;
    }

    decks.forEach((deck) => {
        const button = document.createElement("button");
        button.className = "v2-tournament-deck-result";
        button.type = "button";

        const title = document.createElement("strong");
        title.textContent = `#${deck.id} ${deck.name}`;
        const meta = document.createElement("span");
        meta.textContent = `${deck.author} / ${deck.character} / ${deck.version} / ${deck.is_owner ? "내 덱" : deck.visibility}`;
        button.append(title, meta);
        button.setAttribute("aria-label", deckResultLabel(deck));
        button.addEventListener("click", () => selectTournamentDeck(picker, deck));
        results.appendChild(button);
    });
}

function setupTournamentDeckSearch() {
    if (!tournamentConfig.deckSearchUrl) return;

    document.querySelectorAll("[data-deck-picker]").forEach((picker) => {
        const input = picker.querySelector("[data-deck-search-input]");
        if (!input) return;

        let timerId = null;
        input.addEventListener("input", () => {
            window.clearTimeout(timerId);
            const query = input.value.trim();
            const results = picker.querySelector("[data-deck-search-results]");
            const isDeckId = /^\d+$/.test(query);

            if (query.length < 2 && !isDeckId) {
                if (results) results.replaceChildren();
                return;
            }

            timerId = window.setTimeout(() => {
                const url = new URL(tournamentConfig.deckSearchUrl, window.location.origin);
                url.searchParams.set("q", query);
                fetch(url)
                    .then((response) => response.json())
                    .then((decks) => renderTournamentDeckResults(picker, decks))
                    .catch(() => renderTournamentDeckResults(picker, []));
            }, 180);
        });
    });
}

setupTournamentDeckSearch();

document.querySelectorAll("[data-tournament-join-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const hasExternalDeck = Array.from(form.querySelectorAll("[data-deck-picker]"))
            .some((picker) => picker.dataset.selectedOwner === "other");
        if (hasExternalDeck) {
            window.alert("타인의 덱으로 참가 신청하는 경우, 해당 덱이 내 덱으로 복사된 뒤 신청됩니다.");
        }
    });
});
