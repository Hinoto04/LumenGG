(function () {
    const stateNode = document.getElementById("lumen-simulator-state");
    const i18nNode = document.getElementById("lumen-simulator-i18n");
    const root = document.querySelector("[data-lumen-simulator]");
    const config = window.lumenSimulatorConfig || {};
    if (!stateNode || !root || !config.stateUrl) return;

    let envelope = JSON.parse(stateNode.textContent);
    const i18n = i18nNode ? JSON.parse(i18nNode.textContent) : {};
    const translations = i18n.translations || {};
    const translationKeys = Object.keys(translations).sort((a, b) => b.length - a.length);
    const ACTION_BATCH_DELAY_MS = 900;
    const SOCKET_ACTION_TIMEOUT_MS = 15000;
    const DIRTY_STATE_DEBOUNCE_MS = 700;
    const SIM_LOG_LIMIT = 150;
    const POLLING_INITIAL_DELAY_MS = 10000;
    const POLLING_MAX_DELAY_MS = 30000;
    let state = envelope.state || {};
    let events = Array.isArray(envelope.events) ? envelope.events : [];
    let eventsLoaded = Array.isArray(envelope.events);
    let lastLogSeq = maxEventSeq(events);
    const cardMetadataCache = new Map();
    const pendingMetadataIds = new Set();
    let socket = null;
    let socketReady = false;
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let pollingTimer = null;
    let pollingActive = false;
    let pollingDelayMs = POLLING_INITIAL_DELAY_MS;
    let nextRequestId = 1;
    let logOpen = false;
    let selectedCardId = "";
    let pendingTimerTimeoutKey = "";
    let reportedTimerTimeoutKey = "";
    let actionBatchTimer = null;
    let queuedActionBatch = [];
    let queuedActionRollbackEnvelope = null;
    let dirtyStateTimer = null;
    let metadataFetchTimer = null;
    let metadataFetchInFlight = false;
    let realtimeToastTimer = null;
    let realtimeToastMessage = "";
    let realtimeToastCount = 0;
    const tooltip = document.createElement("div");
    const pendingSocketActions = new Map();
    const pendingCounters = {
        hp: new Map(),
        fp: new Map(),
    };

    const phases = ["lumen", "ready", "battle", "get", "recovery"];
    const zones = ["ultimate", "lumen", "battle", "hand", "list", "side", "break"];
    tooltip.className = "v2-sim-card-tooltip";
    document.body.appendChild(tooltip);

    function t(value) {
        if (value === null || value === undefined) return "";
        const raw = String(value);
        if (!raw) return raw;
        if (translations[raw]) return translations[raw];
        return translationKeys.reduce((output, key) => output.replaceAll(key, translations[key]), raw);
    }

    function showRealtimeToast(message) {
        const text = message || t("네트워크 오류가 발생했습니다.");
        let toast = document.querySelector("[data-realtime-toast]");
        if (!toast) {
            toast = document.createElement("div");
            toast.className = "v2-realtime-toast";
            toast.dataset.realtimeToast = "true";
            toast.setAttribute("role", "status");
            document.body.appendChild(toast);
        }
        if (realtimeToastMessage === text) {
            realtimeToastCount += 1;
        } else {
            realtimeToastMessage = text;
            realtimeToastCount = 1;
        }
        toast.textContent = realtimeToastCount > 1 ? `${text} (${realtimeToastCount})` : text;
        toast.classList.add("is-visible");
        window.clearTimeout(realtimeToastTimer);
        realtimeToastTimer = window.setTimeout(() => {
            toast.classList.remove("is-visible");
            realtimeToastMessage = "";
            realtimeToastCount = 0;
        }, 3600);
    }

    function canControl() {
        return !!envelope.can_control && !envelope.is_expired;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    }

    function playerLabel(side) {
        return side === "p1" ? "P1" : side === "p2" ? "P2" : t("관전");
    }

    function zoneLabel(zone) {
        return (envelope.zone_labels && envelope.zone_labels[zone]) || zone;
    }

    function phaseLabel(phase) {
        return (envelope.phase_labels && envelope.phase_labels[phase]) || phase;
    }

    function roleText() {
        if (envelope.role === "p1") return t("P1 조작 링크로 접속 중입니다.");
        if (envelope.role === "p2") return t("P2 조작 링크로 접속 중입니다.");
        return t("관전 링크로 접속 중입니다. 조작은 비활성화됩니다.");
    }

    function formatSigned(value) {
        const number = Number(value || 0);
        return number > 0 ? `+${number}` : String(number);
    }

    function maxEventSeq(rows) {
        return Math.max(0, ...(rows || []).map((event) => Number(event && event.seq || 0)).filter(Number.isFinite));
    }

    function hasValue(value) {
        return value !== null && value !== undefined && String(value).trim() !== "";
    }

    function valueOrDash(value) {
        return hasValue(value) ? String(value) : "-";
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
        return hasValue(card.text) ? t(card.text) : "";
    }

    function cacheCardMetadata(cards) {
        Object.entries(cards || {}).forEach(([cardId, metadata]) => {
            if (!cardId || !metadata || typeof metadata !== "object") return;
            cardMetadataCache.set(String(cardId), metadata);
        });
    }

    function hydrateCard(card) {
        if (!card || card.hidden || !card.card_id) return card;
        const metadata = cardMetadataCache.get(String(card.card_id));
        return metadata ? { ...metadata, ...card } : card;
    }

    function cardDisplayName(card) {
        const hydrated = hydrateCard(card);
        if (!hydrated || hydrated.hidden) return t("비공개 카드");
        return hydrated.name || t("카드");
    }

    function collectVisibleCardIds() {
        const ids = new Set();
        Object.values((state && state.players) || {}).forEach((player) => {
            Object.values((player && player.zones) || {}).forEach((cards) => {
                (cards || []).forEach((card) => {
                    if (!card || card.hidden || !card.card_id) return;
                    const cardId = String(card.card_id);
                    if (!cardMetadataCache.has(cardId)) ids.add(cardId);
                });
            });
        });
        return ids;
    }

    function scheduleCardMetadataFetch(ids) {
        if (!config.metadataUrl) return;
        (ids || []).forEach((cardId) => pendingMetadataIds.add(String(cardId)));
        if (!pendingMetadataIds.size || metadataFetchTimer || metadataFetchInFlight) return;
        metadataFetchTimer = window.setTimeout(fetchPendingCardMetadata, 0);
    }

    function ensureVisibleCardMetadata() {
        scheduleCardMetadataFetch(collectVisibleCardIds());
    }

    function fetchPendingCardMetadata() {
        metadataFetchTimer = null;
        if (!pendingMetadataIds.size || metadataFetchInFlight || !config.metadataUrl) return;
        const ids = Array.from(pendingMetadataIds).slice(0, 200);
        ids.forEach((cardId) => pendingMetadataIds.delete(cardId));
        metadataFetchInFlight = true;
        const url = new URL(config.metadataUrl, window.location.origin);
        url.searchParams.set("ids", ids.join(","));
        if (config.language) url.searchParams.set("language", config.language);
        fetch(url)
            .then((response) => response.json())
            .then((data) => {
                cacheCardMetadata(data.cards || {});
                render();
            })
            .catch(() => {
                ids.forEach((cardId) => pendingMetadataIds.add(cardId));
            })
            .finally(() => {
                metadataFetchInFlight = false;
                if (pendingMetadataIds.size) scheduleCardMetadataFetch([]);
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

    function allCards() {
        const cards = [];
        Object.values((state && state.players) || {}).forEach((player) => {
            Object.entries((player && player.zones) || {}).forEach(([zone, zoneCards]) => {
                (zoneCards || []).forEach((card) => cards.push(hydrateCard({ ...card, zone })));
            });
        });
        return cards;
    }

    function findCard(instanceId) {
        return allCards().find((card) => card.instance_id === instanceId) || null;
    }

    function cardTitle(card) {
        card = hydrateCard(card);
        if (!card || card.hidden) return t("비공개 카드");
        if (isAttackCard(card)) {
            const result = `${valueOrDashLabel(card, "hit")}|${valueOrDashLabel(card, "guard")}|${valueOrDashLabel(card, "counter")}`;
            return `${card.name}(${valueOrDash(card.frame)} / ${result} / ${valueOrDash(card.damage)})`;
        }
        if (isDefenseCard(card)) {
            return `${card.name}(${valueOrDashLabel(card, "g_top")}|${valueOrDashLabel(card, "g_mid")}|${valueOrDashLabel(card, "g_bot")})`;
        }
        return cardDisplayName(card);
    }

    function buildActionBody(action, payload) {
        return {
            action,
            seat: config.seat || "",
            seat_token: config.seatToken || "",
            payload: payload || {},
        };
    }

    function envelopeVersion(source) {
        const version = Number(source && source.version);
        return Number.isFinite(version) ? version : 0;
    }

    function bumpLocalVersion() {
        envelope.version = envelopeVersion(envelope) + 1;
    }

    function updateEnvelope(nextEnvelope, options) {
        const incomingVersion = envelopeVersion(nextEnvelope);
        const currentVersion = envelopeVersion(envelope);
        if (!(options && options.force) && incomingVersion && currentVersion && incomingVersion <= currentVersion) {
            return envelope;
        }
        const previousEvents = events;
        const previousEventCount = Number(envelope.event_count || previousEvents.length || 0);
        envelope = nextEnvelope || envelope;
        state = envelope.state || {};
        if (Array.isArray(envelope.events)) {
            events = envelope.events;
        } else {
            events = previousEvents;
            envelope.events = previousEvents;
            if (envelope.event_count === undefined) envelope.event_count = previousEventCount;
        }
        ensureVisibleCardMetadata();
        render();
        return envelope;
    }

    function cloneData(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function shuffledOrder(cards) {
        const order = (cards || []).map((card) => String(card.instance_id));
        for (let index = order.length - 1; index > 0; index -= 1) {
            const nextIndex = Math.floor(Math.random() * (index + 1));
            [order[index], order[nextIndex]] = [order[nextIndex], order[index]];
        }
        if (order.length > 1 && order.every((instanceId, index) => instanceId === String(cards[index].instance_id))) {
            order.push(order.shift());
        }
        return order;
    }

    function findCardLocation(localState, instanceId) {
        for (const [playerSide, player] of Object.entries((localState && localState.players) || {})) {
            for (const [zone, cards] of Object.entries((player && player.zones) || {})) {
                const index = (cards || []).findIndex((card) => card.instance_id === instanceId);
                if (index >= 0) return { playerSide, zone, index, card: cards[index] };
            }
        }
        return null;
    }

    function resetLocalStatus(localState) {
        localState.status = localState.status || {};
        ["p1", "p2"].forEach((side) => {
            localState.status[side] = { requested: false, done: false };
        });
    }

    function setLocalCardVisibilityForZone(card, zone, localState) {
        if (["character", "passive", "list", "break", "ultimate"].includes(zone)) {
            card.face_up = true;
            return;
        }
        if (["hand", "side", "lumen"].includes(zone)) {
            card.face_up = false;
            return;
        }
        if (zone === "battle") {
            card.face_up = localState.phase === "battle";
        }
    }

    function localCardLabel(card) {
        if (!card || card.hidden) return t("비공개 카드");
        return cardDisplayName(card);
    }

    function appendOptimisticEvent(action, payload) {
        envelope.event_count = Number(envelope.event_count || events.length || 0) + 1;
        events.push({
            id: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            type: action,
            actor: envelope.role,
            payload: cloneData(payload || {}),
            optimistic: true,
        });
        const limit = Number(envelope.event_limit || SIM_LOG_LIMIT);
        if (limit > 0 && events.length > limit) {
            events.splice(0, events.length - limit);
        }
        envelope.events = events;
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
            setLocalCardVisibilityForZone(location.card, toZone, state);
            state.players[toPlayer].zones[toZone].push(location.card);
            localPayload.from_player = location.playerSide;
            localPayload.from_zone = location.zone;
            localPayload.to_player = toPlayer;
            localPayload.card_label = localCardLabel(location.card);
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "bulk_move") {
            const playerSide = String(localPayload.player || "");
            const fromZone = String(localPayload.from_zone || "battle");
            const toZone = String(localPayload.to_zone || "");
            const player = state.players[playerSide];
            if (!player || fromZone !== "battle" || !["list", "hand"].includes(toZone)) return false;
            const cards = player.zones[fromZone] || [];
            player.zones[fromZone] = [];
            cards.forEach((card) => {
                const owner = card.owner || playerSide;
                if (!state.players[owner] || !state.players[owner].zones[toZone]) return;
                setLocalCardVisibilityForZone(card, toZone, state);
                state.players[owner].zones[toZone].push(card);
            });
            localPayload.count = cards.length;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "shuffle_hand") {
            const playerSide = String(localPayload.player || "");
            const player = state.players[playerSide];
            const hand = player && player.zones ? player.zones.hand || [] : [];
            const order = Array.isArray(localPayload.order) ? localPayload.order.map(String) : [];
            if (!player || order.length !== hand.length) return false;
            const cardsById = new Map(hand.map((card) => [String(card.instance_id), card]));
            if (cardsById.size !== hand.length || order.some((instanceId) => !cardsById.has(instanceId))) return false;
            player.zones.hand = order.map((instanceId) => cardsById.get(instanceId));
            localPayload.order = order;
            localPayload.count = order.length;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_phase") {
            if (!phases.includes(localPayload.phase)) return false;
            state.phase = localPayload.phase;
            resetLocalStatus(state);
            if (state.phase === "battle") {
                Object.values(state.players || {}).forEach((player) => {
                    ((player.zones && player.zones.battle) || []).forEach((card) => {
                        card.face_up = true;
                        card.hidden = false;
                    });
                });
            }
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "next_turn") {
            state.turn = Number(state.turn || 1) + 1;
            state.phase = "lumen";
            resetLocalStatus(state);
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "request_action") {
            const target = localPayload.target;
            if (!state.status || !state.status[target]) return false;
            state.status[target].requested = !!localPayload.requested;
            if (state.status[target].requested) state.status[target].done = false;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_done") {
            const target = localPayload.target || envelope.role;
            if (!state.status || !state.status[target]) return false;
            localPayload.target = target;
            state.status[target].done = !!localPayload.done;
            if (state.status[target].done) state.status[target].requested = false;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "hp" || action === "fp") {
            const target = localPayload.target;
            const player = state.players[target];
            const amount = Number(localPayload.amount || 0);
            if (!player || !amount) return false;
            const before = Number(player[action] || 0);
            player[action] = before + amount;
            localPayload.before = before;
            localPayload.after = player[action];
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "fp_reset") {
            const target = localPayload.target;
            const player = state.players[target];
            if (!player) return false;
            localPayload.before = Number(player.fp || 0);
            player.fp = 0;
            localPayload.after = 0;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "timer") {
            const timer = state.timer || {};
            const duration = Number(timer.duration_seconds || 10);
            const running = !timer.is_running;
            const now = Date.now();
            state.timer = {
                ...timer,
                started_at: running ? new Date(now).toISOString() : null,
                duration_seconds: duration,
                remaining_seconds: running ? duration : duration,
                ends_at: running ? new Date(now + duration * 1000).toISOString() : null,
                is_running: running,
                owner: running ? envelope.role : timer.owner,
                timeout_reported: false,
            };
            localPayload.running = running;
            localPayload.owner = state.timer.owner;
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
            location.card.face_up = !!localPayload.face_up;
            location.card.hidden = false;
            localPayload.owner = location.card.owner;
            localPayload.card_label = localCardLabel(location.card);
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

    function shouldOptimisticallyApply(action) {
        return [
            "move_card",
            "bulk_move",
            "shuffle_hand",
            "set_phase",
            "next_turn",
            "request_action",
            "set_done",
            "hp",
            "fp",
            "fp_reset",
            "timer",
            "passive",
            "set_visibility",
            "log_note",
        ].includes(action);
    }

    function stateUrl(forceFull) {
        const url = new URL(config.stateUrl, window.location.origin);
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        if (!forceFull && envelopeVersion(envelope)) url.searchParams.set("since_version", envelopeVersion(envelope));
        return url.toString();
    }

    function eventsUrl() {
        if (!config.eventsUrl) return "";
        const url = new URL(config.eventsUrl, window.location.origin);
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        url.searchParams.set("event_limit", String(SIM_LOG_LIMIT));
        return url.toString();
    }

    function sendLogSubscription(enabled) {
        if (!socketReady || !socket || socket.readyState !== WebSocket.OPEN) return false;
        socket.send(JSON.stringify({
            type: enabled ? "log_subscribe" : "log_unsubscribe",
            since_seq: lastLogSeq,
        }));
        return true;
    }

    function buildWebSocketUrl(path) {
        const url = new URL(path, window.location.href);
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        if (config.language) url.searchParams.set("language", config.language);
        return url.toString();
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

    function isBatchableAction(action) {
        return [
            "move_card",
            "bulk_move",
            "shuffle_hand",
            "request_action",
            "set_done",
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
            showRealtimeToast(t("실시간 연결이 복구되는 중입니다."));
            return Promise.resolve(null);
        }
        if (actionBatchTimer) {
            window.clearTimeout(actionBatchTimer);
            actionBatchTimer = null;
        }
        const batch = queuedActionBatch;
        const rollbackEnvelope = queuedActionRollbackEnvelope;
        queuedActionBatch = [];
        queuedActionRollbackEnvelope = null;
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
                    updateEnvelope(rollbackEnvelope, { force: true });
                    fetchState(true);
                }
                showRealtimeToast(error && error.message ? error.message : t("네트워크 오류가 발생했습니다."));
                batch.forEach((item) => item.resolve(null));
                return null;
            });
    }

    function queueBatchAction(action, payload, rollbackEnvelope) {
        if (!queuedActionRollbackEnvelope && rollbackEnvelope) {
            queuedActionRollbackEnvelope = rollbackEnvelope;
        }
        const promise = new Promise((resolve, reject) => {
            queuedActionBatch.push({ action, payload, resolve, reject });
        });
        if (actionBatchTimer) window.clearTimeout(actionBatchTimer);
        actionBatchTimer = window.setTimeout(flushActionBatch, ACTION_BATCH_DELAY_MS);
        return promise;
    }

    function postAction(action, payload) {
        if (!canControl()) return Promise.resolve();
        const actionPayload = cloneData(payload || {});
        const rollbackEnvelope = shouldOptimisticallyApply(action) ? cloneData(envelope) : null;
        let optimisticApplied = false;
        if (rollbackEnvelope) {
            optimisticApplied = applyOptimisticAction(action, cloneData(actionPayload));
            if (optimisticApplied) {
                if (!isBatchableAction(action) || !queuedActionBatch.length) {
                    bumpLocalVersion();
                }
                render();
            }
        }
        if (optimisticApplied && isBatchableAction(action)) {
            return queueBatchAction(action, actionPayload, rollbackEnvelope);
        }
        return flushActionBatch().then(() => postSocketAction(action, actionPayload)).catch((error) => {
            if (optimisticApplied && rollbackEnvelope && error && error.serverRejected) {
                updateEnvelope(rollbackEnvelope, { force: true });
                fetchState(true);
            }
            showRealtimeToast(error && error.message ? error.message : t("네트워크 오류가 발생했습니다."));
            return null;
        });
    }

    function timerRemaining() {
        const timer = state.timer || {};
        const duration = Number(timer.duration_seconds || 10);
        if (timer.is_running && timer.ends_at) {
            const endsAt = new Date(timer.ends_at).getTime();
            if (!Number.isNaN(endsAt)) return Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
        }
        return Math.max(0, Math.min(duration, Number(timer.remaining_seconds ?? duration) || 0));
    }

    function maybeReportTimerTimeout(remaining) {
        const timer = state.timer || {};
        const owner = timer.owner;
        const key = `${timer.started_at || ""}:${owner || ""}`;
        if (
            !canControl() ||
            !["p1", "p2"].includes(envelope.role) ||
            remaining > 0 ||
            !timer.started_at ||
            !owner ||
            owner === envelope.role ||
            timer.timeout_reported ||
            pendingTimerTimeoutKey === key ||
            reportedTimerTimeoutKey === key
        ) {
            return;
        }
        pendingTimerTimeoutKey = key;
        postAction("timer_timeout", { started_at: timer.started_at }).then((result) => {
            pendingTimerTimeoutKey = "";
            if (result) reportedTimerTimeoutKey = key;
        });
    }

    function renderTimer() {
        const timerNode = document.querySelector("[data-sim-timer]");
        const timerButton = document.querySelector("[data-sim-action='timer']");
        const remaining = timerRemaining();
        if (timerNode) timerNode.textContent = String(remaining);
        if (timerButton) {
            timerButton.disabled = !canControl();
            timerButton.classList.toggle("is-active", !!(state.timer && state.timer.is_running));
            timerButton.classList.toggle("is-danger", !!(state.timer && state.timer.is_running && remaining <= 3));
        }
        maybeReportTimerTimeout(remaining);
    }

    function renderPhase() {
        const turn = document.querySelector("[data-sim-turn]");
        const current = document.querySelector("[data-sim-phase-current]");
        const holder = document.querySelector("[data-sim-phase-buttons]");
        if (turn) turn.textContent = String(state.turn || 1);
        if (current) current.textContent = `${phaseLabel(state.phase)} ${t("Phase")}`;
        if (!holder) return;
        holder.replaceChildren();
        phases.forEach((phase) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "v2-button";
            button.dataset.phase = phase;
            button.textContent = phaseLabel(phase);
            button.disabled = !canControl();
            button.classList.toggle("is-active", state.phase === phase);
            holder.appendChild(button);
        });
    }

    function renderStatus() {
        const holder = document.querySelector("[data-sim-status]");
        if (!holder) return;
        holder.replaceChildren();
        ["p1", "p2"].forEach((side) => {
            const status = (state.status && state.status[side]) || {};
            const row = document.createElement("div");
            row.className = "v2-sim-status-row";
            if (side === envelope.role) row.classList.add("is-own");
            const label = document.createElement("strong");
            label.textContent = `${playerLabel(side)} ${status.done ? t("완료") : status.requested ? t("요청됨") : t("대기")}`;
            label.className = status.done ? "is-done" : status.requested ? "is-requested" : "";
            const requestButton = document.createElement("button");
            requestButton.type = "button";
            requestButton.className = "v2-button";
            requestButton.dataset.requestTarget = side;
            requestButton.dataset.requestValue = status.requested ? "false" : "true";
            requestButton.textContent = status.requested ? t("요청 해제") : t("행동 요청");
            requestButton.disabled = !canControl();
            row.append(label, requestButton);
            if (side === envelope.role) {
                const done = document.createElement("button");
                done.type = "button";
                done.className = "v2-button v2-button-primary";
                done.dataset.doneTarget = envelope.role;
                done.dataset.doneValue = status.done ? "false" : "true";
                done.textContent = status.done ? t("완료 취소") : t("내 행동 완료");
                done.disabled = !canControl();
                row.appendChild(done);
            }
            holder.appendChild(row);
        });
    }

    function counterButton(label, side, kind, amount, extraClass) {
        return `<button class="v2-sim-counter ${extraClass || ""}" type="button" data-counter-kind="${kind}" data-counter-target="${side}" data-counter-amount="${amount}" data-counter-label="${escapeHtml(label)}">${label}</button>`;
    }

    function renderPlayer(side) {
        const rootNode = document.querySelector(`[data-player-board="${side}"]`);
        const player = state.players && state.players[side];
        if (!rootNode || !player) return;
        const character = player.character || {};
        const bgStyle = character.img
            ? ` style="--sim-character-bg: url('${escapeHtml(String(character.img).replaceAll("'", "%27"))}')"`
            : "";
        const requested = !!(state.status && state.status[side] && state.status[side].requested);
        const requestClass = requested
            ? side === envelope.role
                ? " is-action-requested is-own-request"
                : " is-action-requested is-opponent-request"
            : "";
        rootNode.className = `v2-sim-player-wrap v2-sim-${side}`;
        rootNode.innerHTML = `
            <article class="v2-panel v2-sim-player${requestClass}"${bgStyle}>
                <header class="v2-sim-player-head">
                    <div>
                        <span>${playerLabel(side)}</span>
                        <h2>${escapeHtml(player.name)}</h2>
                    </div>
                    <div class="v2-sim-passive" data-passive-panel="${side}"></div>
                </header>
                <div class="v2-sim-life">
                    <div class="v2-sim-hp">
                        ${counterButton("-500", side, "hp", -500, "is-damage")}
                        ${counterButton("-", side, "hp", -100, "is-damage")}
                        <strong data-counter-value="hp:${side}">${Number(player.hp || 0)}</strong>
                        ${counterButton("+", side, "hp", 100, "is-heal")}
                        ${counterButton("+500", side, "hp", 500, "is-heal")}
                    </div>
                    <div class="v2-sim-fp">
                        ${counterButton("-", side, "fp", -1, "")}
                        <button class="v2-sim-fp-value" type="button" data-fp-reset="${side}" data-counter-value="fp:${side}">${formatSigned(player.fp || 0)} FP</button>
                        ${counterButton("+", side, "fp", 1, "")}
                    </div>
                </div>
                <div class="v2-sim-zones" data-zone-grid="${side}"></div>
            </article>
        `;
        renderPassive(side, player);
        renderZones(side, player);
    }

    function renderPassive(side, player) {
        const holder = document.querySelector(`[data-passive-panel="${side}"]`);
        if (!holder) return;
        holder.replaceChildren();
        const passiveState = player.passive_state || {};
        const passiveCards = ((player.zones && player.zones.passive) || []).filter((card) => !card.hidden);
        const character = player.character || {};
        const passiveUi = character.passive_ui || {};
        const options = passiveOptions(passiveUi);
        const entries = Object.entries(passiveState);
        const rows = entries.length
            ? entries.map(([key, entry]) => {
                const value = entry.value !== undefined ? entry.value : entry.count ?? "";
                return `<span>${escapeHtml(entry.label || key)} <strong>${escapeHtml(value)}</strong></span>`;
            }).join("")
            : "";
        const controlsNode = document.createElement("div");
        controlsNode.className = "v2-sim-passive-controls";
        const cardsNode = document.createElement("div");
        cardsNode.className = "v2-sim-passive-cards";
        cardsNode.innerHTML = passiveCards.map((card) => renderPassiveCard(card)).join("");

        const hasCustomPanel = passiveUi.html || passiveUi.css || passiveUi.js;
        if (hasPassiveControls(options)) {
            renderNativePassiveControls(side, controlsNode, options, passiveState, player);
        } else if (hasCustomPanel) {
            controlsNode.classList.add("has-custom-passive");
            renderCustomPassiveUi(side, controlsNode, passiveUi);
        } else if (rows) {
            const listNode = document.createElement("div");
            listNode.className = "v2-sim-passive-list";
            listNode.innerHTML = rows;
            controlsNode.appendChild(listNode);
        }
        if (controlsNode.children.length) holder.appendChild(controlsNode);
        if (passiveCards.length) holder.appendChild(cardsNode);
    }

    function renderPassiveCard(card) {
        card = hydrateCard(card);
        const image = card.img_sm || card.img;
        return `
            <button class="v2-sim-passive-card" type="button" data-card-open="${escapeHtml(card.instance_id)}" data-card-tooltip="${escapeHtml(cardTitle(card))}">
                ${image ? `<img src="${escapeHtml(image)}" alt="">` : ""}
            </button>
        `;
    }

    function passiveSetButton(side, key, value, label, text, extraClass, resetKeys) {
        const encodedValue = JSON.stringify(value);
        const encodedResetKeys = resetKeys && resetKeys.length ? JSON.stringify(resetKeys) : "";
        return `
            <button class="v2-sim-passive-native-button ${extraClass || ""}" type="button"
                data-passive-native-target="${escapeHtml(side)}"
                data-passive-native-key="${escapeHtml(key)}"
                data-passive-native-value="${escapeHtml(encodedValue)}"
                data-passive-native-label="${escapeHtml(label || key)}"
                ${encodedResetKeys ? `data-passive-reset-keys="${escapeHtml(encodedResetKeys)}"` : ""}>
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
                    <div class="v2-sim-passive-native is-counter">
                        <span>${escapeHtml(label)}</span>
                        ${passiveSetButton(side, control.key, minus, label, "-", current <= 0 ? "is-disabled" : "")}
                        ${passiveSetButton(
                            side,
                            control.key,
                            0,
                            control.resetLabel || label,
                            max === null ? `${current}${control.unit || ""}` : `${current}/${max}${control.unit || ""}`,
                            current <= 0 ? "is-value is-disabled" : "is-value",
                        )}
                        ${passiveSetButton(side, control.key, plus, label, "+", max !== null && current >= max ? "is-disabled" : "")}
                    </div>
                `);
            } else if (control.type === "toggle") {
                const active = passiveBool(passiveEntryValue(passiveState, control.key, false));
                parts.push(`
                    <div class="v2-sim-passive-native is-toggle ${active ? "is-active" : ""}">
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
                    <div class="v2-sim-passive-native is-choice">
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
                    <div class="v2-sim-passive-native is-status ${active ? "is-active" : ""}">
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
                    <div class="v2-sim-passive-native is-threshold ${active ? "is-active" : ""}">
                        <span>${escapeHtml(label)}</span>
                        ${passiveSetButton(side, control.key, active ? false : true, label, text, active ? "is-active" : (!ready ? "is-disabled" : ""), active ? [] : (control.resetKeys || []))}
                    </div>
                `);
            }
        });
        const badges = [...(options.badges || []), ...(options.latchedStatuses || [])];
        badges.forEach((badge) => {
            if (badge.key && renderedStatusKeys.has(badge.key)) return;
            const label = badge.label || badge.key || t("패시브");
            const stored = passiveBool(passiveEntryValue(passiveState, badge.key, false));
            const met = passiveConditionMet(badge.condition || badge.activateWhen, player, passiveState);
            const keep = passiveConditionMet(badge.keepWhile || badge.activateWhen || badge.condition, player, passiveState);
            const active = badge.type === "latchedStatus" ? (met || (stored && keep)) : met;
            parts.push(`
                <div class="v2-sim-passive-native is-status ${active ? "is-active" : ""}">
                    <span>${escapeHtml(label)}</span>
                    <strong>${escapeHtml(active ? (badge.activeText || t("활성")) : (badge.inactiveText || t("대기")))}</strong>
                </div>
            `);
        });
        holder.innerHTML = parts.join("");
        holder.querySelectorAll(".is-disabled").forEach((button) => {
            button.disabled = true;
        });
        holder.querySelectorAll("[data-passive-native-target]").forEach((button) => {
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
                const entry = passiveState[String(key)] || {};
                if (entry.value !== undefined) return entry.value;
                if (entry.count !== undefined) return entry.count;
                return fallback;
            },
        };
    }

    function renderCustomPassiveUi(side, holder, passiveUi) {
        const passiveRoot = document.createElement("div");
        const rootId = `v2-sim-passive-${envelope.id}-${side}-${(state.players[side].character || {}).id || "none"}`;
        passiveRoot.id = rootId;
        passiveRoot.className = "v2-sim-passive-custom";
        passiveRoot.innerHTML = passiveUi.html || "";

        if (passiveUi.css) {
            const style = document.createElement("style");
            style.textContent = String(passiveUi.css).replaceAll(":host", `#${rootId}`);
            holder.appendChild(style);
        }
        holder.appendChild(passiveRoot);

        if (passiveUi.js) {
            try {
                const api = makePassiveApi(side, passiveRoot, passiveUi.options || {});
                const run = new Function("api", `"use strict";\n${passiveUi.js}`);
                run(api);
            } catch (error) {
                const message = document.createElement("span");
                message.className = "v2-sim-passive-error";
                message.textContent = t("패시브 UI 오류");
                holder.appendChild(message);
                console.error(error);
            }
        }
        passiveRoot.querySelectorAll("button, input, select, textarea").forEach((node) => {
            if ("disabled" in node && !canControl()) node.disabled = true;
        });
    }

    function renderZones(side, player) {
        const holder = document.querySelector(`[data-zone-grid="${side}"]`);
        if (!holder) return;
        holder.replaceChildren();
        const makeZone = (zone) => {
            const cards = (player.zones && player.zones[zone]) || [];
            const zoneNode = document.createElement("section");
            zoneNode.className = `v2-sim-zone v2-sim-zone-${zone}`;
            zoneNode.dataset.dropZone = zone;
            zoneNode.dataset.dropPlayer = side;
            const actions = [];
            if (zone === "battle" && canControl()) {
                actions.push(`<button type="button" data-bulk-player="${side}" data-bulk-target="list">${t("리스트")}</button>`);
                actions.push(`<button type="button" data-bulk-player="${side}" data-bulk-target="hand">${t("손패")}</button>`);
            }
            if (zone === "hand" && canControl()) {
                actions.push(`<button type="button" data-shuffle-hand-player="${side}">${t("셔플")}</button>`);
            }
            const zoneActions = actions.length
                ? `<div class="v2-sim-zone-actions">${actions.join("")}</div>`
                : "";
            zoneNode.innerHTML = `
                <header>
                    <strong>${zone === "ultimate" ? "ULTIMATE" : zoneLabel(zone)}</strong>
                    ${zone === "ultimate" ? "" : `<span>${cards.length}</span>`}
                    ${zoneActions}
                </header>
                <div class="v2-sim-card-grid">
                    ${cards.map((card) => renderCard(card)).join("")}
                </div>
            `;
            return zoneNode;
        };

        const topRow = document.createElement("div");
        topRow.className = "v2-sim-zone-row v2-sim-zone-row-top";
        topRow.append(makeZone("ultimate"), makeZone("lumen"));
        holder.appendChild(topRow);
        holder.appendChild(makeZone("battle"));
        holder.appendChild(makeZone("hand"));
        holder.appendChild(makeZone("list"));
        const bottomRow = document.createElement("div");
        bottomRow.className = "v2-sim-zone-row v2-sim-zone-row-bottom";
        bottomRow.append(makeZone("side"), makeZone("break"));
        holder.appendChild(bottomRow);
    }

    function renderCard(card) {
        card = hydrateCard(card);
        const draggable = canControl() && card.kind !== "character";
        const classes = ["v2-sim-card"];
        if (card.hidden) classes.push("is-hidden");
        if (card.face_up) classes.push("is-face-up");
        if (!card.face_up) classes.push("is-face-down");
        if (card.kind === "character") classes.push("is-character");
        const image = !card.hidden && card.img_sm
            ? `<img src="${escapeHtml(card.img_sm)}" alt="">`
            : "";
        const visibility = canToggleCardVisibility(card)
            ? `<button class="v2-sim-card-toggle ${card.face_up ? "is-public" : "is-private"}" type="button" data-visibility-card="${escapeHtml(card.instance_id)}" data-visibility-value="${card.face_up ? "false" : "true"}" aria-label="${card.face_up ? t("비공개로 전환") : t("공개로 전환")}"></button>`
            : "";
        return `
            <div class="${classes.join(" ")}" data-card-instance="${escapeHtml(card.instance_id)}" data-card-owner="${escapeHtml(card.owner)}" data-card-open="${escapeHtml(card.instance_id)}" data-card-tooltip="${escapeHtml(cardTitle(card))}" draggable="${draggable ? "true" : "false"}">
                ${image}
                ${visibility}
            </div>
        `;
    }

    function canToggleCardVisibility(card) {
        return !!(
            card &&
            ["hand", "side", "battle", "lumen"].includes(card.zone) &&
            canControl() &&
            envelope.role === card.owner &&
            card.kind !== "character" &&
            !card.hidden
        );
    }

    function toggleCardVisibility(card) {
        if (!canToggleCardVisibility(card)) return;
        postAction("set_visibility", {
            card_instance_id: card.instance_id,
            face_up: !card.face_up,
        });
    }

    function fitCardGrids() {
        document.querySelectorAll(".v2-sim-card-grid").forEach((grid) => {
            const cards = grid.querySelectorAll(".v2-sim-card").length;
            if (!cards) {
                grid.style.removeProperty("--sim-card-fit-step");
                return;
            }
            const style = window.getComputedStyle(grid);
            const rows = Math.max(1, Number.parseInt(style.getPropertyValue("--sim-zone-rows"), 10) || 1);
            const cardWidth = Number.parseFloat(style.getPropertyValue("--sim-card-width")) || 94;
            const padding = (Number.parseFloat(style.paddingLeft) || 0) + (Number.parseFloat(style.paddingRight) || 0);
            const contentWidth = Math.max(0, grid.clientWidth - padding);
            const columns = Math.max(1, Math.ceil(cards / rows));
            const fullStep = cardWidth + 6;
            const minStep = Math.min(24, cardWidth);
            const fitStep = columns > 1
                ? (contentWidth - cardWidth) / (columns - 1)
                : fullStep;
            const step = Math.max(minStep, Math.min(fullStep, fitStep));
            grid.style.setProperty("--sim-card-fit-step", `${Math.floor(step)}px`);
        });
    }

    function scheduleFitCardGrids() {
        window.requestAnimationFrame(fitCardGrids);
    }

    function eventLabel(event) {
        const payload = event.payload || {};
        const actor = playerLabel(event.actor);
        if (event.type === "move_card") {
            const from = payload.from_player
                ? `${playerLabel(payload.from_player)} ${zoneLabel(payload.from_zone)}`
                : zoneLabel(payload.from_zone);
            const to = payload.to_player
                ? `${playerLabel(payload.to_player)} ${zoneLabel(payload.to_zone)}`
                : zoneLabel(payload.to_zone);
            return `${actor} ${payload.card_label || t("카드")}: ${from} → ${to}`;
        }
        if (event.type === "bulk_move") {
            return `${actor} ${playerLabel(payload.player)} ${zoneLabel("battle")} ${payload.count || 0}${t("장")} → ${zoneLabel(payload.to_zone)}`;
        }
        if (event.type === "shuffle_hand") return `${playerLabel(payload.player)} ${zoneLabel("hand")} ${t("셔플")}`;
        if (event.type === "set_phase") return `${phaseLabel(payload.phase)} ${t("Phase")}`;
        if (event.type === "import_card") return `${actor} ${payload.card_label || payload.card_name || t("카드")} → ${zoneLabel("lumen")}`;
        if (event.type === "next_turn") return t("다음 턴");
        if (event.type === "request_action") return `${playerLabel(payload.target)} ${t("행동")} ${payload.requested ? t("요청") : t("요청 해제")}`;
        if (event.type === "set_done") return `${playerLabel(payload.target)} ${t("행동")} ${payload.done ? t("완료") : t("완료 취소")}`;
        if (event.type === "hp") return `${playerLabel(payload.target)} HP ${formatSigned(payload.amount)} → ${payload.after}`;
        if (event.type === "fp") return `${playerLabel(payload.target)} FP ${formatSigned(payload.amount)} → ${formatSigned(payload.after)}`;
        if (event.type === "fp_reset") return `${playerLabel(payload.target)} ${t("FP 초기화")} (${formatSigned(payload.before)} → 0)`;
        if (event.type === "timer") return payload.running ? t("10초 타이머 시작") : t("10초 타이머 정지");
        if (event.type === "timer_timeout") return `${playerLabel(payload.target || payload.owner)} ${t("10초 초과")}`;
        if (event.type === "passive") {
            const entry = payload.state || {};
            const value = entry.value !== undefined ? entry.value : entry.count ?? "";
            return `${playerLabel(payload.target)} ${payload.label || payload.key || t("패시브")} ${value}`;
        }
        if (event.type === "set_visibility") return `${actor} ${payload.card_label || t("카드")} ${payload.face_up ? t("공개") : t("비공개")}`;
        if (event.type === "log_note") return t(payload.text || "기록");
        return event.type;
    }

    function eventRelatedSide(event) {
        const payload = event.payload || {};
        if (["set_phase", "next_turn"].includes(event.type)) return "";
        if (["request_action", "set_done", "hp", "fp", "fp_reset", "passive", "timer_timeout"].includes(event.type)) return payload.target || payload.owner || "";
        if (event.type === "bulk_move") return payload.player || "";
        if (event.type === "shuffle_hand") return payload.player || "";
        if (event.type === "import_card") return payload.target || event.actor || "";
        if (event.type === "set_visibility") return payload.owner || event.actor || "";
        if (event.type === "move_card") return payload.owner || event.actor || payload.to_player || payload.from_player || "";
        if (event.type === "timer") return payload.owner || event.actor || "";
        if (event.type === "log_note") return event.actor || "";
        return event.actor || "";
    }

    function logAlignmentClass(event) {
        const side = eventRelatedSide(event);
        if (!side || !["p1", "p2"].includes(side)) return "is-neutral-log";
        if (["p1", "p2"].includes(envelope.role)) {
            return side === envelope.role ? "is-own-log" : "is-opponent-log";
        }
        return side === "p1" ? "is-own-log" : "is-opponent-log";
    }

    function renderLog() {
        const holder = document.querySelector("[data-sim-log]");
        if (!holder) return;
        holder.replaceChildren();
        if (logOpen && !eventsLoaded) {
            const loading = document.createElement("p");
            loading.className = "v2-battle-empty";
            loading.textContent = t("로그를 불러오는 중입니다.");
            holder.appendChild(loading);
            return;
        }
        const rows = events.slice().reverse();
        if (!rows.length) {
            const empty = document.createElement("p");
            empty.className = "v2-battle-empty";
            empty.textContent = t("표시할 로그가 없습니다.");
            holder.appendChild(empty);
            return;
        }
        const omitted = Math.max(0, Number(envelope.event_count || rows.length) - rows.length);
        if (omitted) {
            const notice = document.createElement("p");
            notice.className = "v2-battle-empty";
            notice.textContent = t(`이전 로그 ${omitted}개는 생략되었습니다.`);
            holder.appendChild(notice);
        }
        rows.forEach((event) => {
            const row = document.createElement("div");
            row.className = "v2-sim-log-row";
            const relatedSide = eventRelatedSide(event);
            if (relatedSide === "p1") row.classList.add("is-p1");
            if (relatedSide === "p2") row.classList.add("is-p2");
            row.classList.add(logAlignmentClass(event));
            const label = document.createElement("strong");
            label.textContent = t(eventLabel(event));
            row.append(label);
            holder.appendChild(row);
        });
    }

    function renderCardDetail() {
        const drawer = document.querySelector("[data-card-drawer]");
        const holder = document.querySelector("[data-card-detail]");
        if (!drawer || !holder) return;
        const card = selectedCardId ? hydrateCard(findCard(selectedCardId)) : null;
        if (!card || card.hidden) {
            drawer.classList.remove("is-open");
            document.body.classList.remove("v2-sim-card-detail-open");
            holder.replaceChildren();
            return;
        }
        const image = card.img || card.img_sm || "";
        const details = [];
        const text = effectText(card);
        if (isAttackCard(card)) {
            details.push(`<p class="v2-sim-card-detail-line">${escapeHtml(valueOrDashLabel(card, "hit"))} | ${escapeHtml(valueOrDashLabel(card, "guard"))} | ${escapeHtml(valueOrDashLabel(card, "counter"))}</p>`);
            const judgments = joinPresent([displayValue(card, "body"), displayValue(card, "special")], " / ");
            if (judgments) details.push(`<p class="v2-sim-card-detail-line is-muted">${escapeHtml(judgments)}</p>`);
        } else if (isDefenseCard(card)) {
            details.push(`<p class="v2-sim-card-detail-line">${escapeHtml(valueOrDashLabel(card, "g_top"))} | ${escapeHtml(valueOrDashLabel(card, "g_mid"))} | ${escapeHtml(valueOrDashLabel(card, "g_bot"))}</p>`);
        }
        if (text) details.push(`<p class="v2-sim-card-detail-effect">${escapeHtml(text)}</p>`);
        holder.innerHTML = `
            ${image ? `<img src="${escapeHtml(image)}" alt="">` : ""}
            <h2>${escapeHtml(cardDisplayName(card))}</h2>
            <section class="v2-sim-card-detail-text">${details.join("")}</section>
        `;
        drawer.classList.add("is-open");
        document.body.classList.add("v2-sim-card-detail-open");
    }

    function setLogOpen(nextOpen) {
        logOpen = nextOpen;
        document.querySelectorAll("[data-log-drawer]").forEach((drawer) => {
            drawer.classList.toggle("is-open", logOpen);
        });
        document.querySelectorAll("[data-log-toggle]").forEach((button) => {
            button.textContent = logOpen ? t("접기") : t("로그");
        });
        if (!logOpen) {
            sendLogSubscription(false);
            return;
        }
        const subscribed = sendLogSubscription(true);
        if (!subscribed && (!eventsLoaded || Number(envelope.event_count || 0) > events.length)) {
            fetchEvents();
        }
    }

    function attachDragAndDrop() {
        document.querySelectorAll("[data-card-instance]").forEach((card) => {
            card.addEventListener("dragstart", (event) => {
                if (!canControl() || card.getAttribute("draggable") !== "true") {
                    event.preventDefault();
                    return;
                }
                event.dataTransfer.setData("text/plain", JSON.stringify({
                    instanceId: card.dataset.cardInstance,
                    owner: card.dataset.cardOwner,
                }));
            });
        });
        document.querySelectorAll("[data-drop-zone]").forEach((zone) => {
            zone.addEventListener("dragover", (event) => {
                if (!canControl()) return;
                event.preventDefault();
                zone.classList.add("is-drop-hover");
            });
            zone.addEventListener("dragleave", () => zone.classList.remove("is-drop-hover"));
            zone.addEventListener("drop", (event) => {
                if (!canControl()) return;
                event.preventDefault();
                zone.classList.remove("is-drop-hover");
                let dragged = null;
                try {
                    dragged = JSON.parse(event.dataTransfer.getData("text/plain") || "{}");
                } catch (error) {
                    dragged = null;
                }
                if (!dragged || !dragged.instanceId) return;
                const canDropToOpponent = ["battle", "lumen"].includes(zone.dataset.dropZone);
                if (dragged.owner !== zone.dataset.dropPlayer && !canDropToOpponent) {
                    showRealtimeToast(t("상대 플레이어의 루멘 존 또는 배틀 존으로만 이동할 수 있습니다."));
                    return;
                }
                postAction("move_card", {
                    card_instance_id: dragged.instanceId,
                    to_player: zone.dataset.dropPlayer,
                    to_zone: zone.dataset.dropZone,
                });
            });
        });
    }

    function clearQueuedCounter(kind, side) {
        const queue = pendingCounters[kind];
        const queued = queue.get(side);
        if (queued && queued.timer) window.clearTimeout(queued.timer);
        queue.delete(side);
        updateQueuedCounters();
    }

    function updateQueuedCounters() {
        document.querySelectorAll("[data-counter-kind]").forEach((button) => {
            button.textContent = button.dataset.counterLabel || button.textContent;
        });
        document.querySelectorAll("[data-counter-value]").forEach((value) => {
            delete value.dataset.pendingAmount;
        });
        ["hp", "fp"].forEach((kind) => {
            pendingCounters[kind].forEach((queued, side) => {
                const amount = Number(queued.amount || 0);
                if (kind !== "hp") {
                    document.querySelectorAll(`[data-counter-kind="${kind}"][data-counter-target="${side}"]`).forEach((button) => {
                        const step = Number(button.dataset.counterAmount || 0);
                        const sameDirection = (amount > 0 && step > 0) || (amount < 0 && step < 0);
                        button.textContent = sameDirection ? formatSigned(amount) : (button.dataset.counterLabel || button.textContent);
                    });
                }
                const value = document.querySelector(`[data-counter-value="${kind}:${side}"]`);
                if (value && amount) {
                    value.dataset.pendingAmount = formatSigned(amount);
                }
            });
        });
    }

    function queueCounter(kind, side, amount) {
        if (!canControl()) return;
        const queue = pendingCounters[kind];
        const queued = queue.get(side) || { amount: 0, timer: null };
        queued.amount += amount;
        window.clearTimeout(queued.timer);
        if (!queued.amount) {
            clearQueuedCounter(kind, side);
            return;
        }
        queued.timer = window.setTimeout(() => {
            const finalAmount = queued.amount;
            clearQueuedCounter(kind, side);
            postAction(kind, { target: side, amount: finalAmount });
        }, kind === "hp" ? 900 : 700);
        queue.set(side, queued);
        updateQueuedCounters();
    }

    function render() {
        ensureVisibleCardMetadata();
        const role = document.querySelector("[data-sim-role]");
        if (role) role.textContent = roleText();
        renderPresence();
        renderPhase();
        renderStatus();
        renderTimer();
        renderPlayer("p2");
        renderPlayer("p1");
        renderLog();
        renderCardDetail();
        setLogOpen(logOpen);
        scheduleFitCardGrids();
        document.querySelectorAll([
            "[data-sim-action='next_turn']",
            "[data-sim-action='undo']",
            "[data-quick-log]",
            "[data-sim-action='manual_log']",
            "[data-counter-kind]",
            "[data-fp-reset]",
            "[data-bulk-player]",
            "[data-shuffle-hand-player]",
            "[data-visibility-card]",
            "[data-sim-action='import_card']",
        ].join(", ")).forEach((button) => {
            button.disabled = !canControl();
        });
        document.querySelectorAll("[data-manual-log-input]").forEach((input) => {
            input.disabled = !canControl();
        });
        document.querySelectorAll("[data-card-import-input]").forEach((input) => {
            input.disabled = !canControl();
        });
        attachDragAndDrop();
        updateQueuedCounters();
    }

    function renderPresence() {
        const holder = document.querySelector("[data-sim-presence]");
        if (!holder) return;
        const presence = envelope.presence || {};
        holder.innerHTML = `
            <span>P1 <strong>${Number(presence.p1 || 0)}</strong></span>
            <span>P2 <strong>${Number(presence.p2 || 0)}</strong></span>
            <span>${t("관전")} <strong>${Number(presence.viewer || 0)}</strong></span>
        `;
    }

    function passivePayload(side, delta) {
        const keyInput = document.querySelector(`[data-passive-key="${side}"]`);
        const valueInput = document.querySelector(`[data-passive-value="${side}"]`);
        const rawKey = keyInput ? keyInput.value.trim() : "";
        const rawValue = valueInput ? valueInput.value.trim() : "";
        const key = rawKey || rawValue || "memo";
        const payload = { target: side, key, label: key };
        if (delta) payload.delta = delta;
        if (rawValue && !delta) payload.value = rawValue;
        if (rawValue) payload.note = rawValue;
        return payload;
    }

    root.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) {
            const card = event.target.closest("[data-card-open]");
            if (!card) return;
            const cardData = findCard(card.dataset.cardOpen);
            if (!cardData || cardData.hidden) return;
            selectedCardId = card.dataset.cardOpen;
            renderCardDetail();
            return;
        }
        if (button.disabled) return;

        if (button.dataset.cardOpen) {
            const cardData = findCard(button.dataset.cardOpen);
            if (!cardData || cardData.hidden) return;
            selectedCardId = button.dataset.cardOpen;
            renderCardDetail();
            return;
        }

        if (button.dataset.cardDrawerClose !== undefined) {
            selectedCardId = "";
            renderCardDetail();
            return;
        }

        if (button.dataset.logToggle !== undefined) {
            setLogOpen(!logOpen);
            return;
        }

        if (button.dataset.copyLink) {
            const value = button.dataset.copyLink;
            if (navigator.clipboard) {
                navigator.clipboard.writeText(value).then(() => {
                    button.classList.add("is-copied");
                    window.setTimeout(() => button.classList.remove("is-copied"), 1200);
                });
            } else {
                window.prompt(t("링크"), value);
            }
            return;
        }

        if (button.dataset.phase) {
            postAction("set_phase", { phase: button.dataset.phase });
            return;
        }
        if (button.dataset.requestTarget) {
            postAction("request_action", {
                target: button.dataset.requestTarget,
                requested: button.dataset.requestValue === "true",
            });
            return;
        }
        if (button.dataset.doneTarget) {
            postAction("set_done", {
                target: button.dataset.doneTarget,
                done: button.dataset.doneValue === "true",
            });
            return;
        }
        if (button.dataset.counterKind) {
            const kind = button.dataset.counterKind;
            queueCounter(kind, button.dataset.counterTarget, Number(button.dataset.counterAmount || 0));
            return;
        }
        if (button.dataset.fpReset) {
            clearQueuedCounter("fp", button.dataset.fpReset);
            postAction("fp_reset", { target: button.dataset.fpReset });
            return;
        }
        if (button.dataset.bulkPlayer) {
            postAction("bulk_move", {
                player: button.dataset.bulkPlayer,
                from_zone: "battle",
                to_zone: button.dataset.bulkTarget,
            });
            return;
        }
        if (button.dataset.shuffleHandPlayer) {
            const side = button.dataset.shuffleHandPlayer;
            const player = state.players && state.players[side];
            const cards = player && player.zones ? player.zones.hand || [] : [];
            if (cards.length <= 1) return;
            postAction("shuffle_hand", {
                player: side,
                order: shuffledOrder(cards),
            });
            return;
        }
        if (button.dataset.visibilityCard) {
            postAction("set_visibility", {
                card_instance_id: button.dataset.visibilityCard,
                face_up: button.dataset.visibilityValue === "true",
            });
            return;
        }
        if (button.dataset.passiveAction) {
            const side = button.dataset.passiveTarget;
            const delta = button.dataset.passiveAction === "inc" ? Number(button.dataset.passiveDelta || 0) : 0;
            postAction("passive", passivePayload(side, delta));
            return;
        }
        if (button.dataset.passiveNativeTarget) {
            let value = button.dataset.passiveNativeValue;
            let resetKeys = [];
            try {
                value = JSON.parse(value);
            } catch (error) {
                value = button.dataset.passiveNativeValue;
            }
            try {
                resetKeys = JSON.parse(button.dataset.passiveResetKeys || "[]");
            } catch (error) {
                resetKeys = [];
            }
            let chain = postAction("passive", {
                target: button.dataset.passiveNativeTarget,
                key: button.dataset.passiveNativeKey,
                value,
                label: button.dataset.passiveNativeLabel || button.dataset.passiveNativeKey,
            });
            passiveLatchedUpdates(button.dataset.passiveNativeTarget, button.dataset.passiveNativeKey, value).forEach((update) => {
                chain = chain.then(() => postAction("passive", {
                    target: button.dataset.passiveNativeTarget,
                    key: update.key,
                    value: update.value,
                    label: update.label,
                }));
            });
            resetKeys.forEach((key) => {
                chain = chain.then(() => postAction("passive", {
                    target: button.dataset.passiveNativeTarget,
                    key,
                    value: 0,
                    label: key,
                }));
            });
            return;
        }
        if (button.dataset.quickLog) {
            postAction("log_note", { text: button.dataset.quickLog });
            return;
        }
        if (button.dataset.simAction === "manual_log") {
            const input = document.querySelector("[data-manual-log-input]");
            const text = input ? input.value.trim() : "";
            if (!text) return;
            postAction("log_note", { text }).then(() => {
                if (input) input.value = "";
            });
            return;
        }
        if (button.dataset.simAction === "import_card") {
            const input = document.querySelector("[data-card-import-input]");
            const cardName = input ? input.value.trim() : "";
            if (!cardName) return;
            postAction("import_card", { card_name: cardName }).then(() => {
                if (input) input.value = "";
            });
            return;
        }
        if (button.dataset.simAction === "timer") {
            postAction("timer", {});
            return;
        }
        if (button.dataset.simAction === "next_turn") {
            postAction("next_turn", {});
            return;
        }
        if (button.dataset.simAction === "undo") {
            postAction("undo", {});
            return;
        }
        if (button.dataset.fullscreenToggle !== undefined) {
            const target = document.querySelector("[data-lumen-simulator]") || document.documentElement;
            if (!document.fullscreenElement && target.requestFullscreen) {
                target.requestFullscreen().catch(() => {});
            } else if (document.exitFullscreen) {
                document.exitFullscreen().catch(() => {});
            }
        }
    });

    root.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        const cardNode = event.target.closest("[data-card-instance]");
        if (!cardNode) return;
        const card = findCard(cardNode.dataset.cardInstance);
        toggleCardVisibility(card);
    });

    document.addEventListener("click", (event) => {
        if (!selectedCardId) return;
        if (event.target.closest("[data-card-drawer]")) return;
        if (event.target.closest("[data-card-open]")) return;
        selectedCardId = "";
        renderCardDetail();
    });

    root.addEventListener("mouseover", (event) => {
        const target = event.target.closest("[data-card-tooltip]");
        if (!target) return;
        const card = target.dataset.cardOpen ? findCard(target.dataset.cardOpen) : null;
        if (!card || card.hidden) return;
        tooltip.textContent = target.dataset.cardTooltip || cardTitle(card);
        tooltip.classList.add("is-visible");
    });

    root.addEventListener("mousemove", (event) => {
        if (!tooltip.classList.contains("is-visible")) return;
        const offset = 14;
        const width = tooltip.offsetWidth || 220;
        const height = tooltip.offsetHeight || 44;
        const left = Math.min(window.innerWidth - width - 10, event.clientX + offset);
        const top = Math.min(window.innerHeight - height - 10, event.clientY + offset);
        tooltip.style.left = `${Math.max(10, left)}px`;
        tooltip.style.top = `${Math.max(10, top)}px`;
    });

    root.addEventListener("mouseout", (event) => {
        if (!event.target.closest("[data-card-tooltip]")) return;
        tooltip.classList.remove("is-visible");
    });

    root.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        const input = event.target.closest("[data-card-import-input]");
        if (!input || !canControl()) return;
        const cardName = input.value.trim();
        if (!cardName) return;
        event.preventDefault();
        postAction("import_card", { card_name: cardName }).then(() => {
            input.value = "";
        });
    });

    window.addEventListener("resize", scheduleFitCardGrids);
    document.addEventListener("fullscreenchange", scheduleFitCardGrids);

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
            const limit = Number(data.event_limit || envelope.event_limit || SIM_LOG_LIMIT);
            if (limit > 0 && events.length > limit) {
                events.splice(0, events.length - limit);
            }
        }
        eventsLoaded = true;
        envelope.events = events;
        envelope.event_count = Number(data && data.event_count || envelope.event_count || events.length || 0);
        envelope.event_limit = Number(data && data.event_limit || envelope.event_limit || SIM_LOG_LIMIT);
        lastLogSeq = Math.max(lastLogSeq, maxEventSeq(events), Number(envelope.event_count || 0));
        renderLog();
    }

    function fetchState(forceFull) {
        return fetch(stateUrl(forceFull))
            .then((response) => response.json())
            .then((nextEnvelope) => {
                pollingDelayMs = POLLING_INITIAL_DELAY_MS;
                if (nextEnvelope && nextEnvelope.unchanged) {
                    if (nextEnvelope.presence) {
                        envelope.presence = nextEnvelope.presence;
                        renderPresence();
                    }
                    return nextEnvelope;
                }
                const result = updateEnvelope(nextEnvelope);
                if (logOpen && !sendLogSubscription(true)) fetchEvents();
                return result;
            })
            .catch(() => {
                pollingDelayMs = Math.min(POLLING_MAX_DELAY_MS, Math.max(POLLING_INITIAL_DELAY_MS, pollingDelayMs * 2));
                return null;
            });
    }

    function schedulePollingFallback(delay) {
        if (!pollingActive) return;
        window.clearTimeout(pollingTimer);
        pollingTimer = window.setTimeout(() => {
            fetchState().finally(() => {
                if (pollingActive) schedulePollingFallback(pollingDelayMs);
            });
        }, delay);
    }

    function startPollingFallback() {
        if (pollingActive) return;
        pollingActive = true;
        pollingDelayMs = POLLING_INITIAL_DELAY_MS;
        fetchState().finally(() => {
            if (pollingActive) schedulePollingFallback(pollingDelayMs);
        });
    }

    function stopPollingFallback() {
        pollingActive = false;
        if (!pollingTimer) return;
        window.clearTimeout(pollingTimer);
        pollingTimer = null;
    }

    function scheduleDirtyStateFetch(version) {
        const incomingVersion = Number(version || 0);
        const currentVersion = envelopeVersion(envelope);
        if (incomingVersion && currentVersion && incomingVersion < currentVersion) return;
        window.clearTimeout(dirtyStateTimer);
        dirtyStateTimer = window.setTimeout(() => {
            dirtyStateTimer = null;
            fetchState();
        }, DIRTY_STATE_DEBOUNCE_MS);
    }

    function resolveSocketAction(message) {
        if (!message.request_id) return;
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
                if (message.event_count !== undefined) envelope.event_count = Number(message.event_count || 0);
                scheduleDirtyStateFetch(message.version);
                return;
            }
            if (message.type === "log_events") {
                applyLogEvents(message, !!message.reset);
                return;
            }
            if (message.type === "presence" && message.presence) {
                envelope.presence = message.presence;
                renderPresence();
                return;
            }
            if (message.type === "action_ack" || message.type === "error") resolveSocketAction(message);
        });
        socket.addEventListener("close", () => {
            socketReady = false;
            rejectPendingSocketActions(t("시뮬레이터 연결이 끊겼습니다."));
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

    render();
    connectSocket();
    window.setInterval(() => {
        if (socketReady && socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "presence" }));
        }
    }, 30000);
    window.setInterval(renderTimer, 1000);
})();
