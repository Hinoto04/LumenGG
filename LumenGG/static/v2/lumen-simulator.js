(function () {
    const stateNode = document.getElementById("lumen-simulator-state");
    const i18nNode = document.getElementById("lumen-simulator-i18n");
    const root = document.querySelector("[data-lumen-simulator]");
    const config = window.lumenSimulatorConfig || {};
    if (!stateNode || !root || !config.stateUrl) return;

    let envelope = JSON.parse(stateNode.textContent);
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
    const ACTION_BATCH_DELAY_MS = 500;
    const SOCKET_ACTION_TIMEOUT_MS = 15000;
    const DIRTY_STATE_DEBOUNCE_MS = 700;
    const SIM_LOG_LIMIT = 150;
    const TIMER_DEFAULT_DURATION_SECONDS = 10;
    const POLLING_INITIAL_DELAY_MS = 10000;
    const POLLING_MAX_DELAY_MS = 30000;
    const HAND_SHUFFLE_COOLDOWN_MS = 3000;
    const CARD_SIZE_STORAGE_KEY = "lumengg.simulator.cardSize";
    const CARD_ACTIONS_MIN_VISIBLE_PX = 52;
    const CARD_ACTIONS_MIN_VISIBLE_RATIO = 0.68;
    const CARD_SIZE_PRESETS = [
        { key: "xsmall", label: "최소", width: 68, height: 96, uiFont: 11, smallFont: 10, strongFont: 14, controlHeight: 24, gap: 4, padY: 3, padX: 6, guideHeight: 32 },
        { key: "small", label: "작게", width: 76, height: 107, uiFont: 12, smallFont: 10, strongFont: 15, controlHeight: 26, gap: 5, padY: 4, padX: 7, guideHeight: 34 },
        { key: "default", label: "기본", width: 84, height: 118, uiFont: 12, smallFont: 11, strongFont: 16, controlHeight: 28, gap: 6, padY: 5, padX: 8, guideHeight: 36 },
        { key: "large", label: "크게", width: 94, height: 132, uiFont: 13, smallFont: 11, strongFont: 17, controlHeight: 30, gap: 7, padY: 6, padX: 9, guideHeight: 40 },
        { key: "xlarge", label: "최대", width: 104, height: 146, uiFont: 14, smallFont: 12, strongFont: 18, controlHeight: 32, gap: 8, padY: 7, padX: 10, guideHeight: 44 },
    ];
    const CARD_SIZE_DEFAULT_INDEX = 2;
    const CARD_SIZE_FHD_INDEX = 0;
    const CARD_SIZE_QHD_INDEX = 3;
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
    let shuffleCooldownTimer = null;
    let realtimeToastTimer = null;
    let realtimeToastMessage = "";
    let realtimeToastCount = 0;
    let selectedLogCard = null;
    let draggedCardInstanceId = "";
    let lastPhaseOverlayKey = `${state.turn || 1}:${state.phase || ""}`;
    let lastSignalOverlayKey = "";
    let timerSync = null;
    let cardSizeIndex = CARD_SIZE_DEFAULT_INDEX;
    const tooltip = document.createElement("div");
    const pendingSocketActions = new Map();
    const pendingCounters = {
        hp: new Map(),
        fp: new Map(),
    };

    const phases = ["lumen", "ready", "battle", "get", "recovery"];
    const zones = ["ultimate", "lumen", "battle", "hand", "list", "side", "break"];
    const visibilityToggleZones = new Set(["hand", "side", "battle", "lumen"]);
    const cardEffectLabels = {
        blackout: "암전",
        specialBreak: "브레이크",
        specialLumen: "루멘",
        gwiseomSide: "사이드",
        tokenDelete: "삭제",
    };
    const phaseGuideLabels = {
        lumen: "루멘 페이즈에 처리할 효과를 처리하세요",
        ready: "기술을 배틀 존에 레디하세요",
        battle: "상대와의 배틀 결과를 처리하세요",
        get: "리스트에서 기술을 획득하세요",
        recovery: "리커버리 페이즈에 처리할 효과를 처리하세요",
    };
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

    function clampCardSizeIndex(index) {
        const next = Number(index);
        if (!Number.isFinite(next)) return CARD_SIZE_DEFAULT_INDEX;
        return Math.max(0, Math.min(CARD_SIZE_PRESETS.length - 1, Math.round(next)));
    }

    function initialCardSizeIndexForViewport() {
        const width = Math.max(
            Number(window.innerWidth || 0),
            Number(document.documentElement && document.documentElement.clientWidth || 0)
        );
        const height = Math.max(
            Number(window.innerHeight || 0),
            Number(document.documentElement && document.documentElement.clientHeight || 0)
        );
        if (width >= 2300 && height >= 1200) return CARD_SIZE_QHD_INDEX;
        if (width >= 1700 && height >= 850) return CARD_SIZE_FHD_INDEX;
        return CARD_SIZE_DEFAULT_INDEX;
    }

    function loadCardSizeSetting() {
        try {
            const stored = window.localStorage && window.localStorage.getItem(CARD_SIZE_STORAGE_KEY);
            const storedIndex = CARD_SIZE_PRESETS.findIndex((preset) => preset.key === stored);
            cardSizeIndex = storedIndex >= 0 ? storedIndex : initialCardSizeIndexForViewport();
        } catch (error) {
            cardSizeIndex = initialCardSizeIndexForViewport();
        }
    }

    function renderCardSizeControls() {
        const preset = CARD_SIZE_PRESETS[cardSizeIndex] || CARD_SIZE_PRESETS[CARD_SIZE_DEFAULT_INDEX];
        document.querySelectorAll("[data-card-size-label]").forEach((node) => {
            node.textContent = t(preset.label);
        });
        document.querySelectorAll("[data-card-size-step]").forEach((button) => {
            const step = Number(button.dataset.cardSizeStep || 0);
            button.disabled = (step < 0 && cardSizeIndex <= 0) || (step > 0 && cardSizeIndex >= CARD_SIZE_PRESETS.length - 1);
        });
    }

    function applyCardSizeSetting() {
        const preset = CARD_SIZE_PRESETS[cardSizeIndex] || CARD_SIZE_PRESETS[CARD_SIZE_DEFAULT_INDEX];
        root.style.setProperty("--sim-card-width-setting", `${preset.width}px`);
        root.style.setProperty("--sim-card-height-setting", `${preset.height}px`);
        root.style.setProperty("--sim-ui-font-size", `${preset.uiFont}px`);
        root.style.setProperty("--sim-ui-small-font-size", `${preset.smallFont}px`);
        root.style.setProperty("--sim-ui-strong-font-size", `${preset.strongFont}px`);
        root.style.setProperty("--sim-ui-control-height", `${preset.controlHeight}px`);
        root.style.setProperty("--sim-ui-gap", `${preset.gap}px`);
        root.style.setProperty("--sim-ui-pad-y", `${preset.padY}px`);
        root.style.setProperty("--sim-ui-pad-x", `${preset.padX}px`);
        root.style.setProperty("--sim-phase-guide-height", `${preset.guideHeight}px`);
        root.dataset.cardSize = preset.key;
        renderCardSizeControls();
        scheduleFitCardGrids();
    }

    function setCardSizeIndex(index) {
        cardSizeIndex = clampCardSizeIndex(index);
        try {
            if (window.localStorage) window.localStorage.setItem(CARD_SIZE_STORAGE_KEY, CARD_SIZE_PRESETS[cardSizeIndex].key);
        } catch (error) {
            // Local display settings are optional.
        }
        applyCardSizeSetting();
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

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    }

    function playerLabel(side) {
        if (side !== "p1" && side !== "p2") return t("관전");
        const base = side === "p1" ? "P1" : "P2";
        if (envelope.role === side) return `${base}(${t("자신")})`;
        if (["p1", "p2"].includes(envelope.role)) return `${base}(${t("상대")})`;
        return base;
    }

    function zoneLabel(zone) {
        return (envelope.zone_labels && envelope.zone_labels[zone]) || zone;
    }

    function phaseLabel(phase) {
        return (envelope.phase_labels && envelope.phase_labels[phase]) || phase;
    }

    function phaseGuideText(phase) {
        return t(phaseGuideLabels[phase] || "");
    }

    function signalLabel(signal, fallback) {
        const labels = {
            effect: "효과 발동",
            combo: "콤보 타임",
            catch: "캐치 타임",
        };
        return t(fallback || labels[signal] || signal || "신호");
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

    function clampRatio(value) {
        return Math.max(0, Math.min(1, Number(value) || 0));
    }

    function hpToneStyle(player) {
        const initialHp = Number(player && player.initial_hp || 0);
        const ratio = initialHp > 0 ? clampRatio(Number(player && player.hp || 0) / initialHp) : 0.5;
        const hue = Math.round(4 + (ratio * 136));
        return ` style="--sim-hp-ratio:${ratio.toFixed(3)}; --sim-hp-percent:${(ratio * 100).toFixed(1)}%; --sim-hp-hue:${hue}"`;
    }

    function valueSignClass(value) {
        const number = Number(value || 0);
        if (number > 0) return "is-positive";
        if (number < 0) return "is-negative";
        return "is-zero";
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
        const hydrated = hydrateCard(card);
        return String((hydrated && (hydrated.original_type || hydrated.type)) || "");
    }

    function isAttackCard(card) {
        return cardType(card).includes("공격");
    }

    function isDefenseCard(card) {
        return cardType(card).includes("수비");
    }

    function isSpecialCard(card) {
        return cardType(card).includes("특수");
    }

    function isPassiveCard(card) {
        const code = String((card && card.code) || "").toUpperCase();
        return code.includes("PS") || cardType(card).includes("특성");
    }

    function isTechniqueCard(card) {
        if (isPassiveCard(card)) return false;
        const type = cardType(card);
        return ["공격", "수비", "특수"].some((keyword) => type.includes(keyword));
    }

    function isTokenCard(card) {
        return !!(card && (card.kind === "token" || cardType(card).includes("토큰")));
    }

    function joinPresent(values, separator) {
        return values.filter(hasValue).map((value) => String(value)).join(separator || " / ");
    }

    function effectText(card) {
        if (!card) return "";
        if (hasValue(card.text_label)) return String(card.text_label);
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

    function cardDisplayName(card) {
        const hydrated = hydrateCard(card);
        if (!hydrated || hydrated.hidden) return t("비공개 카드");
        return hydrated.name || t("카드");
    }

    function originalCardName(card) {
        const hydrated = hydrateCard(card);
        return String((hydrated && (hydrated.original_name || hydrated.name)) || "");
    }

    function isBlackoutCard(card) {
        return originalCardName(card).includes("블랙아웃");
    }

    function isGwiseomCard(card) {
        return originalCardName(card).includes("귀섬");
    }

    function canUseBlackoutAction(card) {
        return !!(
            card &&
            canControl() &&
            envelope.role === card.owner &&
            card.face_up &&
            !String(card.instance_id || "").startsWith("log-") &&
            isBlackoutCard(card)
        );
    }

    function canUseCardEffectAction(card) {
        return !!(
            card &&
            canControl() &&
            envelope.role === card.owner &&
            !card.hidden &&
            card.kind !== "character" &&
            !String(card.instance_id || "").startsWith("log-")
        );
    }

    function cardEffectActions(card) {
        card = hydrateCard(card);
        const actions = [];
        if (canUseBlackoutAction(card)) {
            actions.push({
                key: "blackout",
                label: cardEffectLabels.blackout,
                tool: "blackout_random_get",
                tone: "dark",
            });
        }
        if (!canUseCardEffectAction(card)) return actions;
        const gwiseom = isGwiseomCard(card);
        if (isSpecialCard(card) && card.zone === "lumen") {
            actions.push({
                key: "special_break",
                label: cardEffectLabels.specialBreak,
                tool: "move_card",
                toZone: "break",
                tone: "danger",
            });
        }
        if (gwiseom && card.zone === "lumen") {
            actions.push({
                key: "gwiseom_side",
                label: cardEffectLabels.gwiseomSide,
                tool: "move_card",
                toZone: "side",
                tone: "primary",
            });
        }
        if ((isSpecialCard(card) || gwiseom) && card.zone === "side") {
            actions.push({
                key: gwiseom ? "gwiseom_lumen" : "special_lumen",
                label: cardEffectLabels.specialLumen,
                tool: "move_card",
                toZone: "lumen",
                tone: "primary",
            });
        }
        if (isTokenCard(card)) {
            actions.push({
                key: "token_delete",
                label: cardEffectLabels.tokenDelete,
                tool: "move_card",
                toZone: "break",
                tone: "danger",
            });
        }
        return actions;
    }

    function renderCardEffectButtons(card, compact) {
        const actions = cardEffectActions(card);
        if (!actions.length) return "";
        const className = compact ? "v2-sim-card-effects" : "v2-sim-card-detail-actions";
        const buttons = actions.map((action) => {
            const moveAttrs = action.tool === "move_card"
                ? ` data-target-player="${escapeHtml(card.owner || envelope.role || "")}" data-target-zone="${escapeHtml(action.toZone || "")}"`
                : "";
            const toneClass = action.tone ? ` is-${action.tone}` : "";
            const buttonClass = compact ? `v2-sim-card-effect-button${toneClass}` : "v2-button";
            return `<button class="${buttonClass}" type="button" data-card-effect="${escapeHtml(action.key)}" data-card-tool="${escapeHtml(action.tool)}" data-source-card="${escapeHtml(card.instance_id)}"${moveAttrs} aria-label="${escapeHtml(t(action.label))}">${escapeHtml(t(action.label))}</button>`;
        }).join("");
        return `<div class="${className}">${buttons}</div>`;
    }

    function collectKnownCardIds() {
        const ids = new Set();
        Object.values((state && state.players) || {}).forEach((player) => {
            Object.values((player && player.zones) || {}).forEach((cards) => {
                (cards || []).forEach((card) => {
                    if (!card || !card.card_id) return;
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

    function ensureKnownCardMetadata() {
        scheduleCardMetadataFetch(collectKnownCardIds());
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

    function isCmykPlayer(side) {
        const character = (((state || {}).players || {})[side] || {}).character || {};
        return String(character.name || "").toUpperCase().includes("CMYK");
    }

    function canAttachCmykCard(source, host) {
        if (!source || !host || source.instance_id === host.instance_id) return false;
        if (!canControl() || state.phase !== "ready" || envelope.role !== source.owner) return false;
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

    function selectCardInstance(instanceId) {
        selectedCardId = instanceId || "";
        selectedLogCard = null;
        renderCardDetail();
    }

    function selectLogCard(card) {
        selectedCardId = "";
        selectedLogCard = card || null;
        if (selectedLogCard && selectedLogCard.card_id) {
            scheduleCardMetadataFetch(new Set([String(selectedLogCard.card_id)]));
        }
        renderCardDetail();
    }

    function logCardPayload(event) {
        const payload = event && event.payload ? event.payload : {};
        const instanceId = payload.card_instance_id || payload.instance_id || payload.target_card_instance_id || "";
        const liveCard = instanceId ? findCard(instanceId) : null;
        if (liveCard && !liveCard.hidden) return { instanceId, card: null };
        const cardId = payload.card_id || payload.public_card_id || "";
        const name = payload.card_label || payload.public_card_label || payload.card_name || "";
        if (!cardId && !name) return null;
        if (String(name) === t("비공개 카드") || String(name) === "비공개 카드") return null;
        return {
            instanceId: "",
            card: {
                instance_id: `log-${event.id || event.seq || Date.now()}`,
                kind: "card",
                owner: event.actor || "",
                card_id: cardId || undefined,
                name,
                hidden: false,
                face_up: true,
            },
        };
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
        const incomingVersion = envelopeVersion(nextEnvelope);
        const currentVersion = envelopeVersion(envelope);
        if (!(options && options.force) && incomingVersion && currentVersion && incomingVersion <= currentVersion) {
            return envelope;
        }
        const previousEvents = events;
        const previousEventCount = Number(envelope.event_count || previousEvents.length || 0);
        envelope = nextEnvelope || envelope;
        state = envelope.state || {};
        syncTimerFromState();
        if (Array.isArray(envelope.events)) {
            events = envelope.events;
        } else {
            events = previousEvents;
            envelope.events = previousEvents;
            if (envelope.event_count === undefined) envelope.event_count = previousEventCount;
        }
        ensureKnownCardMetadata();
        render();
        window.dispatchEvent(new CustomEvent("lumen-simulator-state", { detail: envelope }));
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

    function shuffleCooldownRemaining(side) {
        const cooldowns = state.hand_shuffle_cooldowns || {};
        const until = cooldowns[side] ? new Date(cooldowns[side]).getTime() : 0;
        if (!Number.isFinite(until) || until <= 0) return 0;
        return Math.max(0, Math.ceil((until - Date.now()) / 1000));
    }

    function setLocalShuffleCooldown(side) {
        state.hand_shuffle_cooldowns = state.hand_shuffle_cooldowns || {};
        state.hand_shuffle_cooldowns[side] = new Date(Date.now() + HAND_SHUFFLE_COOLDOWN_MS).toISOString();
    }

    function hasActiveShuffleCooldown() {
        return ["p1", "p2"].some((side) => shuffleCooldownRemaining(side) > 0);
    }

    function scheduleShuffleCooldownTick() {
        window.clearTimeout(shuffleCooldownTimer);
        shuffleCooldownTimer = null;
        if (!hasActiveShuffleCooldown()) return;
        shuffleCooldownTimer = window.setTimeout(() => {
            shuffleCooldownTimer = null;
            render();
        }, 1000);
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

    function localPriorityScore(localState, side) {
        const player = (localState.players && localState.players[side]) || {};
        const zones = player.zones || {};
        return [
            Number(player.fp || 0),
            Number(player.hp || 0),
            ((zones.hand || [])).length,
        ];
    }

    function comparePriorityScore(left, right) {
        for (let index = 0; index < left.length; index += 1) {
            if (left[index] > right[index]) return 1;
            if (left[index] < right[index]) return -1;
        }
        return 0;
    }

    function determineLocalPriorityPlayer(localState) {
        const compared = comparePriorityScore(localPriorityScore(localState, "p1"), localPriorityScore(localState, "p2"));
        if (compared > 0) return "p1";
        if (compared < 0) return "p2";
        return ["p1", "p2"].includes(localState.priority_player) ? localState.priority_player : "p1";
    }

    function requestLocalPriorityForPhase(localState) {
        if (["ready", "battle"].includes(localState.phase)) return "";
        const target = determineLocalPriorityPlayer(localState);
        localState.priority_player = target;
        localState.status = localState.status || {};
        ["p1", "p2"].forEach((side) => {
            localState.status[side] = { requested: side === target, done: false };
        });
        return target;
    }

    function initialTurnChanges() {
        return {
            p1: { hp: 0, fp: 0, hp_changed: false, fp_changed: false },
            p2: { hp: 0, fp: 0, hp_changed: false, fp_changed: false },
        };
    }

    function ensureLocalTurnChanges(localState) {
        localState.turn_changes = localState.turn_changes || {};
        ["p1", "p2"].forEach((side) => {
            localState.turn_changes[side] = localState.turn_changes[side] || {};
            localState.turn_changes[side].hp = Number(localState.turn_changes[side].hp || 0);
            localState.turn_changes[side].fp = Number(localState.turn_changes[side].fp || 0);
            localState.turn_changes[side].hp_changed = !!localState.turn_changes[side].hp_changed;
            localState.turn_changes[side].fp_changed = !!localState.turn_changes[side].fp_changed;
        });
        return localState.turn_changes;
    }

    function recordLocalTurnChange(localState, side, kind, amount) {
        const delta = Number(amount || 0);
        if (!["p1", "p2"].includes(side) || !["hp", "fp"].includes(kind) || !delta) return;
        const changes = ensureLocalTurnChanges(localState);
        changes[side][kind] = Number(changes[side][kind] || 0) + delta;
        changes[side][`${kind}_changed`] = true;
    }

    function resetLocalTurnChanges(localState) {
        localState.turn_changes = initialTurnChanges();
    }

    function initialCounterRevisions() {
        return {
            p1: { hp: 0, fp: 0 },
            p2: { hp: 0, fp: 0 },
        };
    }

    function ensureLocalCounterRevisions(localState) {
        localState.counter_revisions = localState.counter_revisions || initialCounterRevisions();
        ["p1", "p2"].forEach((side) => {
            localState.counter_revisions[side] = localState.counter_revisions[side] || {};
            localState.counter_revisions[side].hp = Number(localState.counter_revisions[side].hp || 0);
            localState.counter_revisions[side].fp = Number(localState.counter_revisions[side].fp || 0);
        });
        return localState.counter_revisions;
    }

    function counterRevision(kind, side, localState) {
        const revisions = ensureLocalCounterRevisions(localState || state);
        return Number(((revisions[side] || {})[kind]) || 0);
    }

    function advanceLocalCounterRevision(localState, side, kind, payload) {
        const revisions = ensureLocalCounterRevisions(localState);
        const current = Number(((revisions[side] || {})[kind]) || 0);
        if (payload.base_revision === undefined || payload.base_revision === null || payload.base_revision === "") {
            payload.base_revision = current;
        }
        const baseRevision = Number(payload.base_revision);
        if (!Number.isFinite(baseRevision) || baseRevision !== current) return false;
        revisions[side][kind] = current + 1;
        payload.revision = revisions[side][kind];
        return true;
    }

    function startLocalBattlePhase(localState, payload) {
        const readyCards = {};
        const revealedCounts = {};
        const revealedCards = { p1: [], p2: [] };
        Object.entries(localState.players || {}).forEach(([side, player]) => {
            if (!["p1", "p2"].includes(side)) return;
            const battleCards = (player.zones && player.zones.battle) || [];
            readyCards[side] = battleCards.map((card) => card.instance_id).filter(Boolean);
            let revealedCount = 0;
            battleCards.forEach((card) => {
                if (!card.face_up) revealedCount += 1;
                revealedCards[side].push({
                    card_instance_id: card.instance_id,
                    card_id: card.card_id,
                    card_label: localRevealedCardLabel(card),
                    owner: card.owner || side,
                });
                card.face_up = true;
                card.hidden = false;
            });
            revealedCounts[side] = revealedCount;
        });
        localState.battle_phase_ready_cards = readyCards;
        if (payload) {
            payload.battle_ready_cards = cloneData(readyCards);
            payload.revealed_counts = revealedCounts;
            payload.revealed_cards = revealedCards;
        }
    }

    function cleanupLocalBattlePhase(localState, payload) {
        const readyMap = localState.battle_phase_ready_cards || {};
        const readyIds = new Set();
        Object.values(readyMap).forEach((instanceIds) => {
            (instanceIds || []).forEach((instanceId) => {
                if (instanceId) readyIds.add(String(instanceId));
            });
        });
        const movedToHand = { p1: 0, p2: 0 };
        const movedToList = { p1: 0, p2: 0 };
        ["p1", "p2"].forEach((zoneOwner) => {
            const player = localState.players && localState.players[zoneOwner];
            if (!player || !player.zones) return;
            const battleCards = [...(player.zones.battle || [])];
            player.zones.battle = [];
            battleCards.forEach((card) => {
                const owner = ["p1", "p2"].includes(card.owner) ? card.owner : zoneOwner;
                if (!localState.players[owner] || !localState.players[owner].zones) return;
                if (readyIds.has(String(card.instance_id || ""))) {
                    card.face_up = false;
                    card.hidden = owner !== envelope.role;
                    localState.players[owner].zones.hand.push(card);
                    movedToHand[owner] += 1;
                } else {
                    setLocalCardVisibilityForZone(card, "list", localState, "battle");
                    localState.players[owner].zones.list.push(card);
                    movedToList[owner] += 1;
                }
            });
        });
        ["p1", "p2"].forEach((side) => {
            const zones = (((localState.players || {})[side] || {}).zones) || {};
            Object.values(zones).forEach((cards) => {
                (cards || []).forEach((card) => {
                    delete card.attached_to;
                    delete card.attachment_expires;
                    delete card.return_to_hand_on_attachment_expiry;
                    delete card.set_order;
                });
            });
        });
        delete localState.battle_phase_ready_cards;
        if (payload) {
            payload.battle_cleanup = {
                hand: movedToHand,
                list: movedToList,
            };
        }
    }

    function hideAllLocalHands(localState, payload) {
        const counts = { p1: 0, p2: 0 };
        ["p1", "p2"].forEach((side) => {
            const hand = (((localState.players || {})[side] || {}).zones || {}).hand || [];
            hand.forEach((card) => {
                if (!card || card.kind === "character") return;
                card.face_up = false;
                card.hidden = card.owner !== envelope.role;
                counts[side] += 1;
            });
        });
        if (payload) payload.hidden_hand_counts = counts;
    }

    function startLocalPhase(localState, phase, payload) {
        const previousPhase = localState.phase;
        localState.phase = phase;
        resetLocalStatus(localState);
        if (phase === "ready") {
            if (previousPhase !== "ready") {
                localState.cmyk_ready_staged_cards = collectLocalCmykReadyStagedCards(localState);
                localState.cmyk_ready_host_cards = {};
            }
        } else {
            delete localState.cmyk_ready_staged_cards;
            delete localState.cmyk_ready_host_cards;
        }
        if (phase === "battle") {
            startLocalBattlePhase(localState, payload);
        }
        return requestLocalPriorityForPhase(localState);
    }

    function collectLocalCmykReadyStagedCards(localState) {
        const staged = {};
        ["p1", "p2"].forEach((side) => {
            const player = ((localState || {}).players || {})[side] || {};
            if (!String((player.character || {}).name || "").toUpperCase().includes("CMYK")) return;
            const characterId = (player.character || {}).id;
            const candidates = ((player.zones || {}).battle || [])
                .map((card) => hydrateCard(card))
                .filter((card) => (
                    card.owner === side && !card.face_up && !card.attached_to &&
                    isTechniqueCard(card) && (!card.character_id || card.character_id === characterId)
                ))
                .slice(0, 3)
                .map((card) => card.instance_id)
                .filter(Boolean);
            if (candidates.length) staged[side] = candidates;
        });
        return staged;
    }

    function autoAttachLocalCmykReadyCards(localState, hostCard, fromZone, toPlayer, toZone, payload) {
        if (
            localState.phase !== "ready" || fromZone === "battle" || toZone !== "battle" ||
            !hostCard || hostCard.owner !== toPlayer || !isCmykPlayer(toPlayer) ||
            !isTechniqueCard(hostCard) || hostCard.attached_to
        ) return;
        const hostCards = localState.cmyk_ready_host_cards || {};
        if (hostCards[toPlayer]) return;
        const stagedIds = (((localState.cmyk_ready_staged_cards || {})[toPlayer]) || []).map(String);
        if (!stagedIds.length || stagedIds.includes(String(hostCard.instance_id || ""))) return;
        const stagedSet = new Set(stagedIds);
        const candidates = ((((localState.players || {})[toPlayer] || {}).zones || {}).battle || [])
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
        localState.cmyk_ready_host_cards = { ...hostCards, [toPlayer]: hostCard.instance_id };
        payload.auto_attached_card_instance_ids = candidates.map((card) => card.instance_id);
        payload.auto_attached_count = candidates.length;
        payload.auto_set_host_card_instance_id = hostCard.instance_id;
    }

    function advanceLocalPhase(localState, payload) {
        const currentPhase = phases.includes(localState.phase) ? localState.phase : "lumen";
        if (payload) {
            payload.from_phase = currentPhase;
            payload.from_turn = Number(localState.turn || 1);
        }
        if (currentPhase === "battle") {
            cleanupLocalBattlePhase(localState, payload);
        }
        if (currentPhase === "get") {
            hideAllLocalHands(localState, payload);
        }
        let priority = "";
        if (currentPhase === "recovery") {
            localState.turn = Number(localState.turn || 1) + 1;
            resetLocalTurnChanges(localState);
            priority = startLocalPhase(localState, "lumen", payload);
        } else {
            const nextIndex = Math.min(phases.indexOf(currentPhase) + 1, phases.length - 1);
            priority = startLocalPhase(localState, phases[nextIndex], payload);
        }
        if (payload) {
            payload.to_phase = localState.phase;
            payload.to_turn = Number(localState.turn || 1);
            if (priority) payload.priority_player = priority;
        }
        return priority;
    }

    function shouldPreserveLocalCardVisibility(fromZone, toZone) {
        return visibilityToggleZones.has(fromZone) && visibilityToggleZones.has(toZone);
    }

    function setLocalCardVisibilityForZone(card, zone, localState, fromZone) {
        if (zone === "battle" && !["lumen", "ready"].includes(localState.phase)) {
            card.face_up = true;
            card.hidden = false;
            return;
        }
        if (zone === "hand" && localState.phase === "get") {
            card.face_up = true;
            card.hidden = false;
            return;
        }
        if (shouldPreserveLocalCardVisibility(fromZone, zone)) return;
        if (["character", "passive", "list", "break", "ultimate"].includes(zone)) {
            card.face_up = true;
            card.hidden = false;
            return;
        }
        if (["hand", "side", "lumen"].includes(zone)) {
            card.face_up = false;
            card.hidden = card.owner !== envelope.role;
            return;
        }
        if (zone === "battle") {
            card.face_up = !["lumen", "ready"].includes(localState.phase);
            card.hidden = !card.face_up && card.owner !== envelope.role;
        }
    }

    function localCardLabel(card) {
        if (!card || card.hidden) return t("비공개 카드");
        return cardDisplayName(card);
    }

    function localRevealedCardLabel(card) {
        if (!card) return t("카드");
        const revealedCard = card.card_id ? hydrateCard({ ...card, hidden: false }) : hydrateCard(card);
        return (revealedCard && revealedCard.name) || t("카드");
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
            const preserveAttachment = location.zone === toZone || (
                state.phase === "battle" && location.zone === "battle" && toZone === "list"
            );
            if (!preserveAttachment) {
                delete location.card.attached_to;
                delete location.card.attachment_expires;
                delete location.card.return_to_hand_on_attachment_expiry;
                delete location.card.set_order;
            }
            state.players[location.playerSide].zones[location.zone].splice(location.index, 1);
            localPayload.from_player = location.playerSide;
            localPayload.from_zone = location.zone;
            localPayload.to_player = toPlayer;
            localPayload.card_label = localCardLabel(location.card);
            if (isTokenCard(hydrateCard(location.card)) && toZone === "break") {
                localPayload.deleted_token = true;
                localPayload.was_face_up = !!location.card.face_up;
                if (location.card.card_id) localPayload.card_id = location.card.card_id;
                appendOptimisticEvent(action, localPayload);
                return true;
            }
            setLocalCardVisibilityForZone(location.card, toZone, state, location.zone);
            location.card.zone = toZone;
            location.card.zone_owner = toPlayer;
            state.players[toPlayer].zones[toZone].push(location.card);
            autoAttachLocalCmykReadyCards(
                state, hydrateCard(location.card), location.zone, toPlayer, toZone, localPayload,
            );
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "attach_card") {
            const source = findCardLocation(state, localPayload.card_instance_id);
            const host = findCardLocation(state, localPayload.host_card_instance_id);
            if (!source || !host || source.card === host.card || state.phase !== "ready") return false;
            if (source.playerSide !== envelope.role || host.playerSide !== envelope.role) return false;
            if (source.zone !== "battle" || host.zone !== "battle") return false;
            const attached = Object.values(state.players[envelope.role].zones || {})
                .flatMap((cards) => cards || [])
                .filter((card) => !!card.attached_to);
            const order = Math.max(0, ...attached
                .filter((card) => card.attached_to === host.card.instance_id)
                .map((card) => Number(card.set_order || 0))) + 1;
            source.card.attached_to = host.card.instance_id;
            source.card.attachment_expires = "battle";
            source.card.return_to_hand_on_attachment_expiry = true;
            source.card.set_order = order;
            source.card.face_up = false;
            source.card.hidden = false;
            localPayload.owner = envelope.role;
            localPayload.card_label = localCardLabel(source.card);
            localPayload.host_card_label = localCardLabel(host.card);
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
                if (!(state.phase === "battle" && toZone === "list")) {
                    delete card.attached_to;
                    delete card.attachment_expires;
                    delete card.return_to_hand_on_attachment_expiry;
                    delete card.set_order;
                }
                setLocalCardVisibilityForZone(card, toZone, state, fromZone);
                card.zone = toZone;
                card.zone_owner = owner;
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
            setLocalShuffleCooldown(playerSide);
            localPayload.cooldown_seconds = Math.ceil(HAND_SHUFFLE_COOLDOWN_MS / 1000);
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_hand_visibility") {
            const target = localPayload.target || envelope.role;
            const player = state.players[target];
            if (!player || target !== envelope.role) return false;
            const faceUp = !!localPayload.face_up;
            let count = 0;
            ((player.zones && player.zones.hand) || []).forEach((card) => {
                if (!card || card.kind === "character" || card.owner !== target) return;
                card.face_up = faceUp;
                card.hidden = false;
                count += 1;
            });
            localPayload.target = target;
            localPayload.face_up = faceUp;
            localPayload.count = count;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "set_phase") {
            if (!phases.includes(localPayload.phase)) return false;
            const fromPhase = phases.includes(state.phase) ? state.phase : "lumen";
            localPayload.from_phase = fromPhase;
            localPayload.from_turn = Number(state.turn || 1);
            if (fromPhase === "battle" && localPayload.phase !== "battle") {
                cleanupLocalBattlePhase(state, localPayload);
            }
            if (fromPhase === "get" && localPayload.phase !== "get") {
                hideAllLocalHands(state, localPayload);
            }
            const priority = startLocalPhase(state, localPayload.phase, localPayload);
            localPayload.to_phase = state.phase;
            localPayload.to_turn = Number(state.turn || 1);
            if (priority) localPayload.priority_player = priority;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "next_turn") {
            if (state.phase === "battle") cleanupLocalBattlePhase(state, localPayload);
            if (state.phase === "get") hideAllLocalHands(state, localPayload);
            state.turn = Number(state.turn || 1) + 1;
            resetLocalTurnChanges(state);
            startLocalPhase(state, "lumen", localPayload);
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
            if (state.status[target].done) {
                state.status[target].requested = false;
                const opponent = target === "p1" ? "p2" : "p1";
                if (state.status[opponent] && state.status[opponent].done) {
                    appendOptimisticEvent(action, localPayload);
                    const advancePayload = {};
                    advanceLocalPhase(state, advancePayload);
                    appendOptimisticEvent("phase_advance", advancePayload);
                    return true;
                }
                if (state.status[opponent]) {
                    state.status[opponent].requested = true;
                    state.status[opponent].done = false;
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
            if (!advanceLocalCounterRevision(state, target, action, localPayload)) return false;
            const before = Number(player[action] || 0);
            player[action] = before + amount;
            recordLocalTurnChange(state, target, action, amount);
            localPayload.before = before;
            localPayload.after = player[action];
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "fp_reset") {
            const target = localPayload.target;
            const player = state.players[target];
            if (!player) return false;
            if (!advanceLocalCounterRevision(state, target, "fp", localPayload)) return false;
            localPayload.before = Number(player.fp || 0);
            player.fp = 0;
            recordLocalTurnChange(state, target, "fp", -localPayload.before);
            localPayload.after = 0;
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        if (action === "timer") {
            const timer = state.timer || {};
            const duration = timerDuration(timer);
            const remaining = timerRemaining();
            const expired = remaining <= 0 && (!!timer.started_at || Number(timer.remaining_seconds) <= 0);
            const running = !timer.is_running && !expired;
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
            syncTimerFromState();
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
            localPayload.was_face_up = !!location.card.face_up;
            localPayload.card_id = location.card.card_id;
            localPayload.card_label = localCardLabel(location.card);
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

        if (action === "signal") {
            const signal = String(localPayload.signal || "");
            const label = signalLabel(signal, localPayload.label);
            if (!["effect", "combo", "catch"].includes(signal)) return false;
            localPayload.signal = signal;
            localPayload.label = label;
            const id = `local-signal-${Date.now()}-${Math.random().toString(36).slice(2)}`;
            state.last_signal = { id, actor: envelope.role, signal, label };
            appendOptimisticEvent(action, localPayload);
            return true;
        }

        return false;
    }

    function shouldOptimisticallyApply(action) {
        return [
            "move_card",
            "attach_card",
            "bulk_move",
            "shuffle_hand",
            "set_hand_visibility",
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
            "signal",
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
            "attach_card",
            "bulk_move",
            "shuffle_hand",
            "set_hand_visibility",
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
                if (batch.some((item) => item.action === "set_done")) {
                    return fetchState(true).then(() => result);
                }
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
        const needsAuthoritativeState = (action === "set_phase" && actionPayload.phase === "battle") || action === "set_done";
        return flushActionBatch()
            .then(() => postSocketAction(action, actionPayload))
            .then((result) => {
                if (optimisticApplied && needsAuthoritativeState) {
                    return fetchState(true).then(() => result);
                }
                return result;
            })
            .catch((error) => {
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
        let countdown = root.querySelector("[data-sim-timer-countdown]") || document.querySelector("[data-sim-timer-countdown]");
        if (!countdown) {
            countdown = document.createElement("div");
            countdown.className = "v2-sim-timer-countdown";
            countdown.dataset.simTimerCountdown = "true";
            countdown.setAttribute("aria-hidden", "true");
        }
        if (countdown.parentElement !== root) root.appendChild(countdown);
        return countdown;
    }

    function updateTimerPresentation(remaining, active) {
        const progress = timerProgress(remaining);
        const color = timerColor(progress);
        document.body.style.setProperty("--v2-sim-timer-rgb", color.join(", "));
        document.body.style.setProperty("--v2-sim-timer-progress", progress.toFixed(3));
        root.style.setProperty("--v2-sim-timer-rgb", color.join(", "));
        root.style.setProperty("--v2-sim-timer-progress", progress.toFixed(3));
        document.body.classList.toggle("v2-sim-timer-active", active);
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
        const timerNode = document.querySelector("[data-sim-timer]");
        const timerButton = document.querySelector("[data-sim-action='timer']");
        const remaining = timerRemaining();
        const timerActive = !!(state.timer && state.timer.is_running && remaining > 0);
        if (timerNode) timerNode.textContent = String(remaining);
        if (timerButton) {
            timerButton.disabled = !canControl();
            timerButton.classList.toggle("is-active", timerActive);
            timerButton.classList.toggle("is-danger", timerActive && remaining <= 3);
        }
        updateTimerPresentation(remaining, timerActive);
        maybeReportTimerTimeout(remaining);
    }

    function renderPhase() {
        const turn = document.querySelector("[data-sim-turn]");
        const current = document.querySelector("[data-sim-phase-current]");
        const holder = document.querySelector("[data-sim-phase-buttons]");
        const guide = document.querySelector("[data-sim-phase-guide]");
        if (turn) turn.textContent = String(state.turn || 1);
        if (current) current.textContent = `${phaseLabel(state.phase)} ${t("Phase")}`;
        if (guide) guide.textContent = phaseGuideText(state.phase);
        maybeShowPhaseOverlay();
        maybeShowSignalOverlay();
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

    function maybeShowPhaseOverlay() {
        const key = `${state.turn || 1}:${state.phase || ""}`;
        if (!key || key === lastPhaseOverlayKey) return;
        lastPhaseOverlayKey = key;
        let overlay = document.querySelector("[data-phase-overlay]");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "v2-sim-phase-overlay";
            overlay.dataset.phaseOverlay = "true";
            overlay.setAttribute("aria-hidden", "true");
            document.body.appendChild(overlay);
        }
        overlay.textContent = `${phaseLabel(state.phase)} ${t("Phase")}`;
        overlay.classList.remove("is-visible");
        void overlay.offsetWidth;
        overlay.classList.add("is-visible");
        window.setTimeout(() => overlay.classList.remove("is-visible"), 1150);
    }

    function showSignalOverlay(actor, label, key) {
        if (!actor || !label) return;
        const overlayKey = key || `${actor}:${label}:${Date.now()}`;
        if (overlayKey === lastSignalOverlayKey) return;
        lastSignalOverlayKey = overlayKey;
        let overlay = document.querySelector("[data-signal-overlay]");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "v2-sim-phase-overlay v2-sim-signal-overlay";
            overlay.dataset.signalOverlay = "true";
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
        window.setTimeout(() => overlay.classList.remove("is-visible"), 1150);
    }

    function maybeShowSignalOverlay() {
        const signal = state.last_signal || {};
        const label = signalLabel(signal.signal, signal.label);
        if (!signal.id || !signal.actor || !label) return;
        showSignalOverlay(signal.actor, label, signal.id);
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

    function turnChangeAmount(side, kind) {
        const changes = (state.turn_changes && state.turn_changes[side]) || {};
        return Number(changes[kind] || 0);
    }

    function turnChangeTouched(side, kind) {
        const changes = (state.turn_changes && state.turn_changes[side]) || {};
        return !!changes[`${kind}_changed`] || !!turnChangeAmount(side, kind);
    }

    function turnChangeBadge(side, kind) {
        const amount = turnChangeAmount(side, kind);
        if (!turnChangeTouched(side, kind)) return "";
        const className = amount > 0 ? "is-positive" : amount < 0 ? "is-negative" : "is-neutral";
        return `<span class="v2-sim-turn-change ${className}" title="${escapeHtml(t("이번 턴 변화"))}">${formatSigned(amount)}</span>`;
    }

    function counterValueMarkup(kind, side, value) {
        const label = kind === "fp" ? `${formatSigned(value || 0)} FP` : String(Number(value || 0));
        return `<span class="v2-sim-counter-main">${escapeHtml(label)}</span>${turnChangeBadge(side, kind)}`;
    }

    function playerBoardOrder() {
        const own = ownSide();
        if (own) return [own, opponentSide(own)];
        return ["p1", "p2"];
    }

    function playerBoardPosition(side) {
        return playerBoardOrder()[0] === side ? "left" : "right";
    }

    function orderPlayerBoards() {
        const layout = document.querySelector(".v2-sim-layout");
        if (!layout) return;
        playerBoardOrder().forEach((side) => {
            const board = layout.querySelector(`[data-player-board="${side}"]`);
            if (board) layout.appendChild(board);
        });
    }

    function renderPlayer(side) {
        const rootNode = document.querySelector(`[data-player-board="${side}"]`);
        const player = state.players && state.players[side];
        if (!rootNode || !player) return;
        const position = playerBoardPosition(side);
        const character = player.character || {};
        const bgStyle = character.img
            ? ` style="--sim-character-bg: url('${escapeHtml(String(character.img).replaceAll("'", "%27"))}')"`
            : "";
        const requested = !!(state.status && state.status[side] && state.status[side].requested);
        const done = !!(state.status && state.status[side] && state.status[side].done);
        const requestClass = requested
            ? side === envelope.role
                ? " is-action-requested is-own-request"
                : " is-action-requested is-opponent-request"
            : "";
        const doneClass = done
            ? side === envelope.role
                ? " is-action-done is-own-done"
                : " is-action-done is-opponent-done"
            : "";
        rootNode.className = `v2-sim-player-wrap v2-sim-${side} v2-sim-board-${position}`;
        rootNode.innerHTML = `
            <article class="v2-panel v2-sim-player${requestClass}${doneClass}"${bgStyle}>
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
                        <strong data-counter-value="hp:${side}"${hpToneStyle(player)}>${counterValueMarkup("hp", side, player.hp)}</strong>
                        ${counterButton("+", side, "hp", 100, "is-heal")}
                        ${counterButton("+500", side, "hp", 500, "is-heal")}
                    </div>
                    <div class="v2-sim-fp">
                        ${counterButton("-", side, "fp", -1, "")}
                        <button class="v2-sim-fp-value ${valueSignClass(player.fp)}" type="button" data-fp-reset="${side}" data-counter-value="fp:${side}">${counterValueMarkup("fp", side, player.fp)}</button>
                        ${counterButton("+", side, "fp", 1, "")}
                    </div>
                </div>
                <div class="v2-sim-zones" data-zone-grid="${side}"></div>
            </article>
        `;
        renderPassive(side, player);
        renderZones(side, player, position);
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

    function handLimitForPlayer(player) {
        const character = (player && player.character) || {};
        const table = character.hand_table || {};
        const hp = Number(player && player.hp || 0);
        const thresholds = Object.keys(table)
            .map((key) => Number(key))
            .filter((value) => Number.isFinite(value))
            .sort((a, b) => a - b);
        if (thresholds.length) {
            for (const threshold of thresholds) {
                if (hp <= threshold) return table[String(threshold)] ?? table[threshold];
            }
            const highest = thresholds[thresholds.length - 1];
            return table[String(highest)] ?? table[highest];
        }
        return character.hand_limit;
    }

    function zoneCountText(zone, cards, player) {
        const count = (cards || []).length;
        if (zone === "hand") {
            const limit = handLimitForPlayer(player);
            if (limit !== null && limit !== undefined && limit !== "") return `${count}/${limit}`;
        }
        return String(count);
    }

    function renderBattleCards(cards) {
        const boardKey = (card) => card.instance_id || card.board_key || "";
        const attachmentKey = (card) => card.attached_to || card.attached_to_board_key || "";
        const cardById = new Map((cards || []).map((card) => [boardKey(card), card]));
        const attachments = new Map();
        (cards || []).forEach((card) => {
            const hostKey = attachmentKey(card);
            if (!hostKey || !cardById.has(hostKey)) return;
            if (!attachments.has(hostKey)) attachments.set(hostKey, []);
            attachments.get(hostKey).push(card);
        });
        attachments.forEach((items) => items.sort((left, right) => (
            Number(left.set_order || 0) - Number(right.set_order || 0)
        )));

        return (cards || [])
            .filter((card) => !attachmentKey(card) || !cardById.has(attachmentKey(card)))
            .map((host) => {
                const hostKey = boardKey(host);
                const setCards = attachments.get(hostKey) || [];
                if (!setCards.length) return renderCard({ ...host, zone: "battle" });
                return `
                    <div class="v2-sim-card-set-group" data-card-set-host="${escapeHtml(hostKey)}">
                        ${renderCard({ ...host, zone: "battle" })}
                        <div class="v2-sim-card-set-cards" aria-label="${escapeHtml(t("세트된 카드"))}">
                            ${setCards.map((card) => renderCard({ ...card, zone: "battle" })).join("")}
                        </div>
                    </div>
                `;
            }).join("");
    }

    function renderZones(side, player, position) {
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
                if (side === envelope.role && cards.length) {
                    const ownHandCards = cards.filter((card) => card.kind !== "character" && card.owner === side);
                    const handPublic = ownHandCards.length > 0 && ownHandCards.every((card) => !!card.face_up);
                    actions.push(`<button type="button" data-hand-visibility-player="${side}" data-hand-visibility-value="${handPublic ? "false" : "true"}">${handPublic ? t("손패 비공개") : t("손패 공개")}</button>`);
                }
                const cooldown = shuffleCooldownRemaining(side);
                actions.push(`<button type="button" data-shuffle-hand-player="${side}"${cooldown ? ` data-force-disabled="true" disabled` : ""}>${cooldown ? `${t("셔플")} ${cooldown}s` : t("셔플")}</button>`);
            }
            const zoneActions = actions.length
                ? `<div class="v2-sim-zone-actions">${actions.join("")}</div>`
                : "";
            const cardMarkup = zone === "battle"
                ? renderBattleCards(cards)
                : cards.map((card) => renderCard({ ...card, zone })).join("");
            zoneNode.innerHTML = `
                <header>
                    <strong>${zone === "ultimate" ? "ULTIMATE" : zoneLabel(zone)}</strong>
                    ${zone === "ultimate" ? "" : `<span>${escapeHtml(zoneCountText(zone, cards, player))}</span>`}
                    ${zoneActions}
                </header>
                <div class="v2-sim-card-grid">
                    ${cardMarkup}
                </div>
            `;
            return zoneNode;
        };

        const topRow = document.createElement("div");
        topRow.className = "v2-sim-zone-row v2-sim-zone-row-top";
        if (position === "right") {
            topRow.append(makeZone("lumen"), makeZone("ultimate"));
        } else {
            topRow.append(makeZone("ultimate"), makeZone("lumen"));
        }
        holder.appendChild(topRow);
        holder.appendChild(makeZone("battle"));
        holder.appendChild(makeZone("hand"));
        holder.appendChild(makeZone("list"));
        const bottomRow = document.createElement("div");
        bottomRow.className = "v2-sim-zone-row v2-sim-zone-row-bottom";
        if (position === "right") {
            bottomRow.append(makeZone("break"), makeZone("side"));
        } else {
            bottomRow.append(makeZone("side"), makeZone("break"));
        }
        holder.appendChild(bottomRow);
    }

    function renderCard(card) {
        card = hydrateCard(card);
        const draggable = canControl() && card.kind !== "character" && !isPassiveCard(card);
        const classes = ["v2-sim-card"];
        if (card.hidden) classes.push("is-hidden");
        if (card.face_up) classes.push("is-face-up");
        if (!card.face_up) classes.push("is-face-down");
        if (card.kind === "character") classes.push("is-character");
        if (card.attached_to) classes.push("is-set-card");
        const image = !card.hidden && card.img_sm
            ? `<img src="${escapeHtml(card.img_sm)}" alt="">`
            : "";
        const visibility = canToggleCardVisibility(card)
            ? `<button class="v2-sim-card-toggle ${card.face_up ? "is-public" : "is-private"}" type="button" data-visibility-card="${escapeHtml(card.instance_id)}" data-visibility-value="${card.face_up ? "false" : "true"}" aria-label="${card.face_up ? t("비공개로 전환") : t("공개로 전환")}"></button>`
            : "";
        const effects = renderCardEffectButtons(card, true);
        return `
            <div class="${classes.join(" ")}" data-card-instance="${escapeHtml(card.instance_id)}" data-card-owner="${escapeHtml(card.owner)}" data-card-zone="${escapeHtml(card.zone || "")}" data-card-attached-to="${escapeHtml(card.attached_to || "")}" data-card-open="${escapeHtml(card.instance_id)}" data-card-tooltip="${escapeHtml(cardTitle(card))}" draggable="${draggable ? "true" : "false"}">
                ${image}
                ${visibility}
                ${effects}
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
            const cardNodes = Array.from(grid.querySelectorAll(".v2-sim-card"));
            const layoutNodes = Array.from(grid.children);
            const cards = layoutNodes.length;
            if (!cards) {
                grid.style.removeProperty("--sim-card-fit-step");
                grid.style.removeProperty("--sim-card-visible-width");
                grid.classList.remove("is-overlapped");
                grid.classList.remove("has-card-sets");
                return;
            }
            const hasCardSets = layoutNodes.some((node) => node.classList.contains("v2-sim-card-set-group"));
            grid.classList.toggle("has-card-sets", hasCardSets);
            if (hasCardSets) {
                grid.style.removeProperty("--sim-card-fit-step");
                grid.style.setProperty("--sim-card-visible-width", `${Math.floor(Number.parseFloat(window.getComputedStyle(grid).getPropertyValue("--sim-card-width")) || 94)}px`);
                grid.classList.remove("is-overlapped");
                cardNodes.forEach((node) => node.classList.remove("is-actions-hidden"));
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
            const overlapped = step < cardWidth;
            const overlappedWidth = Math.floor(Math.min(cardWidth, step));
            const fullWidth = Math.floor(cardWidth);
            grid.style.setProperty("--sim-card-visible-width", `${overlapped ? overlappedWidth : fullWidth}px`);
            grid.classList.toggle("is-overlapped", overlapped);
            cardNodes.forEach((node, index) => {
                const hasCardToRight = index + rows < cards;
                const visibleWidth = overlapped && hasCardToRight ? overlappedWidth : fullWidth;
                const minActionsWidth = Math.min(fullWidth, Math.max(CARD_ACTIONS_MIN_VISIBLE_PX, Math.ceil(cardWidth * CARD_ACTIONS_MIN_VISIBLE_RATIO)));
                node.style.setProperty("--sim-card-visible-width", `${visibleWidth}px`);
                node.classList.toggle("is-actions-hidden", visibleWidth < minActionsWidth);
            });
        });
    }

    function scheduleFitCardGrids() {
        window.requestAnimationFrame(fitCardGrids);
    }

    function countSummary(counts) {
        if (!counts || typeof counts !== "object") return "";
        return ["p1", "p2"]
            .map((side) => {
                const count = Number(counts[side] || 0);
                return count > 0 ? `${playerLabel(side)} ${count}${t("장")}` : "";
            })
            .filter(Boolean)
            .join(", ");
    }

    function revealedCardSummary(revealedCards) {
        if (!revealedCards || typeof revealedCards !== "object") return "";
        const namesFor = (side) => ((revealedCards[side] || [])
            .map((card) => card && card.card_label)
            .filter(Boolean)
            .join(", ")) || "-";
        return `P1 ${namesFor("p1")} : ${namesFor("p2")} P2`;
    }

    function phaseEventLabel(phase, payload) {
        const base = `${phaseLabel(phase)} ${t("Phase")}`;
        const revealed = revealedCardSummary(payload.revealed_cards) || countSummary(payload.revealed_counts);
        return revealed ? `${base} ${t("배틀 카드 공개")}\n${revealed}` : base;
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
            const autoSet = Number(payload.auto_attached_count || 0) > 0
                ? ` / ${payload.auto_attached_count}${t("장")} ${t("자동 세트")}`
                : "";
            return `${actor} ${payload.card_label || t("카드")}: ${from} → ${to}${autoSet}`;
        }
        if (event.type === "attach_card") {
            return `${actor} ${payload.card_label || t("카드")} → ${payload.host_card_label || t("카드")} ${t("세트")}`;
        }
        if (event.type === "bulk_move") {
            return `${actor} ${playerLabel(payload.player)} ${zoneLabel("battle")} ${payload.count || 0}${t("장")} → ${zoneLabel(payload.to_zone)}`;
        }
        if (event.type === "shuffle_hand") return `${playerLabel(payload.player)} ${zoneLabel("hand")} ${t("셔플")}`;
        if (event.type === "set_hand_visibility") return `${playerLabel(payload.target)} ${zoneLabel("hand")} ${payload.face_up ? t("공개") : t("비공개")} (${payload.count || 0}${t("장")})`;
        if (event.type === "set_phase") return phaseEventLabel(payload.phase, payload);
        if (event.type === "phase_advance") return phaseEventLabel(payload.to_phase, payload);
        if (event.type === "import_card") return `${actor} ${payload.card_label || payload.card_name || t("카드")} → ${zoneLabel("lumen")}`;
        if (event.type === "blackout_random_get") return `${actor} ${payload.source_card_label || t("블랙아웃")}: ${playerLabel(payload.opponent)} ${zoneLabel("list")} ${t("무작위")} 1${t("장")} → ${zoneLabel("hand")} - ${payload.card_label || t("카드")}`;
        if (event.type === "yohan_declare_reveal") return `${actor} ${t("선언")} : ${payload.declaration_label || payload.declaration || ""} - ${t("공개")} : ${payload.card_label || t("카드")}`;
        if (event.type === "yohan_foresight_reveal") return `${t("예지")} - ${payload.card_label || t("카드")}`;
        if (event.type === "nia_lumen_cards_to_list") return `${actor} ${zoneLabel("lumen")} ${t("공격/수비")} ${payload.count || 0}${t("장")} → ${zoneLabel("list")}`;
        if (event.type === "cmyk_new_single") return `${actor} ${payload.card_label || t("뉴 싱글")} ${payload.count || 0}${t("장")} → ${zoneLabel("lumen")}`;
        if (event.type === "next_turn") return t("다음 턴");
        if (event.type === "request_action") return `${playerLabel(payload.target)} ${t("행동")} ${payload.requested ? t("요청") : t("요청 해제")}`;
        if (event.type === "set_done") {
            const doneLabel = `${playerLabel(payload.target)} ${t("행동")} ${payload.done ? t("완료") : t("완료 취소")}`;
            return payload.requested_opponent
                ? `${doneLabel} / ${playerLabel(payload.requested_opponent)} ${t("행동")} ${t("요청")}`
                : doneLabel;
        }
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
        if (event.type === "signal") return `${actor} : ${signalLabel(payload.signal, payload.label)}`;
        if (event.type === "log_note") return t(payload.text || "기록");
        return event.type;
    }

    function eventRelatedSide(event) {
        const payload = event.payload || {};
        if (["set_phase", "phase_advance", "next_turn"].includes(event.type)) return "";
        if (["request_action", "set_done", "hp", "fp", "fp_reset", "passive", "timer_timeout"].includes(event.type)) return payload.target || payload.owner || "";
        if (event.type === "bulk_move") return payload.player || "";
        if (event.type === "shuffle_hand") return payload.player || "";
        if (event.type === "set_hand_visibility") return payload.target || "";
        if (event.type === "import_card") return payload.target || event.actor || "";
        if (["yohan_declare_reveal", "yohan_foresight_reveal", "nia_lumen_cards_to_list", "cmyk_new_single", "blackout_random_get"].includes(event.type)) return payload.target || event.actor || "";
        if (event.type === "set_visibility") return payload.owner || event.actor || "";
        if (event.type === "signal") return event.actor || "";
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
            const logCard = logCardPayload(event);
            if (logCard) {
                row.classList.add("has-card-link");
                if (logCard.instanceId) row.dataset.logCardInstance = logCard.instanceId;
                if (logCard.card) row.dataset.logCard = JSON.stringify(logCard.card);
            }
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
        const card = selectedLogCard ? hydrateCard(selectedLogCard) : selectedCardId ? hydrateCard(findCard(selectedCardId)) : null;
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
        const actions = renderCardEffectButtons(card, false);
        holder.innerHTML = `
            ${image ? `<img src="${escapeHtml(image)}" alt="">` : ""}
            <h2>${escapeHtml(cardDisplayName(card))}</h2>
            ${actions}
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
            button.classList.toggle("is-log-open", logOpen);
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
                draggedCardInstanceId = card.dataset.cardInstance || "";
                event.dataTransfer.setData("text/plain", JSON.stringify({
                    instanceId: card.dataset.cardInstance,
                    owner: card.dataset.cardOwner,
                }));
            });
            card.addEventListener("dragend", () => {
                draggedCardInstanceId = "";
                document.querySelectorAll(".is-set-drop-target").forEach((node) => {
                    node.classList.remove("is-set-drop-target");
                });
            });
            card.addEventListener("dragover", (event) => {
                const source = findCard(draggedCardInstanceId);
                const host = findCard(card.dataset.cardInstance);
                if (!canAttachCmykCard(source, host)) return;
                event.preventDefault();
                event.stopPropagation();
                card.classList.add("is-set-drop-target");
            });
            card.addEventListener("dragleave", () => card.classList.remove("is-set-drop-target"));
            card.addEventListener("drop", (event) => {
                const source = findCard(draggedCardInstanceId);
                const host = findCard(card.dataset.cardInstance);
                const isSetGesture = !!(
                    source && host && state.phase === "ready" &&
                    source.zone === "battle" && host.zone === "battle" &&
                    source.owner === host.owner && isCmykPlayer(source.owner)
                );
                if (!isSetGesture) return;
                event.preventDefault();
                event.stopPropagation();
                card.classList.remove("is-set-drop-target");
                if (!canAttachCmykCard(source, host)) {
                    showRealtimeToast(t("이 카드에는 CMYK 기술을 세트할 수 없습니다."));
                    return;
                }
                postAction("attach_card", {
                    card_instance_id: source.instance_id,
                    host_card_instance_id: host.instance_id,
                });
                draggedCardInstanceId = "";
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
                draggedCardInstanceId = "";
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
        const queued = queue.get(side) || { amount: 0, timer: null, baseRevision: counterRevision(kind, side) };
        queued.amount += amount;
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
        }, kind === "hp" ? 900 : 700);
        queue.set(side, queued);
        updateQueuedCounters();
    }

    function render() {
        ensureKnownCardMetadata();
        const role = document.querySelector("[data-sim-role]");
        if (role) role.textContent = roleText();
        renderPresence();
        renderPhase();
        renderStatus();
        renderTimer();
        orderPlayerBoards();
        playerBoardOrder().forEach((side) => renderPlayer(side));
        renderLog();
        renderCardDetail();
        renderCardSizeControls();
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
            "[data-hand-visibility-player]",
            "[data-visibility-card]",
            "[data-sim-action='import_card']",
        ].join(", ")).forEach((button) => {
            button.disabled = !canControl() || button.dataset.forceDisabled === "true";
        });
        document.querySelectorAll("[data-manual-log-input]").forEach((input) => {
            input.disabled = !canControl();
        });
        document.querySelectorAll("[data-card-import-input]").forEach((input) => {
            input.disabled = !canControl();
        });
        attachDragAndDrop();
        updateQueuedCounters();
        scheduleShuffleCooldownTick();
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

    function submitManualLog() {
        const input = document.querySelector("[data-manual-log-input]");
        const text = input ? input.value.trim() : "";
        if (!text) return;
        if (input) input.value = "";
        postAction("log_note", { text });
    }

    function setShortcutModalOpen(open) {
        const modal = document.querySelector("[data-shortcut-modal]");
        if (!modal) return;
        modal.hidden = !open;
    }

    function isEditableTarget(target) {
        return !!(
            target &&
            target.closest &&
            target.closest("input, textarea, select, [contenteditable='true'], [contenteditable='']")
        );
    }

    function shuffleHand(side) {
        const player = state.players && state.players[side];
        const cards = player && player.zones ? player.zones.hand || [] : [];
        const cooldown = shuffleCooldownRemaining(side);
        if (cooldown > 0) {
            showRealtimeToast(t(`패 셔플은 ${cooldown}초 뒤에 다시 사용할 수 있습니다.`));
            return;
        }
        if (cards.length <= 1) return;
        postAction("shuffle_hand", {
            player: side,
            order: shuffledOrder(cards),
        });
    }

    function completeOwnAction() {
        const side = ownSide();
        if (!side || !canControl()) return;
        const status = (state.status && state.status[side]) || {};
        postAction("set_done", { target: side, done: !status.done });
    }

    function requestOpponentAction() {
        const side = ownSide();
        const target = opponentSide(side);
        if (!target || !canControl()) return;
        const status = (state.status && state.status[target]) || {};
        postAction("request_action", { target, requested: !status.requested });
    }

    function sendSignal(signal) {
        if (!ownSide() || !canControl()) return;
        postAction("signal", { signal });
    }

    function queueShortcutCounter(side, kind, amount) {
        if (!side || !canControl()) return;
        queueCounter(kind, side, amount);
    }

    function handleSimulatorShortcut(event) {
        if (event.defaultPrevented) return;
        if (event.key === "Escape") {
            setShortcutModalOpen(false);
            return;
        }
        const shortcutModal = document.querySelector("[data-shortcut-modal]");
        if (shortcutModal && !shortcutModal.hidden) return;
        if (event.ctrlKey || event.altKey || event.metaKey) return;
        if (isEditableTarget(event.target)) return;

        const side = ownSide();
        const opponent = opponentSide(side);
        let handled = true;
        if (event.key === "Tab") {
            setLogOpen(!logOpen);
        } else if (event.code === "Space" && event.shiftKey) {
            requestOpponentAction();
        } else if (event.code === "Space") {
            completeOwnAction();
        } else if (event.code === "KeyR" && event.shiftKey) {
            shuffleHand(side);
        } else if (!event.shiftKey && event.code === "Digit1") {
            queueShortcutCounter(side, "hp", -500);
        } else if (!event.shiftKey && event.code === "Digit2") {
            queueShortcutCounter(side, "hp", -100);
        } else if (!event.shiftKey && event.code === "Digit3") {
            queueShortcutCounter(side, "hp", 100);
        } else if (!event.shiftKey && event.code === "Digit4") {
            queueShortcutCounter(side, "hp", 500);
        } else if (!event.shiftKey && event.code === "Digit5") {
            queueShortcutCounter(side, "fp", -1);
        } else if (!event.shiftKey && event.code === "Digit6") {
            queueShortcutCounter(side, "fp", 1);
        } else if (!event.shiftKey && event.code === "KeyQ") {
            queueShortcutCounter(opponent, "hp", -500);
        } else if (!event.shiftKey && event.code === "KeyW") {
            queueShortcutCounter(opponent, "hp", -100);
        } else if (!event.shiftKey && event.code === "KeyE") {
            queueShortcutCounter(opponent, "hp", 100);
        } else if (!event.shiftKey && event.code === "KeyR") {
            queueShortcutCounter(opponent, "hp", 500);
        } else if (!event.shiftKey && event.code === "KeyT") {
            queueShortcutCounter(opponent, "fp", -1);
        } else if (!event.shiftKey && event.code === "KeyY") {
            queueShortcutCounter(opponent, "fp", 1);
        } else if (!event.shiftKey && event.code === "KeyZ") {
            sendSignal("effect");
        } else if (!event.shiftKey && event.code === "KeyX") {
            sendSignal("combo");
        } else if (!event.shiftKey && event.code === "KeyC") {
            sendSignal("catch");
        } else {
            handled = false;
        }
        if (handled) {
            event.preventDefault();
            event.stopPropagation();
        }
    }

    document.addEventListener("keydown", handleSimulatorShortcut);

    root.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || event.isComposing) return;
        if (!event.target.closest("[data-manual-log-input]")) return;
        event.preventDefault();
        submitManualLog();
    });

    root.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) {
            if (event.target.closest("[data-shortcut-close]")) {
                setShortcutModalOpen(false);
                return;
            }
            const logRow = event.target.closest("[data-log-card-instance], [data-log-card]");
            if (logRow) {
                if (logRow.dataset.logCardInstance) {
                    selectCardInstance(logRow.dataset.logCardInstance);
                    return;
                }
                if (logRow.dataset.logCard) {
                    try {
                        selectLogCard(JSON.parse(logRow.dataset.logCard));
                    } catch (error) {
                        selectLogCard(null);
                    }
                    return;
                }
            }
            const card = event.target.closest("[data-card-open]");
            if (!card) return;
            const cardData = findCard(card.dataset.cardOpen);
            if (!cardData || cardData.hidden) return;
            selectCardInstance(card.dataset.cardOpen);
            return;
        }
        if (button.disabled) return;

        if (button.dataset.cardOpen) {
            const cardData = findCard(button.dataset.cardOpen);
            if (!cardData || cardData.hidden) return;
            selectCardInstance(button.dataset.cardOpen);
            return;
        }

        if (button.dataset.cardDrawerClose !== undefined) {
            selectedCardId = "";
            selectedLogCard = null;
            renderCardDetail();
            return;
        }

        if (button.dataset.cardTool === "blackout_random_get") {
            postAction("blackout_random_get", {
                source_card_instance_id: button.dataset.sourceCard,
            });
            return;
        }

        if (button.dataset.cardTool === "move_card") {
            postAction("move_card", {
                card_instance_id: button.dataset.sourceCard,
                to_player: button.dataset.targetPlayer || envelope.role,
                to_zone: button.dataset.targetZone,
            });
            return;
        }

        if (button.dataset.logToggle !== undefined) {
            setLogOpen(!logOpen);
            return;
        }

        if (button.dataset.shortcutOpen !== undefined) {
            setShortcutModalOpen(true);
            return;
        }

        if (button.dataset.shortcutClose !== undefined) {
            setShortcutModalOpen(false);
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
            const target = button.dataset.fpReset;
            const baseRevision = counterRevision("fp", target);
            clearQueuedCounter("fp", target);
            postAction("fp_reset", { target, base_revision: baseRevision });
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
            shuffleHand(button.dataset.shuffleHandPlayer);
            return;
        }
        if (button.dataset.handVisibilityPlayer) {
            postAction("set_hand_visibility", {
                target: button.dataset.handVisibilityPlayer,
                face_up: button.dataset.handVisibilityValue === "true",
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
            submitManualLog();
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
        if (button.dataset.cardSizeStep !== undefined) {
            setCardSizeIndex(cardSizeIndex + Number(button.dataset.cardSizeStep || 0));
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
        if (!selectedCardId && !selectedLogCard) return;
        if (event.target.closest("[data-card-drawer]")) return;
        if (event.target.closest("[data-card-open]")) return;
        if (event.target.closest("[data-log-card-instance], [data-log-card]")) return;
        selectedCardId = "";
        selectedLogCard = null;
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
                const result = updateEnvelope(nextEnvelope, forceFull ? { force: true } : undefined);
                if (logOpen && !sendLogSubscription(true)) fetchEvents();
                return result;
            })
            .catch((error) => {
                dispatchAutomaticClientError(error, "state_fetch");
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
                dispatchAutomaticClientError(error, "websocket_message_parse");
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
            if (message.type === "warning") {
                showRealtimeToast(message.message || t("요청이 너무 빠르게 반복되고 있습니다."));
                return;
            }
            if (message.type === "signal") {
                if (message.actor !== envelope.role) {
                    showSignalOverlay(message.actor, signalLabel(message.signal, message.label), message.id);
                }
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

    loadCardSizeSetting();
    applyCardSizeSetting();
    render();
    connectSocket();
    window.setInterval(() => {
        if (socketReady && socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "presence" }));
        }
    }, 30000);
    window.addEventListener("lumen-simulator-refresh-request", () => fetchState(true));
    window.setInterval(renderTimer, 1000);
})();
