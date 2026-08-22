(function () {
    "use strict";

    const initialNode = document.getElementById("lumen-simulator-state");
    const panel = document.querySelector("[data-automatic-panel]");
    if (!initialNode || !panel) return;

    const desktopConfig = window.lumenSimulatorConfig || {};
    const mobileConfig = window.lumenSimulatorMobileConfig || {};
    const config = desktopConfig.commandUrl ? desktopConfig : mobileConfig;
    let envelope;
    let initialParseError = null;
    let deadlineRequest = {deadline: "", requestedAt: 0};
    let clientReportInFlight = false;
    let latestAutomaticReportId = "";
    let commandInFlight = false;
    let automaticFeedback = null;
    let feedbackTimer = null;
    let choiceLayer = null;
    let choiceContextKey = "";
    let choiceLayerMinimized = false;
    let choiceScrollLeft = 0;
    let automaticBoardFocusFrame = 0;
    let automaticBoardObserver = null;
    let automaticExpandedZoneKey = "";
    const selectedChoiceKeys = new Set();
    const choiceCardMetadata = new Map();
    const reportedClientErrors = new Set();
    const AUTOMATIC_PRIMARY_ZONES = new Set(["battle", "hand"]);
    try {
        envelope = JSON.parse(initialNode.textContent || "{}");
    } catch (error) {
        initialParseError = error;
        envelope = {};
    }

    function csrfToken() {
        const input = document.querySelector("input[name='csrfmiddlewaretoken']");
        return input ? input.value : "";
    }

    function commandId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }
        return `cmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function automaticContextActive() {
        return !!(
            config.automaticMode ||
            (envelope && envelope.mode === "automatic") ||
            (envelope && envelope.automation_failure)
        );
    }

    function normalizedClientError(value, context) {
        const error = value && typeof value === "object" ? value : {};
        return {
            error_type: String(error.error_type || error.name || "ClientError").slice(0, 120),
            message: String(error.message || value || "브라우저 자동 모드 오류").slice(0, 500),
            source: String(error.source || error.filename || "").slice(0, 1000),
            line: Number(error.line || error.lineno || 0),
            column: Number(error.column || error.colno || 0),
            stack: String(error.stack || "").slice(0, 4000),
            context: String(error.context || context || "client").slice(0, 120),
        };
    }

    async function reportClientError(value, context) {
        if (
            clientReportInFlight || !automaticContextActive() ||
            !config.reportUrl || !["p1", "p2"].includes(config.seat)
        ) return null;
        const diagnostic = normalizedClientError(value, context);
        const fingerprint = JSON.stringify([
            diagnostic.error_type, diagnostic.message, diagnostic.source,
            diagnostic.line, diagnostic.column, diagnostic.context,
        ]);
        if (reportedClientErrors.has(fingerprint)) return null;
        reportedClientErrors.add(fingerprint);
        if (reportedClientErrors.size > 50) {
            reportedClientErrors.delete(reportedClientErrors.values().next().value);
        }
        clientReportInFlight = true;
        try {
            const response = await fetch(config.reportUrl, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
                keepalive: true,
                body: JSON.stringify({
                    kind: "client_error",
                    seat: config.seat || "",
                    seat_token: config.seatToken || "",
                    diagnostic,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) return null;
            latestAutomaticReportId = data.report_id || latestAutomaticReportId;
            panel.querySelectorAll(".v2-automatic-issue-status").forEach((node) => {
                node.textContent = `자동 보고 완료 · ${latestAutomaticReportId}`;
            });
            return data;
        } catch (_reportError) {
            return null;
        } finally {
            clientReportInFlight = false;
        }
    }

    window.addEventListener("error", (event) => {
        if (event.target && event.target !== window) {
            const tag = String(event.target.tagName || "").toUpperCase();
            if (!["SCRIPT", "LINK"].includes(tag)) return;
            reportClientError({
                error_type: "ResourceLoadError",
                message: `${tag} 리소스를 불러오지 못했습니다.`,
                source: event.target.src || event.target.href || "",
            }, "resource_load");
            return;
        }
        reportClientError(event.error || event, "uncaught_error");
    }, true);
    window.addEventListener("unhandledrejection", (event) => {
        reportClientError(event.reason, "unhandled_rejection");
    });
    window.addEventListener("lumen-simulator-client-error", (event) => {
        reportClientError(event.detail || {}, "simulator_transport");
    });

    function hideManualControls(automatic) {
        document.documentElement.classList.toggle("has-automatic-simulator", automatic);
        document.querySelectorAll([
            "[data-sim-action]", "[data-quick-log]", "[data-manual-log-input]",
            "[data-mobile-done-button]", "[data-mobile-log-form]",
        ].join(",")).forEach((node) => {
            node.hidden = automatic;
        });
    }

    function automaticZoneKey(zoneNode) {
        return `${zoneNode.dataset.dropPlayer || ""}:${zoneNode.dataset.dropZone || ""}`;
    }

    function applyAutomaticBoardFocus() {
        automaticBoardFocusFrame = 0;
        const automatic = envelope && envelope.mode === "automatic";
        document.querySelectorAll(".v2-sim-zone").forEach((zoneNode) => {
            const zone = zoneNode.dataset.dropZone || "";
            const header = zoneNode.querySelector(":scope > header");
            const collapsible = automatic && !AUTOMATIC_PRIMARY_ZONES.has(zone);
            const expanded = collapsible
                && automaticExpandedZoneKey === automaticZoneKey(zoneNode);
            zoneNode.classList.toggle("is-automatic-collapsible", collapsible);
            zoneNode.classList.toggle("is-automatic-expanded", expanded);
            if (!header) return;
            if (collapsible) {
                header.tabIndex = 0;
                header.setAttribute("role", "button");
                header.setAttribute("aria-expanded", String(expanded));
                header.title = expanded ? "영역 접기" : "영역 펼치기";
            } else {
                header.removeAttribute("tabindex");
                header.removeAttribute("role");
                header.removeAttribute("aria-expanded");
                header.removeAttribute("title");
            }
        });
        if (automatic) {
            document.querySelectorAll(".v2-sim-card[draggable='true']").forEach((card) => {
                card.draggable = false;
            });
        }
    }

    function scheduleAutomaticBoardFocus() {
        if (automaticBoardFocusFrame) window.cancelAnimationFrame(automaticBoardFocusFrame);
        automaticBoardFocusFrame = window.requestAnimationFrame(applyAutomaticBoardFocus);
    }

    function observeAutomaticBoard() {
        const board = document.querySelector(".v2-sim-layout");
        if (!board || typeof window.MutationObserver !== "function") return;
        automaticBoardObserver = new window.MutationObserver(() => {
            if (envelope && envelope.mode === "automatic") {
                scheduleAutomaticBoardFocus();
            }
        });
        automaticBoardObserver.observe(board, {childList: true, subtree: true});
    }

    function toggleAutomaticZone(header) {
        if (!envelope || envelope.mode !== "automatic") return;
        const zoneNode = header && header.closest(".v2-sim-zone");
        if (!zoneNode || AUTOMATIC_PRIMARY_ZONES.has(zoneNode.dataset.dropZone || "")) return;
        const key = automaticZoneKey(zoneNode);
        automaticExpandedZoneKey = automaticExpandedZoneKey === key ? "" : key;
        applyAutomaticBoardFocus();
    }

    document.addEventListener("click", (event) => {
        const header = event.target.closest && event.target.closest(".v2-sim-zone > header");
        if (header) toggleAutomaticZone(header);
    });
    document.addEventListener("keydown", (event) => {
        if (!['Enter', ' '].includes(event.key)) return;
        const header = event.target.closest && event.target.closest(".v2-sim-zone > header");
        if (!header || header.getAttribute("role") !== "button") return;
        event.preventDefault();
        toggleAutomaticZone(header);
    });

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function cloneData(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function allVisibleCards(sourceEnvelope) {
        const cards = [];
        const players = ((sourceEnvelope || {}).state || {}).players || {};
        Object.values(players).forEach((player) => {
            Object.values((player || {}).zones || {}).forEach((zoneCards) => {
                (zoneCards || []).forEach((card) => cards.push(card));
            });
        });
        return cards;
    }

    function hydrateChoiceCard(card) {
        if (!card || card.hidden || !card.card_id) return card;
        const metadata = choiceCardMetadata.get(String(card.card_id));
        if (!metadata) return card;
        const hydrated = {...metadata, ...card};
        if (config.language && config.language !== "ko") {
            ["name", "text", "detail_text"].forEach((field) => {
                if (Object.prototype.hasOwnProperty.call(metadata, field)) {
                    hydrated[field] = metadata[field];
                }
            });
        }
        return hydrated;
    }

    function findVisibleCard(instanceId, sourceEnvelope) {
        if (!instanceId) return null;
        const card = allVisibleCards(sourceEnvelope || envelope).find(
            (card) => String(card.instance_id || "") === String(instanceId),
        ) || null;
        return hydrateChoiceCard(card);
    }

    function findVisibleCardZone(instanceId, sourceEnvelope) {
        if (!instanceId) return "";
        const players = (((sourceEnvelope || envelope) || {}).state || {}).players || {};
        for (const player of Object.values(players)) {
            for (const [zone, cards] of Object.entries((player || {}).zones || {})) {
                if ((cards || []).some(
                    (card) => String(card.instance_id || "") === String(instanceId),
                )) return zone;
            }
        }
        return "";
    }

    window.addEventListener("lumen-simulator-card-metadata", (event) => {
        Object.entries(((event.detail || {}).cards) || {}).forEach(([cardId, metadata]) => {
            if (!cardId || !metadata || typeof metadata !== "object") return;
            choiceCardMetadata.set(String(cardId), metadata);
        });
        if (choiceLayer && !choiceLayer.hidden) renderChoiceLayer();
    });

    function actionCardIds(action) {
        const payload = (action && action.payload) || {};
        if (Array.isArray(payload.card_instance_ids)) return payload.card_instance_ids.filter(Boolean);
        if (payload.card_instance_id) return [payload.card_instance_id];
        if (Array.isArray(action && action.cards)) {
            return action.cards.map((card) => card && card.instance_id).filter(Boolean);
        }
        if (action && action.card && action.card.instance_id) return [action.card.instance_id];
        return [];
    }

    function actionCards(action) {
        const supplied = Array.isArray(action && action.cards)
            ? action.cards
            : action && action.card ? [action.card] : [];
        const byId = new Map(supplied.map((card) => [String(card.instance_id || ""), card]));
        return actionCardIds(action).map((instanceId) => ({
            ...(findVisibleCard(instanceId) || {}),
            ...(byId.get(String(instanceId)) || {}),
        }));
    }

    function actionSignature(action) {
        return `${(action && action.type) || ""}:${JSON.stringify((action && action.payload) || {})}`;
    }

    function actionSelectionsRemainValid(action, selections) {
        if (!action || action.type !== "submit_decision") return true;
        const valid = new Set((action.options || []).map((option) => String(option.id)));
        const selected = ((selections || {}).selected || []).map(String);
        return selected.every((item) => valid.has(item))
            && selected.length >= Number(action.minimum || 0)
            && selected.length <= Number(action.maximum || 1);
    }

    function equivalentLegalAction(previousAction, selections) {
        const signature = actionSignature(previousAction);
        return (envelope.legal_actions || []).find(
            (action) => actionSignature(action) === signature
                && actionSelectionsRemainValid(action, selections),
        ) || null;
    }

    function automaticStateUrl() {
        const url = new URL(config.stateUrl, window.location.origin);
        if (config.seat) url.searchParams.set("seat", config.seat);
        if (config.seatToken) url.searchParams.set("seat_token", config.seatToken);
        return url.toString();
    }

    async function fetchLatestAutomaticState() {
        const response = await fetch(automaticStateUrl(), {cache: "no-store"});
        const data = await response.json();
        if (!response.ok || !data || data.unchanged) {
            throw new Error("최신 게임 상태를 불러오지 못했습니다.");
        }
        return data;
    }

    function applyBoardEnvelope(nextEnvelope, optimistic) {
        window.dispatchEvent(new CustomEvent("lumen-simulator-apply-state", {detail: {
            envelope: nextEnvelope,
            optimistic: !!optimistic,
        }}));
    }

    function moveProjectedCard(projected, instanceId, toZone, faceUp, toPlayer) {
        const players = ((projected || {}).state || {}).players || {};
        let found = null;
        Object.entries(players).some(([side, player]) => Object.entries((player || {}).zones || {}).some(([zone, cards]) => {
            const index = (cards || []).findIndex(
                (card) => String(card.instance_id || "") === String(instanceId),
            );
            if (index < 0) return false;
            found = {side, zone, card: cards.splice(index, 1)[0]};
            return true;
        }));
        if (!found) return;
        const owner = ["p1", "p2"].includes(found.card.owner) ? found.card.owner : found.side;
        const target = players[toPlayer] || players[owner] || players[found.side];
        if (!target || !target.zones || !Array.isArray(target.zones[toZone])) return;
        found.card.face_up = !!faceUp;
        found.card.hidden = false;
        target.zones[toZone].push(found.card);
    }

    function optimisticEnvelope(action, selections) {
        const projected = cloneData(envelope);
        const ids = actionCardIds(action);
        if (action.type === "ready_card") {
            ids.forEach((instanceId) => moveProjectedCard(projected, instanceId, "battle", false, envelope.role));
        } else if (["select_get_card", "select_ultimate"].includes(action.type)) {
            ids.forEach((instanceId) => moveProjectedCard(projected, instanceId, "hand", false, envelope.role));
        } else if (["play_combo_card", "play_combo_pair", "play_combo_sequence", "play_catch_card"].includes(action.type)) {
            ids.forEach((instanceId) => moveProjectedCard(projected, instanceId, "battle", true, envelope.role));
        } else if (action.type === "select_combo_followup") {
            (((action.payload || {}).proposal || {}).card_instance_ids || []).forEach(
                (instanceId) => moveProjectedCard(projected, instanceId, "battle", true, envelope.role),
            );
        }
        projected.legal_actions = [];
        projected.optimistic_submission = {
            type: action.type,
            label: action.label || action.type,
            selected: cloneData((selections || {}).selected || []),
        };
        return projected;
    }

    function setFeedback(message, kind) {
        window.clearTimeout(feedbackTimer);
        feedbackTimer = null;
        automaticFeedback = message ? {message, kind: kind || "info"} : null;
        if (automaticFeedback && ["info", "success"].includes(automaticFeedback.kind)) {
            feedbackTimer = window.setTimeout(() => {
                automaticFeedback = null;
                feedbackTimer = null;
                render();
            }, 4500);
        }
    }

    function clockText(clock) {
        if (!clock) return "";
        if (clock.paused) return `일시정지 · ${clock.pause_reason || "사유 기록됨"}`;
        if (!clock.deadline) return "";
        const remaining = Math.max(0, Math.ceil((new Date(clock.deadline).getTime() - Date.now()) / 1000));
        return `${clock.owner || ""} · ${remaining}초`;
    }

    function timeoutLabel(value) {
        return value === null || value === undefined ? "제한 없음" : `${value}초`;
    }

    const PHASE_LABELS = {
        setup: "게임 준비", lumen: "루멘", ready: "레디",
        battle: "배틀", get: "겟", recovery: "리커버리",
    };
    const ENGINE_STEP_LABELS = {
        setup: "게임 준비", lumen: "루멘 행동", ready: "레디 선택",
        battle: "배틀 처리", battle_reveal: "기술 공개",
        battle_resolution: "판정 처리", battle_cleanup: "배틀 정리",
        get_actions: "기술 획득", recovery: "리커버리 처리",
        combo: "콤보 선택", combo_resolution: "콤보 처리",
        catch: "캐치 선택", catch_resolution: "캐치 처리",
    };

    function focusPhaseLabel(phase) {
        return (envelope.phase_labels && envelope.phase_labels[phase])
            || PHASE_LABELS[phase] || phase || "-";
    }

    function focusStepLabel(step) {
        return ENGINE_STEP_LABELS[step]
            || String(step || "처리 중").replaceAll("_", " ");
    }

    function focusPlayerOrder() {
        if (["p1", "p2"].includes(envelope.role)) {
            return [envelope.role, envelope.role === "p1" ? "p2" : "p1"];
        }
        return ["p1", "p2"];
    }

    function appendFocusStat(holder, label, value, className) {
        const stat = element("span", `v2-automatic-focus-stat ${className || ""}`.trim());
        stat.append(element("small", "", label), element("strong", "", String(value)));
        holder.appendChild(stat);
    }

    function renderFocusPlayer(side) {
        const state = envelope.state || {};
        const player = ((state.players || {})[side]) || {};
        const priority = state.priority_player === side;
        const active = (envelope.clocks || {}).owner === side
            || (envelope.pending_decision || {}).owner === side;
        const card = element(
            "article",
            `v2-automatic-focus-player${side === envelope.role ? " is-self" : ""}`
                + `${priority ? " is-priority" : ""}${active ? " is-active" : ""}`,
        );
        const head = element("header", "");
        const identity = element("div", "");
        identity.append(
            element("span", "", `${side.toUpperCase()}${side === envelope.role ? " · 나" : ""}`),
            element("strong", "", player.name || side.toUpperCase()),
        );
        head.appendChild(identity);
        const flags = element("div", "v2-automatic-focus-flags");
        if (priority) flags.appendChild(element("span", "is-priority", "우선권"));
        if ((envelope.controllers || {})[side] === "ai") flags.appendChild(element("span", "", "AI"));
        if (active) flags.appendChild(element("span", "is-active", "선택 중"));
        head.appendChild(flags);
        card.appendChild(head);

        const stats = element("div", "v2-automatic-focus-stats");
        appendFocusStat(stats, "HP", Number(player.hp || 0), "is-hp");
        appendFocusStat(stats, "FP", Number(player.fp || 0), Number(player.fp || 0) < 0 ? "is-fp is-negative" : "is-fp");
        card.appendChild(stats);
        return card;
    }

    function renderAutomaticFocus(status) {
        const state = envelope.state || {};
        const focus = element("section", "v2-automatic-focus");
        const top = element("header", "v2-automatic-focus-head");
        const brand = element("div", "");
        brand.append(
            element("span", "", "AUTOMATIC JUDGMENT"),
            element("strong", "", envelope.ruleset_version || "자동 규칙"),
        );
        top.appendChild(brand);
        const fullscreenActive = !!(
            document.fullscreenElement
            || document.webkitFullscreenElement
            || document.msFullscreenElement
        );
        const fullscreen = element(
            "button", "v2-button v2-automatic-fullscreen",
            fullscreenActive ? "전체화면 종료" : "전체화면",
        );
        fullscreen.type = "button";
        fullscreen.dataset.fullscreenToggle = "";
        fullscreen.setAttribute("aria-pressed", String(fullscreenActive));
        top.appendChild(fullscreen);
        focus.appendChild(top);

        const matchup = element("div", "v2-automatic-focus-matchup");
        const order = focusPlayerOrder();
        matchup.appendChild(renderFocusPlayer(order[0]));
        const center = element("div", "v2-automatic-focus-center");
        center.append(
            element("span", "", `${Number(state.turn || 1)} TURN`),
            element("strong", "", focusPhaseLabel(state.phase)),
            element("small", "", focusStepLabel(status.step)),
        );
        const clock = element("div", "v2-automatic-clock", clockText(envelope.clocks));
        if (clock.textContent) center.appendChild(clock);
        const decision = envelope.pending_decision;
        let prompt = "자동 해결 또는 상대 행동을 기다리는 중입니다.";
        if (decision) prompt = decision.prompt || "선택을 처리하고 있습니다.";
        else if ((envelope.legal_actions || []).length) prompt = "화면 아래에서 행동을 선택하세요.";
        if (status.status && status.status !== "running") {
            prompt = status.winner
                ? `${String(status.winner).toUpperCase()} 승리 · ${status.reason || "게임 종료"}`
                : status.reason || status.status;
        }
        center.appendChild(element("p", "v2-automatic-focus-prompt", prompt));
        matchup.append(center, renderFocusPlayer(order[1]));
        focus.appendChild(matchup);

        const meta = element("footer", "v2-automatic-focus-meta");
        const timerSettings = envelope.timer_settings || {};
        meta.appendChild(element(
            "span", "",
            `레디 ${timeoutLabel(timerSettings.ready_timeout_seconds)} · 효과 ${timeoutLabel(timerSettings.effect_timeout_seconds)}`,
        ));
        if (envelope.ai_policy_version) {
            meta.appendChild(element("span", "", `AI ${envelope.ai_policy_version}`));
        }
        focus.appendChild(meta);
        panel.appendChild(focus);
    }

    async function submit(action, selections, button) {
        if (commandInFlight || !action) return;
        selections = cloneData(selections || {});
        if (action.type === "pause_clock") {
            const reason = window.prompt("일시정지 사유를 입력하세요.", "");
            if (!reason) return;
            selections.reason = reason;
        }
        commandInFlight = true;
        setFeedback("선택을 적용하고 있습니다.", "pending");
        const stableCommandId = commandId();
        let currentAction = action;
        let retryCount = 0;
        applyBoardEnvelope(optimisticEnvelope(currentAction, selections), true);
        render();
        try {
            while (retryCount <= 1) {
                const response = await fetch(config.commandUrl, {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
                    body: JSON.stringify({
                        seat: config.seat || "",
                        seat_token: config.seatToken || "",
                        command_id: stableCommandId,
                        expected_version: envelope.version,
                        action_id: currentAction.action_id,
                        selections,
                    }),
                });
                let data;
                try {
                    data = await response.json();
                } catch (error) {
                    error.context = "command_response_parse";
                    throw error;
                }
                if (response.ok && data.ok) {
                    envelope = data.state;
                    setFeedback("선택이 적용되었습니다.", "success");
                    applyBoardEnvelope(envelope, false);
                    return;
                }
                if (data.code === "stale_state" && retryCount === 0) {
                    envelope = data.state || await fetchLatestAutomaticState();
                    applyBoardEnvelope(envelope, false);
                    const retryAction = equivalentLegalAction(currentAction, selections);
                    if (retryAction) {
                        currentAction = retryAction;
                        retryCount += 1;
                        setFeedback("최신 상태에 맞춰 선택을 다시 적용하고 있습니다.", "pending");
                        applyBoardEnvelope(optimisticEnvelope(currentAction, selections), true);
                        render();
                        continue;
                    }
                    setFeedback("게임이 먼저 진행되어 선택지가 바뀌었습니다. 새 선택지를 확인해 주세요.", "info");
                    return;
                }
                const error = new Error(data.error || "자동 명령을 처리하지 못했습니다.");
                error.serverRejected = true;
                error.code = data.code || "";
                throw error;
            }
        } catch (error) {
            if (!error.serverRejected) {
                reportClientError(error, error.context || "command_submit");
            }
            setFeedback(error.message || String(error), "error");
            applyBoardEnvelope(envelope, false);
        } finally {
            commandInFlight = false;
            if (button) button.disabled = false;
            render();
        }
    }

    async function submitIssue(textarea, button, status) {
        const details = textarea.value.trim();
        if (!details) return;
        button.disabled = true;
        try {
            const response = await fetch(config.reportUrl, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
                body: JSON.stringify({
                    kind: "user",
                    seat: config.seat || "",
                    seat_token: config.seatToken || "",
                    details,
                    report_id: latestAutomaticReportId || "",
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) throw new Error(data.error || "문제를 제보하지 못했습니다.");
            textarea.value = "";
            latestAutomaticReportId = data.report_id || latestAutomaticReportId;
            status.textContent = `제보 완료 · ${data.report_id}`;
        } catch (error) {
            status.textContent = error.message || String(error);
        } finally {
            button.disabled = false;
        }
    }

    function renderIssueReporter() {
        if (!config.reportUrl || !["p1", "p2"].includes(envelope.role)) return;
        const details = element("details", "v2-automatic-issue");
        const summary = element("summary", "", envelope.automation_failure ? "자동 오류에 내용 추가" : "문제 제보");
        const textarea = element("textarea", "v2-automatic-issue-text");
        textarea.maxLength = 4000;
        textarea.rows = 3;
        textarea.placeholder = "발생한 상황과 기대한 동작을 적어주세요.";
        const button = element("button", "v2-button", "서버에 제보");
        button.type = "button";
        const status = element("span", "v2-automatic-issue-status", "");
        if (latestAutomaticReportId) {
            status.textContent = `자동 보고 · ${latestAutomaticReportId}`;
        }
        button.addEventListener("click", () => submitIssue(textarea, button, status));
        details.append(summary, textarea, button, status);
        panel.appendChild(details);
    }

    function choiceLayerNode() {
        if (choiceLayer) return choiceLayer;
        choiceLayer = element("section", "v2-automatic-choice-layer");
        choiceLayer.hidden = true;
        choiceLayer.setAttribute("aria-live", "polite");
        document.body.appendChild(choiceLayer);
        return choiceLayer;
    }

    function isCardAction(action) {
        return !!(
            (action && action.card)
            || (Array.isArray(action && action.cards) && action.cards.length)
            || actionCardIds(action).length
        );
    }

    const CARD_DECISION_KINDS = new Set([
        "ability_target", "effect_choice", "hand_guess_card",
        "no_response_card", "grab_negation", "break_replenish",
        "play_cost", "defense_cost", "hand_limit_discard",
    ]);

    function decisionOptionCard(option, decisionKind) {
        const instanceId = option && (option.card_instance_id || option.id);
        const optionId = String((option && option.id) || "");
        // ``decline`` is a control value, not a card. Treating it as an
        // instance id used to render a misleading face-down card that players
        // had to select in order to confirm zero choices. ``accept`` keeps its
        // source card so choosing the optional effect remains image-based.
        if (optionId === "decline" && !(option && option.card)) {
            return null;
        }
        const supplied = option && option.card
            ? hydrateChoiceCard({...option.card, instance_id: option.card.instance_id || instanceId})
            : null;
        if (supplied) return supplied;
        const visible = findVisibleCard(instanceId);
        if (visible) return visible;
        if (!instanceId || !CARD_DECISION_KINDS.has(String(decisionKind || ""))) return null;
        return {
            instance_id: String(instanceId), hidden: true,
            name: "비공개 카드",
        };
    }

    function choiceModel() {
        const actions = envelope.legal_actions || [];
        const decisionAction = actions.find((action) => action.type === "submit_decision");
        if (decisionAction) {
            const decisionKind = (envelope.pending_decision || {}).kind || "";
            const mapped = (decisionAction.options || []).map((option) => {
                const card = decisionOptionCard(option, decisionKind);
                return {
                    key: String(option.id),
                    value: String(option.id),
                    label: option.label || option.id,
                    option,
                    cards: card ? [card] : [],
                    effectMode: option.effect_mode || "",
                    effectZones: Array.isArray(option.active_zones)
                        ? option.active_zones.filter(Boolean)
                        : option.source_zone ? [option.source_zone] : [],
                };
            });
            const hasCardChoice = mapped.some((entry) => entry.cards.length);
            const declineEntry = hasCardChoice
                ? mapped.find((entry) => !entry.cards.length && entry.value === "decline")
                : null;
            const entries = mapped.filter((entry) => entry !== declineEntry);
            const canConfirmEmpty = !!declineEntry || Number(decisionAction.minimum || 0) === 0;
            return {
                kind: "decision",
                action: decisionAction,
                entries,
                secondary: [],
                minimum: canConfirmEmpty ? 0 : Number(decisionAction.minimum || 0),
                maximum: Number(decisionAction.maximum || 1),
                emptySelectionValues: declineEntry ? [declineEntry.value] : [],
                prompt: (envelope.pending_decision || {}).prompt || decisionAction.label,
            };
        }
        const primary = actions.filter(isCardAction).map((action) => {
            const payload = action.payload || {};
            const actionZones = action.active_zones
                || action.source_zones
                || payload.source_zones
                || [
                    action.source_zone
                    || payload.source_zone
                    || findVisibleCardZone(actionCardIds(action)[0]),
                ];
            return {
                key: actionSignature(action),
                value: actionSignature(action),
                label: action.label || action.type,
                action,
                cards: actionCards(action),
                choiceSpeed: action.choice_speed
                    ?? payload.choice_speed
                    ?? payload.combo_speed,
                effectZones: actionZones.filter(Boolean),
            };
        });
        const secondary = actions.filter((action) => !isCardAction(action));
        if (!primary.length && secondary.length === 1 && ![
            "concede", "request_rewind", "pause_clock", "resume_clock",
        ].includes(secondary[0].type)) {
            const action = secondary.shift();
            primary.push({
                key: actionSignature(action), value: actionSignature(action),
                label: action.label || action.type, action, cards: [],
            });
        }
        return {
            kind: "action",
            entries: primary,
            secondary,
            minimum: primary.length ? 1 : 0,
            maximum: primary.length ? 1 : 0,
            emptySelectionValues: [],
            prompt: actionChoicePrompt(actions, primary),
        };
    }

    function actionChoicePrompt(actions, primary) {
        const pendingPrompt = (envelope.pending_decision || {}).prompt;
        if (pendingPrompt) return pendingPrompt;
        const types = new Set((actions || []).map((action) => action.type));
        const comboNumbers = (primary || []).map((entry) => Number(
            entry.action.combo_number
            ?? ((entry.action.payload || {}).combo_number),
        )).filter((value) => Number.isFinite(value) && value > 0);
        const comboNumber = comboNumbers.length ? Math.min(...comboNumbers) : 0;
        if (types.has("select_get_card") || types.has("select_ultimate")) {
            return "GET PHASE : 획득할 기술을 선택하세요.";
        }
        if (types.has("ready_card")) {
            return "READY PHASE : 레디할 기술을 선택하세요.";
        }
        if (types.has("select_combo_first")) {
            return `COMBO TIME : ${comboNumber || 2}콤보로 사용할 첫 기술을 선택하세요.`;
        }
        if (types.has("select_combo_followup")) {
            return `COMBO TIME : ${comboNumber || 3}콤보로 사용할 기술을 선택하세요.`;
        }
        if (
            types.has("play_combo_card") || types.has("play_combo_pair")
            || types.has("play_combo_sequence")
        ) {
            return comboNumber
                ? `COMBO TIME : ${comboNumber}콤보로 사용할 기술을 선택하세요.`
                : "COMBO TIME : 다음 콤보로 사용할 기술을 선택하세요.";
        }
        if (types.has("play_catch_card")) {
            return "CATCH TIME : 캐치할 기술과 사용할 속도를 선택하세요.";
        }
        if (types.has("end_combo")) return "COMBO TIME : 콤보를 종료할지 선택하세요.";
        if (types.has("decline_catch")) return "CATCH TIME : 캐치를 종료할지 선택하세요.";
        const phase = String(((envelope.state || {}).phase) || "").toUpperCase();
        if (types.has("pass_phase") && phase) {
            return `${phase} PHASE : 페이즈를 종료할지 선택하세요.`;
        }
        return "현재 진행할 행동을 선택하세요.";
    }

    function syncChoiceContext(model) {
        const nextKey = `${model.kind}:${(model.action || {}).action_id || ""}:${model.entries.map((entry) => entry.key).join("|")}`;
        if (choiceContextKey === nextKey) return false;
        choiceContextKey = nextKey;
        choiceLayerMinimized = false;
        choiceScrollLeft = 0;
        selectedChoiceKeys.clear();
        return true;
    }

    function choiceIsSelected(entry) {
        return selectedChoiceKeys.has(entry.key);
    }

    function toggleChoice(model, entry) {
        if (commandInFlight) return;
        if (choiceIsSelected(entry)) {
            selectedChoiceKeys.delete(entry.key);
        } else {
            if (model.maximum <= 1) selectedChoiceKeys.clear();
            if (selectedChoiceKeys.size < model.maximum) selectedChoiceKeys.add(entry.key);
        }
        renderChoiceLayer();
        openChoiceCardDetail(model, entry);
    }

    function openChoiceCardDetail(model, entry) {
        const cards = (entry && entry.cards) || [];
        const card = cards.find((item) => item && !item.hidden && item.instance_id);
        if (!card) return;
        window.dispatchEvent(new CustomEvent("lumen-simulator-open-card-detail", {detail: {
            instance_id: String(card.instance_id),
            effect_prompt: String((model && model.prompt) || (entry && entry.label) || ""),
            option_label: entry && entry.value === "accept"
                ? ""
                : String((entry && entry.label) || ""),
            sequence_labels: cards.map((item) => item && !item.hidden
                ? String(item.name || item.code || "카드")
                : "비공개 카드"),
        }}));
    }

    function choiceCardMedia(entry) {
        const media = element("span", "v2-automatic-choice-media");
        const cards = entry.cards || [];
        if (!cards.length) {
            media.classList.add("is-effect-choice");
            media.appendChild(element("span", "v2-automatic-choice-symbol", "◆"));
            media.appendChild(element("strong", "", entry.label));
            return media;
        }
        media.classList.toggle("is-card-sequence", cards.length > 1);
        cards.forEach((card) => {
            const frame = element("span", "v2-automatic-choice-card-frame");
            const imageUrl = card && !card.hidden ? (card.img || card.img_sm || "") : "";
            if (imageUrl) {
                const image = element("img", "", undefined);
                image.src = imageUrl;
                image.alt = card.name || entry.label || "카드";
                image.loading = "lazy";
                frame.appendChild(image);
            } else if (card && !card.hidden) {
                frame.classList.add("is-image-loading");
            } else {
                frame.classList.add("is-card-back");
                frame.appendChild(element("span", "", "LUMEN"));
            }
            media.appendChild(frame);
        });
        return media;
    }

    function choiceEntryLabel(entry) {
        const cards = entry.cards || [];
        if (!cards.length) return entry.label;
        return cards.map((card) => (
            card && !card.hidden ? (card.name || "카드") : "비공개 카드"
        )).join(" → ");
    }

    const EFFECT_MODE_ICONS = {
        mandatory: {symbol: "!", label: "강제 효과"},
        optional: {symbol: "?", label: "선택 가능 효과"},
    };
    const EFFECT_ZONE_ICONS = {
        battle: {symbol: "⚔", label: "배틀 존"},
        hand: {symbol: "▤", label: "패"},
        list: {symbol: "≡", label: "리스트"},
        side: {symbol: "◫", label: "사이드 덱"},
        lumen: {symbol: "✦", label: "루멘 존"},
        break: {symbol: "×", label: "브레이크 존"},
        passive: {symbol: "∞", label: "패시브 존"},
        ultimate: {symbol: "★", label: "얼티밋 존"},
        character: {symbol: "♟", label: "캐릭터 존"},
    };

    function renderChoiceEffectBadges(button, entry) {
        const mode = EFFECT_MODE_ICONS[entry.effectMode];
        if (mode) {
            const badge = element(
                "span", `v2-automatic-effect-badge is-${entry.effectMode}`,
                mode.symbol,
            );
            badge.title = mode.label;
            badge.setAttribute("aria-label", mode.label);
            button.appendChild(badge);
        }
        const zones = Array.from(new Set(entry.effectZones || []))
            .map((zone) => ({zone, ...(EFFECT_ZONE_ICONS[zone] || {})}))
            .filter((zone) => zone.symbol);
        if (!zones.length) return;
        const holder = element("span", "v2-automatic-zone-badges");
        zones.forEach((zone) => {
            const badge = element("span", "v2-automatic-zone-badge", zone.symbol);
            badge.title = `${zone.label}에서 발동`;
            badge.setAttribute("aria-label", `${zone.label}에서 발동`);
            holder.appendChild(badge);
        });
        button.appendChild(holder);
    }

    function renderChoiceSpeedBadge(button, entry) {
        if (entry.choiceSpeed === null || entry.choiceSpeed === undefined || entry.choiceSpeed === "") return;
        const badge = element(
            "span", "v2-automatic-speed-badge", String(entry.choiceSpeed),
        );
        badge.title = `${entry.choiceSpeed}속도`;
        badge.setAttribute("aria-label", `${entry.choiceSpeed}속도`);
        button.appendChild(badge);
        if (entry.effectMode) button.classList.add("has-speed-and-effect-badge");
    }

    function renderChoiceEntry(model, entry, index) {
        const button = element("button", "v2-automatic-choice-card");
        button.type = "button";
        button.dataset.choiceKey = entry.key;
        button.classList.toggle("is-selected", choiceIsSelected(entry));
        button.setAttribute("aria-pressed", choiceIsSelected(entry) ? "true" : "false");
        button.disabled = commandInFlight;
        button.appendChild(choiceCardMedia(entry));
        renderChoiceSpeedBadge(button, entry);
        renderChoiceEffectBadges(button, entry);
        const label = element("span", "v2-automatic-choice-label", choiceEntryLabel(entry));
        button.appendChild(label);
        if (choiceIsSelected(entry)) {
            const order = Array.from(selectedChoiceKeys).indexOf(entry.key) + 1;
            button.appendChild(element("span", "v2-automatic-choice-order", String(order || index + 1)));
        }
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            toggleChoice(model, entry);
        });
        return button;
    }

    function submitChoiceModel(model, button) {
        const selected = model.entries.filter((entry) => choiceIsSelected(entry));
        if (selected.length < model.minimum || selected.length > model.maximum) return;
        if (model.kind === "decision") {
            const values = selected.length
                ? selected.map((entry) => entry.value)
                : model.emptySelectionValues;
            submit(model.action, {selected: values}, button);
            return;
        }
        submit(selected[0] && selected[0].action, {}, button);
    }

    function renderChoiceLayer() {
        const layer = choiceLayerNode();
        const previousCards = layer.querySelector(".v2-automatic-choice-scroll");
        if (previousCards) choiceScrollLeft = previousCards.scrollLeft || 0;
        const previousScroll = choiceScrollLeft;
        const automatic = envelope && envelope.mode === "automatic";
        const model = choiceModel();
        const hasControls = model.entries.length || model.secondary.length;
        layer.hidden = !automatic || !hasControls;
        document.documentElement.classList.toggle(
            "has-automatic-choice", automatic && hasControls,
        );
        if (layer.hidden) {
            choiceLayerMinimized = false;
            layer.classList.remove("is-minimized");
            document.documentElement.classList.remove("has-automatic-choice-minimized");
            layer.replaceChildren();
            return;
        }
        const contextChanged = syncChoiceContext(model);
        layer.classList.toggle("is-minimized", choiceLayerMinimized);
        document.documentElement.classList.toggle(
            "has-automatic-choice-minimized", choiceLayerMinimized,
        );
        layer.replaceChildren();

        if (choiceLayerMinimized) {
            const minimized = element("div", "v2-automatic-choice-minimized");
            const progress = element("div", "v2-automatic-choice-progress");
            progress.appendChild(element("span", ""));
            minimized.appendChild(progress);
            const summary = element("div", "");
            summary.append(
                element("span", "", "ACTION SELECT"),
                element("strong", "", model.prompt || "선택이 대기 중입니다."),
            );
            minimized.appendChild(summary);
            const open = element("button", "v2-button v2-button-primary", "선택창 열기");
            open.type = "button";
            open.addEventListener("click", () => {
                choiceLayerMinimized = false;
                renderChoiceLayer();
            });
            minimized.appendChild(open);
            layer.appendChild(minimized);
            updateChoiceClockVisual();
            return;
        }

        const shell = element("div", "v2-automatic-choice-shell");
        const progress = element("div", "v2-automatic-choice-progress");
        progress.appendChild(element("span", ""));
        shell.appendChild(progress);
        const head = element("header", "v2-automatic-choice-head");
        const title = element("div", "");
        title.appendChild(element("span", "", "ACTION SELECT"));
        title.appendChild(element("strong", "", model.prompt || "행동을 선택하세요."));
        head.appendChild(title);
        const headActions = element("div", "v2-automatic-choice-head-actions");
        if (model.maximum > 1) {
            headActions.appendChild(element(
                "span", "v2-automatic-choice-count",
                `${selectedChoiceKeys.size} / ${model.minimum}~${model.maximum}`,
            ));
        }
        const hide = element("button", "v2-button v2-automatic-choice-hide", "숨기기");
        hide.type = "button";
        hide.addEventListener("click", () => {
            choiceLayerMinimized = true;
            renderChoiceLayer();
        });
        headActions.appendChild(hide);
        head.appendChild(headActions);
        shell.appendChild(head);

        const body = element("div", "v2-automatic-choice-body");
        const cards = element("div", "v2-automatic-choice-scroll");
        cards.addEventListener("scroll", () => {
            choiceScrollLeft = cards.scrollLeft;
        }, {passive: true});
        cards.addEventListener("wheel", (event) => {
            if (
                cards.scrollWidth <= cards.clientWidth
                || Math.abs(event.deltaY) <= Math.abs(event.deltaX)
            ) return;
            const previous = cards.scrollLeft;
            cards.scrollLeft += event.deltaY;
            if (cards.scrollLeft !== previous) event.preventDefault();
        }, {passive: false});
        model.entries.forEach((entry, index) => cards.appendChild(renderChoiceEntry(model, entry, index)));
        if (!model.entries.length) {
            cards.appendChild(element("p", "v2-automatic-wait", "아래 행동을 선택하세요."));
        }
        body.appendChild(cards);
        if (!contextChanged && previousScroll) {
            cards.scrollLeft = previousScroll;
            window.requestAnimationFrame(() => {
                cards.scrollLeft = previousScroll;
            });
        }
        shell.appendChild(body);

        const footer = element("footer", "v2-automatic-choice-footer");
        const secondary = element("div", "v2-automatic-choice-secondary");
        model.secondary.forEach((action) => {
            const button = element("button", "v2-button", action.label || action.type);
            button.type = "button";
            button.disabled = commandInFlight;
            button.addEventListener("click", () => submit(action, {}, button));
            secondary.appendChild(button);
        });
        footer.appendChild(secondary);
        if (model.entries.length) {
            const selectedCount = selectedChoiceKeys.size;
            const confirm = element(
                "button", "v2-button v2-button-primary v2-automatic-confirm",
                commandInFlight ? `${selectedCount} 처리 중…` : `${selectedCount} 확정`,
            );
            confirm.type = "button";
            confirm.disabled = commandInFlight
                || selectedCount < model.minimum
                || selectedCount > model.maximum;
            confirm.addEventListener("click", () => submitChoiceModel(model, confirm));
            footer.appendChild(confirm);
        }
        shell.appendChild(footer);
        layer.appendChild(shell);
        updateChoiceClockVisual();
    }

    function updateChoiceClockVisual() {
        const bar = choiceLayer && choiceLayer.querySelector(".v2-automatic-choice-progress > span");
        if (!bar) return;
        const clock = envelope.clocks || {};
        const duration = Number(clock.duration_seconds || 0);
        let remaining = duration;
        if (clock.paused) {
            remaining = Number(clock.remaining_seconds || 0);
        } else if (clock.deadline) {
            remaining = Math.max(0, (new Date(clock.deadline).getTime() - Date.now()) / 1000);
        }
        const actualRatio = duration > 0 ? Math.max(0, Math.min(1, remaining / duration)) : 0;
        // Presentation easing only: the deadline and timeout settlement still
        // use the unmodified server clock.
        const visualRatio = Math.pow(actualRatio, 1.65);
        bar.style.width = `${visualRatio * 100}%`;
        bar.classList.toggle("is-urgent", actualRatio <= 0.25);
        bar.parentElement.hidden = !duration;
    }

    function render() {
        const automatic = envelope && envelope.mode === "automatic";
        hideManualControls(automatic);
        scheduleAutomaticBoardFocus();
        panel.hidden = !automatic && !envelope.automation_failure;
        panel.replaceChildren();
        if (!automatic) {
            const layer = choiceLayerNode();
            layer.hidden = true;
            layer.classList.remove("is-minimized");
            choiceLayerMinimized = false;
            document.documentElement.classList.remove("has-automatic-choice");
            document.documentElement.classList.remove("has-automatic-choice-minimized");
            const failure = envelope.automation_failure;
            if (failure) {
                latestAutomaticReportId = failure.report_id || latestAutomaticReportId;
                panel.appendChild(element("strong", "", "자동 판정 오류가 서버에 보고되어 수동 모드로 전환됐습니다."));
                panel.appendChild(element("p", "v2-automatic-status", `제보 번호: ${failure.report_id || "생성 중"}`));
                renderIssueReporter();
            }
            return;
        }

        const status = envelope.engine_status || {};
        renderAutomaticFocus(status);
        if (automaticFeedback) {
            panel.appendChild(element(
                "p", `v2-automatic-feedback is-${automaticFeedback.kind}`,
                automaticFeedback.message,
            ));
        }
        renderIssueReporter();
        renderChoiceLayer();
    }

    window.addEventListener("lumen-simulator-state", (event) => {
        if (event.detail) {
            envelope = event.detail;
            render();
        }
    });
    window.setInterval(() => {
        if (envelope && envelope.mode === "automatic" && envelope.clocks) {
            const clock = panel.querySelector(".v2-automatic-clock");
            if (clock) clock.textContent = clockText(envelope.clocks);
            updateChoiceClockVisual();
            const deadline = envelope.clocks.deadline || "";
            const expired = deadline && new Date(deadline).getTime() <= Date.now();
            const canSettle = envelope.role === "p1" || envelope.role === "p2";
            if (expired && canSettle && (
                deadlineRequest.deadline !== deadline || Date.now() - deadlineRequest.requestedAt >= 5000
            )) {
                deadlineRequest = {deadline, requestedAt: Date.now()};
                window.dispatchEvent(new CustomEvent("lumen-simulator-refresh-request"));
            }
        }
    }, 1000);
    if (initialParseError) {
        reportClientError(initialParseError, "initial_state_parse");
    }
    observeAutomaticBoard();
    render();
}());
