(function () {
    const stateNode = document.getElementById("battle-initial-state");
    const optionsNode = document.getElementById("battle-character-options");
    const config = window.v2BattleConfig || {};
    if (!stateNode || !optionsNode || !config.stateUrl || !config.actionUrl) return;

    let state = JSON.parse(stateNode.textContent);
    const characterOptions = JSON.parse(optionsNode.textContent);
    let historyFilter = "all";
    let historyOpen = false;
    let shareOpen = false;
    let historyLoaded = Array.isArray(state.events);
    if (!state.events) state.events = [];
    const pendingHp = new Map();
    const pendingFp = new Map();
    const pendingSocketActions = new Map();
    const lastRenderedHp = new Map();
    let socket = null;
    let socketReady = false;
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let pollingTimer = null;
    let nextRequestId = 1;
    const TIMER_DISPLAY_GRACE_MS = 1500;

    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    const csrfToken = csrfInput ? csrfInput.value : "";

    function buildWebSocketUrl(path) {
        const url = new URL(path, window.location.href);
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        if (config.controlToken) url.searchParams.set("control_token", config.controlToken);
        return url.toString();
    }

    function formatSeconds(value) {
        if (value === null || value === undefined) return "--:--";
        const seconds = Math.max(0, Number(value) || 0);
        const minutes = Math.floor(seconds / 60);
        const rest = seconds % 60;
        return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
    }

    function playerLabel(target) {
        return target === "p1" ? "P1" : target === "p2" ? "P2" : "공통";
    }

    function cloneState() {
        return JSON.parse(JSON.stringify(state));
    }

    function keepEventsAndApplyState(nextState) {
        const previousEvents = state.events || [];
        state = nextState;
        if (!state.events) state.events = previousEvents;
    }

    function timerRemainingSeconds() {
        const timer = state.timer || {};
        const duration = Number(timer.duration_seconds || 10);
        if (timer.is_running && timer.ends_at) {
            const endsAt = new Date(timer.ends_at).getTime();
            if (!Number.isNaN(endsAt)) {
                return Math.max(0, Math.min(duration, Math.ceil((endsAt - Date.now() + TIMER_DISPLAY_GRACE_MS) / 1000)));
            }
        }
        return Math.max(0, Math.min(duration, Number(timer.remaining_seconds ?? duration) || 0));
    }

    function setShortTimerDisplay() {
        const timer = state.timer || {};
        const duration = Number(timer.duration_seconds || 10);
        const remaining = timerRemainingSeconds();
        const shortTimer = document.querySelector("[data-battle-short-timer]");
        const timerButton = document.querySelector("[data-battle-action='timer']");
        const dangerRatio = timer.is_running ? Math.max(0, Math.min(1, 1 - (remaining / duration))) : 0;
        const dangerAlpha = (dangerRatio * 0.48).toFixed(3);
        if (shortTimer) {
            shortTimer.textContent = String(remaining);
            shortTimer.classList.toggle("is-danger", timer.is_running && remaining <= 3);
        }
        if (timerButton) {
            timerButton.classList.toggle("is-active", !!timer.is_running);
            timerButton.style.setProperty("--battle-timer-danger-color", `rgba(217, 105, 105, ${dangerAlpha})`);
        }
    }

    function actionLabel(event) {
        if (event.type === "hp") {
            const amount = Number(event.amount || 0);
            const sign = amount > 0 ? "+" : "";
            return `${playerLabel(event.target)} HP ${sign}${amount} → ${event.hp_after}`;
        }
        if (event.type === "fp") {
            const amount = Number(event.amount || 0);
            const sign = amount > 0 ? "+" : "";
            const after = event.payload && event.payload.after !== undefined ? event.payload.after : "";
            return event.payload && event.payload.reset
                ? `${playerLabel(event.target)} FP 초기화`
                : `${playerLabel(event.target)} FP ${sign}${amount} → ${after}`;
        }
        if (event.type === "undo") return `${playerLabel(event.target)} 체력 변경 되돌림`;
        if (event.type === "timer") return event.payload && event.payload.running ? "10초 타이머 시작" : "10초 타이머 정지";
        if (event.type === "sudden_death") {
            return event.payload && event.payload.enabled ? "서든 데스 진입" : "서든 데스 해제";
        }
        if (event.type === "set_report") {
            if (event.payload && event.payload.confirmed) {
                return `${playerLabel(event.target)} 세트 결과 확인`;
            }
            const setNumber = event.payload && event.payload.set_number ? `${event.payload.set_number}세트 ` : "";
            return `${setNumber}${playerLabel(event.target)} 승`;
        }
        if (event.type === "set_start") {
            return `${event.payload && event.payload.set_number ? event.payload.set_number : ""}세트 시작`;
        }
        if (event.type === "extra_time") {
            return `추가 시간 ${formatSeconds(event.amount || 0)}`;
        }
        if (event.type === "character") {
            return `${playerLabel(event.target)} 캐릭터 ${event.payload.character || "선택"}`;
        }
        if (event.type === "passive") {
            const label = event.payload && event.payload.label ? event.payload.label : "패시브";
            const note = event.payload && event.payload.note ? ` / ${event.payload.note}` : "";
            let valueText = "";
            if (event.payload && event.payload.value !== null && event.payload.value !== undefined) {
                const rawValue = event.payload.value;
                const displayValue = typeof rawValue === "boolean" ? (rawValue ? "ON" : "OFF") : rawValue;
                valueText = ` = ${displayValue}`;
            }
            const amount = event.amount ? ` ${event.amount > 0 ? "+" : ""}${event.amount}` : "";
            return `${playerLabel(event.target)} ${label}${amount}${valueText}${note}`;
        }
        return event.type;
    }

    function setControlDisabled() {
        document.querySelectorAll("[data-hp-target], [data-fp-target], [data-fp-reset]").forEach((button) => {
            const target = button.dataset.hpTarget || button.dataset.fpTarget || button.dataset.fpReset;
            const player = target && state.players ? state.players[target] : null;
            button.disabled = !state.can_control || state.is_expired || !player || !player.character;
        });
        document.querySelectorAll("[data-battle-action='timer'], [data-battle-action='undo']").forEach((button) => {
            button.disabled = !state.can_control || state.is_expired;
        });
        const suddenButton = document.querySelector("[data-battle-action='sudden']");
        if (suddenButton) {
            suddenButton.disabled = !state.can_sudden_death || state.is_expired;
            suddenButton.classList.toggle("is-active", state.sudden_death);
            suddenButton.textContent = state.sudden_death ? "서든 데스 해제" : "서든 데스";
        }
        document.querySelectorAll("[data-report-set]").forEach((button) => {
            const setState = state.set || {};
            const alreadyReported = (
                (setState.report_side === "p1" && setState.player1_confirmed)
                || (setState.report_side === "p2" && setState.player2_confirmed)
            );
            button.disabled = !setState.can_report || !setState.winner_candidate || setState.ambiguous_result || alreadyReported;
            button.hidden = state.type !== "tournament";
            button.textContent = alreadyReported ? "보고 완료" : "결과 보고";
        });
        document.querySelectorAll("[data-extra-time]").forEach((button) => {
            button.disabled = !(state.set && state.set.can_add_time);
        });
    }

    function renderCharacter(target) {
        const player = state.players[target];
        const panel = document.querySelector(`[data-player-panel="${target}"]`);
        if (!panel) return;

        if (!player.character || !player.character.img) {
            panel.style.removeProperty("--battle-character-bg");
            panel.classList.remove("has-character-bg");
            return;
        }

        const imageUrl = String(player.character.img).replaceAll('"', "%22");
        panel.style.setProperty("--battle-character-bg", `url("${imageUrl}")`);
        panel.classList.add("has-character-bg");
    }

    function clampRatio(value) {
        return Math.max(0, Math.min(1, Number(value) || 0));
    }

    function updatePlayerHpColor(target, player) {
        const panel = document.querySelector(`[data-player-panel="${target}"]`);
        if (!panel) return;
        const rawInitialHp = Number(player.initial_hp || 0);
        const ratio = rawInitialHp > 0 ? clampRatio(Number(player.hp || 0) / rawInitialHp) : 0.5;
        const hue = Math.round(4 + (ratio * 136));
        panel.style.setProperty("--battle-hp-ratio", ratio.toFixed(3));
        panel.style.setProperty("--battle-hp-color", `hsl(${hue} 58% 52%)`);
        panel.style.setProperty("--battle-hp-strong-color", `hsl(${hue} 78% 62%)`);
    }

    function showHpDelta(target, amount) {
        if (!amount) return;
        const hpBox = document.querySelector(`[data-player-hp="${target}"]`)?.closest(".v2-battle-hp > div");
        if (!hpBox) return;
        const badge = document.createElement("span");
        badge.className = `v2-battle-hp-delta ${amount > 0 ? "is-heal" : "is-damage"}`;
        badge.textContent = `${amount > 0 ? "+" : ""}${amount}`;
        hpBox.querySelectorAll(".v2-battle-hp-delta").forEach((node) => node.remove());
        hpBox.appendChild(badge);
        window.setTimeout(() => badge.remove(), 1150);
    }

    function makePassiveApi(target, root, options) {
        const player = state.players[target];
        const passiveState = player.passive_state || {};
        return {
            target,
            root,
            options: options || {},
            state,
            player,
            passiveState,
            canControl: state.can_control && !state.is_expired,
            action(payload) {
                return postAction({ action: "passive", target, ...(payload || {}) });
            },
            increment(key, delta, label) {
                return postAction({ action: "passive", target, key, delta: Number(delta || 1), label: label || key });
            },
            set(key, value, label) {
                return postAction({ action: "passive", target, key, value, label: label || key });
            },
            note(key, note, label) {
                return postAction({ action: "passive", target, key: key || "memo", note, label: label || key || "메모" });
            },
            get(key, fallback) {
                const entry = passiveState[String(key)] || {};
                if (entry.value !== undefined) return entry.value;
                if (entry.count !== undefined) return entry.count;
                return fallback;
            },
        };
    }

    function renderCustomPassiveUi(target, holder, passiveUi) {
        const root = document.createElement("div");
        const rootId = `v2-battle-passive-${state.id}-${target}-${state.players[target].character.id}`;
        root.id = rootId;
        root.className = "v2-battle-passive-custom";
        root.innerHTML = passiveUi.html || "";

        if (passiveUi.css) {
            const style = document.createElement("style");
            style.textContent = String(passiveUi.css).replaceAll(":host", `#${rootId}`);
            holder.appendChild(style);
        }
        holder.appendChild(root);

        if (passiveUi.js) {
            try {
                const api = makePassiveApi(target, root, passiveUi.options || {});
                const run = new Function("api", `"use strict";\n${passiveUi.js}`);
                run(api);
            } catch (error) {
                const message = document.createElement("p");
                message.className = "v2-battle-empty";
                message.textContent = "패시브 패널 스크립트 오류가 발생했습니다.";
                holder.appendChild(message);
                console.error(error);
            }
        }
    }

    function renderFallbackPassiveMemo(target, holder) {
        holder.replaceChildren();
    }

    function renderPassives(target) {
        const holder = document.querySelector(`[data-player-passives="${target}"]`);
        if (!holder) return;
        holder.replaceChildren();

        const player = state.players[target];
        const passiveUi = player.character ? player.character.passive_ui || {} : {};
        const hasCustomPanel = passiveUi.html || passiveUi.css || passiveUi.js;
        if (!player.character) {
            const empty = document.createElement("p");
            empty.className = "v2-battle-empty";
            empty.textContent = "캐릭터를 선택하면 패시브 패널이 표시됩니다.";
            holder.appendChild(empty);
            return;
        }
        if (hasCustomPanel) {
            renderCustomPassiveUi(target, holder, passiveUi);
            return;
        }
        renderFallbackPassiveMemo(target, holder);
    }

    function renderCharacterSelectors() {
        const holder = document.querySelector("[data-character-selectors]");
        if (!holder) return;
        holder.replaceChildren();

        ["p1", "p2"].forEach((target) => {
            const player = state.players[target];
            const options = characterOptions[target] || { can_choose: false, options: [] };
            if (player.character || !state.can_control || !options.can_choose || !options.options.length) return;

            const field = document.createElement("label");
            field.className = "v2-battle-character-select";
            const span = document.createElement("span");
            span.textContent = `${playerLabel(target)} 캐릭터`;
            const select = document.createElement("select");
            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "선택";
            select.appendChild(empty);
            options.options.forEach((character) => {
                const option = document.createElement("option");
                option.value = character.id;
                option.textContent = character.name;
                select.appendChild(option);
            });
            select.addEventListener("change", () => {
                if (select.value) {
                    postAction({ action: "character", target, character_id: select.value });
                }
            });
            field.append(span, select);
            holder.appendChild(field);
        });
    }

    function renderHistory() {
        const holder = document.querySelector("[data-battle-history]");
        if (!holder) return;
        holder.replaceChildren();

        const events = (state.events || []).filter((event) => {
            if (historyFilter === "all") return true;
            return event.target === historyFilter && ["hp", "fp", "undo", "set_report"].includes(event.type);
        });

        if (!events.length) {
            const empty = document.createElement("p");
            empty.className = "v2-battle-empty";
            empty.textContent = "표시할 기록이 없습니다.";
            holder.appendChild(empty);
            return;
        }

        events.forEach((event) => {
            const row = document.createElement("div");
            row.className = "v2-battle-history-row";
            if (event.undone) row.classList.add("is-undone");
            const label = document.createElement("strong");
            label.textContent = actionLabel(event);
            const meta = document.createElement("span");
            const created = new Date(event.created_at);
            meta.textContent = `${Number.isNaN(created.getTime()) ? "" : created.toLocaleTimeString()} / ${event.actor}`;
            row.append(label, meta);
            holder.appendChild(row);
        });
    }

    function renderState() {
        document.querySelectorAll("[data-player-name]").forEach((node) => {
            node.textContent = state.players[node.dataset.playerName].name;
        });
        ["p1", "p2"].forEach((target) => {
            const player = state.players[target];
            const hp = document.querySelector(`[data-player-hp="${target}"]`);
            const fp = document.querySelector(`[data-player-fp="${target}"]`);
            const hand = document.querySelector(`[data-player-hand="${target}"]`);
            const previousHp = lastRenderedHp.get(target);
            if (previousHp !== undefined && Number(player.hp) !== Number(previousHp)) {
                showHpDelta(target, Number(player.hp) - Number(previousHp));
            }
            lastRenderedHp.set(target, Number(player.hp));
            if (hp) hp.textContent = player.hp;
            if (fp) {
                const value = document.createElement("strong");
                value.textContent = player.fp > 0 ? `+${player.fp}` : String(player.fp);
                fp.replaceChildren(value);
            }
            if (hand) {
                const limit = player.character ? player.character.hand_limit : null;
                hand.textContent = limit ? `손패 ${limit}` : "손패 -";
            }
            renderCharacter(target);
            updatePlayerHpColor(target, player);
            renderPassives(target);
        });

        const roundTimeLarge = document.querySelector("[data-battle-round-time-large]");
        if (roundTimeLarge) {
            roundTimeLarge.textContent = state.round_timer.ends_at
                ? formatSeconds(state.round_timer.remaining_seconds)
                : "--:--";
            roundTimeLarge.classList.toggle("is-danger", !!state.round_timer.is_over);
        }
        setShortTimerDisplay();
        const suggestion = document.querySelector("[data-battle-suggestion]");
        if (suggestion) {
            suggestion.textContent = state.set && state.set.ambiguous_result
                ? "운영자 판정 또는 서든 데스 필요"
                : (state.suggested_winner ? `${playerLabel(state.suggested_winner)} 승자 후보` : "");
            suggestion.hidden = !suggestion.textContent;
        }
        const setStatus = document.querySelector("[data-battle-set-status]");
        if (setStatus) {
            const setState = state.set || {};
            setStatus.hidden = state.type !== "tournament";
            setStatus.textContent = `${setState.current_number || 1}세트 / ${setState.score ? setState.score.p1 : 0}:${setState.score ? setState.score.p2 : 0}`;
        }
        const statusBar = document.querySelector(".v2-battle-status-bar");
        if (statusBar) {
            statusBar.hidden = state.type !== "tournament" && !(suggestion && suggestion.textContent);
        }
        const extraTimePanel = document.querySelector("[data-extra-time-panel]");
        if (extraTimePanel) {
            extraTimePanel.hidden = !(state.set && state.set.can_add_time);
        }
        renderSetPanel();

        document.body.classList.toggle("v2-battle-readonly", !state.can_control);
        document.body.classList.toggle("v2-battle-history-open", historyOpen);
        renderCharacterSelectors();
        if (historyOpen) renderHistory();
        setControlDisabled();
    }

    function renderSetPanel() {
        const panel = document.querySelector("[data-battle-set-panel]");
        if (!panel) return;
        panel.replaceChildren();
        panel.hidden = state.type !== "tournament";
        if (state.type !== "tournament") {
            return;
        }
        const setState = state.set || {};
        const title = document.createElement("strong");
        title.textContent = `${setState.current_number || 1}세트`;
        const score = document.createElement("span");
        score.textContent = `${state.players.p1.name} ${setState.score ? setState.score.p1 : 0} : ${setState.score ? setState.score.p2 : 0} ${state.players.p2.name}`;
        panel.append(title, score);

        const report = document.createElement("span");
        if (setState.ambiguous_result) {
            report.textContent = "양쪽 HP가 0 이하입니다. 운영자 판정 또는 서든 데스를 진행하세요.";
        } else if (setState.winner_candidate) {
            report.textContent = `${playerLabel(setState.winner_candidate)} 승자 후보 / 확인 ${setState.player1_confirmed ? "P1 완료" : "P1 대기"} · ${setState.player2_confirmed ? "P2 완료" : "P2 대기"}`;
        } else {
            report.textContent = "세트 진행 중";
        }
        panel.appendChild(report);

        if (setState.can_force) {
            const actions = document.createElement("div");
            actions.className = "v2-battle-force-actions";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "v2-button v2-button-primary";
            button.textContent = "결과 확정";
            button.disabled = !setState.winner_candidate || setState.ambiguous_result;
            button.title = button.disabled ? "승자 후보가 있을 때 확정할 수 있습니다." : `${playerLabel(setState.winner_candidate)} 승으로 확정`;
            button.addEventListener("click", () => {
                if (!setState.winner_candidate || setState.ambiguous_result) return;
                postAction({ action: "force_set_result", winner: setState.winner_candidate });
            });
            actions.appendChild(button);
            panel.appendChild(actions);
        }
    }

    function setHistoryOpen(nextOpen) {
        historyOpen = nextOpen;
        document.body.classList.toggle("v2-battle-history-open", historyOpen);
        document.querySelectorAll("[data-history-toggle]").forEach((button) => {
            button.textContent = historyOpen ? "로그 닫기" : "로그 확인";
        });
        if (historyOpen) fetchHistory(true);
    }

    function setShareOpen(nextOpen) {
        shareOpen = nextOpen;
        document.body.classList.toggle("v2-battle-share-open", shareOpen);
    }

    function postHttpAction(payload) {
        return fetch(config.actionUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ ...payload, control_token: config.controlToken || "" }),
        })
            .then((response) => response.json().then((data) => ({ response, data })))
            .then(({ response, data }) => {
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "요청을 처리하지 못했습니다.");
                }
                keepEventsAndApplyState(data.state);
                renderState();
                if (historyOpen) fetchHistory(true);
                return data;
            })
            .catch((error) => {
                throw new Error(error && error.message ? error.message : "네트워크 오류가 발생했습니다.");
            });
    }

    function postSocketAction(payload) {
        if (!socketReady || !socket || socket.readyState !== WebSocket.OPEN) {
            return postHttpAction(payload);
        }

        const requestId = String(nextRequestId++);
        return new Promise((resolve, reject) => {
            const timeout = window.setTimeout(() => {
                pendingSocketActions.delete(requestId);
                reject(new Error("요청 응답 시간이 초과되었습니다."));
            }, 5000);
            pendingSocketActions.set(requestId, { resolve, reject, timeout });
            try {
                socket.send(JSON.stringify({
                    type: "action",
                    request_id: requestId,
                    payload: { ...payload, control_token: config.controlToken || "" },
                }));
            } catch (error) {
                window.clearTimeout(timeout);
                pendingSocketActions.delete(requestId);
                reject(error);
            }
        });
    }

    function postAction(payload, optimisticUpdate, rollbackState) {
        const previousState = rollbackState || (optimisticUpdate ? cloneState() : null);
        if (optimisticUpdate) {
            optimisticUpdate(state);
            renderState();
        }
        const request = config.wsPath && "WebSocket" in window
            ? postSocketAction(payload)
            : postHttpAction(payload);
        return request.catch((error) => {
            if (previousState) {
                state = previousState;
                renderState();
            }
            window.alert(error && error.message ? error.message : "네트워크 오류가 발생했습니다.");
        });
    }

    function optimisticHp(target, amount) {
        return (draft) => {
            if (!draft.players || !draft.players[target]) return;
            draft.players[target].hp += amount;
            draft.suggested_winner = "";
            if (draft.players.p1.hp <= 0 && draft.players.p2.hp > 0) draft.suggested_winner = "p2";
            if (draft.players.p2.hp <= 0 && draft.players.p1.hp > 0) draft.suggested_winner = "p1";
            if (draft.set) {
                draft.set.winner_candidate = draft.suggested_winner;
                draft.set.ambiguous_result = draft.players.p1.hp <= 0 && draft.players.p2.hp <= 0;
                draft.set.player1_confirmed = false;
                draft.set.player2_confirmed = false;
            }
        };
    }

    function optimisticFp(target, amount) {
        return (draft) => {
            if (!draft.players || !draft.players[target]) return;
            draft.players[target].fp += amount;
        };
    }

    function optimisticFpReset(target) {
        return (draft) => {
            if (!draft.players || !draft.players[target]) return;
            draft.players[target].fp = 0;
        };
    }

    function optimisticTimer() {
        return (draft) => {
            const timer = draft.timer || {};
            const duration = Number(timer.duration_seconds || 10);
            if (timer.is_running) {
                timer.started_at = null;
                timer.ends_at = null;
                timer.remaining_seconds = duration;
                timer.is_running = false;
            } else {
                const startedAt = new Date();
                const endsAt = new Date(startedAt.getTime() + duration * 1000);
                timer.started_at = startedAt.toISOString();
                timer.ends_at = endsAt.toISOString();
                timer.remaining_seconds = duration;
                timer.is_running = true;
            }
            draft.timer = timer;
        };
    }

    function optimisticSuddenDeath(enabled) {
        return (draft) => {
            draft.sudden_death = !!enabled;
        };
    }

    function fetchHistory(force) {
        if (!config.eventsUrl || (!force && historyLoaded)) {
            renderHistory();
            return Promise.resolve();
        }
        const url = new URL(config.eventsUrl, window.location.origin);
        if (config.controlToken) url.searchParams.set("control_token", config.controlToken);
        return fetch(url)
            .then((response) => response.json())
            .then((data) => {
                state.events = Array.isArray(data.events) ? data.events : [];
                historyLoaded = true;
                renderHistory();
            })
            .catch(() => {
                historyLoaded = true;
                renderHistory();
            });
    }

    function pollState() {
        const url = new URL(config.stateUrl, window.location.origin);
        if (config.controlToken) url.searchParams.set("control_token", config.controlToken);
        fetch(url)
            .then((response) => response.json())
            .then((nextState) => {
                keepEventsAndApplyState(nextState);
                renderState();
                if (historyOpen) fetchHistory(true);
            })
            .catch(() => {});
    }

    function startPollingFallback() {
        if (pollingTimer) return;
        pollState();
        pollingTimer = window.setInterval(pollState, 2000);
    }

    function stopPollingFallback() {
        if (!pollingTimer) return;
        window.clearInterval(pollingTimer);
        pollingTimer = null;
    }

    function resolveSocketAction(message) {
        if (!message.request_id) return;
        const pending = pendingSocketActions.get(String(message.request_id));
        if (!pending) return;
        window.clearTimeout(pending.timeout);
        pendingSocketActions.delete(String(message.request_id));
        if (message.type === "error" || message.ok === false) {
            pending.reject(new Error(message.error || "요청을 처리하지 못했습니다."));
            return;
        }
        pending.resolve(message);
    }

    function rejectPendingSocketActions(message) {
        pendingSocketActions.forEach((pending) => {
            window.clearTimeout(pending.timeout);
            pending.reject(new Error(message));
        });
        pendingSocketActions.clear();
    }

    function connectSocket() {
        if (!config.wsPath || !("WebSocket" in window)) {
            startPollingFallback();
            return;
        }

        window.clearTimeout(reconnectTimer);
        socket = new WebSocket(buildWebSocketUrl(config.wsPath));

        socket.addEventListener("open", () => {
            socketReady = true;
            reconnectAttempts = 0;
            stopPollingFallback();
        });

        socket.addEventListener("message", (event) => {
            let message = null;
            try {
                message = JSON.parse(event.data);
            } catch (error) {
                return;
            }

            if (message.type === "state" && message.state) {
                keepEventsAndApplyState(message.state);
                renderState();
                if (historyOpen) fetchHistory(true);
                return;
            }
            if (message.type === "action_ack" || message.type === "error") {
                resolveSocketAction(message);
            }
        });

        socket.addEventListener("close", () => {
            socketReady = false;
            rejectPendingSocketActions("계산기 연결이 끊겼습니다.");
            if (reconnectAttempts >= 5) {
                startPollingFallback();
                return;
            }
            const delay = Math.min(10000, 1000 * (2 ** reconnectAttempts));
            reconnectAttempts += 1;
            reconnectTimer = window.setTimeout(connectSocket, delay);
        });

        socket.addEventListener("error", () => {
            socketReady = false;
        });
    }

    function formatQueuedAmount(amount) {
        return amount > 0 ? `+${amount}` : String(amount);
    }

    function buttonBaseText(step) {
        return Number(step || 0) > 0 ? "+" : "-";
    }

    function queuedButtonConfig(kind) {
        if (kind === "hp") {
            return { targetAttr: "hpTarget", stepAttr: "hpStep", selector: "data-hp-target" };
        }
        return { targetAttr: "fpTarget", stepAttr: "fpStep", selector: "data-fp-target" };
    }

    function updateQueuedButtons(kind, target, amount) {
        const configForKind = queuedButtonConfig(kind);
        document.querySelectorAll(`[${configForKind.selector}="${target}"]`).forEach((button) => {
            const step = Number(button.dataset[configForKind.stepAttr] || 0);
            const isActiveDirection = (amount > 0 && step > 0) || (amount < 0 && step < 0);
            button.textContent = isActiveDirection ? formatQueuedAmount(amount) : buttonBaseText(step);
        });
    }

    function clearQueuedDelta(queue, kind, target) {
        const queued = queue.get(target);
        if (queued && queued.timer) window.clearTimeout(queued.timer);
        queue.delete(target);
        updateQueuedButtons(kind, target, 0);
    }

    function queueDelta(queue, kind, target, step, delay, action, optimisticUpdate) {
        const queued = queue.get(target) || { amount: 0, timer: null };
        queued.amount += step;
        window.clearTimeout(queued.timer);

        if (!queued.amount) {
            clearQueuedDelta(queue, kind, target);
            return;
        }

        updateQueuedButtons(kind, target, queued.amount);
        queued.timer = window.setTimeout(() => {
            const amount = queued.amount;
            const rollbackState = cloneState();
            clearQueuedDelta(queue, kind, target);
            postAction(
                { action, target, amount },
                optimisticUpdate(target, amount),
                rollbackState,
            );
        }, delay);
        queue.set(target, queued);
    }

    document.querySelectorAll("[data-hp-target]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!state.can_control || state.is_expired) return;
            const player = state.players ? state.players[button.dataset.hpTarget] : null;
            if (!player || !player.character) return;
            const target = button.dataset.hpTarget;
            const step = Number(button.dataset.hpStep || 0);
            queueDelta(pendingHp, "hp", target, step, 900, "hp", optimisticHp);
        });
    });

    document.querySelectorAll("[data-fp-target]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!state.can_control || state.is_expired) return;
            const player = state.players ? state.players[button.dataset.fpTarget] : null;
            if (!player || !player.character) return;
            const target = button.dataset.fpTarget;
            const step = Number(button.dataset.fpStep || 0);
            queueDelta(pendingFp, "fp", target, step, 700, "fp", optimisticFp);
        });
    });

    document.querySelectorAll("[data-fp-reset]").forEach((button) => {
        button.addEventListener("click", () => {
            if (!state.can_control || state.is_expired) return;
            const player = state.players ? state.players[button.dataset.fpReset] : null;
            if (!player || !player.character) return;
            clearQueuedDelta(pendingFp, "fp", button.dataset.fpReset);
            postAction(
                { action: "fp_reset", target: button.dataset.fpReset },
                optimisticFpReset(button.dataset.fpReset),
            );
        });
    });

    document.querySelectorAll("[data-battle-action]").forEach((button) => {
        button.addEventListener("click", () => {
            const action = button.dataset.battleAction;
            if (action === "timer") postAction({ action: "timer" }, optimisticTimer());
            if (action === "undo") postAction({ action: "undo" });
            if (action === "sudden") postAction(
                { action: "sudden_death", enabled: !state.sudden_death },
                optimisticSuddenDeath(!state.sudden_death),
            );
        });
    });

    document.querySelectorAll("[data-report-set]").forEach((button) => {
        button.addEventListener("click", () => postAction({ action: "report_set" }));
    });

    document.querySelectorAll("[data-extra-time]").forEach((button) => {
        button.addEventListener("click", () => {
            postAction({ action: "extra_time", seconds: Number(button.dataset.extraTime || 0) });
        });
    });

    document.querySelectorAll("[data-history-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            setHistoryOpen(!historyOpen);
        });
    });

    document.querySelectorAll("[data-history-backdrop]").forEach((button) => {
        button.addEventListener("click", () => {
            setHistoryOpen(false);
        });
    });

    document.querySelectorAll("[data-history-target]").forEach((button) => {
        button.addEventListener("click", () => {
            historyFilter = button.dataset.historyTarget;
            if (!historyOpen) {
                setHistoryOpen(true);
                return;
            }
            fetchHistory(true);
        });
    });

    document.querySelectorAll("[data-share-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            setShareOpen(true);
        });
    });

    document.querySelectorAll("[data-share-close]").forEach((button) => {
        button.addEventListener("click", () => {
            setShareOpen(false);
        });
    });

    document.querySelectorAll("[data-copy-link]").forEach((button) => {
        button.addEventListener("click", () => {
            const value = button.dataset.copyLink;
            const markCopied = () => {
                button.classList.add("is-copied");
                window.setTimeout(() => { button.classList.remove("is-copied"); }, 1200);
            };
            if (navigator.clipboard) {
                navigator.clipboard.writeText(value).then(() => {
                    markCopied();
                    window.setTimeout(() => setShareOpen(false), 500);
                });
                return;
            }
            window.prompt("링크", value);
            markCopied();
            window.setTimeout(() => setShareOpen(false), 500);
        });
    });

    renderState();
    connectSocket();
    window.setInterval(() => {
        if (state.round_timer.remaining_seconds > 0) state.round_timer.remaining_seconds -= 1;
        const roundTimeLarge = document.querySelector("[data-battle-round-time-large]");
        if (roundTimeLarge && state.round_timer.ends_at) roundTimeLarge.textContent = formatSeconds(state.round_timer.remaining_seconds);
        setShortTimerDisplay();
    }, 1000);
})();
