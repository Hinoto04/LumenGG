(function () {
    "use strict";

    // Automatic matches are played in the game client (/battlelog/play/).
    // This page only sees a session that fell back to manual mode after an
    // automatic engine failure: show the report number, let the players add
    // details, and keep reporting browser errors to the same report.
    const initialNode = document.getElementById("lumen-simulator-state");
    const panel = document.querySelector("[data-automatic-panel]");
    if (!initialNode || !panel) return;

    const config = window.lumenSimulatorConfig || window.lumenSimulatorMobileConfig || {};
    let envelope = {};
    try {
        envelope = JSON.parse(initialNode.textContent || "{}");
    } catch (_error) {
        envelope = {};
    }
    let reportId = "";
    let reportInFlight = false;
    const reported = new Set();

    function csrfToken() {
        const input = document.querySelector("input[name='csrfmiddlewaretoken']");
        return input ? input.value : "";
    }

    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function canReport() {
        return !!(envelope && envelope.automation_failure && config.reportUrl && ["p1", "p2"].includes(config.seat));
    }

    async function post(body) {
        const response = await fetch(config.reportUrl, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
            keepalive: true,
            body: JSON.stringify({seat: config.seat || "", seat_token: config.seatToken || "", ...body}),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "문제를 제보하지 못했습니다.");
        reportId = data.report_id || reportId;
        return data;
    }

    async function reportClientError(value, context) {
        if (reportInFlight || !canReport()) return;
        const error = value && typeof value === "object" ? value : {};
        const diagnostic = {
            error_type: String(error.error_type || error.name || "ClientError").slice(0, 120),
            message: String(error.message || value || "브라우저 오류").slice(0, 500),
            source: String(error.source || error.filename || "").slice(0, 1000),
            line: Number(error.line || error.lineno || 0),
            column: Number(error.column || error.colno || 0),
            stack: String(error.stack || "").slice(0, 4000),
            context: String(error.context || context || "client").slice(0, 120),
        };
        const fingerprint = JSON.stringify([diagnostic.error_type, diagnostic.message, diagnostic.source, diagnostic.context]);
        if (reported.has(fingerprint) || reported.size > 50) return;
        reported.add(fingerprint);
        reportInFlight = true;
        try {
            await post({kind: "client_error", diagnostic});
        } catch (_error) {
            // A failed diagnostic must never break the manual board.
        } finally {
            reportInFlight = false;
        }
    }

    window.addEventListener("error", (event) => reportClientError(event.error || event, "uncaught_error"));
    window.addEventListener("unhandledrejection", (event) => reportClientError(event.reason, "unhandled_rejection"));
    window.addEventListener("lumen-simulator-client-error", (event) => reportClientError(event.detail || {}, "simulator_transport"));

    function renderReporter() {
        if (!canReport()) return;
        const details = element("details", "v2-automatic-issue");
        const summary = element("summary", "", "자동 오류에 내용 추가");
        const textarea = element("textarea", "v2-automatic-issue-text");
        textarea.maxLength = 4000;
        textarea.rows = 3;
        textarea.placeholder = "발생한 상황과 기대한 동작을 적어주세요.";
        const button = element("button", "v2-button", "서버에 제보");
        button.type = "button";
        const status = element("span", "v2-automatic-issue-status", "");
        button.addEventListener("click", async () => {
            const text = textarea.value.trim();
            if (!text) return;
            button.disabled = true;
            try {
                const data = await post({kind: "user", details: text, report_id: reportId});
                textarea.value = "";
                status.textContent = `제보 완료 · ${data.report_id}`;
            } catch (error) {
                status.textContent = error.message || String(error);
            } finally {
                button.disabled = false;
            }
        });
        details.append(summary, textarea, button, status);
        panel.appendChild(details);
    }

    function render() {
        const failure = envelope && envelope.automation_failure;
        panel.hidden = !failure;
        panel.replaceChildren();
        if (!failure) return;
        reportId = failure.report_id || reportId;
        panel.appendChild(element("strong", "", "자동 판정 오류가 서버에 보고되어 수동 모드로 전환됐습니다."));
        panel.appendChild(element("p", "v2-automatic-status", `제보 번호: ${failure.report_id || "생성 중"}`));
        renderReporter();
    }

    window.addEventListener("lumen-simulator-state", (event) => {
        if (event.detail) {
            envelope = event.detail;
            render();
        }
    });
    render();
}());
