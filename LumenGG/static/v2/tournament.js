document.querySelectorAll('[data-round-timer]').forEach((timer) => {
    const endsAt = new Date(timer.dataset.endsAt);
    const timeoutActions = Array.from(document.querySelectorAll("[data-round-timeout-action]"))
        .filter((action) => action.dataset.endsAt === timer.dataset.endsAt);

    const tick = () => {
        const remaining = endsAt.getTime() - Date.now();
        if (Number.isNaN(remaining)) {
            timer.textContent = '--:--';
            timeoutActions.forEach((action) => { action.hidden = true; });
            return;
        }
        if (remaining <= 0) {
            timer.textContent = '시간 초과';
            timer.classList.add('is-over');
            timeoutActions.forEach((action) => { action.hidden = false; });
            return;
        }
        const totalSeconds = Math.floor(remaining / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        timer.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        timeoutActions.forEach((action) => { action.hidden = true; });
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

function setupTournamentSections() {
    const tabs = Array.from(document.querySelectorAll("[data-tournament-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-tournament-panel]"));
    if (!tabs.length || !panels.length) return;

    const validKeys = new Set(tabs.map((tab) => tab.dataset.tournamentTab));
    const hashKey = window.location.hash.replace(/^#section-/, "");
    const initialKey = validKeys.has(hashKey) ? hashKey : tabs[0].dataset.tournamentTab;

    const activate = (key, updateHash) => {
        if (!validKeys.has(key)) return;
        tabs.forEach((tab) => {
            const active = tab.dataset.tournamentTab === key;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
        });
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.tournamentPanel !== key;
        });
        if (updateHash) {
            window.history.replaceState(null, "", `#section-${key}`);
        }
    };

    tabs.forEach((tab) => {
        tab.setAttribute("aria-selected", "false");
        tab.addEventListener("click", () => activate(tab.dataset.tournamentTab, true));
    });

    activate(initialKey, false);
}

setupTournamentSections();

function setupRoundTabs() {
    const tabs = Array.from(document.querySelectorAll("[data-round-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-round-panel]"));
    if (!tabs.length || !panels.length) return;

    const validKeys = new Set(tabs.map((tab) => tab.dataset.roundTab));
    const defaultPanel = panels.find((panel) => panel.dataset.roundDefault === "true") || panels[0];
    const initialKey = defaultPanel ? defaultPanel.dataset.roundPanel : tabs[0].dataset.roundTab;

    const activate = (key) => {
        if (!validKeys.has(key)) return;
        tabs.forEach((tab) => {
            const active = tab.dataset.roundTab === key;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
        });
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.roundPanel !== key;
        });
    };

    tabs.forEach((tab) => {
        tab.setAttribute("aria-selected", "false");
        tab.addEventListener("click", () => activate(tab.dataset.roundTab));
    });

    activate(initialKey);
}

setupRoundTabs();

function tournamentHpRatio(hp, initialHp) {
    const current = Number(hp);
    const initial = Number(initialHp);
    if (!Number.isFinite(current) || !Number.isFinite(initial) || initial <= 0) return null;
    return Math.max(0, Math.min(1, current / initial));
}

function tournamentHpColor(hp, initialHp) {
    const ratio = tournamentHpRatio(hp, initialHp);
    if (ratio === null) return "transparent";
    const hue = Math.round(4 + (ratio * 136));
    return `hsl(${hue} 58% 52%)`;
}

function safeCssUrl(value) {
    const url = String(value || "").trim();
    return url ? `url("${url.replaceAll('"', "%22")}")` : "none";
}

function applyTournamentMatchVisual(matchRow, summary) {
    const p1Hp = summary ? summary.p1_hp : matchRow.dataset.battleP1Hp;
    const p1InitialHp = summary ? summary.p1_initial_hp : matchRow.dataset.battleP1InitialHp;
    const p1CharacterImg = summary ? summary.p1_character_img : matchRow.dataset.battleP1CharacterImg;
    const p2Hp = summary ? summary.p2_hp : matchRow.dataset.battleP2Hp;
    const p2InitialHp = summary ? summary.p2_initial_hp : matchRow.dataset.battleP2InitialHp;
    const p2CharacterImg = summary ? summary.p2_character_img : matchRow.dataset.battleP2CharacterImg;

    matchRow.style.setProperty("--tournament-p1-hp-color", tournamentHpColor(p1Hp, p1InitialHp));
    matchRow.style.setProperty("--tournament-p2-hp-color", tournamentHpColor(p2Hp, p2InitialHp));
    matchRow.style.setProperty("--tournament-p1-character-img", safeCssUrl(p1CharacterImg));
    matchRow.style.setProperty("--tournament-p2-character-img", safeCssUrl(p2CharacterImg));

    if (summary) {
        matchRow.dataset.battleP1Hp = summary.p1_hp ?? "";
        matchRow.dataset.battleP1InitialHp = summary.p1_initial_hp ?? "";
        matchRow.dataset.battleP1CharacterImg = summary.p1_character_img || "";
        matchRow.dataset.battleP2Hp = summary.p2_hp ?? "";
        matchRow.dataset.battleP2InitialHp = summary.p2_initial_hp ?? "";
        matchRow.dataset.battleP2CharacterImg = summary.p2_character_img || "";
    }
}

function renderTournamentBattleState(data) {
    document.querySelectorAll("[data-battle-match-id]").forEach((matchRow) => {
        const summary = data[String(matchRow.dataset.battleMatchId)];
        if (!summary) return;
        const p1 = matchRow.querySelector('[data-battle-hp="p1"]');
        const p2 = matchRow.querySelector('[data-battle-hp="p2"]');
        const sudden = matchRow.querySelector("[data-battle-sudden]");
        if (p1) {
            p1.textContent = summary.p1_ready
                ? `${summary.p1_hp} HP / FP ${summary.p1_fp}`
                : "캐릭터 선택 필요";
        }
        if (p2) {
            p2.textContent = summary.p2_ready
                ? `${summary.p2_hp} HP / FP ${summary.p2_fp}`
                : "캐릭터 선택 필요";
        }
        const setInfo = matchRow.querySelector("[data-battle-set]");
        if (setInfo) {
            if (summary.sudden_death) {
                setInfo.textContent = `서든 데스 / 추가 턴 ${summary.sudden_death_turns_remaining || 0}`;
            } else {
                setInfo.textContent = summary.set_number
                ? `${summary.set_number}세트 / ${summary.p1_set_score}:${summary.p2_set_score} / 확인 ${summary.p1_confirmed ? "P1" : "-"} ${summary.p2_confirmed ? "P2" : "-"}`
                : `${summary.p1_set_score}:${summary.p2_set_score}`;
            }
        }
        if (sudden) {
            sudden.hidden = !summary.sudden_death;
        }
        applyTournamentMatchVisual(matchRow, summary);
    });
}

function buildTournamentWebSocketUrl(path) {
    const url = new URL(path, window.location.href);
    url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
}

function setupTournamentBattleState() {
    if (!document.querySelector("[data-battle-match-id]")) return;

    document.querySelectorAll("[data-battle-match-id]").forEach((matchRow) => {
        applyTournamentMatchVisual(matchRow, null);
    });

    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let socket = null;

    const fetchOnceFallback = () => {
        if (!tournamentConfig.battleStateUrl) return;
        fetch(tournamentConfig.battleStateUrl)
            .then((response) => response.json())
            .then(renderTournamentBattleState)
            .catch(() => {});
    };

    const connectSocket = () => {
        if (!tournamentConfig.battleStateWsPath || !("WebSocket" in window)) {
            fetchOnceFallback();
            return;
        }

        window.clearTimeout(reconnectTimer);
        socket = new WebSocket(buildTournamentWebSocketUrl(tournamentConfig.battleStateWsPath));

        socket.addEventListener("open", () => {
            reconnectAttempts = 0;
        });

        socket.addEventListener("message", (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === "state") {
                    renderTournamentBattleState(message.state || {});
                }
            } catch (error) {
                // Ignore malformed realtime payloads and keep the current display.
            }
        });

        socket.addEventListener("close", () => {
            const delay = Math.min(15000, 1000 * (2 ** reconnectAttempts));
            reconnectAttempts += 1;
            reconnectTimer = window.setTimeout(connectSocket, delay);
        });

        socket.addEventListener("error", () => {});
    };

    connectSocket();

    window.addEventListener("beforeunload", () => {
        window.clearTimeout(reconnectTimer);
        if (socket) socket.close();
    });
}

setupTournamentBattleState();

document.querySelectorAll("[data-tournament-join-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const hasExternalDeck = Array.from(form.querySelectorAll("[data-deck-picker]"))
            .some((picker) => picker.dataset.selectedOwner === "other");
        if (hasExternalDeck) {
            window.alert("타인의 덱으로 참가 신청하는 경우, 해당 덱이 내 덱으로 복사된 뒤 신청됩니다.");
        }
    });
});
