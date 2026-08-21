(() => {
    const root = document.querySelector("[data-simulator-start]");
    if (!root) return;

    const searchUrl = root.dataset.deckSearchUrl;
    const searchInput = root.querySelector("[data-simulator-deck-search-input]");
    const results = root.querySelector("[data-simulator-deck-search-results]");
    const modeSelect = root.querySelector("#simulator_mode");
    const opponentSelect = root.querySelector("[data-opponent-type]");
    if (!searchUrl || !searchInput || !results) return;

    const playerInputs = {
        p1: {
            name: root.querySelector('[data-player-name="p1"]'),
            deck: root.querySelector('[data-player-deck="p1"]'),
            fallback: "플레이어1",
        },
        p2: {
            name: root.querySelector('[data-player-name="p2"]'),
            deck: root.querySelector('[data-player-deck="p2"]'),
            fallback: "플레이어2",
        },
    };

    function syncOpponentMode() {
        if (!modeSelect || !opponentSelect) return;
        const manualOption = modeSelect.querySelector('option[value="manual"]');
        const usesAI = opponentSelect.value === "ai";
        if (manualOption) manualOption.disabled = usesAI;
        if (usesAI) {
            modeSelect.value = "automatic";
            if (playerInputs.p2.name && !playerInputs.p2.name.value.trim()) {
                playerInputs.p2.name.value = "Lumen AI";
            }
        }
    }

    if (opponentSelect) opponentSelect.addEventListener("change", syncOpponentMode);
    syncOpponentMode();

    function playerNameWithCharacter(currentName, fallback, characterName) {
        let baseName = (currentName || "").trim() || fallback;
        const suffix = `(${characterName})`;
        if (baseName.endsWith(suffix)) return baseName;
        if (baseName.endsWith(")") && baseName.includes("(")) {
            baseName = baseName.slice(0, baseName.lastIndexOf("(")).trim() || fallback;
        }
        return `${baseName}${suffix}`;
    }

    function assignDeck(side, deck) {
        const player = playerInputs[side];
        if (!player || !deck) return;
        if (player.deck) player.deck.value = deck.id;
        if (player.name) {
            player.name.value = playerNameWithCharacter(player.name.value, player.fallback, deck.character);
        }
    }

    function renderEmpty(message) {
        results.replaceChildren();
        const empty = document.createElement("div");
        empty.className = "v2-simulator-deck-search-empty";
        empty.textContent = message;
        results.appendChild(empty);
    }

    function renderResults(decks) {
        results.replaceChildren();
        if (!decks.length) {
            renderEmpty("검색 결과가 없습니다.");
            return;
        }

        decks.forEach((deck) => {
            const item = document.createElement("div");
            item.className = "v2-simulator-deck-result";

            const body = document.createElement("div");
            body.className = "v2-simulator-deck-result-body";

            const title = document.createElement("strong");
            title.textContent = `#${deck.id} ${deck.name}`;

            const meta = document.createElement("span");
            meta.textContent = `${deck.author} / ${deck.character} / ${deck.version} / ${deck.is_owner ? "내 덱" : deck.visibility}`;

            body.append(title, meta);

            const actions = document.createElement("div");
            actions.className = "v2-simulator-deck-result-actions";
            ["p1", "p2"].forEach((side) => {
                const button = document.createElement("button");
                button.className = "v2-button";
                button.type = "button";
                button.textContent = side.toUpperCase();
                button.addEventListener("click", () => assignDeck(side, deck));
                actions.appendChild(button);
            });

            item.append(body, actions);
            results.appendChild(item);
        });
    }

    let timerId = null;
    searchInput.addEventListener("input", () => {
        window.clearTimeout(timerId);
        const query = searchInput.value.trim();
        const isDeckId = /^\d+$/.test(query);
        if (query.length < 2 && !isDeckId) {
            results.replaceChildren();
            return;
        }

        timerId = window.setTimeout(() => {
            const url = new URL(searchUrl, window.location.origin);
            url.searchParams.set("q", query);
            fetch(url)
                .then((response) => {
                    if (!response.ok) throw new Error("deck search failed");
                    return response.json();
                })
                .then(renderResults)
                .catch(() => renderEmpty("덱 검색 중 오류가 발생했습니다."));
        }, 180);
    });
})();
