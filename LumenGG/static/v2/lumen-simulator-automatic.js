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
    const reportedClientErrors = new Set();
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

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function clockText(clock) {
        if (!clock) return "";
        if (clock.paused) return `일시정지 · ${clock.pause_reason || "사유 기록됨"}`;
        if (!clock.deadline) return "";
        const remaining = Math.max(0, Math.ceil((new Date(clock.deadline).getTime() - Date.now()) / 1000));
        return `${clock.owner || ""} · ${remaining}초`;
    }

    function selectedValues(select) {
        if (!select) return [];
        return Array.from(select.selectedOptions || []).map((option) => option.value).filter(Boolean);
    }

    async function submit(action, select, button) {
        const selections = {};
        if (action.type === "submit_decision") {
            selections.selected = selectedValues(select);
        }
        if (action.type === "pause_clock") {
            const reason = window.prompt("일시정지 사유를 입력하세요.", "");
            if (!reason) return;
            selections.reason = reason;
        }
        button.disabled = true;
        try {
            const response = await fetch(config.commandUrl, {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
                body: JSON.stringify({
                    seat: config.seat || "",
                    seat_token: config.seatToken || "",
                    command_id: commandId(),
                    expected_version: envelope.version,
                    action_id: action.action_id,
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
            if (!response.ok || !data.ok) {
                const error = new Error(data.error || "자동 명령을 처리하지 못했습니다.");
                error.serverRejected = true;
                throw error;
            }
            envelope = data.state;
            render();
            window.dispatchEvent(new CustomEvent("lumen-simulator-refresh-request"));
        } catch (error) {
            if (!error.serverRejected) {
                reportClientError(error, error.context || "command_submit");
            }
            window.alert(error.message || String(error));
            button.disabled = false;
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

    function renderAction(action, holder) {
        const row = element("div", "v2-automatic-action");
        let select = null;
        if (action.type === "submit_decision") {
            select = element("select", "v2-automatic-select");
            if (Number(action.minimum || 0) === 0) {
                const decline = element("option", "", "선택하지 않음");
                decline.value = "";
                decline.selected = true;
                select.appendChild(decline);
            }
            if (Number(action.maximum || 1) > 1) {
                select.multiple = true;
                select.size = Math.min(6, Math.max(2, (action.options || []).length));
            }
            (action.options || []).forEach((option, index) => {
                const item = element("option", "", option.label || option.id);
                item.value = option.id;
                item.selected = index < Number(action.minimum || 1);
                select.appendChild(item);
            });
            row.appendChild(select);
        }
        const button = element("button", "v2-button v2-button-primary", action.label || action.type);
        button.type = "button";
        button.addEventListener("click", () => submit(action, select, button));
        row.appendChild(button);
        holder.appendChild(row);
    }

    function render() {
        const automatic = envelope && envelope.mode === "automatic";
        hideManualControls(automatic);
        panel.hidden = !automatic && !envelope.automation_failure;
        panel.replaceChildren();
        if (!automatic) {
            const failure = envelope.automation_failure;
            if (failure) {
                latestAutomaticReportId = failure.report_id || latestAutomaticReportId;
                panel.appendChild(element("strong", "", "자동 판정 오류가 서버에 보고되어 수동 모드로 전환됐습니다."));
                panel.appendChild(element("p", "v2-automatic-status", `제보 번호: ${failure.report_id || "생성 중"}`));
                renderIssueReporter();
            }
            return;
        }

        const header = element("header", "v2-automatic-head");
        const title = element("div", "");
        title.appendChild(element("strong", "", "자동 규칙 모드"));
        title.appendChild(element("span", "", envelope.ruleset_version || ""));
        header.appendChild(title);
        const status = envelope.engine_status || {};
        header.appendChild(element("span", "v2-automatic-status", `${status.status || "running"} · ${status.step || ""}`));
        panel.appendChild(header);

        const clock = element("div", "v2-automatic-clock", clockText(envelope.clocks));
        if (clock.textContent) panel.appendChild(clock);
        const decision = envelope.pending_decision;
        if (decision) {
            panel.appendChild(element("p", "v2-automatic-prompt", decision.prompt || "선택 처리 중"));
        }
        const actions = element("div", "v2-automatic-actions");
        (envelope.legal_actions || []).forEach((action) => renderAction(action, actions));
        if (!(envelope.legal_actions || []).length) {
            actions.appendChild(element("p", "v2-automatic-wait", envelope.role === "viewer" ? "관전 중입니다." : "자동 해결 또는 상대 행동을 기다리는 중입니다."));
        }
        panel.appendChild(actions);
        if (envelope.ai_policy_version) {
            panel.appendChild(element("p", "v2-automatic-status", `AI 정책: ${envelope.ai_policy_version}`));
        }
        renderIssueReporter();
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
    render();
}());
