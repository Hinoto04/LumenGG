(function () {
    const stateNode = document.getElementById("lumen-simulator-state");
    const i18nNode = document.getElementById("lumen-simulator-i18n");
    const root = document.querySelector("[data-lumen-simulator-mobile]");
    const config = window.lumenSimulatorMobileConfig || {};
    if (!stateNode || !root || !config.stateUrl) return;

    let envelope = JSON.parse(stateNode.textContent);
    let state = envelope.state || {};
    const i18n = i18nNode ? JSON.parse(i18nNode.textContent) : {};
    const translations = i18n.translations || {};
    const translationKeys = Object.keys(translations).sort((a, b) => b.length - a.length);
    const metadataCache = new Map();
    const pendingMetadataIds = new Set();
    let metadataTimer = null;
    let socket = null;
    let socketReady = false;
    let dirtyTimer = null;
    let pollTimer = null;
    let modalSide = "";
    let modalZone = "";
    let selectedCardId = "";
    let logOpen = false;
    let events = Array.isArray(envelope.events) ? envelope.events : [];
    let eventsLoaded = Array.isArray(envelope.events);
    let lastLogSeq = 0;
    let toastTimer = null;
    let nextRequestId = 1;
    let actionBatchTimer = null;
    let queuedActionBatch = [];
    let queuedActionRollbackEnvelope = null;
    let lastPhaseOverlayKey = `${state.turn || 1}:${state.phase || ""}`;
    let lastSignalOverlayKey = "";
    let phaseOverlayTimer = null;
    let signalOverlayTimer = null;
    let passiveHeightFrame = 0;
    let longPressTimer = null;
    let longPressCardId = "";
    let longPressStartX = 0;
    let longPressStartY = 0;
    let suppressNextCardOpen = false;
    let lastVisibilityToggleAt = 0;
    const pendingSocketActions = new Map();
    const SOCKET_ACTION_TIMEOUT_MS = 4500;
    const ACTION_BATCH_DELAY_MS = 500;
    const OPTIMISTIC_STATE_SUPPRESS_MS = 1600;
    let suppressAuthoritativeStateUntil = 0;
    let suppressNextStateDirtyCount = 0;
    const pendingCounters = {
        hp: new Map(),
        fp: new Map(),
    };
    const MOBILE_LOG_LIMIT = 80;

    const zoneCodes = {
        battle: "BT",
        ultimate: "UL",
        lumen: "LM",
        hand: "HD",
        list: "LI",
        side: "SD",
        break: "BR",
    };
    const mobileZones = ["ultimate", "lumen", "hand", "list", "side", "break"];
    const visibilityToggleZones = new Set(["hand", "side", "battle", "lumen"]);
    const moveTargets = {
        battle: ["hand", "list", "lumen", "break"],
        ultimate: ["lumen", "hand", "list", "break"],
        lumen: ["side", "list", "hand", "break"],
        hand: ["battle", "list", "lumen", "side"],
        list: ["hand", "battle", "lumen", "break"],
        side: ["lumen", "list", "hand", "break"],
        break: ["lumen", "battle", "list", "hand"],
    };

    function t(value) {
        if (value === null || value === undefined) return "";
        const raw = String(value);
        if (!raw) return raw;
        if (translations[raw]) return translations[raw];
        return translationKeys.reduce((output, key) => output.replaceAll(key, translations[key]), raw);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function canControl() {
        return !!envelope.can_control && !envelope.is_expired;
    }

    function ownSide() {
        return ["p1", "p2"].includes(envelope.role) ? envelope.role : "";
    }

    function opponentSide(side) {
        return side === "p1" ? "p2" : side === "p2" ? "p1" : "";
    }

    function playerOrder() {
        const own = ownSide();
        return own ? [own, opponentSide(own)] : ["p1", "p2"];
    }

    function playerLabel(side) {
        const base = side === "p1" ? "P1" : side === "p2" ? "P2" : t("관전");
        if (envelope.role === side) return `${base}(${t("자신")})`;
        if (["p1", "p2"].includes(envelope.role)) return `${base}(${t("상대")})`;
        return base;
    }

    function roleText() {
        if (envelope.role === "p1") return "P1";
        if (envelope.role === "p2") return "P2";
        return t("관전");
    }

    function phaseLabel(phase) {
        return (envelope.phase_labels && envelope.phase_labels[phase]) || phase || "";
    }

    function signalLabel(signal, fallback) {
        const labels = {
            effect: "효과 발동",
            combo: "콤보 타임",
            catch: "캐치 타임",
        };
        return t(fallback || labels[signal] || signal || "신호");
    }

    function zoneLabel(zone) {
        return (envelope.zone_labels && envelope.zone_labels[zone]) || zone || "";
    }

    function formatSigned(value) {
        const number = Number(value || 0);
        return number > 0 ? `+${number}` : String(number);
    }

    function cloneData(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function maxEventSeq(rows) {
        return Math.max(0, ...(rows || []).map((event) => Number(event && event.seq || 0)).filter(Number.isFinite));
    }

    function hasValue(value) {
        return value !== null && value !== undefined && String(value).trim() !== "";
    }

    function displayValue(card, field) {
        if (!card) return "";
        if (hasValue(card[`${field}_label`])) return String(card[`${field}_label`]);
        return t(card[field]);
    }

    function valueOrDashLabel(card, field) {
        return hasValue(card && card[field]) || hasValue(card && card[`${field}_label`])
            ? displayValue(card, field)
            : "-";
    }

    function cardType(card) {
        return String((card && card.type) || "");
    }

    function isAttackCard(card) {
        return cardType(card).includes("공격");
    }

    function isDefenseCard(card) {
        return cardType(card).includes("수비");
    }

    function joinPresent(values, separator) {
        return values.filter(hasValue).map((value) => String(value)).join(separator || " / ");
    }

    function effectText(card) {
        return hasValue(card && card.text) ? t(card.text) : "";
    }

    function csrfToken() {
        const input = document.querySelector("[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function cacheMetadata(cards) {
        Object.entries(cards || {}).forEach(([cardId, metadata]) => {
            if (!cardId || !metadata || typeof metadata !== "object") return;
            metadataCache.set(String(cardId), metadata);
        });
    }

    function hydrateCard(card) {
        if (!card || card.hidden || !card.card_id) return card;
        const metadata = metadataCache.get(String(card.card_id));
        return metadata ? { ...metadata, ...card } : card;
    }

    function cardName(card) {
        const hydrated = hydrateCard(card);
        if (!hydrated || hydrated.hidden) return t("비공개 카드");
        return hydrated.name || t("카드");
    }

    function cardsFor(side, zone) {
        const player = state.players && state.players[side];
        return ((player && player.zones && player.zones[zone]) || []).map((card) => ({
            ...card,
            zone,
            zone_owner: side,
        }));
    }

    function allCards() {
        const cards = [];
        Object.entries((state && state.players) || {}).forEach(([side, player]) => {
            Object.entries((player && player.zones) || {}).forEach(([zone, zoneCards]) => {
                (zoneCards || []).forEach((card) => cards.push(hydrateCard({ ...card, zone, zone_owner: side })));
            });
        });
        return cards;
    }

    function findCard(instanceId) {
        return allCards().find((card) => card.instance_id === instanceId) || null;
    }

    function findCardLocation(localState, instanceId) {
        const id = String(instanceId || "");
        for (const side of ["p1", "p2"]) {
            const player = localState.players && localState.players[side];
            const zones = (player && player.zones) || {};
            for (const [zone, zoneCards] of Object.entries(zones)) {
                const index = (zoneCards || []).findIndex((card) => String(card.instance_id || "") === id);
                if (index >= 0) {
                    return { playerSide: side, zone, index, card: zoneCards[index] };
                }
            }
        }
        return null;
    }

    function collectMetadataIds() {
        const ids = new Set();
        Object.values((state && state.players) || {}).forEach((player) => {
            Object.values((player && player.zones) || {}).forEach((cards) => {
                (cards || []).forEach((card) => {
                    if (!card || !card.card_id) return;
                    const id = String(card.card_id);
                    if (!metadataCache.has(id)) ids.add(id);
                });
            });
        });
        return ids;
    }

    function scheduleMetadataFetch(ids) {
        if (!config.metadataUrl) return;
        (ids || []).forEach((id) => pendingMetadataIds.add(String(id)));
        if (!pendingMetadataIds.size || metadataTimer) return;
        metadataTimer = window.setTimeout(fetchMetadata, 0);
    }

    function fetchMetadata() {
        metadataTimer = null;
        if (!pendingMetadataIds.size || !config.metadataUrl) return;
        const ids = Array.from(pendingMetadataIds).slice(0, 200);
        ids.forEach((id) => pendingMetadataIds.delete(id));
        const url = new URL(config.metadataUrl, window.location.origin);
        url.searchParams.set("ids", ids.join(","));
        if (config.language) url.searchParams.set("language", config.language);
        fetch(url)
            .then((response) => response.json())
            .then((data) => {
                cacheMetadata(data.cards || {});
                render();
            })
            .catch(() => ids.forEach((id) => pendingMetadataIds.add(id)))
            .finally(() => {
                if (pendingMetadataIds.size) scheduleMetadataFetch([]);
            });
    }

    function stateUrl(forceFull) {
        const url = new URL(config.stateUrl, window.location.origin);
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        if (!forceFull && envelope.version) url.searchParams.set("since_version", envelope.version);
        return url.toString();
    }

    function eventsUrl() {
        if (!config.eventsUrl) return "";
        const url = new URL(config.eventsUrl, window.location.origin);
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        url.searchParams.set("event_limit", String(MOBILE_LOG_LIMIT));
        return url.toString();
    }

    function updateEnvelope(nextEnvelope) {
        if (!nextEnvelope || nextEnvelope.unchanged) {
            if (nextEnvelope && nextEnvelope.presence) envelope.presence = nextEnvelope.presence;
            return;
        }
        envelope = nextEnvelope;
        state = envelope.state || {};
        if (Array.isArray(envelope.events)) {
            events = envelope.events;
            eventsLoaded = true;
            lastLogSeq = Math.max(lastLogSeq, maxEventSeq(events));
        }
        scheduleMetadataFetch(collectMetadataIds());
        render();
    }

    function suppressAuthoritativeStateOnce() {
        suppressAuthoritativeStateUntil = Math.max(
            suppressAuthoritativeStateUntil,
            Date.now() + OPTIMISTIC_STATE_SUPPRESS_MS,
        );
    }

    function expectOptimisticStateDirty() {
        suppressNextStateDirtyCount += 1;
        suppressAuthoritativeStateOnce();
    }

    function shouldSuppressAuthoritativeState() {
        if (suppressNextStateDirtyCount > 0) {
            suppressNextStateDirtyCount -= 1;
            return true;
        }
        return Date.now() < suppressAuthoritativeStateUntil;
    }

    function fetchState(forceFull) {
        return fetch(stateUrl(forceFull))
            .then((response) => response.json())
            .then((data) => {
                updateEnvelope(data);
                return data;
            })
            .catch(() => null);
    }

    function startPollingFallback() {
        if (pollTimer) return;
        pollTimer = window.setInterval(() => fetchState(), 5000);
    }

    function stopPollingFallback() {
        if (!pollTimer) return;
        window.clearInterval(pollTimer);
        pollTimer = null;
    }

    function fetchEvents() {
        const url = eventsUrl();
        if (!url) return Promise.resolve(null);
        return fetch(url)
            .then((response) => response.json())
            .then((data) => {
                applyLogEvents(data, true);
                return data;
            })
            .catch(() => null);
    }

    function applyLogEvents(data, forceReset) {
        const incoming = Array.isArray(data && data.events) ? data.events : [];
        const reset = forceReset || !!(data && data.reset);
        if (reset) {
            events = incoming;
        } else if (incoming.length) {
            const seenIds = new Set(events.map((event) => event && event.id).filter(Boolean));
            const seenSeqs = new Set(events.map((event) => Number(event && event.seq || 0)).filter((seq) => seq > 0));
            events = events.filter((event) => !(event && event.optimistic));
            incoming.forEach((event) => {
                const seq = Number(event && event.seq || 0);
                if (event && event.id && seenIds.has(event.id)) return;
                if (seq && seenSeqs.has(seq)) return;
                events.push(event);
                if (event && event.id) seenIds.add(event.id);
                if (seq) seenSeqs.add(seq);
            });
            if (events.length > MOBILE_LOG_LIMIT) {
                events.splice(0, events.length - MOBILE_LOG_LIMIT);
            }
        }
        eventsLoaded = true;
        envelope.events = events;
        envelope.event_count = Number(data && data.event_count || envelope.event_count || events.length || 0);
        lastLogSeq = Math.max(lastLogSeq, maxEventSeq(events), Number(envelope.event_count || 0));
        renderLog();
    }

    function sendLogSubscription(enabled) {
        if (!socketReady || !socket || socket.readyState !== WebSocket.OPEN) return false;
        socket.send(JSON.stringify({
            type: enabled ? "log_subscribe" : "log_unsubscribe",
            since_seq: lastLogSeq,
        }));
        return true;
    }

    function buildActionBody(action, payload) {
        return {
            action,
            seat: config.seat || "",
            seat_token: config.seatToken || "",
            payload: payload || {},
        };
    }

    function showToast(message) {
        let toast = document.querySelector("[data-mobile-toast]");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "v2-mobile-toast";
            toast.dataset.mobileToast = "true";
            document.body.appendChild(toast);
        }
        toast.textContent = message || t("네트워크 오류가 발생했습니다.");
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => toast.remove(), 2200);
    }

    function canSendSocketAction() {
        return !!(socketReady && socket && "WebSocket" in window && socket.readyState === WebSocket.OPEN);
    }

    function postSocketAction(action, payload) {
        if (!canSendSocketAction()) {
            return Promise.reject(new Error(t("실시간 연결이 복구되는 중입니다.")));
        }
        const requestId = String(nextRequestId++);
        return new Promise((resolve, reject) => {
            const timeout = window.setTimeout(() => {
                pendingSocketActions.delete(requestId);
                reject(new Error(t("요청 응답 시간이 초과되었습니다.")));
            }, SOCKET_ACTION_TIMEOUT_MS);
            pendingSocketActions.set(requestId, { resolve, reject, timeout });
            socket.send(JSON.stringify({
                type: "action",
                request_id: requestId,
                payload: buildActionBody(action, payload),
            }));
        });
    }

    function requestSocketState() {
        if (!socketReady || !socket || socket.readyState !== WebSocket.OPEN) return false;
        socket.send(JSON.stringify({ type: "state" }));
        return true;
    }

    function postHttpAction(action, payload, options) {
        const applyState = !(options && options.applyState === false);
        return fetch(config.actionUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            body: JSON.stringify(buildActionBody(action, payload)),
        })
            .then((response) => response.json().then((data) => ({ response, data })))
            .then(({ response, data }) => {
                if (!response.ok || data.ok === false) {
                    const error = new Error(data.error || t("요청을 처리하지 못했습니다."));
                    error.serverRejected = true;
                    throw error;
                }
                if (applyState && data.state) updateEnvelope(data.state);
                return data;
            });
    }

    function isBatchableAction(action) {
        return [
            "move_card",
            "set_done",
            "hp",
            "fp",
            "fp_reset",
            "passive",
            "set_visibility",
            "log_note",
        ].includes(action);
    }

    function shouldSuppressSuccessfulStateForAction(action) {
        return [
            "move_card",
            "hp",
            "fp",
            "fp_reset",
            "passive",
            "set_visibility",
            "log_note",
        ].includes(action);
    }

    function flushActionBatch() {
        if (!queuedActionBatch.length) return Promise.resolve(null);
        if (!canSendSocketAction()) {
            if (actionBatchTimer) {
                window.clearTimeout(actionBatchTimer);
                actionBatchTimer = null;
            }
            const batch = queuedActionBatch;
            const rollbackEnvelope = queuedActionRollbackEnvelope;
            queuedActionBatch = [];
            queuedActionRollbackEnvelope = null;
            return batch.reduce((chain, item) => (
                chain.then(() => postHttpAction(item.action, item.payload, { applyState: false }))
                    .then((result) => item.resolve(result))
            ), Promise.resolve(null)).catch((error) => {
                if (error && error.serverRejected && rollbackEnvelope) {
                    updateEnvelope(rollbackEnvelope);
                }
                batch.forEach((item) => item.resolve(null));
                showToast(error.message || t("네트워크 오류가 발생했습니다."));
                return null;
            });
        }
        if (actionBatchTimer) {
            window.clearTimeout(actionBatchTimer);
            actionBatchTimer = null;
        }
        const batch = queuedActionBatch;
        const rollbackEnvelope = queuedActionRollbackEnvelope;
        queuedActionBatch = [];
        queuedActionRollbackEnvelope = null;
        const suppressSuccessfulState = batch.every((item) => shouldSuppressSuccessfulStateForAction(item.action));
        if (rollbackEnvelope && suppressSuccessfulState) expectOptimisticStateDirty();
        return postSocketAction("batch", {
            actions: batch.map((item) => ({
                action: item.action,
                payload: item.payload,
            })),
        })
            .then((result) => {
                batch.forEach((item) => item.resolve(result));
                return result;
            })
            .catch((error) => {
                if (error && error.serverRejected && rollbackEnvelope) {
                    if (suppressSuccessfulState) {
                        suppressNextStateDirtyCount = Math.max(0, suppressNextStateDirtyCount - 1);
                    }
                    updateEnvelope(rollbackEnvelope);
                }
                showToast(error.message || t("네트워크 오류가 발생했습니다."));
                batch.forEach((item) => item.resolve(null));
                return null;
            });
    }

    function queueBatchAction(action, payload, rollbackEnvelope) {
        if (!queuedActionRollbackEnvelope && rollbackEnvelope) {
            queuedActionRollbackEnvelope = rollbackEnvelope;
        }
        const promise = new Promise((resolve) => {
            queuedActionBatch.push({ action, payload, resolve });
        });
        if (actionBatchTimer) window.clearTimeout(actionBatchTimer);
        actionBatchTimer = window.setTimeout(flushActionBatch, ACTION_BATCH_DELAY_MS);
        return promise;
    }

    function appendOptimisticEvent(action, payload) {
        if (!logOpen) return;
        events.push({
            id: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            type: action,
            actor: envelope.role,
            payload: cloneData(payload || {}),
            optimistic: true,
        });
        if (events.length > MOBILE_LOG_LIMIT) events.splice(0, events.length - MOBILE_LOG_LIMIT);
        eventsLoaded = true;
        envelope.events = events;
    }

    function recordLocalTurnChange(target, kind, amount) {
        state.turn_changes = state.turn_changes || {};
        state.turn_changes[target] = state.turn_changes[target] || {};
        state.turn_changes[target][kind] = Number(state.turn_changes[target][kind] || 0) + Number(amount || 0);
        state.turn_changes[target][`${kind}_changed`] = true;
    }

    function advanceLocalCounterRevision(target, kind) {
        state.counter_revisions = state.counter_revisions || {};
        state.counter_revisions[target] = state.counter_revisions[target] || {};
        state.counter_revisions[target][kind] = Number(state.counter_revisions[target][kind] || 0) + 1;
    }

    function applyOptimisticAction(action, payload) {
        if (!state || !state.players || !["p1", "p2"].includes(envelope.role)) return false;
        const localPayload = payload || {};

        if (action === "move_card") {
            const location = findCardLocation(state, localPayload.card_instance_id);
            if (!location || !location.card || location.card.kind === "character") return false;
            const toZone = String(localPayload.to_zone || "");
            const owner = location.card.owner || location.playerSide;
            const toPlayer = localPayload.to_player || owner;
            if (!state.players[toPlayer] || !state.players[toPlayer].zones || !state.players[toPlayer].zones[toZone]) return false;
            if (toPlayer !== owner && !["battle", "lumen"].includes(toZone)) return false;
            state.players[location.playerSide].zones[location.zone].splice(location.index, 1);
            location.card.zone = toZone;
            location.card.zone_owner = toPlayer;
            state.players[toPlayer].zones[toZone].push(location.card);
            localPayload.from_player = location.playerSide;
            localPayload.from_zone = location.zone;
            localPayload.to_player = toPlayer;
            localPayload.card_label = cardName({ ...location.card, hidden: false });
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_done") {
            const target = localPayload.target || envelope.role;
            if (!state.status || !state.status[target]) return false;
            localPayload.target = target;
            state.status[target].done = !!localPayload.done;
            if (state.status[target].done) {
                state.status[target].requested = false;
                const opponent = opponentSide(target);
                if (state.status[opponent] && !state.status[opponent].done) {
                    state.status[opponent].requested = true;
                    localPayload.requested_opponent = opponent;
                }
            }
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "hp" || action === "fp") {
            const target = localPayload.target;
            const player = state.players[target];
            const amount = Number(localPayload.amount || 0);
            if (!player || !amount) return false;
            advanceLocalCounterRevision(target, action);
            const before = Number(player[action] || 0);
            player[action] = before + amount;
            recordLocalTurnChange(target, action, amount);
            localPayload.before = before;
            localPayload.after = player[action];
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "fp_reset") {
            const target = localPayload.target;
            const player = state.players[target];
            if (!player) return false;
            advanceLocalCounterRevision(target, "fp");
            const before = Number(player.fp || 0);
            player.fp = 0;
            recordLocalTurnChange(target, "fp", -before);
            localPayload.before = before;
            localPayload.after = 0;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "passive") {
            const target = localPayload.target;
            const player = state.players[target];
            if (!player) return false;
            const key = String(localPayload.key || "memo").slice(0, 80);
            const passiveState = player.passive_state || {};
            const current = { ...(passiveState[key] || {}) };
            const delta = Number(localPayload.delta || 0);
            if (delta) current.count = Math.max(0, Number(current.count || 0) + delta);
            if ("value" in localPayload) current.value = localPayload.value;
            if (localPayload.note) current.last_note = String(localPayload.note).slice(0, 200);
            if (localPayload.label) current.label = String(localPayload.label).slice(0, 80);
            passiveState[key] = current;
            player.passive_state = passiveState;
            localPayload.key = key;
            localPayload.state = current;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_visibility") {
            const location = findCardLocation(state, localPayload.card_instance_id);
            if (!location || !location.card || location.card.owner !== envelope.role) return false;
            if (!visibilityToggleZones.has(location.zone)) return false;
            localPayload.was_face_up = !!location.card.face_up;
            localPayload.card_id = location.card.card_id;
            localPayload.card_label = cardName({ ...location.card, hidden: false });
            location.card.face_up = !!localPayload.face_up;
            location.card.hidden = false;
            localPayload.owner = location.card.owner;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "log_note") {
            const text = String(localPayload.text || "").trim();
            if (!text) return false;
            localPayload.text = text.slice(0, 300);
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        return false;
    }

    function postAction(action, payload) {
        if (!canControl()) return Promise.resolve(null);
        const actionPayload = cloneData(payload || {});
        const rollbackEnvelope = cloneData(envelope);
        const optimisticApplied = applyOptimisticAction(action, actionPayload);
        const suppressSuccessfulState = optimisticApplied && shouldSuppressSuccessfulStateForAction(action);
        if (optimisticApplied) {
            if (suppressSuccessfulState) suppressAuthoritativeStateOnce();
            render();
        }
        if (optimisticApplied && isBatchableAction(action)) {
            return queueBatchAction(action, actionPayload, rollbackEnvelope);
        }
        const request = canSendSocketAction()
            ? flushActionBatch().then(() => {
                if (suppressSuccessfulState) expectOptimisticStateDirty();
                return postSocketAction(action, actionPayload);
            })
            : postHttpAction(action, actionPayload, { applyState: !suppressSuccessfulState });
        return request
            .catch((error) => {
                if (optimisticApplied && error && error.serverRejected) {
                    if (suppressSuccessfulState) {
                        suppressNextStateDirtyCount = Math.max(0, suppressNextStateDirtyCount - 1);
                    }
                    updateEnvelope(rollbackEnvelope);
                }
                showToast(error.message || t("네트워크 오류가 발생했습니다."));
                return null;
            });
    }

    function passiveOptions(passiveUi) {
        const options = passiveUi && passiveUi.options;
        return options && typeof options === "object" && !Array.isArray(options) ? options : {};
    }

    function hasPassiveControls(options) {
        return ["controls", "badges", "latchedStatuses"].some((key) => Array.isArray(options[key]) && options[key].length);
    }

    function passiveEntryValue(passiveState, key, fallback) {
        const entry = passiveState[String(key)] || {};
        if (entry.value !== undefined) return entry.value;
        if (entry.count !== undefined) return entry.count;
        return fallback;
    }

    function passiveNumber(value, fallback) {
        const number = Number(value);
        return Number.isFinite(number) ? number : (fallback || 0);
    }

    function passiveBool(value) {
        return value === true || value === "true" || value === "on" || value === "ON";
    }

    function passiveConditionValue(passiveState, key, overrideKey, overrideValue) {
        return key === overrideKey ? overrideValue : passiveEntryValue(passiveState, key, 0);
    }

    function passiveConditionMet(condition, player, passiveState, overrideKey, overrideValue) {
        if (!condition || typeof condition !== "object") return false;
        if (condition.type === "hpAtMost") {
            return passiveNumber(player.hp) <= passiveNumber(condition.value);
        }
        if (condition.type === "allEquals") {
            return (condition.keys || []).every((key) => passiveNumber(passiveConditionValue(passiveState, key, overrideKey, overrideValue)) === passiveNumber(condition.value));
        }
        if (condition.type === "allAtLeast") {
            return (condition.keys || []).every((key) => passiveNumber(passiveConditionValue(passiveState, key, overrideKey, overrideValue)) >= passiveNumber(condition.value));
        }
        if (condition.type === "counterAtLeast") {
            return passiveNumber(passiveConditionValue(passiveState, condition.key, overrideKey, overrideValue)) >= passiveNumber(condition.value);
        }
        return false;
    }

    function passiveLatchedUpdates(side, changedKey, changedValue) {
        const player = (state.players && state.players[side]) || {};
        const character = player.character || {};
        const options = passiveOptions(character.passive_ui || {});
        const passiveState = player.passive_state || {};
        const updates = [];
        (options.latchedStatuses || []).forEach((status) => {
            if (!status || !status.key || status.key === changedKey) return;
            const stored = passiveBool(passiveEntryValue(passiveState, status.key, false));
            const shouldActivate = passiveConditionMet(status.activateWhen, player, passiveState, changedKey, changedValue);
            const shouldKeep = passiveConditionMet(status.keepWhile || status.activateWhen, player, passiveState, changedKey, changedValue);
            if (shouldActivate && !stored) {
                updates.push({ key: status.key, value: true, label: status.label || status.key });
            } else if (stored && !shouldKeep) {
                updates.push({ key: status.key, value: false, label: status.label || status.key });
            }
        });
        return updates;
    }

    function counterRevision(kind, side) {
        return Number((((state.counter_revisions || {})[side] || {})[kind]) || 0);
    }

    function counterDelta(side, kind) {
        const entry = ((state.turn_changes || {})[side] || {});
        const amount = Number(entry[kind] || 0);
        const touched = !!entry[`${kind}_changed`] || !!amount;
        return touched ? `<span class="v2-mobile-turn-delta">${formatSigned(amount)}</span>` : "";
    }

    function counterPending(side, kind) {
        const queued = pendingCounters[kind].get(side);
        const amount = Number(queued && queued.amount || 0);
        return amount ? `<span class="v2-mobile-pending-delta">${formatSigned(amount)}</span>` : "";
    }

    function clearQueuedCounter(kind, side) {
        const queued = pendingCounters[kind].get(side);
        if (queued && queued.timer) window.clearTimeout(queued.timer);
        pendingCounters[kind].delete(side);
        render();
    }

    function queueCounter(kind, side, amount) {
        if (!canControl()) return;
        const queue = pendingCounters[kind];
        const queued = queue.get(side) || { amount: 0, timer: null, baseRevision: counterRevision(kind, side) };
        queued.amount += Number(amount || 0);
        window.clearTimeout(queued.timer);
        if (!queued.amount) {
            clearQueuedCounter(kind, side);
            return;
        }
        queued.timer = window.setTimeout(() => {
            const finalAmount = queued.amount;
            const baseRevision = queued.baseRevision;
            clearQueuedCounter(kind, side);
            postAction(kind, { target: side, amount: finalAmount, base_revision: baseRevision });
        }, 500);
        queue.set(side, queued);
        render();
    }

    function counterButton(side, kind, amount, label) {
        return `<button class="v2-mobile-counter" type="button" data-mobile-counter-kind="${kind}" data-mobile-counter-side="${side}" data-mobile-counter-amount="${amount}">${escapeHtml(label)}</button>`;
    }

    function renderCounterPanel(side, kind, value) {
        if (kind === "hp") {
            return `
                <div class="v2-mobile-hp">
                    ${counterButton(side, "hp", -100, "-")}
                    <div class="v2-mobile-counter-value">${escapeHtml(Number(value || 0))}${counterDelta(side, "hp")}${counterPending(side, "hp")}</div>
                    ${counterButton(side, "hp", 100, "+")}
                </div>
            `;
        }
        return `
            <div class="v2-mobile-fp">
                ${counterButton(side, "fp", 1, "+")}
                <button class="v2-mobile-counter-value" type="button" data-mobile-fp-reset="${side}">${escapeHtml(formatSigned(value || 0))} FP${counterDelta(side, "fp")}${counterPending(side, "fp")}</button>
                ${counterButton(side, "fp", -1, "-")}
            </div>
        `;
    }

    function canToggleCardVisibility(card) {
        return !!(
            card &&
            visibilityToggleZones.has(card.zone) &&
            canControl() &&
            envelope.role === card.owner &&
            card.kind !== "character" &&
            !card.hidden
        );
    }

    function visibilityToggleMarkup(card) {
        if (!canToggleCardVisibility(card)) return "";
        const faceUp = !!card.face_up;
        return `<button class="v2-mobile-card-toggle ${faceUp ? "is-public" : "is-private"}" type="button" data-mobile-visibility-card="${escapeHtml(card.instance_id)}" data-mobile-visibility-value="${faceUp ? "false" : "true"}" aria-label="${faceUp ? t("비공개로 전환") : t("공개로 전환")}"></button>`;
    }

    function toggleCardVisibility(card, faceUp) {
        const target = typeof card === "string" ? findCard(card) : card;
        if (!canToggleCardVisibility(target)) return false;
        lastVisibilityToggleAt = Date.now();
        postAction("set_visibility", {
            card_instance_id: target.instance_id,
            face_up: typeof faceUp === "boolean" ? faceUp : !target.face_up,
        });
        return true;
    }

    function renderMiniCard(card) {
        const hydrated = hydrateCard(card);
        const image = !hydrated.hidden && (hydrated.img_sm || hydrated.img)
            ? `<img src="${escapeHtml(hydrated.img_sm || hydrated.img)}" alt="">`
            : `<span>${escapeHtml(hydrated.hidden ? "PRIVATE" : cardName(hydrated))}</span>`;
        return `<div class="v2-mobile-mini-card ${hydrated.hidden ? "is-hidden" : ""}" role="button" tabindex="0" data-mobile-open-zone="${card.zone}" data-mobile-zone-side="${card.zone_owner}" data-mobile-card-instance="${escapeHtml(hydrated.instance_id)}">${image}${visibilityToggleMarkup(hydrated)}</div>`;
    }

    function passiveSummary(player) {
        const entries = Object.entries(player.passive_state || {});
        const chips = [];
        entries.forEach(([key, entry]) => {
            const value = entry.value !== undefined ? entry.value : entry.count ?? "";
            chips.push(`<span class="v2-mobile-passive-chip">${escapeHtml(entry.label || key)} ${escapeHtml(value)}</span>`);
        });
        const passiveCards = (((player.zones || {}).passive) || []).filter((card) => !card.hidden);
        if (!chips.length && passiveCards.length) {
            passiveCards.forEach((card) => chips.push(`<span class="v2-mobile-passive-chip">${escapeHtml(cardName(card))}</span>`));
        }
        if (!chips.length) chips.push(`<span class="v2-mobile-passive-chip">${t("패시브")}</span>`);
        return `<div class="v2-mobile-passive-inner">${chips.join("")}</div>`;
    }

    function renderPassiveCard(card) {
        const hydrated = hydrateCard(card);
        const image = hydrated.img_sm || hydrated.img;
        return `
            <button class="v2-mobile-passive-card" type="button" data-mobile-card-open="${escapeHtml(hydrated.instance_id)}">
                ${image ? `<img src="${escapeHtml(image)}" alt="">` : `<span>${escapeHtml(cardName(hydrated))}</span>`}
            </button>
        `;
    }

    function passiveSetButton(side, key, value, label, text, extraClass, resetKeys) {
        const encodedValue = JSON.stringify(value);
        const encodedResetKeys = resetKeys && resetKeys.length ? JSON.stringify(resetKeys) : "";
        return `
            <button class="v2-mobile-passive-button ${extraClass || ""}" type="button"
                data-mobile-passive-target="${escapeHtml(side)}"
                data-mobile-passive-key="${escapeHtml(key)}"
                data-mobile-passive-value="${escapeHtml(encodedValue)}"
                data-mobile-passive-label="${escapeHtml(label || key)}"
                ${encodedResetKeys ? `data-mobile-passive-reset-keys="${escapeHtml(encodedResetKeys)}"` : ""}>
                ${escapeHtml(text)}
            </button>
        `;
    }

    function renderNativePassiveControls(side, holder, options, passiveState, player) {
        const parts = [];
        const renderedStatusKeys = new Set();
        (options.controls || []).forEach((control) => {
            if (!control || !control.key) return;
            const label = control.label || control.key;
            if (control.type === "counter") {
                const current = Math.max(0, passiveNumber(passiveEntryValue(passiveState, control.key, 0)));
                const max = control.max === undefined || control.max === null ? null : passiveNumber(control.max);
                const minus = Math.max(0, current - 1);
                const plus = max === null ? current + 1 : Math.min(max, current + 1);
                parts.push(`
                    <div class="v2-mobile-passive-native is-counter">
                        <span>${escapeHtml(label)}</span>
                        ${passiveSetButton(side, control.key, minus, label, "-", current <= 0 ? "is-disabled" : "")}
                        ${passiveSetButton(side, control.key, 0, control.resetLabel || label, max === null ? `${current}${control.unit || ""}` : `${current}/${max}${control.unit || ""}`, current <= 0 ? "is-value is-disabled" : "is-value")}
                        ${passiveSetButton(side, control.key, plus, label, "+", max !== null && current >= max ? "is-disabled" : "")}
                    </div>
                `);
            } else if (control.type === "toggle") {
                const active = passiveBool(passiveEntryValue(passiveState, control.key, false));
                parts.push(`
                    <div class="v2-mobile-passive-native is-toggle ${active ? "is-active" : ""}">
                        <span>${escapeHtml(label)}</span>
                        ${passiveSetButton(side, control.key, !active, label, active ? "ON" : "OFF", active ? "is-active" : "")}
                    </div>
                `);
            } else if (control.type === "choice") {
                const current = passiveEntryValue(passiveState, control.key, control.default || "");
                const choices = (control.choices || []).map((choice) => {
                    const value = typeof choice === "string" ? choice : choice.value;
                    const choiceLabel = typeof choice === "string" ? choice : choice.label;
                    return passiveSetButton(side, control.key, value, label, choiceLabel || value, current === value ? "is-active" : "");
                }).join("");
                parts.push(`
                    <div class="v2-mobile-passive-native is-choice">
                        <span>${escapeHtml(label)}</span>
                        <div>${choices}</div>
                    </div>
                `);
            } else if (control.type === "status" || control.type === "latchedStatus") {
                const stored = passiveBool(passiveEntryValue(passiveState, control.key, false));
                const met = passiveConditionMet(control.condition || control.activateWhen, player, passiveState);
                const keep = passiveConditionMet(control.keepWhile || control.activateWhen || control.condition, player, passiveState);
                const active = control.type === "latchedStatus" ? (met || (stored && keep)) : met;
                parts.push(`
                    <div class="v2-mobile-passive-native is-status ${active ? "is-active" : ""}">
                        <span>${escapeHtml(label)}</span>
                        <strong>${escapeHtml(active ? (control.activeText || t("활성")) : (control.inactiveText || t("대기")))}</strong>
                    </div>
                `);
                renderedStatusKeys.add(control.key);
            } else if (control.type === "thresholdAction") {
                const active = passiveBool(passiveEntryValue(passiveState, control.key, false));
                const ready = passiveConditionMet(control.requires, player, passiveState);
                const text = active ? "ON" : (ready ? (control.actionText || t("발동")) : t("대기"));
                parts.push(`
                    <div class="v2-mobile-passive-native is-threshold ${active ? "is-active" : ""}">
                        <span>${escapeHtml(label)}</span>
                        ${passiveSetButton(side, control.key, active ? false : true, label, text, active ? "is-active" : (!ready ? "is-disabled" : ""), active ? [] : (control.resetKeys || []))}
                    </div>
                `);
            }
        });
        [...(options.badges || []), ...(options.latchedStatuses || [])].forEach((badge) => {
            if (badge.key && renderedStatusKeys.has(badge.key)) return;
            const label = badge.label || badge.key || t("패시브");
            const stored = passiveBool(passiveEntryValue(passiveState, badge.key, false));
            const met = passiveConditionMet(badge.condition || badge.activateWhen, player, passiveState);
            const keep = passiveConditionMet(badge.keepWhile || badge.activateWhen || badge.condition, player, passiveState);
            const active = badge.type === "latchedStatus" ? (met || (stored && keep)) : met;
            parts.push(`
                <div class="v2-mobile-passive-native is-status ${active ? "is-active" : ""}">
                    <span>${escapeHtml(label)}</span>
                    <strong>${escapeHtml(active ? (badge.activeText || t("활성")) : (badge.inactiveText || t("대기")))}</strong>
                </div>
            `);
        });
        holder.innerHTML = parts.join("");
        holder.querySelectorAll(".is-disabled").forEach((button) => {
            button.disabled = true;
        });
        holder.querySelectorAll("[data-mobile-passive-target]").forEach((button) => {
            if (!canControl()) button.disabled = true;
        });
    }

    function makePassiveApi(side, passiveRoot, options) {
        const player = state.players[side] || {};
        const passiveState = player.passive_state || {};
        return {
            target: side,
            root: passiveRoot,
            options: options || {},
            state,
            player,
            passiveState,
            canControl: canControl(),
            action(payload) {
                return postAction("passive", { target: side, ...(payload || {}) });
            },
            simulatorAction(action, payload) {
                return postAction(action, { target: side, ...(payload || {}) });
            },
            increment(key, delta, label) {
                return postAction("passive", { target: side, key, delta: Number(delta || 1), label: label || key });
            },
            set(key, value, label) {
                return postAction("passive", { target: side, key, value, label: label || key });
            },
            note(key, note, label) {
                return postAction("passive", { target: side, key: key || "memo", note, label: label || key || "메모" });
            },
            get(key, fallback) {
                return passiveEntryValue(passiveState, key, fallback);
            },
        };
    }

    function renderCustomPassiveUi(side, holder, passiveUi) {
        const passiveRoot = document.createElement("div");
        const rootId = `v2-mobile-passive-${envelope.id}-${side}-${((state.players[side] || {}).character || {}).id || "none"}`;
        passiveRoot.id = rootId;
        passiveRoot.className = "v2-mobile-passive-custom v2-sim-passive-custom";
        passiveRoot.innerHTML = passiveUi.html || "";
        if (passiveUi.css) {
            const style = document.createElement("style");
            style.textContent = String(passiveUi.css).replaceAll(":host", `#${rootId}`);
            holder.appendChild(style);
        }
        const compactStyle = document.createElement("style");
        compactStyle.textContent = `
            #${rootId} .character-passive-row.is-counter > span,
            #${rootId} .tao-counter-card > span,
            #${rootId} .cmyk-passive-panel .character-passive-row > span {
                display: none;
            }
            #${rootId} .character-passive-row,
            #${rootId} .character-passive-row.is-counter,
            #${rootId} .character-passive-row.is-wide {
                grid-template-columns: minmax(0, 1fr);
                gap: 2px;
                padding: 2px 3px;
            }
            #${rootId} .yohan-passive-top,
            #${rootId} .character-passive-buttons,
            #${rootId} .yohan-passive-panel .character-passive-buttons,
            #${rootId} .tao-counter-grid,
            #${rootId} .tao-harmony-row {
                grid-template-columns: minmax(0, 1fr);
            }
            #${rootId} .character-passive-row > span,
            #${rootId} .yohan-passive-panel .character-passive-row > span {
                display: none;
            }
            #${rootId} .yohan-passive-panel .character-passive-buttons {
                grid-template-columns: repeat(2, 24px);
                grid-auto-rows: 20px;
                justify-content: center;
            }
            #${rootId} .yohan-passive-panel .character-passive-buttons button {
                width: 24px;
                min-height: 20px;
                padding: 0;
                overflow: hidden;
                font-size: 0;
            }
            #${rootId} .yohan-passive-panel .character-passive-buttons button::first-letter {
                font-size: .68rem;
            }
            #${rootId} .character-passive-counter-actions,
            #${rootId} .yohan-passive-panel .character-passive-counter-actions {
                grid-template-columns: 20px 40px 20px;
                gap: 1px;
            }
            #${rootId} .character-passive-counter-actions > strong,
            #${rootId} .yohan-passive-panel .character-passive-counter-actions > strong,
            #${rootId} button {
                min-height: 20px;
                padding: 1px 5px;
            }
            #${rootId} .tao-counter-card {
                grid-template-columns: 20px 34px 20px;
                gap: 1px;
                padding: 2px 3px;
            }
            #${rootId} .tao-counter-card > strong {
                grid-column: 2;
            }
            #${rootId} .tao-counter-actions [data-tao-delta="-1"] {
                grid-column: 1;
            }
            #${rootId} .tao-counter-actions [data-tao-delta="1"] {
                grid-column: 3;
            }
        `;
        holder.appendChild(compactStyle);
        holder.appendChild(passiveRoot);
        if (passiveUi.js) {
            try {
                const api = makePassiveApi(side, passiveRoot, passiveUi.options || {});
                const run = new Function("api", `"use strict";\n${passiveUi.js}`);
                run(api);
            } catch (error) {
                const message = document.createElement("span");
                message.className = "v2-mobile-passive-error";
                message.textContent = t("패시브 UI 오류");
                holder.appendChild(message);
                console.error(error);
            }
        }
        passiveRoot.querySelectorAll("button, input, select, textarea").forEach((node) => {
            if ("disabled" in node && !canControl()) node.disabled = true;
        });
    }

    function renderPassive(side) {
        const holder = document.querySelector(`[data-mobile-passive-panel="${side}"]`);
        const player = state.players && state.players[side];
        if (!holder || !player) return;
        const position = playerOrder()[0] === side ? "left" : "right";
        holder.replaceChildren();
        holder.className = `v2-mobile-passive is-${position}`;
        const passiveState = player.passive_state || {};
        const passiveCards = ((player.zones && player.zones.passive) || []).filter((card) => !card.hidden);
        const passiveUi = ((player.character || {}).passive_ui) || {};
        const options = passiveOptions(passiveUi);
        const controlsNode = document.createElement("div");
        controlsNode.className = "v2-mobile-passive-controls";
        if (hasPassiveControls(options)) {
            renderNativePassiveControls(side, controlsNode, options, passiveState, player);
        } else if (passiveUi.html || passiveUi.css || passiveUi.js) {
            controlsNode.classList.add("has-custom-passive");
            renderCustomPassiveUi(side, controlsNode, passiveUi);
        } else {
            controlsNode.innerHTML = passiveSummary(player);
        }
        const hasControls = !!controlsNode.children.length;
        if (passiveCards.length) {
            const cardsNode = document.createElement("div");
            cardsNode.className = "v2-mobile-passive-cards";
            cardsNode.innerHTML = passiveCards.map(renderPassiveCard).join("");
            if (position === "right") holder.appendChild(cardsNode);
            if (hasControls) holder.appendChild(controlsNode);
            if (position === "left") holder.appendChild(cardsNode);
        } else if (hasControls) {
            holder.appendChild(controlsNode);
        }
    }

    function syncPassivePanelHeights() {
        passiveHeightFrame = 0;
        const panels = Array.from(document.querySelectorAll("[data-mobile-passive-panel]"));
        if (panels.length < 2) return;
        panels.forEach((panel) => {
            panel.style.minHeight = "";
        });
        const maxHeight = Math.ceil(Math.max(...panels.map((panel) => panel.getBoundingClientRect().height)));
        if (!Number.isFinite(maxHeight) || maxHeight <= 0) return;
        panels.forEach((panel) => {
            panel.style.minHeight = `${maxHeight}px`;
        });
    }

    function schedulePassiveHeightSync() {
        if (passiveHeightFrame) return;
        passiveHeightFrame = window.requestAnimationFrame(syncPassivePanelHeights);
    }

    function renderPlayer(side) {
        const player = state.players && state.players[side];
        if (!player) return "";
        const position = playerOrder()[0] === side ? "left" : "right";
        const status = (state.status && state.status[side]) || {};
        const statusClass = status.done
            ? " is-action-done"
            : status.requested
                ? " is-action-requested"
                : "";
        const battleCards = cardsFor(side, "battle");
        const battleHtml = battleCards.length
            ? renderMiniCard(battleCards[0])
            : `<button class="v2-mobile-battle-open" type="button" data-mobile-open-zone="battle" data-mobile-zone-side="${side}">BT</button>`;
        const zoneButtons = mobileZones.map((zone) => {
            const count = cardsFor(side, zone).length;
            return `<button class="v2-mobile-zone-button" type="button" data-mobile-open-zone="${zone}" data-mobile-zone-side="${side}">${zoneCodes[zone]} <span>${count}</span></button>`;
        }).join("");
        return `
            <section class="v2-mobile-player is-${position}${statusClass}" data-mobile-player="${side}">
                <div class="v2-mobile-player-name">${escapeHtml(playerLabel(side))} ${escapeHtml(player.name || "")}</div>
                ${renderCounterPanel(side, "hp", player.hp)}
                <div class="v2-mobile-combat-line is-${position}">
                    ${position === "left" ? renderCounterPanel(side, "fp", player.fp) : ""}
                    <div class="v2-mobile-battle">
                        <div class="v2-mobile-battle-cards">${battleHtml}</div>
                    </div>
                    ${position === "right" ? renderCounterPanel(side, "fp", player.fp) : ""}
                </div>
                <div class="v2-mobile-passive" data-mobile-passive-panel="${side}"></div>
                <div class="v2-mobile-zone-buttons">${zoneButtons}</div>
            </section>
        `;
    }

    function targetPlayerForMove(sourceSide, card, toZone) {
        const owner = ["p1", "p2"].includes(card.owner) ? card.owner : sourceSide;
        return ["battle", "lumen"].includes(toZone) ? sourceSide : owner;
    }

    function renderModalCard(card) {
        const hydrated = hydrateCard(card);
        const image = !hydrated.hidden && (hydrated.img || hydrated.img_sm)
            ? `<img src="${escapeHtml(hydrated.img || hydrated.img_sm)}" alt="">`
            : `<span>${escapeHtml(hydrated.hidden ? t("비공개 카드") : cardName(hydrated))}</span>`;
        const moves = canControl() && card.kind !== "character"
            ? (moveTargets[card.zone] || []).slice(0, 4).map((toZone) => {
                const toPlayer = targetPlayerForMove(card.zone_owner, card, toZone);
                return `<button type="button" data-mobile-move-card="${escapeHtml(card.instance_id)}" data-mobile-to-player="${toPlayer}" data-mobile-to-zone="${toZone}">${zoneCodes[toZone]}</button>`;
            }).join("")
            : "";
        const visibility = visibilityToggleMarkup(hydrated);
        return `
            <article class="v2-mobile-modal-card ${hydrated.hidden ? "is-hidden" : ""}" data-mobile-card-open="${escapeHtml(hydrated.instance_id)}" data-mobile-card-instance="${escapeHtml(hydrated.instance_id)}">
                <div class="v2-mobile-card-face">${image}</div>
                ${visibility}
                <div class="v2-mobile-card-name">${escapeHtml(cardName(hydrated))}</div>
                ${moves ? `<div class="v2-mobile-card-moves">${moves}</div>` : ""}
            </article>
        `;
    }

    function renderModal() {
        const modal = document.querySelector("[data-mobile-zone-modal]");
        if (!modal || !modalSide || !modalZone) return;
        const playerNode = modal.querySelector("[data-mobile-modal-player]");
        const titleNode = modal.querySelector("[data-mobile-modal-title]");
        const cardsNode = modal.querySelector("[data-mobile-modal-cards]");
        const cards = cardsFor(modalSide, modalZone);
        if (playerNode) playerNode.textContent = playerLabel(modalSide);
        if (titleNode) titleNode.textContent = `${zoneCodes[modalZone]} ${zoneLabel(modalZone)}`;
        if (cardsNode) {
            cardsNode.innerHTML = cards.length
                ? cards.map(renderModalCard).join("")
                : `<div class="v2-mobile-empty">${t("카드가 없습니다.")}</div>`;
        }
    }

    function renderCardDetail() {
        const modal = document.querySelector("[data-mobile-card-detail-modal]");
        const holder = document.querySelector("[data-mobile-card-detail]");
        if (!modal || !holder) return;
        const card = selectedCardId ? hydrateCard(findCard(selectedCardId)) : null;
        if (!card || card.hidden) {
            modal.hidden = true;
            holder.replaceChildren();
            return;
        }
        const image = card.img || card.img_sm || "";
        const details = [];
        const text = effectText(card);
        if (isAttackCard(card)) {
            details.push(`<p class="v2-mobile-card-detail-line">${escapeHtml(valueOrDashLabel(card, "hit"))} | ${escapeHtml(valueOrDashLabel(card, "guard"))} | ${escapeHtml(valueOrDashLabel(card, "counter"))}</p>`);
            const judgments = joinPresent([displayValue(card, "body"), displayValue(card, "special")], " / ");
            if (judgments) details.push(`<p class="v2-mobile-card-detail-line is-muted">${escapeHtml(judgments)}</p>`);
        } else if (isDefenseCard(card)) {
            details.push(`<p class="v2-mobile-card-detail-line">${escapeHtml(valueOrDashLabel(card, "g_top"))} | ${escapeHtml(valueOrDashLabel(card, "g_mid"))} | ${escapeHtml(valueOrDashLabel(card, "g_bot"))}</p>`);
        }
        if (text) details.push(`<p class="v2-mobile-card-detail-effect">${escapeHtml(text)}</p>`);
        holder.innerHTML = `
            ${image ? `<img src="${escapeHtml(image)}" alt="">` : ""}
            <h2>${escapeHtml(cardName(card))}</h2>
            <section class="v2-mobile-card-detail-text">${details.join("")}</section>
        `;
        modal.hidden = false;
    }

    function openCardDetail(instanceId) {
        const card = hydrateCard(findCard(instanceId));
        if (!card || card.hidden) return;
        selectedCardId = instanceId || "";
        if (card.card_id && !metadataCache.has(String(card.card_id))) {
            scheduleMetadataFetch([String(card.card_id)]);
        }
        renderCardDetail();
    }

    function closeCardDetail() {
        selectedCardId = "";
        renderCardDetail();
    }

    function eventLabel(event) {
        const payload = event.payload || {};
        const actor = playerLabel(event.actor);
        if (event.type === "move_card") {
            const from = payload.from_player ? `${playerLabel(payload.from_player)} ${zoneLabel(payload.from_zone)}` : zoneLabel(payload.from_zone);
            const to = payload.to_player ? `${playerLabel(payload.to_player)} ${zoneLabel(payload.to_zone)}` : zoneLabel(payload.to_zone);
            return `${actor} ${payload.card_label || t("카드")}: ${from} -> ${to}`;
        }
        if (event.type === "bulk_move") return `${actor} ${playerLabel(payload.player)} ${zoneLabel("battle")} ${payload.count || 0}${t("장")} -> ${zoneLabel(payload.to_zone)}`;
        if (event.type === "shuffle_hand") return `${playerLabel(payload.player)} ${zoneLabel("hand")} ${t("셔플")}`;
        if (event.type === "set_hand_visibility") return `${playerLabel(payload.target)} ${zoneLabel("hand")} ${payload.face_up ? t("공개") : t("비공개")} (${payload.count || 0}${t("장")})`;
        if (event.type === "set_phase") return `${phaseLabel(payload.phase)} ${t("Phase")}`;
        if (event.type === "phase_advance") return `${phaseLabel(payload.to_phase)} ${t("Phase")}`;
        if (event.type === "import_card") return `${actor} ${payload.card_label || payload.card_name || t("카드")} -> ${zoneLabel("lumen")}`;
        if (event.type === "blackout_random_get") return `${actor} ${payload.source_card_label || t("블랙아웃")}: ${playerLabel(payload.opponent)} ${zoneLabel("list")} ${t("무작위")} 1${t("장")} -> ${zoneLabel("hand")} - ${payload.card_label || t("카드")}`;
        if (event.type === "yohan_declare_reveal") return `${actor} ${t("선언")} : ${payload.declaration_label || payload.declaration || ""} - ${t("공개")} : ${payload.card_label || t("카드")}`;
        if (event.type === "yohan_foresight_reveal") return `${t("예지")} - ${payload.card_label || t("카드")}`;
        if (event.type === "nia_lumen_cards_to_list") return `${actor} ${zoneLabel("lumen")} ${t("공격/수비")} ${payload.count || 0}${t("장")} -> ${zoneLabel("list")}`;
        if (event.type === "cmyk_new_single") return `${actor} ${payload.card_label || t("뉴 싱글")} ${payload.count || 0}${t("장")} -> ${zoneLabel("lumen")}`;
        if (event.type === "next_turn") return t("다음 턴");
        if (event.type === "request_action") return `${playerLabel(payload.target)} ${t("행동")} ${payload.requested ? t("요청") : t("요청 해제")}`;
        if (event.type === "set_done") {
            const doneLabel = `${playerLabel(payload.target)} ${t("행동")} ${payload.done ? t("완료") : t("완료 취소")}`;
            return payload.requested_opponent ? `${doneLabel} / ${playerLabel(payload.requested_opponent)} ${t("행동")} ${t("요청")}` : doneLabel;
        }
        if (event.type === "hp") return `${playerLabel(payload.target)} HP ${formatSigned(payload.amount)} -> ${payload.after}`;
        if (event.type === "fp") return `${playerLabel(payload.target)} FP ${formatSigned(payload.amount)} -> ${formatSigned(payload.after)}`;
        if (event.type === "fp_reset") return `${playerLabel(payload.target)} ${t("FP 초기화")} (${formatSigned(payload.before)} -> 0)`;
        if (event.type === "timer") return payload.running ? t("10초 타이머 시작") : t("10초 타이머 정지");
        if (event.type === "timer_timeout") return `${playerLabel(payload.target || payload.owner)} ${t("10초 초과")}`;
        if (event.type === "passive") {
            const entry = payload.state || {};
            const value = entry.value !== undefined ? entry.value : entry.count ?? "";
            return `${playerLabel(payload.target)} ${payload.label || payload.key || t("패시브")} ${value}`;
        }
        if (event.type === "set_visibility") return `${actor} ${payload.card_label || t("카드")} ${payload.face_up ? t("공개") : t("비공개")}`;
        if (event.type === "signal") return `${actor} : ${payload.label || payload.signal || t("신호")}`;
        if (event.type === "log_note") return t(payload.text || "기록");
        return event.type;
    }

    function eventRelatedSide(event) {
        const payload = event.payload || {};
        if (["set_phase", "phase_advance", "next_turn"].includes(event.type)) return "";
        if (["request_action", "set_done", "hp", "fp", "fp_reset", "passive", "timer_timeout"].includes(event.type)) return payload.target || payload.owner || "";
        if (event.type === "bulk_move" || event.type === "shuffle_hand") return payload.player || "";
        if (event.type === "set_hand_visibility") return payload.target || "";
        if (event.type === "move_card") return payload.owner || event.actor || payload.to_player || payload.from_player || "";
        return event.actor || "";
    }

    function logAlignmentClass(event) {
        const side = eventRelatedSide(event);
        if (!side || !["p1", "p2"].includes(side)) return "is-neutral-log";
        if (["p1", "p2"].includes(envelope.role)) return side === envelope.role ? "is-own-log" : "is-opponent-log";
        return side === "p1" ? "is-own-log" : "is-opponent-log";
    }

    function renderLog() {
        const holder = document.querySelector("[data-mobile-log-list]");
        if (!holder) return;
        holder.replaceChildren();
        if (logOpen && !eventsLoaded) {
            const loading = document.createElement("p");
            loading.className = "v2-mobile-empty";
            loading.textContent = t("로그를 불러오는 중입니다.");
            holder.appendChild(loading);
            return;
        }
        if (!events.length) {
            const empty = document.createElement("p");
            empty.className = "v2-mobile-empty";
            empty.textContent = t("표시할 기록이 없습니다.");
            holder.appendChild(empty);
            return;
        }
        events.forEach((event) => {
            const row = document.createElement("div");
            row.className = `v2-mobile-log-row ${logAlignmentClass(event)}${event.optimistic ? " is-optimistic" : ""}`;
            row.textContent = t(eventLabel(event));
            holder.appendChild(row);
        });
        holder.scrollTop = holder.scrollHeight;
    }

    function setLogOpen(nextOpen) {
        logOpen = !!nextOpen;
        const modal = document.querySelector("[data-mobile-log-modal]");
        const button = document.querySelector("[data-mobile-log-toggle]");
        if (modal) modal.hidden = !logOpen;
        if (button) button.textContent = logOpen ? t("접기") : t("로그");
        if (!logOpen) {
            sendLogSubscription(false);
            return;
        }
        renderLog();
        const subscribed = sendLogSubscription(true);
        if (!subscribed && (!eventsLoaded || Number(envelope.event_count || 0) > events.length)) {
            fetchEvents();
        }
    }

    function openZoneModal(side, zone) {
        modalSide = side;
        modalZone = zone;
        const modal = document.querySelector("[data-mobile-zone-modal]");
        if (modal) modal.hidden = false;
        renderModal();
    }

    function closeZoneModal() {
        modalSide = "";
        modalZone = "";
        const modal = document.querySelector("[data-mobile-zone-modal]");
        if (modal) modal.hidden = true;
    }

    function showPhaseOverlay(label, key) {
        if (!label) return;
        if (key && key === lastPhaseOverlayKey) return;
        if (key) lastPhaseOverlayKey = key;
        let overlay = document.querySelector("[data-mobile-phase-overlay]");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "v2-mobile-phase-overlay";
            overlay.dataset.mobilePhaseOverlay = "true";
            overlay.setAttribute("aria-hidden", "true");
            document.body.appendChild(overlay);
        }
        overlay.textContent = label;
        overlay.classList.remove("is-visible");
        void overlay.offsetWidth;
        overlay.classList.add("is-visible");
        window.clearTimeout(phaseOverlayTimer);
        phaseOverlayTimer = window.setTimeout(() => overlay.classList.remove("is-visible"), 1150);
    }

    function maybeShowPhaseOverlay() {
        const key = `${state.turn || 1}:${state.phase || ""}`;
        if (!state.phase || key === lastPhaseOverlayKey) return;
        showPhaseOverlay(`${phaseLabel(state.phase)} ${t("Phase")}`, key);
    }

    function showSignalOverlay(actor, label, key) {
        if (!actor || !label) return;
        const overlayKey = key || `${actor}:${label}:${Date.now()}`;
        if (overlayKey === lastSignalOverlayKey) return;
        lastSignalOverlayKey = overlayKey;
        let overlay = document.querySelector("[data-mobile-signal-overlay]");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "v2-mobile-phase-overlay v2-mobile-signal-overlay";
            overlay.dataset.mobileSignalOverlay = "true";
            overlay.setAttribute("aria-hidden", "true");
            document.body.appendChild(overlay);
        }
        overlay.innerHTML = `
            <span>${escapeHtml(playerLabel(actor))}</span>
            <strong>${escapeHtml(label)}</strong>
        `;
        overlay.classList.remove("is-visible");
        void overlay.offsetWidth;
        overlay.classList.add("is-visible");
        window.clearTimeout(signalOverlayTimer);
        signalOverlayTimer = window.setTimeout(() => overlay.classList.remove("is-visible"), 1150);
    }

    function maybeShowSignalOverlay() {
        const signal = state.last_signal || {};
        const label = signalLabel(signal.signal, signal.label);
        if (!signal.id || !signal.actor || !label) return;
        showSignalOverlay(signal.actor, label, signal.id);
    }

    function render() {
        const turn = document.querySelector("[data-mobile-turn]");
        const phase = document.querySelector("[data-mobile-phase]");
        const role = document.querySelector("[data-mobile-role]");
        const board = document.querySelector("[data-mobile-board]");
        const doneButton = document.querySelector("[data-mobile-done-button]");
        if (turn) turn.textContent = String(state.turn || 1);
        if (phase) phase.textContent = phaseLabel(state.phase);
        if (role) role.textContent = roleText();
        if (doneButton) {
            const own = ownSide();
            const done = !!(own && state.status && state.status[own] && state.status[own].done);
            doneButton.textContent = done ? t("완료 취소") : t("내 행동 완료");
            doneButton.disabled = !canControl() || !own;
            doneButton.dataset.mobileDoneValue = done ? "false" : "true";
            doneButton.classList.toggle("is-done", done);
        }
        if (board) {
            const order = playerOrder();
            board.innerHTML = order.map(renderPlayer).join("");
            order.forEach(renderPassive);
            schedulePassiveHeightSync();
        }
        if (modalSide && modalZone) renderModal();
        renderCardDetail();
        renderLog();
        maybeShowPhaseOverlay();
        maybeShowSignalOverlay();
    }

    function connectSocket() {
        if (!config.wsPath || !("WebSocket" in window)) {
            startPollingFallback();
            return;
        }
        const url = new URL(config.wsPath, window.location.href);
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        if (config.language) url.searchParams.set("language", config.language);
        socket = new WebSocket(url.toString());
        socket.addEventListener("open", () => {
            socketReady = true;
            stopPollingFallback();
            requestSocketState();
            flushActionBatch();
            if (logOpen) sendLogSubscription(true);
        });
        socket.addEventListener("message", (event) => {
            let message = null;
            try {
                message = JSON.parse(event.data);
            } catch (error) {
                return;
            }
            if (message.type === "state" && message.state) {
                updateEnvelope(message.state);
                return;
            }
            if (message.type === "state_dirty") {
                if (shouldSuppressAuthoritativeState()) {
                    return;
                }
                window.clearTimeout(dirtyTimer);
                dirtyTimer = window.setTimeout(() => {
                    if (!requestSocketState()) fetchState();
                }, 350);
                return;
            }
            if (message.type === "log_events") {
                applyLogEvents(message, !!message.reset);
                return;
            }
            if (message.type === "signal") {
                if (message.actor !== envelope.role) {
                    showSignalOverlay(message.actor, signalLabel(message.signal, message.label), message.id);
                }
                return;
            }
            if (message.request_id) {
                const pending = pendingSocketActions.get(String(message.request_id));
                if (!pending) return;
                window.clearTimeout(pending.timeout);
                pendingSocketActions.delete(String(message.request_id));
                if (message.type === "error" || message.ok === false) {
                    const error = new Error(message.error || t("요청을 처리하지 못했습니다."));
                    error.serverRejected = true;
                    pending.reject(error);
                    return;
                }
                pending.resolve(message);
                return;
            }
            if (message.type === "warning") {
                showToast(message.message || t("요청이 너무 빠르게 반복되고 있습니다."));
            }
        });
        socket.addEventListener("close", () => {
            socketReady = false;
            pendingSocketActions.forEach((pending) => {
                window.clearTimeout(pending.timeout);
                pending.reject(new Error(t("실시간 연결이 끊겼습니다.")));
            });
            pendingSocketActions.clear();
            startPollingFallback();
            window.setTimeout(connectSocket, 1600);
        });
    }

    function clearLongPressTimer() {
        if (longPressTimer) window.clearTimeout(longPressTimer);
        longPressTimer = null;
        longPressCardId = "";
    }

    function longPressCardFromTarget(target) {
        const node = target.closest("[data-mobile-card-instance]");
        if (!node) return null;
        const card = findCard(node.dataset.mobileCardInstance);
        return canToggleCardVisibility(card) ? card : null;
    }

    root.addEventListener("pointerdown", (event) => {
        if (event.button && event.button !== 0) return;
        if (event.target.closest("button, a, input, select, textarea, [data-mobile-card-moves]")) return;
        const card = longPressCardFromTarget(event.target);
        if (!card) return;
        longPressCardId = card.instance_id;
        longPressStartX = event.clientX;
        longPressStartY = event.clientY;
        longPressTimer = window.setTimeout(() => {
            const targetCard = findCard(longPressCardId);
            clearLongPressTimer();
            suppressNextCardOpen = true;
            toggleCardVisibility(targetCard);
            if (navigator.vibrate) navigator.vibrate(18);
        }, 560);
    });

    root.addEventListener("pointermove", (event) => {
        if (!longPressTimer) return;
        const movedX = Math.abs(event.clientX - longPressStartX);
        const movedY = Math.abs(event.clientY - longPressStartY);
        if (movedX > 12 || movedY > 12) clearLongPressTimer();
    });

    ["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
        root.addEventListener(eventName, clearLongPressTimer);
    });

    root.addEventListener("contextmenu", (event) => {
        if (event.target.closest("button, a, input, select, textarea")) return;
        const card = longPressCardFromTarget(event.target);
        if (!card) return;
        event.preventDefault();
        suppressNextCardOpen = true;
        if (Date.now() - lastVisibilityToggleAt < 700) return;
        toggleCardVisibility(card);
    });

    root.addEventListener("submit", (event) => {
        const form = event.target.closest("[data-mobile-log-form]");
        if (!form) return;
        event.preventDefault();
        const input = form.querySelector("[data-mobile-log-input]");
        const text = String((input && input.value) || "").trim();
        if (!text) return;
        if (!canControl()) {
            showToast(t("조작 권한이 없습니다."));
            return;
        }
        if (input) input.value = "";
        postAction("log_note", { text });
    });

    root.addEventListener("click", (event) => {
        if (suppressNextCardOpen && event.target.closest("[data-mobile-card-instance]")) {
            event.preventDefault();
            suppressNextCardOpen = false;
            return;
        }
        const detailClose = event.target.closest("[data-mobile-detail-close]");
        if (detailClose) {
            event.preventDefault();
            closeCardDetail();
            return;
        }
        const logToggle = event.target.closest("[data-mobile-log-toggle]");
        if (logToggle) {
            event.preventDefault();
            setLogOpen(!logOpen);
            return;
        }
        const logClose = event.target.closest("[data-mobile-log-close]");
        if (logClose) {
            event.preventDefault();
            setLogOpen(false);
            return;
        }
        const close = event.target.closest("[data-mobile-modal-close]");
        if (close) {
            event.preventDefault();
            closeZoneModal();
            return;
        }
        const visibility = event.target.closest("[data-mobile-visibility-card]");
        if (visibility) {
            event.preventDefault();
            toggleCardVisibility(visibility.dataset.mobileVisibilityCard, visibility.dataset.mobileVisibilityValue === "true");
            return;
        }
        const open = event.target.closest("[data-mobile-open-zone]");
        if (open) {
            openZoneModal(open.dataset.mobileZoneSide, open.dataset.mobileOpenZone);
            return;
        }
        const counter = event.target.closest("[data-mobile-counter-kind]");
        if (counter) {
            const kind = counter.dataset.mobileCounterKind;
            const side = counter.dataset.mobileCounterSide;
            queueCounter(kind, side, Number(counter.dataset.mobileCounterAmount || 0));
            return;
        }
        const fpReset = event.target.closest("[data-mobile-fp-reset]");
        if (fpReset) {
            const side = fpReset.dataset.mobileFpReset;
            clearQueuedCounter("fp", side);
            postAction("fp_reset", { target: side, base_revision: counterRevision("fp", side) });
            return;
        }
        const doneButton = event.target.closest("[data-mobile-done-button]");
        if (doneButton) {
            const own = ownSide();
            if (!own) return;
            postAction("set_done", {
                target: own,
                done: doneButton.dataset.mobileDoneValue !== "false",
            });
            return;
        }
        const move = event.target.closest("[data-mobile-move-card]");
        if (move) {
            postAction("move_card", {
                card_instance_id: move.dataset.mobileMoveCard,
                to_player: move.dataset.mobileToPlayer,
                to_zone: move.dataset.mobileToZone,
            });
            return;
        }
        const passive = event.target.closest("[data-mobile-passive-target]");
        if (passive) {
            let value = passive.dataset.mobilePassiveValue;
            let resetKeys = [];
            try {
                value = JSON.parse(passive.dataset.mobilePassiveValue || "null");
            } catch (error) {
                value = passive.dataset.mobilePassiveValue;
            }
            try {
                resetKeys = JSON.parse(passive.dataset.mobilePassiveResetKeys || "[]");
            } catch (error) {
                resetKeys = [];
            }
            let chain = postAction("passive", {
                target: passive.dataset.mobilePassiveTarget,
                key: passive.dataset.mobilePassiveKey,
                value,
                label: passive.dataset.mobilePassiveLabel || passive.dataset.mobilePassiveKey,
            });
            passiveLatchedUpdates(passive.dataset.mobilePassiveTarget, passive.dataset.mobilePassiveKey, value).forEach((update) => {
                chain = chain.then(() => postAction("passive", {
                    target: passive.dataset.mobilePassiveTarget,
                    ...update,
                }));
            });
            resetKeys.forEach((key) => {
                chain = chain.then(() => postAction("passive", {
                    target: passive.dataset.mobilePassiveTarget,
                    key,
                    value: 0,
                    label: key,
                }));
            });
            return;
        }
        const cardOpen = event.target.closest("[data-mobile-card-open]");
        if (cardOpen) {
            openCardDetail(cardOpen.dataset.mobileCardOpen);
            return;
        }
    });

    scheduleMetadataFetch(collectMetadataIds());
    render();
    connectSocket();
    window.addEventListener("resize", schedulePassiveHeightSync);
    window.addEventListener("beforeunload", () => {
        if (passiveHeightFrame) window.cancelAnimationFrame(passiveHeightFrame);
        if (actionBatchTimer) window.clearTimeout(actionBatchTimer);
        stopPollingFallback();
        if (socket) socket.close();
    });
}());
