(function () {
    "use strict";

    const root = document.getElementById("effect-sandbox");
    const form = document.getElementById("effect-sandbox-form");
    if (!root || !form) return;

    const readData = (id) => {
        const node = document.getElementById(id);
        if (!node) return [];
        try { return JSON.parse(node.textContent || "[]"); }
        catch (_error) { return []; }
    };
    const abilities = readData("effect-sandbox-abilities-data");
    const catalog = readData("effect-sandbox-cards-data");
    const eventCatalog = readData("effect-sandbox-events-data");
    const cardsByCode = new Map(catalog.map((card) => [String(card.code || "").toUpperCase(), card]));
    const zoneLabels = {
        character: "캐릭터", passive: "패시브", battle: "배틀 존", list: "리스트",
        hand: "패", side: "사이드 덱", break: "브레이크", lumen: "루멘", ultimate: "얼티밋",
    };

    const abilitySelect = document.getElementById("effect-sandbox-ability");
    const eventSelect = document.getElementById("effect-sandbox-event");
    const sourceZone = document.getElementById("effect-sandbox-source-zone");
    const description = document.getElementById("effect-sandbox-choice-description");
    const rows = document.getElementById("effect-sandbox-support-cards");
    const rowTemplate = document.getElementById("effect-sandbox-card-row-template");
    const results = document.getElementById("effect-sandbox-results");
    const errorBox = document.getElementById("effect-sandbox-error");
    const busy = document.getElementById("effect-sandbox-busy");
    const decisionBox = document.getElementById("effect-sandbox-decision");
    let currentToken = "";

    function node(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = String(text);
        return element;
    }

    function currentAbility() {
        return abilities.find((ability) => String(ability.id) === abilitySelect.value) || abilities[0];
    }

    function updateAbilityControls() {
        const ability = currentAbility();
        if (!ability) return;
        const defined = new Set((ability.events || []).map((item) => item.value));
        eventSelect.replaceChildren();
        if (ability.mode === "continuous" && !defined.size) {
            eventSelect.append(node("option", "", "상시 규칙 재계산"));
            eventSelect.firstChild.value = "continuous";
        } else {
            const definedGroup = document.createElement("optgroup");
            definedGroup.label = "정의된 타이밍";
            (ability.events || []).forEach((item) => {
                const option = node("option", "", item.label);
                option.value = item.value;
                definedGroup.append(option);
            });
            if (definedGroup.children.length) eventSelect.append(definedGroup);
            const otherGroup = document.createElement("optgroup");
            otherGroup.label = "조건 비교용 다른 타이밍";
            eventCatalog.filter((item) => !defined.has(item.value)).forEach((item) => {
                const option = node("option", "", item.label);
                option.value = item.value;
                otherGroup.append(option);
            });
            eventSelect.append(otherGroup);
        }
        if ((ability.active_zones || []).length) sourceZone.value = ability.active_zones[0];

        description.replaceChildren();
        const steps = ability.choice_steps || [];
        if (steps.length) {
            description.append(node("strong", "", `서버 선택 단계 ${steps.length}개`));
            const list = node("ol");
            steps.forEach((step) => {
                const range = `${JSON.stringify(step.minimum)}~${JSON.stringify(step.maximum)}개`;
                const label = `${step.label} · ${range} · ${step.required ? "필수" : "선택 가능"}`;
                const item = node("li", "", label);
                if ((step.zones || []).length) item.append(node("small", "", ` (${step.zones.join(", ")})`));
                list.append(item);
            });
            description.append(list);
        } else {
            description.append(node("span", "", "이 효과 정의에는 플레이어 선택 요청이 없습니다."));
        }
        (ability.automatic_steps || []).forEach((step) => {
            description.append(node("p", "effect-sandbox-inline-automatic", step.label));
        });
        (ability.choice_warnings || []).forEach((warning) => {
            description.append(node("p", "effect-sandbox-inline-warning", warning));
        });
    }

    function addCardRow(owner = "p2", zone = "battle", code = "") {
        const fragment = rowTemplate.content.cloneNode(true);
        const row = fragment.querySelector(".effect-sandbox-card-row");
        row.querySelector(".effect-sandbox-card-owner").value = owner;
        row.querySelector(".effect-sandbox-card-zone").value = zone;
        row.querySelector(".effect-sandbox-card-code").value = code;
        row.querySelector(".effect-sandbox-remove-card").addEventListener("click", () => row.remove());
        rows.append(fragment);
    }

    function parseObject(id, label) {
        const input = document.getElementById(id);
        let value;
        try { value = JSON.parse(input.value || "{}"); }
        catch (_error) { throw new Error(`${label} JSON이 올바르지 않습니다.`); }
        if (!value || Array.isArray(value) || typeof value !== "object") {
            throw new Error(`${label}은 JSON 객체여야 합니다.`);
        }
        return value;
    }

    function integerValue(id) {
        const value = Number.parseInt(document.getElementById(id).value, 10);
        return Number.isFinite(value) ? value : 0;
    }

    function supportCards() {
        return Array.from(rows.querySelectorAll(".effect-sandbox-card-row")).map((row) => {
            const rawCode = row.querySelector(".effect-sandbox-card-code").value.trim().toUpperCase();
            const card = cardsByCode.get(rawCode);
            if (!card) throw new Error(`카드 코드 ${rawCode || "(빈 값)"}를 DB에서 찾을 수 없습니다.`);
            return {
                card_id: card.id,
                owner: row.querySelector(".effect-sandbox-card-owner").value,
                zone: row.querySelector(".effect-sandbox-card-zone").value,
                face_up: row.querySelector(".effect-sandbox-card-face-up").checked,
            };
        });
    }

    function requestBody() {
        const definitionInput = document.getElementById("id_effect_definition");
        let effectDefinition;
        try { effectDefinition = JSON.parse(definitionInput.value || "{}"); }
        catch (_error) { throw new Error("현재 효과 정의 JSON이 올바르지 않습니다."); }
        return {
            ability_id: abilitySelect.value,
            effect_definition: effectDefinition,
            config: {
                event: eventSelect.value,
                controller: document.getElementById("effect-sandbox-controller").value,
                phase: document.getElementById("effect-sandbox-phase").value,
                source_zone: sourceZone.value,
                fixture_mode: document.getElementById("effect-sandbox-fixtures").value,
                result: document.getElementById("effect-sandbox-result").value,
                controller_speed: integerValue("effect-sandbox-controller-speed"),
                opponent_speed: integerValue("effect-sandbox-opponent-speed"),
                combo_number: integerValue("effect-sandbox-combo-number"),
                controller_damage_received: integerValue("effect-sandbox-controller-damage"),
                opponent_damage_received: integerValue("effect-sandbox-opponent-damage"),
                controller_turn_damage_received: integerValue("effect-sandbox-controller-turn-damage"),
                opponent_turn_damage_received: integerValue("effect-sandbox-opponent-turn-damage"),
                players: {
                    p1: {
                        hp: integerValue("effect-sandbox-p1-hp"),
                        fp: integerValue("effect-sandbox-p1-fp"),
                        passive_state: parseObject("effect-sandbox-p1-passive", "p1 패시브 상태"),
                    },
                    p2: {
                        hp: integerValue("effect-sandbox-p2-hp"),
                        fp: integerValue("effect-sandbox-p2-fp"),
                        passive_state: parseObject("effect-sandbox-p2-passive", "p2 패시브 상태"),
                    },
                },
                context: parseObject("effect-sandbox-context", "추가 이벤트 컨텍스트"),
                engine: parseObject("effect-sandbox-engine", "히스토리·사용 제한"),
                cards: supportCards(),
            },
        };
    }

    function csrfToken() {
        return form.querySelector("input[name=csrfmiddlewaretoken]").value;
    }

    async function post(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
            body: JSON.stringify(payload),
        });
        let data;
        try { data = await response.json(); }
        catch (_error) { throw new Error(`서버가 JSON 응답을 반환하지 않았습니다. (${response.status})`); }
        if (!response.ok || !data.ok) throw new Error(data.error || `효과 테스트에 실패했습니다. (${response.status})`);
        return data;
    }

    function setBusy(value) {
        busy.hidden = !value;
        form.querySelectorAll("button, select, input, textarea").forEach((control) => {
            control.disabled = Boolean(value);
        });
    }

    function showError(error) {
        errorBox.textContent = error instanceof Error ? error.message : String(error);
        errorBox.hidden = false;
    }

    function renderDecision(decision) {
        decisionBox.replaceChildren();
        if (!decision) {
            decisionBox.hidden = true;
            return;
        }
        decisionBox.hidden = false;
        const heading = node("div", "effect-sandbox-decision-head");
        heading.append(node("strong", "", decision.prompt || "카드를 선택하세요."));
        heading.append(node(
            "span", "",
            `${decision.owner}가 ${decision.minimum}~${decision.maximum}개 선택 · ${decision.optional ? "선택 가능" : "필수"}`,
        ));
        decisionBox.append(heading);
        const options = node("div", "effect-sandbox-decision-options");
        const inputType = decision.maximum === 1 ? "radio" : "checkbox";
        const inputName = `sandbox-decision-${decision.id}`;
        (decision.options || []).forEach((option) => {
            const label = node("label", "effect-sandbox-decision-option");
            const input = document.createElement("input");
            input.type = inputType;
            input.name = inputName;
            input.value = option.id;
            const suffix = [option.owner, zoneLabels[option.zone] || option.zone].filter(Boolean).join(" · ");
            label.append(input, node("span", "", `${option.label}${suffix ? ` (${suffix})` : ""}`));
            options.append(label);
        });
        decisionBox.append(options);
        const feedback = node("p", "effect-sandbox-decision-feedback");
        const submit = node("button", "v2-button v2-button-primary", "선택 확정 후 계속");
        submit.type = "button";
        submit.addEventListener("click", async () => {
            const selected = Array.from(options.querySelectorAll("input:checked")).map((input) => input.value);
            if (selected.length < decision.minimum || selected.length > decision.maximum) {
                feedback.textContent = `${decision.minimum}~${decision.maximum}개를 선택해야 합니다.`;
                return;
            }
            feedback.textContent = "";
            try {
                setBusy(true);
                const data = await post(root.dataset.decisionUrl, {token: currentToken, selected});
                currentToken = data.token;
                renderResult(data.result);
            } catch (error) {
                showError(error);
            } finally {
                setBusy(false);
            }
        });
        decisionBox.append(submit, feedback);
    }

    function renderState(players) {
        const container = document.getElementById("effect-sandbox-state");
        container.replaceChildren();
        ["p1", "p2"].forEach((side) => {
            const player = players[side] || {zones: {}};
            const panel = node("article", "v2-panel effect-sandbox-player");
            const head = node("header");
            head.append(node("strong", "", side), node("span", "", `HP ${player.hp} · FP ${player.fp}`));
            panel.append(head);
            const zones = node("div", "effect-sandbox-zones");
            Object.entries(player.zones || {}).forEach(([zone, cards]) => {
                if (!cards.length) return;
                const zoneNode = node("section", "effect-sandbox-zone");
                zoneNode.append(node("h4", "", `${zoneLabels[zone] || zone} ${cards.length}장`));
                const cardList = node("ul");
                cards.forEach((card) => {
                    const item = node("li", card.fixture ? "is-fixture" : "");
                    item.append(node("span", "", card.face_up ? "앞면" : "뒷면"));
                    item.append(node("strong", "", `${card.code ? `${card.code} · ` : ""}${card.name}`));
                    if (card.attached_to) item.append(node("small", "", `세트 → ${card.attached_to}`));
                    cardList.append(item);
                });
                zoneNode.append(cardList);
                zones.append(zoneNode);
            });
            panel.append(zones);
            container.append(panel);
        });
    }

    function renderEvents(events) {
        const list = document.getElementById("effect-sandbox-events");
        list.replaceChildren();
        if (!events.length) {
            list.append(node("li", "effect-sandbox-empty-event", "발생한 이벤트가 없습니다."));
            return;
        }
        events.forEach((event, index) => {
            const item = node("li");
            const details = document.createElement("details");
            const summary = document.createElement("summary");
            summary.append(
                node("span", "", String(index + 1)),
                node("strong", "", event.label),
                node("small", "", [event.actor, event.summary].filter(Boolean).join(" · ")),
            );
            details.append(summary, node("pre", "", JSON.stringify(event.payload, null, 2)));
            item.append(details);
            list.append(item);
        });
    }

    function renderAudit(audit) {
        const list = document.getElementById("effect-sandbox-audit-list");
        list.replaceChildren();
        const decisions = audit.decisions || [];
        const movements = audit.movements || [];
        const operations = audit.operations || [];

        decisions.forEach((decision) => {
            const waiting = decision.status === "waiting";
            const item = node("li", waiting ? "is-waiting" : "is-complete");
            item.append(node("strong", "", waiting ? "선택 대기" : "선택 확정"));
            const requirement = `${decision.owner} · ${decision.minimum}~${decision.maximum}장 · ${decision.optional ? "선택" : "필수"}`;
            const selected = (decision.selected || []).map((option) => option.label || option.id);
            const detail = waiting
                ? `${requirement} · 후보 ${(decision.options || []).length}장`
                : `${requirement} · ${selected.length ? selected.join(", ") : "선택 없음"}`;
            item.append(node("span", "", detail));
            list.append(item);
        });
        movements.forEach((movement) => {
            const item = node("li", "is-complete");
            item.append(node("strong", "", "영역 이동"));
            item.append(node(
                "span", "",
                `${movement.label} · ${zoneLabels[movement.from_zone] || movement.from_zone} → ${zoneLabels[movement.to_zone] || movement.to_zone}`,
            ));
            list.append(item);
        });
        operations.forEach((operation) => {
            const prevented = ["card_break_prevented", "card_move_prevented", "card_effect_ignored"].includes(operation.type);
            const item = node("li", prevented ? "is-blocked" : "is-complete");
            item.append(node("strong", "", operation.label));
            item.append(node(
                "span", "",
                [operation.card_label, operation.reason].filter(Boolean).join(" · "),
            ));
            list.append(item);
        });
        if (audit.blocked) {
            const item = node("li", "is-blocked");
            item.append(node("strong", "", "필수 선택 중단"));
            item.append(node("span", "", "후보가 부족해 이 효과의 후속 명령을 실행하지 않았습니다."));
            list.append(item);
        }
        if (!list.children.length) {
            list.append(node("li", "is-empty", "선택 또는 카드 이동이 발생하지 않았습니다."));
        }
    }

    function renderResult(result) {
        errorBox.hidden = true;
        results.hidden = false;
        const head = document.getElementById("effect-sandbox-result-head");
        head.replaceChildren();
        head.className = `effect-sandbox-result-head is-${result.status}`;
        head.append(node("strong", "", result.status_label));
        head.append(node("span", "", `${result.ability_id} · ${result.event_label || result.event} · 결정 ${result.step}회`));
        renderDecision(result.pending_decision);
        renderAudit(result.audit || {});
        renderState(result.players || {});
        document.getElementById("effect-sandbox-engine-state").textContent = JSON.stringify(result.engine || {}, null, 2);
        renderEvents(result.events || []);
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorBox.hidden = true;
        try {
            const payload = requestBody();
            setBusy(true);
            const data = await post(root.dataset.startUrl, payload);
            currentToken = data.token;
            renderResult(data.result);
        } catch (error) {
            showError(error);
        } finally {
            setBusy(false);
        }
    });

    abilitySelect.addEventListener("change", updateAbilityControls);
    document.getElementById("effect-sandbox-add-card").addEventListener("click", () => addCardRow());
    document.querySelectorAll("[data-sandbox-preset]").forEach((button) => {
        button.addEventListener("click", () => {
            const preset = button.dataset.sandboxPreset;
            const controller = document.getElementById("effect-sandbox-controller");
            const fixtures = document.getElementById("effect-sandbox-fixtures");
            rows.replaceChildren();
            controller.value = preset === "p2-candidates" ? "p2" : "p1";
            fixtures.value = preset === "no-candidates" ? "none" : "choices";
            form.requestSubmit();
        });
    });
    document.getElementById("effect-sandbox-reset").addEventListener("click", () => {
        currentToken = "";
        results.hidden = true;
        errorBox.hidden = true;
    });
    document.querySelectorAll(".effect-sandbox-pick-ability").forEach((button) => {
        button.addEventListener("click", () => {
            abilitySelect.value = button.dataset.sandboxAbility;
            updateAbilityControls();
            root.scrollIntoView({behavior: "smooth", block: "start"});
            abilitySelect.focus({preventScroll: true});
        });
    });
    updateAbilityControls();
}());
