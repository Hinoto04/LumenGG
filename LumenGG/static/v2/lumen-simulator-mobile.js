(function () {
    const stateNode = document.getElementById("lumen-simulator-state");
    const i18nNode = document.getElementById("lumen-simulator-i18n");
    const root = document.querySelector("[data-lumen-simulator-mobile]");
    const config = window.lumenSimulatorMobileConfig || {};
    if (!stateNode || !root || !config.stateUrl) return;

    let envelope = JSON.parse(stateNode.textContent);
    let state = envelope.state || {};
    const i18n = i18nNode ? JSON.parse(i18nNode.textContent) : {};

    function dispatchAutomaticClientError(error, context) {
        if (!(config.automaticMode || envelope.mode === "automatic" || envelope.automation_failure)) return;
        const value = error && typeof error === "object" ? error : {};
        window.dispatchEvent(new CustomEvent("lumen-simulator-client-error", {detail: {
            error_type: value.name || "ClientTransportError",
            message: value.message || String(error || "시뮬레이터 통신 오류"),
            source: value.source || value.filename || "",
            line: value.line || value.lineno || 0,
            column: value.column || value.colno || 0,
            stack: value.stack || "",
            context: context || "simulator_transport",
        }}));
    }
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
    let pendingSetCardId = "";
    let selectedCardId = "";
    let automaticEffectDetail = null;
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
    let timerSync = null;
    let pendingTimerTimeoutKey = "";
    let reportedTimerTimeoutKey = "";
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
    const TIMER_DEFAULT_DURATION_SECONDS = 10;

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

    function clampRatio(value) {
        return Math.max(0, Math.min(1, Number(value) || 0));
    }

    function hpToneStyle(player) {
        const initialHp = Number(player && player.initial_hp || 0);
        const ratio = initialHp > 0 ? clampRatio(Number(player && player.hp || 0) / initialHp) : 0.5;
        const hue = Math.round(4 + (ratio * 136));
        return ` style="--mobile-hp-ratio:${ratio.toFixed(3)}; --mobile-hp-percent:${(ratio * 100).toFixed(1)}%; --mobile-hp-hue:${hue}"`;
    }

    function valueSignClass(value) {
        const number = Number(value || 0);
        if (number > 0) return "is-positive";
        if (number < 0) return "is-negative";
        return "is-zero";
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
        const hydrated = hydrateCard(card);
        return String((hydrated && (hydrated.original_type || hydrated.type)) || "");
    }

    function isAttackCard(card) {
        return cardType(card).includes("공격");
    }

    function isDefenseCard(card) {
        return cardType(card).includes("수비");
    }

    function isTechniqueCard(card) {
        const type = cardType(card);
        return ["공격", "수비", "특수"].some((keyword) => type.includes(keyword));
    }

    function isCmykPlayer(side) {
        const character = (((state || {}).players || {})[side] || {}).character || {};
        return String(character.name || "").toUpperCase().includes("CMYK");
    }

    function canSetCmykCard(source, host) {
        if (!source || !host || source.instance_id === host.instance_id) return false;
        if (!canControl() || state.phase !== "ready" || source.owner !== envelope.role) return false;
        if (source.owner !== host.owner || source.zone !== "battle" || host.zone !== "battle") return false;
        if (!isCmykPlayer(source.owner) || !isTechniqueCard(source) || !isTechniqueCard(host)) return false;
        if (host.attached_to) return false;
        const stagedIds = (((state.cmyk_ready_staged_cards || {})[source.owner]) || []).map(String);
        const readyHostId = (state.cmyk_ready_host_cards || {})[source.owner];
        if (stagedIds.length && !stagedIds.includes(String(source.instance_id || ""))) return false;
        if (readyHostId && readyHostId !== host.instance_id) return false;
        const ownedCards = allCards().filter((card) => card.owner === source.owner);
        if (ownedCards.some((card) => card.attached_to === source.instance_id)) return false;
        if (!source.attached_to && ownedCards.filter((card) => card.attached_to).length >= 3) return false;
        return true;
    }

    function autoAttachMobileCmykReadyCards(hostCard, fromZone, toPlayer, toZone, payload) {
        if (
            state.phase !== "ready" || fromZone === "battle" || toZone !== "battle" ||
            !hostCard || hostCard.owner !== toPlayer || !isCmykPlayer(toPlayer) ||
            !isTechniqueCard(hostCard) || hostCard.attached_to
        ) return;
        const hostCards = state.cmyk_ready_host_cards || {};
        if (hostCards[toPlayer]) return;
        const stagedIds = (((state.cmyk_ready_staged_cards || {})[toPlayer]) || []).map(String);
        if (!stagedIds.length || stagedIds.includes(String(hostCard.instance_id || ""))) return;
        const stagedSet = new Set(stagedIds);
        const candidates = ((((state.players || {})[toPlayer] || {}).zones || {}).battle || [])
            .filter((card) => (
                stagedSet.has(String(card.instance_id || "")) && !card.face_up &&
                !card.attached_to && card.owner === toPlayer
            ))
            .slice(0, 3);
        if (!candidates.length) return;
        candidates.forEach((card, index) => {
            card.attached_to = hostCard.instance_id;
            card.attachment_expires = "battle";
            card.return_to_hand_on_attachment_expiry = true;
            card.set_order = index + 1;
            card.face_up = false;
            card.hidden = false;
        });
        state.cmyk_ready_host_cards = { ...hostCards, [toPlayer]: hostCard.instance_id };
        payload.auto_attached_card_instance_ids = candidates.map((card) => card.instance_id);
        payload.auto_attached_count = candidates.length;
        payload.auto_set_host_card_instance_id = hostCard.instance_id;
    }

    function joinPresent(values, separator) {
        return values.filter(hasValue).map((value) => String(value)).join(separator || " / ");
    }

    function effectText(card) {
        if (!card) return "";
        if (hasValue(card.text_label)) return String(card.text_label);
        return hasValue(card.text) ? t(card.text) : "";
    }

    function csrfToken() {
        const input = document.querySelector("[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function cacheMetadata(cards) {
        const cached = {};
        Object.entries(cards || {}).forEach(([cardId, metadata]) => {
            if (!cardId || !metadata || typeof metadata !== "object") return;
            metadataCache.set(String(cardId), metadata);
            cached[String(cardId)] = metadata;
        });
        if (Object.keys(cached).length) {
            window.dispatchEvent(new CustomEvent("lumen-simulator-card-metadata", {
                detail: {cards: cached},
            }));
        }
    }

    function hydrateCard(card) {
        if (!card || card.hidden || !card.card_id) return card;
        const metadata = metadataCache.get(String(card.card_id));
        if (!metadata) return card;
        const hydrated = { ...metadata, ...card };
        // Automatic matches retain Korean ruleset fields in state. Keep those
        // runtime values pinned, but let localized display metadata win.
        if (config.language && config.language !== "ko") {
            ["name", "text", "detail_text"].forEach((field) => {
                if (Object.prototype.hasOwnProperty.call(metadata, field)) {
                    hydrated[field] = metadata[field];
                }
            });
        }
        return hydrated;
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

    function monotonicNow() {
        return window.performance && typeof window.performance.now === "function"
            ? window.performance.now()
            : Date.now();
    }

    function timerDuration(timer) {
        const duration = Number(timer && timer.duration_seconds);
        return Number.isFinite(duration) && duration > 0 ? duration : TIMER_DEFAULT_DURATION_SECONDS;
    }

    function timerKey(timer) {
        if (!timer) return "";
        return `${timer.started_at || ""}:${timer.owner || ""}:${timerDuration(timer)}`;
    }

    function syncTimerFromState() {
        const timer = state.timer || {};
        if (!timer.is_running || !timer.started_at) {
            timerSync = null;
            return;
        }
        const duration = timerDuration(timer);
        const rawRemaining = Number(timer.remaining_seconds);
        const remaining = Number.isFinite(rawRemaining) ? rawRemaining : duration;
        timerSync = {
            key: timerKey(timer),
            duration,
            remaining: Math.max(0, Math.min(duration, remaining)),
            capturedAtMs: monotonicNow(),
        };
    }

    function updateEnvelope(nextEnvelope, options) {
        if (!nextEnvelope || nextEnvelope.unchanged) {
            if (nextEnvelope && nextEnvelope.presence) envelope.presence = nextEnvelope.presence;
            return;
        }
        envelope = nextEnvelope;
        state = envelope.state || {};
        syncTimerFromState();
        if (Array.isArray(envelope.events)) {
            events = envelope.events;
            eventsLoaded = true;
            lastLogSeq = Math.max(lastLogSeq, maxEventSeq(events));
        }
        scheduleMetadataFetch(collectMetadataIds());
        render();
        if (!(options && options.silent)) {
            window.dispatchEvent(new CustomEvent("lumen-simulator-state", { detail: envelope }));
        }
    }

    window.addEventListener("lumen-simulator-apply-state", (event) => {
        const detail = event.detail || {};
        if (!detail.envelope) return;
        updateEnvelope(detail.envelope, {silent: !!detail.optimistic});
    });

    window.addEventListener("lumen-simulator-open-card-detail", (event) => {
        const detail = event.detail || {};
        const instanceId = String(detail.instance_id || "");
        const card = instanceId ? findCard(instanceId) : null;
        if (!card || card.hidden) return;
        openCardDetail(instanceId, detail);
    });

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
            .catch((error) => {
                dispatchAutomaticClientError(error, "state_fetch");
                return null;
            });
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
            .catch((error) => {
                dispatchAutomaticClientError(error, "events_fetch");
                return null;
            });
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

    function timerRemaining() {
        const timer = state.timer || {};
        const duration = timerDuration(timer);
        if (timer.is_running && timer.started_at) {
            const key = timerKey(timer);
            if (!timerSync || timerSync.key !== key) syncTimerFromState();
            if (timerSync) {
                const elapsed = Math.max(0, (monotonicNow() - timerSync.capturedAtMs) / 1000);
                return Math.max(0, Math.min(timerSync.duration, Math.ceil(timerSync.remaining - elapsed)));
            }
        }
        return Math.max(0, Math.min(duration, Number(timer.remaining_seconds ?? duration) || 0));
    }

    function timerColor(progress) {
        const start = [37, 99, 235];
        const end = [220, 38, 38];
        return start.map((value, index) => Math.round(value + (end[index] - value) * progress));
    }

    function timerProgress(remaining) {
        const duration = timerDuration(state.timer || {});
        if (!duration) return 0;
        return Math.max(0, Math.min(1, (duration - remaining) / duration));
    }

    function ensureTimerCountdown() {
        let countdown = document.querySelector("[data-mobile-timer-countdown]");
        if (!countdown) {
            countdown = document.createElement("div");
            countdown.className = "v2-mobile-timer-countdown";
            countdown.dataset.mobileTimerCountdown = "true";
            countdown.setAttribute("aria-hidden", "true");
            document.body.appendChild(countdown);
        }
        return countdown;
    }

    function updateTimerPresentation(remaining, active) {
        const progress = timerProgress(remaining);
        const color = timerColor(progress);
        document.body.style.setProperty("--v2-mobile-timer-rgb", color.join(", "));
        document.body.style.setProperty("--v2-mobile-timer-progress", progress.toFixed(3));
        document.body.classList.toggle("v2-mobile-timer-active", active);
        root.classList.toggle("is-timer-active", active);

        const countdown = ensureTimerCountdown();
        countdown.textContent = String(remaining);
        countdown.classList.toggle("is-visible", active);
        countdown.classList.toggle("is-urgent", active && remaining <= 3);
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
        const timerNode = document.querySelector("[data-mobile-timer]");
        const timerBox = document.querySelector("[data-mobile-timer-box]");
        const remaining = timerRemaining();
        const timerActive = !!(state.timer && state.timer.is_running && remaining > 0);
        if (timerNode) timerNode.textContent = String(remaining);
        if (timerBox) {
            timerBox.classList.toggle("is-active", timerActive);
            timerBox.classList.toggle("is-danger", timerActive && remaining <= 3);
        }
        updateTimerPresentation(remaining, timerActive);
        maybeReportTimerTimeout(remaining);
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
            const preserveAttachment = (
                location.zone === toZone ||
                (state.phase === "battle" && location.zone === "battle" && toZone === "list")
            );
            if (!preserveAttachment) {
                delete location.card.attached_to;
                delete location.card.attachment_expires;
                delete location.card.return_to_hand_on_attachment_expiry;
                delete location.card.set_order;
            }
            location.card.zone = toZone;
            location.card.zone_owner = toPlayer;
            state.players[toPlayer].zones[toZone].push(location.card);
            autoAttachMobileCmykReadyCards(
                hydrateCard(location.card), location.zone, toPlayer, toZone, localPayload,
            );
            localPayload.from_player = location.playerSide;
            localPayload.from_zone = location.zone;
            localPayload.to_player = toPlayer;
            localPayload.card_label = cardName({ ...location.card, hidden: false });
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "attach_card") {
            const source = findCardLocation(state, localPayload.card_instance_id);
            const host = findCardLocation(state, localPayload.host_card_instance_id);
            if (!source || !host || source.playerSide !== envelope.role || host.playerSide !== envelope.role) return false;
            if (source.zone !== "battle" || host.zone !== "battle" || state.phase !== "ready") return false;
            const attached = allCards().filter((card) => card.attached_to === host.card.instance_id);
            source.card.attached_to = host.card.instance_id;
            source.card.attachment_expires = "battle";
            source.card.return_to_hand_on_attachment_expiry = true;
            source.card.set_order = Math.max(0, ...attached.map((card) => Number(card.set_order || 0))) + 1;
            source.card.face_up = false;
            source.card.hidden = false;
            localPayload.card_label = cardName({ ...source.card, hidden: false });
            localPayload.host_card_label = cardName({ ...host.card, hidden: false });
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

    const PASSIVE_UI_KEY_ALIASES = {
        root_charge: ["charge"],
        notice: ["advance_notice"],
        silver_counter: ["hidden_bond"],
        yang_counter: ["yang"],
        yin_counter: ["yin"],
        foresight_counter: ["foresight"],
        ember_token: ["ember"],
        howling_counter: ["howling"],
    };

    function passiveEntry(passiveState, key) {
        const aliases = PASSIVE_UI_KEY_ALIASES[String(key)] || [];
        const matchedAlias = aliases.find((alias) => Object.prototype.hasOwnProperty.call(passiveState, alias));
        return passiveState[matchedAlias || String(key)] || {};
    }

    function passiveEntryValue(passiveState, key, fallback) {
        const entry = passiveEntry(passiveState, key);
        if (entry.value !== undefined) return entry.value;
        if (entry.count !== undefined) return entry.count;
        return fallback;
    }

    function passiveDisplayLabel(key, entry) {
        return entry.display_label || t(entry.label || key);
    }

    function configuredPassiveKeys(passiveUi, options) {
        const keys = new Set((passiveUi.managed_keys || []).map(String));
        [
            ...(options.controls || []),
            ...(options.badges || []),
            ...(options.latchedStatuses || []),
        ].forEach((item) => {
            if (!item || !item.key) return;
            keys.add(String(item.key));
            (PASSIVE_UI_KEY_ALIASES[String(item.key)] || []).forEach((key) => keys.add(key));
        });
        return keys;
    }

    function genericPassiveMarkup(entries) {
        return entries.map(([key, entry]) => {
            const raw = entry.value !== undefined ? entry.value : entry.count ?? "";
            const value = typeof raw === "boolean" ? (raw ? t("활성") : t("비활성")) : raw;
            const typeClass = entry.count !== undefined ? "is-counter" : "is-status";
            const activeClass = entry.value === true ? "is-active" : "";
            return `
                <div class="v2-mobile-passive-native ${typeClass} ${activeClass}">
                    <span>${escapeHtml(passiveDisplayLabel(key, entry))}</span>
                    <strong>${escapeHtml(value)}</strong>
                </div>
            `;
        }).join("");
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

    function renderCounterPanel(side, kind, value, player) {
        if (kind === "hp") {
            return `
                <div class="v2-mobile-hp"${hpToneStyle(player)}>
                    ${counterButton(side, "hp", -100, "-")}
                    <div class="v2-mobile-counter-value">${escapeHtml(Number(value || 0))}${counterDelta(side, "hp")}${counterPending(side, "hp")}</div>
                    ${counterButton(side, "hp", 100, "+")}
                </div>
            `;
        }
        return `
            <div class="v2-mobile-fp">
                ${counterButton(side, "fp", 1, "+")}
                <button class="v2-mobile-counter-value ${valueSignClass(value)}" type="button" data-mobile-fp-reset="${side}">${escapeHtml(formatSigned(value || 0))} FP${counterDelta(side, "fp")}${counterPending(side, "fp")}</button>
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

    function renderMobileBattleCards(cards) {
        const boardKey = (card) => card.instance_id || card.board_key || "";
        const attachmentKey = (card) => card.attached_to || card.attached_to_board_key || "";
        const cardById = new Map((cards || []).map((card) => [boardKey(card), card]));
        const host = (cards || []).find((card) => !attachmentKey(card) || !cardById.has(attachmentKey(card)));
        if (!host) return "";
        const setCards = (cards || [])
            .filter((card) => attachmentKey(card) === boardKey(host))
            .sort((left, right) => Number(left.set_order || 0) - Number(right.set_order || 0));
        if (!setCards.length) return renderMiniCard(host);
        return `
            <div class="v2-mobile-card-set-group">
                ${renderMiniCard(host)}
                <div class="v2-mobile-card-set-cards" aria-label="${escapeHtml(t("세트된 카드"))}">
                    ${setCards.map(renderMiniCard).join("")}
                </div>
            </div>
        `;
    }

    function passiveSummary(player) {
        const entries = Object.entries(player.passive_state || {});
        const chips = [];
        entries.forEach(([key, entry]) => {
            const raw = entry.value !== undefined ? entry.value : entry.count ?? "";
            const value = typeof raw === "boolean" ? (raw ? t("활성") : t("비활성")) : raw;
            chips.push(`<span class="v2-mobile-passive-chip">${escapeHtml(passiveDisplayLabel(key, entry))} ${escapeHtml(value)}</span>`);
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
            const label = control.label || passiveDisplayLabel(control.key, passiveEntry(passiveState, control.key));
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
            const label = badge.label || (badge.key ? passiveDisplayLabel(badge.key, passiveEntry(passiveState, badge.key)) : t("패시브"));
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
        const configuredKeys = configuredPassiveKeys(passiveUi, options);
        const genericEntries = Object.entries(passiveState).filter(([key]) => !configuredKeys.has(key));
        const controlsNode = document.createElement("div");
        controlsNode.className = "v2-mobile-passive-controls";
        if (hasPassiveControls(options)) {
            renderNativePassiveControls(side, controlsNode, options, passiveState, player);
        } else if (passiveUi.html || passiveUi.css || passiveUi.js) {
            controlsNode.classList.add("has-custom-passive");
            renderCustomPassiveUi(side, controlsNode, passiveUi);
        } else {
            controlsNode.innerHTML = genericEntries.length ? genericPassiveMarkup(genericEntries) : passiveSummary(player);
        }
        if ((hasPassiveControls(options) || passiveUi.html || passiveUi.css || passiveUi.js) && genericEntries.length) {
            const genericNode = document.createElement("div");
            genericNode.className = "v2-mobile-passive-generic";
            genericNode.innerHTML = genericPassiveMarkup(genericEntries);
            controlsNode.appendChild(genericNode);
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
            ? renderMobileBattleCards(battleCards)
            : `<button class="v2-mobile-battle-open" type="button" data-mobile-open-zone="battle" data-mobile-zone-side="${side}">BT</button>`;
        const zoneButtons = mobileZones.map((zone) => {
            const count = cardsFor(side, zone).length;
            return `<button class="v2-mobile-zone-button" type="button" data-mobile-open-zone="${zone}" data-mobile-zone-side="${side}">${zoneCodes[zone]} <span>${count}</span></button>`;
        }).join("");
        return `
            <section class="v2-mobile-player is-${position}${statusClass}" data-mobile-player="${side}">
                <div class="v2-mobile-player-name">${escapeHtml(playerLabel(side))} ${escapeHtml(player.name || "")}</div>
                ${renderCounterPanel(side, "hp", player.hp, player)}
                <div class="v2-mobile-combat-line is-${position}">
                    ${position === "left" ? renderCounterPanel(side, "fp", player.fp, player) : ""}
                    <div class="v2-mobile-battle">
                        <div class="v2-mobile-battle-cards">${battleHtml}</div>
                    </div>
                    ${position === "right" ? renderCounterPanel(side, "fp", player.fp, player) : ""}
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
        let moves = canControl() && card.kind !== "character"
            ? (moveTargets[card.zone] || []).slice(0, 4).map((toZone) => {
                const toPlayer = targetPlayerForMove(card.zone_owner, card, toZone);
                return `<button type="button" data-mobile-move-card="${escapeHtml(card.instance_id)}" data-mobile-to-player="${toPlayer}" data-mobile-to-zone="${toZone}">${zoneCodes[toZone]}</button>`;
            }).join("")
            : "";
        if (
            modalZone === "battle" && state.phase === "ready" &&
            hydrated.owner === envelope.role && isCmykPlayer(hydrated.owner) &&
            isTechniqueCard(hydrated)
        ) {
            const source = pendingSetCardId ? findCard(pendingSetCardId) : null;
            if (!source || source.instance_id === hydrated.instance_id) {
                const label = source ? t("세트 선택 취소") : t("세트 카드 선택");
                moves += `<button type="button" data-mobile-set-source="${escapeHtml(hydrated.instance_id)}">${escapeHtml(label)}</button>`;
            } else if (canSetCmykCard(source, hydrated)) {
                moves += `<button type="button" data-mobile-set-host="${escapeHtml(hydrated.instance_id)}">${escapeHtml(t("여기에 세트"))}</button>`;
            }
        }
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
        const automaticDetail = automaticEffectDetail || {};
        const automaticPrompt = String(automaticDetail.effect_prompt || automaticDetail.option_label || "").trim();
        const automaticOption = String(automaticDetail.option_label || "").trim();
        const automaticSequence = Array.isArray(automaticDetail.sequence_labels)
            ? automaticDetail.sequence_labels.map(String).filter(Boolean)
            : [];
        const showAutomaticEffect = String(automaticDetail.instance_id || "") === String(card.instance_id || "")
            && (automaticPrompt || automaticOption || automaticSequence.length > 1);
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
            ${showAutomaticEffect ? `
                <section class="v2-automatic-card-detail-effect" aria-live="polite">
                    <span>현재 처리할 효과</span>
                    ${automaticPrompt ? `<strong>${escapeHtml(automaticPrompt)}</strong>` : ""}
                    ${automaticOption && automaticOption !== automaticPrompt ? `<p>${escapeHtml(automaticOption)}</p>` : ""}
                    ${automaticSequence.length > 1 ? `<small>사용 순서: ${escapeHtml(automaticSequence.join(" → "))}</small>` : ""}
                </section>
            ` : ""}
            <section class="v2-mobile-card-detail-text">${details.join("")}</section>
        `;
        modal.hidden = false;
    }

    function openCardDetail(instanceId, effectDetail) {
        const card = hydrateCard(findCard(instanceId));
        if (!card || card.hidden) return;
        selectedCardId = instanceId || "";
        automaticEffectDetail = effectDetail || null;
        if (card.card_id && !metadataCache.has(String(card.card_id))) {
            scheduleMetadataFetch([String(card.card_id)]);
        }
        renderCardDetail();
    }

    function closeCardDetail() {
        selectedCardId = "";
        automaticEffectDetail = null;
        renderCardDetail();
    }

    function eventLabel(event) {
        const payload = event.payload || {};
        const actor = playerLabel(event.actor);
        if (event.type === "battle_revealed") {
            const readyCard = (side) => {
                const card = payload[side] || {};
                return card.card_label || card.card_code || t("카드");
            };
            return `${t("레디 공개")} - ${playerLabel("p1")}: ${readyCard("p1")} / ${playerLabel("p2")}: ${readyCard("p2")}`;
        }
        if (event.type === "card_readied") {
            return `${actor} ${payload.card_label || payload.card_code || t("카드")} ${t("레디 선택")}`;
        }
        if (event.type === "decision_resolved") {
            const selected = (payload.selected_options || [])
                .map((option) => option && (option.label || option.id))
                .filter(Boolean)
                .join(", ");
            const result = selected || t("선택하지 않음");
            return `${actor} ${payload.prompt || t("효과 선택")}: ${result}`;
        }
        if (event.type === "card_moved") {
            const from = payload.from_player ? `${playerLabel(payload.from_player)} ${zoneLabel(payload.from_zone)}` : zoneLabel(payload.from_zone);
            const to = payload.to_player ? `${playerLabel(payload.to_player)} ${zoneLabel(payload.to_zone)}` : zoneLabel(payload.to_zone);
            return `${actor} ${payload.card_label || payload.card_code || t("카드")}: ${from} -> ${to}`;
        }
        if (event.type === "card_visibility_changed") {
            const revealed = payload.face_up ? t("공개") : t("비공개");
            return `${actor} ${payload.card_label || (payload.card || {}).name || t("카드")} ${revealed}`;
        }
        if (event.type === "move_card") {
            const from = payload.from_player ? `${playerLabel(payload.from_player)} ${zoneLabel(payload.from_zone)}` : zoneLabel(payload.from_zone);
            const to = payload.to_player ? `${playerLabel(payload.to_player)} ${zoneLabel(payload.to_zone)}` : zoneLabel(payload.to_zone);
            const autoSet = Number(payload.auto_attached_count || 0) > 0
                ? ` / ${payload.auto_attached_count}${t("장")} ${t("자동 세트")}`
                : "";
            return `${actor} ${payload.card_label || t("카드")}: ${from} -> ${to}${autoSet}`;
        }
        if (event.type === "attach_card") return `${actor} ${payload.card_label || t("카드")} -> ${payload.host_card_label || t("카드")} ${t("세트")}`;
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

    function eventPresentation(event) {
        const formatter = window.LumenSimulatorLogFormatter;
        if (
            (config.automaticMode || envelope.mode === "automatic")
            && formatter && typeof formatter.format === "function"
        ) {
            return formatter.format(event, {
                t,
                playerLabel,
                zoneLabel,
                phaseLabel,
                formatSigned,
            });
        }
        return {
            summary: t(eventLabel(event)),
            category: "",
            detail: "",
            tone: "",
            major: false,
            hidden: false,
        };
    }

    function eventRelatedSide(event) {
        const payload = event.payload || {};
        if (["set_phase", "phase_advance", "next_turn"].includes(event.type)) return "";
        if (["request_action", "set_done", "hp", "fp", "fp_reset", "passive", "timer_timeout"].includes(event.type)) return payload.target || payload.owner || "";
        if (event.type === "bulk_move" || event.type === "shuffle_hand") return payload.player || "";
        if (event.type === "set_hand_visibility") return payload.target || "";
        if (["move_card", "card_moved", "attach_card"].includes(event.type)) return payload.owner || event.actor || payload.to_player || payload.from_player || "";
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
        const formatter = window.LumenSimulatorLogFormatter;
        const preparedEvents = (
            (config.automaticMode || envelope.mode === "automatic")
            && formatter && typeof formatter.prepare === "function"
        ) ? formatter.prepare(events) : events;
        const visibleEvents = preparedEvents
            .map((event) => ({ event, presentation: eventPresentation(event) }))
            .filter((item) => !item.presentation.hidden);
        if (!visibleEvents.length) {
            const empty = document.createElement("p");
            empty.className = "v2-mobile-empty";
            empty.textContent = t("표시할 기록이 없습니다.");
            holder.appendChild(empty);
            return;
        }
        visibleEvents.forEach(({ event, presentation }) => {
            const row = document.createElement("div");
            row.className = `v2-mobile-log-row ${logAlignmentClass(event)}${event.optimistic ? " is-optimistic" : ""}`;
            if (presentation.major) row.classList.add("is-major-log");
            if (presentation.tone) row.classList.add(`is-${presentation.tone}-log`);
            if (presentation.category) {
                const category = document.createElement("span");
                category.className = "v2-mobile-log-category";
                category.textContent = presentation.category;
                row.appendChild(category);
            }
            const summary = document.createElement("strong");
            summary.textContent = presentation.summary;
            row.appendChild(summary);
            if (presentation.detail) {
                const detail = document.createElement("small");
                detail.className = "v2-mobile-log-detail";
                detail.textContent = presentation.detail;
                row.appendChild(detail);
            }
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
        renderTimer();
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
                dispatchAutomaticClientError(error, "websocket_message_parse");
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

    function fullscreenElement() {
        return document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.msFullscreenElement ||
            null;
    }

    function callFullscreenMethod(context, method) {
        if (!method) return Promise.reject(new Error(t("전체화면을 사용할 수 없습니다.")));
        try {
            const result = method.call(context);
            return result && typeof result.then === "function" ? result : Promise.resolve(result);
        } catch (error) {
            return Promise.reject(error);
        }
    }

    function updateFullscreenButton() {
        const button = document.querySelector("[data-mobile-fullscreen-toggle]");
        if (!button) return;
        const active = !!fullscreenElement();
        button.classList.toggle("is-active", active);
        const label = active ? t("전체화면 종료") : t("전체화면");
        button.setAttribute("aria-label", label);
        button.title = label;
    }

    function toggleMobileFullscreen() {
        if (fullscreenElement()) {
            return callFullscreenMethod(document, document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen)
                .catch(() => showToast(t("전체화면을 사용할 수 없습니다.")))
                .finally(updateFullscreenButton);
        }
        const target = document.documentElement;
        return callFullscreenMethod(target, target.requestFullscreen || target.webkitRequestFullscreen || target.msRequestFullscreen)
            .catch(() => showToast(t("전체화면을 사용할 수 없습니다.")))
            .finally(updateFullscreenButton);
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
        const fullscreenToggle = event.target.closest("[data-mobile-fullscreen-toggle]");
        if (fullscreenToggle) {
            event.preventDefault();
            toggleMobileFullscreen();
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
        const setSource = event.target.closest("[data-mobile-set-source]");
        if (setSource) {
            const instanceId = setSource.dataset.mobileSetSource || "";
            pendingSetCardId = pendingSetCardId === instanceId ? "" : instanceId;
            renderModal();
            if (pendingSetCardId) showToast(t("세트할 대상 기술을 선택하세요."));
            return;
        }
        const setHost = event.target.closest("[data-mobile-set-host]");
        if (setHost && pendingSetCardId) {
            const sourceId = pendingSetCardId;
            pendingSetCardId = "";
            postAction("attach_card", {
                card_instance_id: sourceId,
                host_card_instance_id: setHost.dataset.mobileSetHost,
            }).then(() => renderModal());
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
    updateFullscreenButton();
    window.addEventListener("lumen-simulator-refresh-request", () => fetchState(true));
    window.setInterval(renderTimer, 1000);
    window.addEventListener("resize", schedulePassiveHeightSync);
    document.addEventListener("fullscreenchange", updateFullscreenButton);
    document.addEventListener("webkitfullscreenchange", updateFullscreenButton);
    document.addEventListener("MSFullscreenChange", updateFullscreenButton);
    window.addEventListener("beforeunload", () => {
        if (passiveHeightFrame) window.cancelAnimationFrame(passiveHeightFrame);
        if (actionBatchTimer) window.clearTimeout(actionBatchTimer);
        stopPollingFallback();
        if (socket) socket.close();
    });
}());
