(function () {
    "use strict";

    const triggerOptions = ["game_start", "turn_start", "turn_end", "phase_start", "phase_end", "battle_end", "ready", "use", "before_judgment", "dodge", "opponent_dodge", "guard", "opponent_guard", "hit", "opponent_hit", "counter", "opponent_counter", "clash", "opponent_clash", "combo", "combo_window", "combo_end", "opponent_combo_end", "catch", "after_judgment", "after_use", "damage_before", "damage_after", "hp_changed", "fp_changed", "card_moved", "card_broken", "card_attached", "card_discarded", "state_gained", "state_lost", "counter_changed", "ability_completed", "speed_fixed", "card_guess_resolved", "grab_negated", "no_response", "sudden_death_start", "defense_over"];
    const timingOptions = ["function", "replacement", "use", "before_judgment", "dodge", "opponent_dodge", "guard", "opponent_guard", "hit_counter", "opponent_hit_counter", "clash", "opponent_clash", "combo", "combo_end", "opponent_combo_end", "result", "after_judgment", "after_use", "catch", "cleanup"];
    // Only commands that can be edited without losing command-specific fields belong
    // here. Other valid DSL commands are rendered as preserved, read-only nodes.
    const operationOptions = ["deal_damage", "change_hp", "change_fp", "reset_fp", "move_card", "discard", "reveal", "hide", "break_card", "break_cards", "gain_state", "lose_state", "change_counter", "set_counter", "modify_stat", "fix_speed", "modify_damage", "modify_judgment", "prevent", "negate", "replace", "skip_phase", "repeat_phase", "grant_catch", "modify_combo", "set_usage_limit"];
    const conditionOptions = ["", "equals", "not_equals", "gt", "gte", "lt", "lte", "exists", "phase_is", "result_is", "has_state", "counter_at_least", "card_matches"];
    const rootConditionOptions = ["equals", "not_equals", "gt", "gte", "lt", "lte", "exists", "has_state", "counter_at_least", "zone_count"];

    function escapeHtml(value) {
        return String(value === undefined || value === null ? "" : value)
            .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
    }

    function optionList(values, selected) {
        return values.map((value) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(value)}</option>`).join("");
    }

    function parsedList(value) {
        return String(value || "").split(",").map((item) => Number(item.trim())).filter((item) => Number.isInteger(item) && item > 0);
    }

    function valueForEditor(value) {
        if (value === undefined || value === null || value === "") return "";
        return typeof value === "object" ? JSON.stringify(value) : String(value);
    }

    function parsedValue(value) {
        const raw = String(value || "").trim();
        if (!raw) return undefined;
        try {
            const parsed = JSON.parse(raw);
            if (typeof parsed === "number" || (parsed && typeof parsed === "object")) return parsed;
        } catch (_error) { /* fall through to numeric parsing */ }
        const numeric = Number(raw);
        return Number.isFinite(numeric) ? numeric : raw;
    }

    function init(root) {
        if (root.dataset.effectReady) return;
        root.dataset.effectReady = "1";
        const field = root.querySelector("textarea");
        const holder = root.querySelector("[data-effect-abilities]");
        const preview = root.querySelector("[data-effect-preview]");
        let definition;
        try { definition = JSON.parse(field.value || "{}"); } catch (_error) { definition = {}; }
        definition = Object.assign({schema_version: 1, reviewed: false, no_effect: false, source_refs: {rulebook_pages: [], qna_ids: []}, abilities: []}, definition);
        if (!definition.source_refs || typeof definition.source_refs !== "object") definition.source_refs = {rulebook_pages: [], qna_ids: []};
        if (!Array.isArray(definition.abilities)) definition.abilities = [];
        const noEffect = root.querySelector("[data-effect-no-effect]");
        const draft = root.querySelector("[data-effect-draft]");
        const reviewed = root.querySelector("[data-effect-reviewed]");
        const rootPages = root.querySelector("[data-effect-root-pages]");
        const rootQnas = root.querySelector("[data-effect-root-qnas]");
        const tokenKey = root.querySelector("[data-effect-token-key]");
        const tokenUsageToken = root.querySelector("[data-effect-token-usage-token]");
        const tokenUsageCounter = root.querySelector("[data-effect-token-usage-counter]");
        const deckMainMin = root.querySelector("[data-effect-deck-main-min]");
        const deckMainMax = root.querySelector("[data-effect-deck-main-max]");
        const deckBaseExcludes = root.querySelector("[data-effect-deck-base-excludes]");
        const deckCharacterMin = root.querySelector("[data-effect-deck-character-min]");
        const deckSupplements = root.querySelector("[data-effect-deck-supplements]");
        const deckImportTypes = root.querySelector("[data-effect-deck-import-types]");
        const deckImportMax = root.querySelector("[data-effect-deck-import-max]");
        const deckImportExcluded = root.querySelector("[data-effect-deck-import-excluded]");
        const deckImportNoUltimate = root.querySelector("[data-effect-deck-import-no-ultimate]");
        const deckImportTreatOwn = root.querySelector("[data-effect-deck-import-treat-own]");
        const deckImportNegate = root.querySelector("[data-effect-deck-import-negate]");
        const deckImportBreak = root.querySelector("[data-effect-deck-import-break]");
        const playConditions = root.querySelector("[data-effect-play-conditions]");
        const comboRules = root.querySelector("[data-effect-combo-rules]");
        const playLimitScope = root.querySelector("[data-effect-play-limit-scope]");
        const playLimitKey = root.querySelector("[data-effect-play-limit-key]");
        const playLimitMax = root.querySelector("[data-effect-play-limit-max]");
        const defenseRules = root.querySelector("[data-effect-defense-rules]");
        const zoneLimits = root.querySelector("[data-effect-zone-limits]");
        const immunityScope = root.querySelector("[data-effect-immunity-scope]");
        const immunityZones = root.querySelector("[data-effect-immunity-zones]");
        const breakZones = root.querySelector("[data-effect-break-zones]");
        const breakOwnerDirect = root.querySelector("[data-effect-break-owner-direct]");
        const breakOpponentEffect = root.querySelector("[data-effect-break-opponent-effect]");
        const breakAll = root.querySelector("[data-effect-break-all]");
        const breakAllState = root.querySelector("[data-effect-break-all-state]");
        const configuredDeckRules = definition.deck_rules || {};
        const preservedDeckRules = JSON.parse(JSON.stringify(configuredDeckRules));
        delete preservedDeckRules.main_size;
        delete preservedDeckRules.character_card_minimum;
        delete preservedDeckRules.supplements;
        delete preservedDeckRules.other_character_cards;
        const preservedPlayConditions = [];
        const configuredBreakPreventions = (definition.break_rules || {}).preventions || [];
        const simpleBreakPrevention = (item) => item && (
            ["owner_direct", "opponent_effect"].includes(item.scope) && !item.condition
            || item.scope === "all" && (!item.condition || (
                item.condition.op === "has_state"
                && item.condition.player && item.condition.player.controller
            ))
        );
        const preservedBreakPreventions = configuredBreakPreventions
            .filter((item) => !simpleBreakPrevention(item))
            .map((item) => JSON.parse(JSON.stringify(item)));
        noEffect.checked = !!definition.no_effect;
        draft.checked = definition.draft === true;
        reviewed.checked = definition.reviewed === true;
        rootPages.value = (definition.source_refs.rulebook_pages || []).join(",");
        rootQnas.value = (definition.source_refs.qna_ids || []).join(",");
        tokenKey.value = definition.token_key || "";
        tokenUsageToken.checked = (definition.token_usage || []).includes("token");
        tokenUsageCounter.checked = (definition.token_usage || []).includes("counter");
        deckMainMin.value = (configuredDeckRules.main_size || {}).min || "";
        deckMainMax.value = (configuredDeckRules.main_size || {}).max || "";
        deckBaseExcludes.checked = !!(configuredDeckRules.main_size || {}).base_excludes_supplements;
        deckCharacterMin.value = configuredDeckRules.character_card_minimum === undefined ? "" : configuredDeckRules.character_card_minimum;
        const configuredImportedCards = configuredDeckRules.other_character_cards || {};
        deckImportTypes.value = (configuredImportedCards.allowed_types || []).join(",");
        deckImportMax.value = configuredImportedCards.max_per_character || "";
        deckImportExcluded.value = (configuredImportedCards.exclude_character_ids || []).join(",");
        deckImportNoUltimate.checked = !!configuredImportedCards.exclude_ultimate;
        deckImportTreatOwn.checked = !!configuredImportedCards.treat_as_own_character;
        deckImportNegate.checked = !!configuredImportedCards.negate_effects;
        deckImportBreak.checked = !!configuredImportedCards.break_after_use;
        playLimitScope.value = (definition.play_limit || {}).scope || "";
        playLimitKey.value = (definition.play_limit || {}).key || "";
        playLimitMax.value = Number((definition.play_limit || {}).max || 1);
        immunityScope.value = (definition.effect_immunity || {}).scope || "";
        immunityZones.value = ((definition.effect_immunity || {}).active_zones || []).join(",");
        breakZones.value = ((definition.break_rules || {}).forbidden_zones || []).join(",");
        breakOwnerDirect.checked = configuredBreakPreventions.some((item) => item.scope === "owner_direct" && !item.condition);
        breakOpponentEffect.checked = configuredBreakPreventions.some((item) => item.scope === "opponent_effect" && !item.condition);
        const configuredBreakAll = configuredBreakPreventions.find((item) => item.scope === "all" && simpleBreakPrevention(item));
        breakAll.checked = !!configuredBreakAll;
        breakAllState.value = configuredBreakAll && configuredBreakAll.condition ? configuredBreakAll.condition.state || "" : "";

        function playerValue(value) {
            if (value === "p1" || value === "p2") return value;
            return value && value.opponent ? "opponent" : "controller";
        }

        function rootConditionNode(condition) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._conditionOriginal = JSON.parse(JSON.stringify(condition || {}));
            const where = condition.where || {};
            const filterKey = ["code", "token_key", "name_contains", "type_contains", "type_in"].find((key) => where[key] !== undefined) || "code";
            const filterValue = Array.isArray(where[filterKey]) ? where[filterKey].join(",") : where[filterKey] || "";
            const key = condition.state || condition.counter || condition.left || "";
            const right = condition.right === undefined ? condition.value === undefined ? "" : condition.value : valueForEditor(condition.right);
            node.innerHTML = `<div class="effect-command-head"><strong>사용 조건</strong><button type="button" class="button" data-remove>삭제</button></div><div class="effect-node-grid"><label>연산<select data-root-condition-op>${optionList(rootConditionOptions, condition.op || "equals")}</select></label><label>상태 경로·키<input data-root-condition-key value="${escapeHtml(key)}"></label><label>비교값(JSON 가능)<input data-root-condition-value value="${escapeHtml(right)}"></label><label>플레이어<select data-root-condition-player>${optionList(["controller", "opponent", "p1", "p2"], playerValue(condition.player))}</select></label><label>존<input data-root-condition-zone value="${escapeHtml(condition.zone || "lumen")}"></label><label>최소 수<input data-root-condition-min type="number" min="0" value="${Number(condition.min || 0)}"></label><label>최대 수<input data-root-condition-max type="number" min="0" value="${escapeHtml(condition.max === undefined ? "" : condition.max)}"></label><label>카드 필터<select data-root-condition-filter>${optionList(["code", "token_key", "name_contains", "type_contains", "type_in"], filterKey)}</select></label><label>필터 값<input data-root-condition-filter-value value="${escapeHtml(filterValue)}"></label></div>`;
            node.querySelector("[data-remove]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input,select").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readRootCondition(node) {
            const original = node._conditionOriginal || {};
            const op = node.querySelector("[data-root-condition-op]").value;
            const key = node.querySelector("[data-root-condition-key]").value.trim();
            const rawValue = node.querySelector("[data-root-condition-value]").value.trim();
            let right = rawValue;
            try { right = JSON.parse(rawValue); } catch (_error) { /* keep text */ }
            const player = node.querySelector("[data-root-condition-player]").value;
            if (op === "has_state") return {op, player: player === "opponent" ? {opponent: true} : player === "controller" ? {controller: true} : player, state: key};
            if (op === "counter_at_least") return {op, player: player === "opponent" ? {opponent: true} : player === "controller" ? {controller: true} : player, counter: key, value: Number(right || 0)};
            if (op === "zone_count") {
                const filterKey = node.querySelector("[data-root-condition-filter]").value;
                const rawFilter = node.querySelector("[data-root-condition-filter-value]").value.trim();
                const filterValue = filterKey === "type_in" ? rawFilter.split(",").map((item) => item.trim()).filter(Boolean) : rawFilter;
                const result = Object.assign({}, original, {
                    op, player: player === "opponent" ? {opponent: true} : player === "controller" ? {controller: true} : player,
                    zone: node.querySelector("[data-root-condition-zone]").value.trim(),
                    min: Number(node.querySelector("[data-root-condition-min]").value || 0),
                    where: rawFilter ? {[filterKey]: filterValue} : {},
                });
                const maximum = node.querySelector("[data-root-condition-max]").value;
                if (maximum !== "") result.max = Number(maximum); else delete result.max;
                return result;
            }
            const result = {op, left: key};
            if (op !== "exists") result.right = right;
            return result;
        }

        function deckSupplementNode(supplement) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._supplementOriginal = JSON.parse(JSON.stringify(supplement || {}));
            const where = supplement.where || {};
            const filterKey = where.token_key !== undefined ? "token_key" : "code";
            node.innerHTML = `<div class="effect-command-head"><strong>보충 카드</strong><button type="button" class="button" data-remove>삭제</button></div><div class="effect-node-grid"><label>필터<select data-deck-supplement-filter>${optionList(["code", "token_key"], filterKey)}</select></label><label>필터 값<input data-deck-supplement-value value="${escapeHtml(where[filterKey] || "")}"></label><label>전체 최대 수<input data-deck-supplement-max type="number" min="1" value="${Number(supplement.max_count || 1)}"></label><label>동명 최대 수<input data-deck-supplement-name-max type="number" min="1" value="${escapeHtml(supplement.same_name_limit || "")}"></label><label><input type="checkbox" data-deck-supplement-foreign${supplement.allow_foreign_mark ? " checked" : ""}> 다른 마크 허용</label><label><input type="checkbox" data-deck-supplement-non-technique${supplement.allow_non_technique ? " checked" : ""}> 비기술 카드 허용</label></div>`;
            node.querySelector("[data-remove]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input,select").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readDeckSupplement(node) {
            const supplement = Object.assign({}, node._supplementOriginal || {});
            const filterKey = node.querySelector("[data-deck-supplement-filter]").value;
            supplement.where = {[filterKey]: node.querySelector("[data-deck-supplement-value]").value.trim()};
            supplement.max_count = Number(node.querySelector("[data-deck-supplement-max]").value || 1);
            const sameNameLimit = node.querySelector("[data-deck-supplement-name-max]").value;
            if (sameNameLimit) supplement.same_name_limit = Number(sameNameLimit);
            else delete supplement.same_name_limit;
            supplement.allow_foreign_mark = node.querySelector("[data-deck-supplement-foreign]").checked;
            supplement.allow_non_technique = node.querySelector("[data-deck-supplement-non-technique]").checked;
            return supplement;
        }

        function comboRuleNode(rule) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._comboOriginal = JSON.parse(JSON.stringify(rule || {}));
            node.innerHTML = `<div class="effect-command-head"><strong>콤보 규칙</strong><button type="button" class="button" data-remove>삭제</button></div><div class="effect-node-grid"><label>허용 존(쉼표)<input data-root-combo-zones value="${escapeHtml((rule.allow_zones || []).join(","))}"></label><label>선택 가능 속도(쉼표)<input data-root-combo-speed-options value="${escapeHtml((rule.speed_options || []).join(","))}"></label><label>최소 콤보<input data-root-combo-min type="number" min="2" value="${escapeHtml(rule.min_combo || "")}"></label><label>최대 콤보<input data-root-combo-max type="number" min="2" value="${escapeHtml(rule.max_combo || "")}"></label><label>카드 이름 포함<input data-root-combo-name value="${escapeHtml((rule.where || {}).name_contains || "")}"></label><label>앞 카드 이름 포함<input data-root-combo-after value="${escapeHtml((rule.after_where || {}).name_contains || "")}"></label><label><input data-root-combo-any-speed type="checkbox"${rule.any_speed ? " checked" : ""}> 원하는 속도</label><label><input data-root-combo-speed type="checkbox"${rule.ignore_speed ? " checked" : ""}> 속도 조건 무시</label><label><input data-root-combo-damage type="checkbox"${rule.ignore_damage_penalty ? " checked" : ""}> 데미지 보정 무시</label><label><input data-root-combo-optional-damage type="checkbox"${rule.optional_ignore_damage_penalty ? " checked" : ""}> 1장 보정 미적용 선택</label><label><input data-root-combo-end type="checkbox"${rule.end_after_use ? " checked" : ""}> 사용 후 콤보 종료</label></div>`;
            node.querySelector("[data-remove]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readComboRule(node) {
            const rule = Object.assign({}, node._comboOriginal || {});
            rule.allow_zones = node.querySelector("[data-root-combo-zones]").value.split(",").map((item) => item.trim()).filter(Boolean);
            const speedOptions = parsedList(node.querySelector("[data-root-combo-speed-options]").value);
            if (speedOptions.length) rule.speed_options = speedOptions; else delete rule.speed_options;
            const minimum = Number(node.querySelector("[data-root-combo-min]").value || 0);
            const maximum = Number(node.querySelector("[data-root-combo-max]").value || 0);
            if (minimum) rule.min_combo = minimum; else delete rule.min_combo;
            if (maximum) rule.max_combo = maximum; else delete rule.max_combo;
            const name = node.querySelector("[data-root-combo-name]").value.trim();
            const after = node.querySelector("[data-root-combo-after]").value.trim();
            rule.where = Object.assign({}, rule.where || {});
            rule.after_where = Object.assign({}, rule.after_where || {});
            if (name) rule.where.name_contains = name; else delete rule.where.name_contains;
            if (after) rule.after_where.name_contains = after; else delete rule.after_where.name_contains;
            if (!Object.keys(rule.where).length) delete rule.where;
            if (!Object.keys(rule.after_where).length) delete rule.after_where;
            rule.ignore_speed = node.querySelector("[data-root-combo-speed]").checked;
            rule.any_speed = node.querySelector("[data-root-combo-any-speed]").checked;
            rule.ignore_damage_penalty = node.querySelector("[data-root-combo-damage]").checked;
            rule.optional_ignore_damage_penalty = node.querySelector("[data-root-combo-optional-damage]").checked;
            rule.end_after_use = node.querySelector("[data-root-combo-end]").checked;
            return rule;
        }

        function zoneLimitNode(limit) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._zoneOriginal = JSON.parse(JSON.stringify(limit || {}));
            node.innerHTML = `<div class="effect-command-head"><strong>존 배치 제한</strong><button type="button" class="button" data-remove>삭제</button></div><div class="effect-node-grid"><label>존<input data-root-zone-name value="${escapeHtml(limit.zone || "lumen")}"></label><label>최대 장수<input data-root-zone-max type="number" min="1" value="${Number(limit.max || 1)}"></label><label>이름 포함<input data-root-zone-filter value="${escapeHtml((limit.where || {}).name_contains || "")}"></label></div>`;
            node.querySelector("[data-remove]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readZoneLimit(node) {
            return Object.assign({}, node._zoneOriginal || {}, {
                zone: node.querySelector("[data-root-zone-name]").value.trim(),
                max: Number(node.querySelector("[data-root-zone-max]").value || 1),
                where: {name_contains: node.querySelector("[data-root-zone-filter]").value.trim()},
            });
        }

        function defenseRuleNode(rule) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._defenseOriginal = JSON.parse(JSON.stringify(rule || {}));
            const simpleState = rule.condition && rule.condition.op === "has_state" && rule.condition.player && rule.condition.player.controller ? rule.condition.state || "" : "";
            node.innerHTML = `<div class="effect-command-head"><strong>회피·상쇄 제한</strong><button type="button" class="button" data-remove>삭제</button></div><div class="effect-node-grid"><label>판정<select data-defense-judgment>${optionList(["dodge", "clash"], rule.judgment || "dodge")}</select></label><label>위치<select data-defense-position>${optionList(["", "상단", "중단", "하단"], rule.position || "")}</select></label><label>최소 속도<input data-defense-min type="number" min="1" value="${escapeHtml(rule.min_speed || "")}"></label><label>최대 속도<input data-defense-max type="number" min="1" value="${escapeHtml(rule.max_speed || "")}"></label><label>최소 데미지<input data-defense-min-damage type="number" min="0" value="${escapeHtml(rule.min_damage === undefined ? "" : rule.min_damage)}"></label><label>최대 데미지<input data-defense-max-damage type="number" min="0" value="${escapeHtml(rule.max_damage === undefined ? "" : rule.max_damage)}"></label><label>최소 히트 수치<input data-defense-min-hit type="number" min="0" value="${escapeHtml(rule.min_hit === undefined ? "" : rule.min_hit)}"></label><label>허용 히트 판정(쉼표)<input data-defense-hit-values value="${escapeHtml((rule.hit_values || []).join(","))}"></label><label>상대 부위 판정<input data-defense-body value="${escapeHtml((rule.where || {}).body || "")}" placeholder="손 또는 발"></label><label>자신의 상태 조건<input data-defense-state value="${escapeHtml(simpleState)}" placeholder="예: harmony"></label></div>`;
            node.querySelector("[data-remove]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input,select").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readDefenseRule(node) {
            const rule = Object.assign({}, node._defenseOriginal || {});
            rule.judgment = node.querySelector("[data-defense-judgment]").value;
            const position = node.querySelector("[data-defense-position]").value;
            const minimum = Number(node.querySelector("[data-defense-min]").value || 0);
            const maximum = Number(node.querySelector("[data-defense-max]").value || 0);
            const minimumDamage = node.querySelector("[data-defense-min-damage]").value;
            const maximumDamage = node.querySelector("[data-defense-max-damage]").value;
            const minimumHit = node.querySelector("[data-defense-min-hit]").value;
            const hitValues = node.querySelector("[data-defense-hit-values]").value.split(",").map((item) => item.trim()).filter(Boolean);
            const body = node.querySelector("[data-defense-body]").value.trim();
            const state = node.querySelector("[data-defense-state]").value.trim();
            if (position) rule.position = position; else delete rule.position;
            if (minimum) rule.min_speed = minimum; else delete rule.min_speed;
            if (maximum) rule.max_speed = maximum; else delete rule.max_speed;
            if (minimumDamage !== "") rule.min_damage = Number(minimumDamage); else delete rule.min_damage;
            if (maximumDamage !== "") rule.max_damage = Number(maximumDamage); else delete rule.max_damage;
            if (minimumHit !== "") rule.min_hit = Number(minimumHit); else delete rule.min_hit;
            if (hitValues.length) rule.hit_values = hitValues; else delete rule.hit_values;
            rule.where = Object.assign({}, rule.where || {});
            if (body) rule.where.body = body; else delete rule.where.body;
            if (!Object.keys(rule.where).length) delete rule.where;
            const originalCondition = (node._defenseOriginal || {}).condition;
            const originalSimpleState = originalCondition && originalCondition.op === "has_state" && originalCondition.player && originalCondition.player.controller;
            if (state) rule.condition = {op: "has_state", player: {controller: true}, state};
            else if (originalSimpleState) delete rule.condition;
            return rule;
        }

        function commandNode(effect) {
            const node = document.createElement("div");
            node.className = "effect-command";
            node._effectOriginal = JSON.parse(JSON.stringify(effect || {}));
            node._effectDirty = false;
            if (!operationOptions.includes(effect.op)) {
                const isStaticRule = effect.op === "static_rule";
                const rules = Array.isArray(effect.rules) ? effect.rules.join(", ") : "";
                node.dataset.preservedCommand = "1";
                node.classList.add("effect-command-preserved");
                node.innerHTML = `<div class="effect-command-head"><strong>${isStaticRule ? "관련 실행 명령 없음" : "고급 명령 · 시각 편집 미지원"}</strong><button type="button" class="button" data-remove-command>삭제</button></div><p class="help">${isStaticRule ? `이 기능은 ${escapeHtml(rules || "카드 최상위 규칙")}에서 처리됩니다. 데미지 명령이 아닙니다.` : `opcode ${escapeHtml(effect.op || "(없음)")}의 원본 JSON을 변경 없이 보존합니다.`}</p><pre data-preserved-json>${escapeHtml(JSON.stringify(effect, null, 2))}</pre>`;
                node.querySelector("[data-remove-command]").addEventListener("click", () => { node.remove(); sync(); });
                return node;
            }
            let configuredValue = effect.amount === undefined ? effect.value : effect.amount;
            if (effect.op === "break_card" && effect.card_instance_id !== undefined) configuredValue = effect.card_instance_id;
            if (effect.op === "break_cards") configuredValue = effect.card_instance_ids || [];
            const catchWhere = effect.where || {};
            const catchFilterKey = ["character_key", "text_contains", "code", "name_contains", "type_contains"].find((item) => catchWhere[item] !== undefined) || "character_key";
            node.innerHTML = `<div class="effect-command-head"><strong>명령</strong><button type="button" class="button" data-remove-command>삭제</button></div><div class="effect-node-grid"><label>opcode<select data-op>${optionList(operationOptions, effect.op || "change_fp")}</select></label><label>대상 플레이어<select data-player>${optionList(["controller", "opponent", "p1", "p2"], effect.player === "p1" || effect.player === "p2" ? effect.player : effect.player && effect.player.opponent ? "opponent" : "controller")}</select></label><label>수치·대상(숫자 또는 JSON)<input data-amount type="text" value="${escapeHtml(valueForEditor(configuredValue))}"></label><label>상태·카운터·페이즈·규칙<input data-key value="${escapeHtml(effect.state || effect.counter || effect.phase || effect.stat || effect.field || effect.kind || effect.key || "")}"></label><label>이동할 존<input data-zone value="${escapeHtml(effect.to_zone || "")}"></label></div><div class="effect-node-grid" data-combo-options><label>콤보 허용 존(쉼표)<input data-combo-zones value="${escapeHtml((effect.allow_zones || []).join(","))}"></label><label>대상 카드 이름 포함<input data-combo-name value="${escapeHtml((effect.where || {}).name_contains || "")}"></label><label>앞 카드 이름 포함<input data-combo-after-name value="${escapeHtml((effect.after_where || {}).name_contains || "")}"></label><label>최소 콤보<input data-combo-min type="number" min="2" value="${escapeHtml(effect.min_combo || "")}"></label><label>최대 콤보<input data-combo-max type="number" min="2" value="${escapeHtml(effect.max_combo || "")}"></label><label><input data-combo-any-speed type="checkbox"${effect.any_speed ? " checked" : ""}> 원하는 속도</label><label><input data-combo-ignore-speed type="checkbox"${effect.ignore_speed ? " checked" : ""}> 속도 조건 무시</label><label><input data-combo-ignore-damage type="checkbox"${effect.ignore_damage_penalty ? " checked" : ""}> 데미지 보정 무시</label><label><input data-combo-optional-ignore-damage type="checkbox"${effect.optional_ignore_damage_penalty ? " checked" : ""}> 1장 보정 미적용 선택</label></div><div class="effect-node-grid" data-catch-options><label>캐치 허용 존(쉼표)<input data-catch-zones value="${escapeHtml((effect.allow_zones || ["hand"]).join(","))}"></label><label>최소 속도<input data-catch-min type="number" min="1" value="${escapeHtml(effect.min_speed || "")}"></label><label>최대 속도<input data-catch-max type="number" min="1" value="${escapeHtml(effect.max_speed || "")}"></label><label>카드 필터<select data-catch-filter-key>${optionList(["character_key", "text_contains", "code", "name_contains", "type_contains"], catchFilterKey)}</select></label><label>필터 값<input data-catch-filter-value value="${escapeHtml(catchWhere[catchFilterKey] || "")}"></label></div>`;
            node.querySelector(":scope > .effect-node-grid").insertAdjacentHTML(
                "beforeend",
                `<label>데미지 반복 횟수<input data-repeat type="text" value="${escapeHtml(valueForEditor(effect.repeat === undefined ? 1 : effect.repeat))}"></label><label data-break-cards-options><input data-break-require-all type="checkbox"${effect.require_all ? " checked" : ""}> 모든 대상이 가능할 때만 브레이크</label>`,
            );
            function updateCommandOptions() {
                node.querySelector("[data-combo-options]").hidden = node.querySelector("[data-op]").value !== "modify_combo";
                node.querySelector("[data-catch-options]").hidden = node.querySelector("[data-op]").value !== "grant_catch";
                node.querySelector("[data-break-cards-options]").hidden = node.querySelector("[data-op]").value !== "break_cards";
            }
            node.querySelector("[data-remove-command]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input,select").forEach((input) => input.addEventListener("input", () => { node._effectDirty = true; updateCommandOptions(); sync(); }));
            updateCommandOptions();
            return node;
        }

        function abilityNode(ability) {
            const node = document.createElement("section");
            node.className = "effect-ability";
            node._abilityOriginal = JSON.parse(JSON.stringify(ability || {}));
            const sources = ability.source_refs || {};
            const triggerEvent = (ability.trigger || {}).event || "";
            node.innerHTML = `<div class="effect-ability-head"><strong>능력 노드</strong><label><input type="checkbox" data-ability-draft${ability.draft ? " checked" : ""}> 자동 초안(게시 불가)</label><button type="button" class="button" data-remove-ability>능력 삭제</button></div><div class="effect-node-grid"><label>안정 ID<input data-id value="${escapeHtml(ability.id || "")}" required></label><label>표시명<input data-label value="${escapeHtml(ability.label || "")}"></label><label>종류<select data-kind>${optionList(["function", "effect"], ability.kind || "effect")}</select></label><label>처리<select data-mode>${optionList(["mandatory", "optional", "continuous", "replacement"], ability.mode || "mandatory")}</select></label><label>공개 범위<select data-visibility>${optionList(["public", "private"], ability.visibility || "public")}</select></label><label>기본 트리거<select data-trigger><option value=""${triggerEvent ? "" : " selected"}>관련 트리거 없음 (상시·정적 규칙)</option>${optionList(triggerOptions, triggerEvent)}</select></label><label>복수 트리거(쉼표)<input data-trigger-events value="${escapeHtml(((ability.trigger || {}).events || []).join(","))}" placeholder="예: hit,counter"></label><label>타이밍<select data-timing>${optionList(timingOptions, ability.timing || (triggerEvent ? "use" : "function"))}</select></label><label>룰북 페이지(쉼표)<input data-pages value="${escapeHtml((sources.rulebook_pages || []).join(","))}"></label><label>Q&A ID(쉼표)<input data-qnas value="${escapeHtml((sources.qna_ids || []).join(","))}"></label><label>사용 제한 범위<select data-limit-scope><option value="">없음</option>${optionList(["game", "turn", "phase", "battle"], (ability.limit || {}).scope || "")}</select></label><label>최대 횟수<input data-limit-max type="number" min="1" value="${Number((ability.limit || {}).max || 1)}"></label></div><div data-commands></div><button type="button" class="button" data-add-command>명령 추가</button>`;
            const condition = ability.condition || {};
            const target = (ability.targets || [])[0] || {};
            const targetWhere = target.where || {};
            const nodes = document.createElement("div");
            nodes.className = "effect-node-grid";
            const conditionLeft = condition.op === "card_matches" ? (condition.card || {}).path || "" : condition.left || condition.state || condition.counter || "";
            const conditionRight = condition.op === "card_matches" ? JSON.stringify(condition.where || {}) : condition.right === undefined ? condition.phase || condition.value || "" : typeof condition.right === "object" ? JSON.stringify(condition.right) : condition.right;
            nodes.innerHTML = `<label>조건 연산<select data-condition-op>${optionList(conditionOptions, condition.op || "")}</select></label><label>조건 상태·카드 경로<input data-condition-left value="${escapeHtml(conditionLeft)}"></label><label>조건 비교값·필터(JSON 가능)<input data-condition-right value="${escapeHtml(conditionRight)}"></label><label>대상 종류<select data-target-kind>${optionList(["", "card", "player"], target.kind || "")}</select></label><label>대상 플레이어<select data-target-player>${optionList(["controller", "opponent", "any", "p1", "p2"], target.player === undefined ? "controller" : typeof target.player === "object" && target.player.opponent ? "opponent" : target.player)}</select></label><label>대상 존<input data-target-zone value="${escapeHtml(target.zone || "hand")}"></label><label>최소 선택<input data-target-min type="number" min="0" value="${Number(target.min === undefined ? 1 : target.min)}"></label><label>최대 선택<input data-target-max type="number" min="0" value="${Number(target.max === undefined ? target.min === undefined ? 1 : target.min : target.max)}"></label><label>카드 종류 포함<input data-target-type value="${escapeHtml(targetWhere.type_contains || "")}"></label>`;
            node.querySelector("[data-commands]").before(nodes);
            const commands = node.querySelector("[data-commands]");
            (ability.effects || []).forEach((effect) => commands.appendChild(commandNode(effect)));
            node.querySelector("[data-add-command]").addEventListener("click", () => { commands.appendChild(commandNode({op: "change_fp"})); sync(); });
            node.querySelector("[data-remove-ability]").addEventListener("click", () => { node.remove(); sync(); });
            node.querySelectorAll("input,select").forEach((input) => input.addEventListener("input", sync));
            return node;
        }

        function readCommand(node) {
            if (node.dataset.preservedCommand === "1" || !node._effectDirty) {
                return JSON.parse(JSON.stringify(node._effectOriginal || {}));
            }
            const player = node.querySelector("[data-player]").value;
            const op = node.querySelector("[data-op]").value;
            const value = parsedValue(node.querySelector("[data-amount]").value);
            const key = node.querySelector("[data-key]").value.trim();
            const zone = node.querySelector("[data-zone]").value.trim();
            const repeat = parsedValue(node.querySelector("[data-repeat]").value);
            const effect = Object.assign({}, node._effectOriginal || {}, {op, player: player === "controller" ? {controller: true} : player === "opponent" ? {opponent: true} : player});
            if (["deal_damage", "change_hp", "change_fp", "change_counter", "modify_stat", "modify_damage"].includes(op)) effect.amount = value;
            if (op === "deal_damage") {
                if (repeat === 1) delete effect.repeat; else effect.repeat = repeat;
            }
            if (op === "set_counter" || op === "set_usage_limit") effect.value = value;
            if (op === "set_usage_limit") effect.key = key;
            if (["gain_state", "lose_state"].includes(op)) effect.state = key;
            if (["change_counter", "set_counter"].includes(op)) effect.counter = key;
            if (["modify_stat", "fix_speed"].includes(op)) {
                effect.stat = key || "frame";
                if (op === "fix_speed") effect.value = value;
            }
            if (op === "modify_judgment") {
                effect.field = key || "hit";
                effect.value = String(value);
                delete effect.amount;
            }
            if (["skip_phase", "repeat_phase"].includes(op)) effect.phase = key;
            if (["prevent", "negate", "replace"].includes(op)) effect.kind = key || "damage";
            if (op === "modify_damage") effect.kind = key || "damage";
            if (op === "modify_combo") {
                effect.allow_zones = node.querySelector("[data-combo-zones]").value.split(",").map((item) => item.trim()).filter(Boolean);
                const candidateName = node.querySelector("[data-combo-name]").value.trim();
                const previousName = node.querySelector("[data-combo-after-name]").value.trim();
                effect.where = Object.assign({}, effect.where || {});
                effect.after_where = Object.assign({}, effect.after_where || {});
                if (candidateName) effect.where.name_contains = candidateName; else delete effect.where.name_contains;
                if (previousName) effect.after_where.name_contains = previousName; else delete effect.after_where.name_contains;
                if (!Object.keys(effect.where).length) delete effect.where;
                if (!Object.keys(effect.after_where).length) delete effect.after_where;
                const minimum = Number(node.querySelector("[data-combo-min]").value || 0);
                const maximum = Number(node.querySelector("[data-combo-max]").value || 0);
                if (minimum) effect.min_combo = minimum; else delete effect.min_combo;
                if (maximum) effect.max_combo = maximum; else delete effect.max_combo;
                effect.ignore_speed = node.querySelector("[data-combo-ignore-speed]").checked;
                effect.any_speed = node.querySelector("[data-combo-any-speed]").checked;
                effect.ignore_damage_penalty = node.querySelector("[data-combo-ignore-damage]").checked;
                effect.optional_ignore_damage_penalty = node.querySelector("[data-combo-optional-ignore-damage]").checked;
                delete effect.amount;
                delete effect.value;
            }
            if (op === "grant_catch") {
                effect.allow_zones = node.querySelector("[data-catch-zones]").value.split(",").map((item) => item.trim()).filter(Boolean);
                const minimum = Number(node.querySelector("[data-catch-min]").value || 0);
                const maximum = Number(node.querySelector("[data-catch-max]").value || 0);
                if (minimum) effect.min_speed = minimum; else delete effect.min_speed;
                if (maximum) effect.max_speed = maximum; else delete effect.max_speed;
                const filterKey = node.querySelector("[data-catch-filter-key]").value;
                const filterValue = node.querySelector("[data-catch-filter-value]").value.trim();
                effect.where = Object.assign({}, effect.where || {});
                ["character_key", "text_contains", "code", "name_contains", "type_contains"].forEach((item) => delete effect.where[item]);
                if (filterValue) effect.where[filterKey] = filterValue;
                if (!Object.keys(effect.where).length) delete effect.where;
                delete effect.amount;
                delete effect.value;
            }
            if (op === "move_card") effect.to_zone = zone;
            if (["discard", "reveal", "hide", "delete_token", "random_select", "request_choice"].includes(op)) {
                const originalSelector = (node._effectOriginal || {}).selector || {};
                effect.selector = Object.assign({}, originalSelector, {
                    kind: "card", player: effect.player, zone: zone || "hand",
                    min: originalSelector.min === undefined ? 1 : originalSelector.min,
                    max: originalSelector.max === undefined ? 1 : originalSelector.max,
                });
            }
            if (op === "break_card") {
                if (value && typeof value === "object" && !Array.isArray(value)) {
                    effect.card_instance_id = value;
                    delete effect.selector;
                } else if (zone) {
                    const originalSelector = (node._effectOriginal || {}).selector || {};
                    effect.selector = Object.assign({}, originalSelector, {
                        kind: "card", player: effect.player, zone,
                        min: originalSelector.min === undefined ? 1 : originalSelector.min,
                        max: originalSelector.max === undefined ? 1 : originalSelector.max,
                    });
                    delete effect.card_instance_id;
                } else {
                    delete effect.card_instance_id;
                    delete effect.selector;
                }
            }
            if (op === "break_cards") {
                effect.card_instance_ids = Array.isArray(value) ? value : [];
                effect.require_all = node.querySelector("[data-break-require-all]").checked;
                delete effect.card_instance_id;
                delete effect.selector;
                delete effect.player;
                delete effect.amount;
                delete effect.value;
            }
            if (op === "request_choice") {
                if (!Array.isArray(effect.default)) effect.default = [];
                if (!Array.isArray(effect.then)) effect.then = [];
            }
            return effect;
        }

        function sync() {
            definition.schema_version = 1;
            definition.draft = draft.checked;
            definition.no_effect = noEffect.checked;
            definition.reviewed = reviewed.checked;
            definition.source_refs = Object.assign({}, definition.source_refs || {}, {
                rulebook_pages: parsedList(rootPages.value),
                qna_ids: parsedList(rootQnas.value),
            });
            const semanticTokenKey = tokenKey.value.trim();
            if (semanticTokenKey) definition.token_key = semanticTokenKey; else delete definition.token_key;
            const tokenUsage = [];
            if (tokenUsageToken.checked) tokenUsage.push("token");
            if (tokenUsageCounter.checked) tokenUsage.push("counter");
            if (tokenUsage.length) definition.token_usage = tokenUsage; else delete definition.token_usage;
            const deckRules = Object.assign({}, preservedDeckRules);
            const minimumDeckSize = deckMainMin.value;
            const maximumDeckSize = deckMainMax.value;
            if (minimumDeckSize || maximumDeckSize) {
                deckRules.main_size = {
                    min: Number(minimumDeckSize || maximumDeckSize),
                    max: Number(maximumDeckSize || minimumDeckSize),
                };
                if (deckBaseExcludes.checked) deckRules.main_size.base_excludes_supplements = true;
            }
            if (deckCharacterMin.value !== "") deckRules.character_card_minimum = Number(deckCharacterMin.value);
            const supplements = Array.from(deckSupplements.querySelectorAll(":scope > .effect-command")).map(readDeckSupplement);
            if (supplements.length) deckRules.supplements = supplements;
            const importedTypes = deckImportTypes.value.split(",").map((item) => item.trim()).filter(Boolean);
            if (importedTypes.length) {
                deckRules.other_character_cards = {
                    allowed_types: importedTypes,
                    max_per_character: Number(deckImportMax.value || 1),
                    exclude_character_ids: parsedList(deckImportExcluded.value),
                    exclude_ultimate: deckImportNoUltimate.checked,
                    treat_as_own_character: deckImportTreatOwn.checked,
                    negate_effects: deckImportNegate.checked,
                    break_after_use: deckImportBreak.checked,
                };
            }
            if (Object.keys(deckRules).length) definition.deck_rules = deckRules;
            else delete definition.deck_rules;
            const conditions = [
                ...preservedPlayConditions,
                ...Array.from(playConditions.querySelectorAll(":scope > .effect-command")).map(readRootCondition),
            ];
            if (conditions.length === 1) definition.play_condition = conditions[0];
            else if (conditions.length > 1) definition.play_condition = {op: "all", conditions};
            else delete definition.play_condition;
            const rootComboRules = Array.from(comboRules.querySelectorAll(":scope > .effect-command")).map(readComboRule);
            if (rootComboRules.length) definition.combo_rules = rootComboRules; else delete definition.combo_rules;
            const configuredPlayLimitScope = playLimitScope.value;
            if (configuredPlayLimitScope) definition.play_limit = {
                scope: configuredPlayLimitScope,
                key: playLimitKey.value.trim(),
                max: Number(playLimitMax.value || 1),
            }; else delete definition.play_limit;
            const rootDefenseRules = Array.from(defenseRules.querySelectorAll(":scope > .effect-command")).map(readDefenseRule);
            if (rootDefenseRules.length) definition.defense_rules = rootDefenseRules; else delete definition.defense_rules;
            const rootZoneLimits = Array.from(zoneLimits.querySelectorAll(":scope > .effect-command")).map(readZoneLimit);
            if (rootZoneLimits.length) definition.zone_limits = rootZoneLimits; else delete definition.zone_limits;
            const configuredImmunityScope = immunityScope.value;
            if (configuredImmunityScope) {
                definition.effect_immunity = Object.assign({}, definition.effect_immunity || {}, {
                    scope: configuredImmunityScope,
                });
                const activeZones = immunityZones.value.split(",").map((item) => item.trim()).filter(Boolean);
                if (activeZones.length) definition.effect_immunity.active_zones = activeZones;
                else delete definition.effect_immunity.active_zones;
            } else {
                delete definition.effect_immunity;
            }
            const configuredBreakZones = breakZones.value.split(",").map((item) => item.trim()).filter(Boolean);
            const breakPreventions = preservedBreakPreventions.map((item) => JSON.parse(JSON.stringify(item)));
            if (breakOwnerDirect.checked) breakPreventions.push({scope: "owner_direct"});
            if (breakOpponentEffect.checked) breakPreventions.push({scope: "opponent_effect"});
            if (breakAll.checked) {
                const prevention = {scope: "all"};
                const state = breakAllState.value.trim();
                if (state) prevention.condition = {op: "has_state", player: {controller: true}, state};
                breakPreventions.push(prevention);
            }
            if (configuredBreakZones.length || breakPreventions.length) {
                definition.break_rules = Object.assign({}, definition.break_rules || {});
                if (configuredBreakZones.length) definition.break_rules.forbidden_zones = configuredBreakZones;
                else delete definition.break_rules.forbidden_zones;
                if (breakPreventions.length) definition.break_rules.preventions = breakPreventions;
                else delete definition.break_rules.preventions;
            } else {
                delete definition.break_rules;
            }
            definition.abilities = Array.from(holder.querySelectorAll(":scope > .effect-ability")).map((node) => {
                const scope = node.querySelector("[data-limit-scope]").value;
                const ability = Object.assign({}, node._abilityOriginal || {}, {
                    id: node.querySelector("[data-id]").value.trim(),
                    label: node.querySelector("[data-label]").value.trim(),
                    kind: node.querySelector("[data-kind]").value,
                    mode: node.querySelector("[data-mode]").value,
                    visibility: node.querySelector("[data-visibility]").value,
                    draft: node.querySelector("[data-ability-draft]").checked,
                    timing: node.querySelector("[data-timing]").value,
                    source_refs: Object.assign({}, (node._abilityOriginal || {}).source_refs || {}, {
                        rulebook_pages: parsedList(node.querySelector("[data-pages]").value),
                        qna_ids: parsedList(node.querySelector("[data-qnas]").value),
                    }),
                    effects: Array.from(node.querySelectorAll("[data-commands] > .effect-command")).map(readCommand),
                });
                const conditionOp = node.querySelector("[data-condition-op]").value;
                const triggerEvent = node.querySelector("[data-trigger]").value;
                const triggerEvents = node.querySelector("[data-trigger-events]").value.split(",").map((item) => item.trim()).filter(Boolean);
                if (triggerEvent) {
                    ability.trigger = Object.assign({}, ability.trigger || {}, {event: triggerEvent});
                } else {
                    delete ability.trigger;
                }
                if (triggerEvents.length && ability.trigger) {
                    ability.trigger.events = [triggerEvent, ...triggerEvents.filter((item) => item !== triggerEvent)];
                } else if (ability.trigger) {
                    delete ability.trigger.events;
                }
                if (conditionOp) {
                    const left = node.querySelector("[data-condition-left]").value.trim();
                    const rawRight = node.querySelector("[data-condition-right]").value.trim();
                    let right = rawRight;
                    try { right = JSON.parse(rawRight); } catch (_error) { /* keep string */ }
                    ability.condition = {op: conditionOp};
                    if (["phase_is"].includes(conditionOp)) ability.condition.phase = right;
                    else if (["result_is"].includes(conditionOp)) ability.condition.result = right;
                    else if (["has_state"].includes(conditionOp)) ability.condition.state = left;
                    else if (["counter_at_least"].includes(conditionOp)) { ability.condition.counter = left; ability.condition.value = right; }
                    else if (conditionOp === "card_matches") {
                        ability.condition.card = {path: left || "context.opponent_card"};
                        ability.condition.where = right && typeof right === "object" && !Array.isArray(right) ? right : {};
                    }
                    else { ability.condition.left = left; if (conditionOp !== "exists") ability.condition.right = right; }
                } else {
                    delete ability.condition;
                }
                const targetKind = node.querySelector("[data-target-kind]").value;
                if (targetKind) {
                    const targetPlayer = node.querySelector("[data-target-player]").value;
                    const whereType = node.querySelector("[data-target-type]").value.trim();
                    const originalTargets = Array.isArray((node._abilityOriginal || {}).targets) ? node._abilityOriginal.targets : [];
                    const mergedWhere = Object.assign({}, (originalTargets[0] || {}).where || {});
                    if (whereType) mergedWhere.type_contains = whereType;
                    else delete mergedWhere.type_contains;
                    ability.targets = [Object.assign({}, originalTargets[0] || {}, {
                        kind: targetKind,
                        player: targetPlayer === "opponent" ? {opponent: true} : targetPlayer === "controller" ? {controller: true} : targetPlayer,
                        zone: node.querySelector("[data-target-zone]").value.trim(),
                        min: Number(node.querySelector("[data-target-min]").value || 0),
                        max: Number(node.querySelector("[data-target-max]").value || 0),
                        where: mergedWhere,
                    }), ...originalTargets.slice(1)];
                } else {
                    ability.targets = [];
                }
                if (scope) ability.limit = Object.assign({}, (node._abilityOriginal || {}).limit || {}, {scope, max: Number(node.querySelector("[data-limit-max]").value || 1)});
                else delete ability.limit;
                return ability;
            });
            const serialized = JSON.stringify(definition, null, 2);
            field.value = serialized;
            preview.textContent = serialized;
        }

        const configuredConditions = definition.play_condition && definition.play_condition.op === "all" ? definition.play_condition.conditions || [] : definition.play_condition ? [definition.play_condition] : [];
        configuredConditions.forEach((condition) => {
            if (condition && rootConditionOptions.includes(condition.op)) playConditions.appendChild(rootConditionNode(condition));
            else if (condition !== undefined) preservedPlayConditions.push(JSON.parse(JSON.stringify(condition)));
        });
        (configuredDeckRules.supplements || []).forEach((supplement) => deckSupplements.appendChild(deckSupplementNode(supplement)));
        (definition.combo_rules || []).forEach((rule) => comboRules.appendChild(comboRuleNode(rule)));
        (definition.defense_rules || []).forEach((rule) => defenseRules.appendChild(defenseRuleNode(rule)));
        (definition.zone_limits || []).forEach((limit) => zoneLimits.appendChild(zoneLimitNode(limit)));
        (definition.abilities || []).forEach((ability) => holder.appendChild(abilityNode(ability)));
        root.querySelector("[data-effect-add-ability]").addEventListener("click", () => {
            holder.appendChild(abilityNode({id: "", kind: "effect", mode: "mandatory", trigger: {event: "use"}, timing: "use", effects: []}));
            sync();
        });
        root.querySelector("[data-effect-add-play-condition]").addEventListener("click", () => {
            playConditions.appendChild(rootConditionNode({op: "equals", left: "context.use_context", right: "ready"}));
            sync();
        });
        root.querySelector("[data-effect-add-deck-supplement]").addEventListener("click", () => {
            deckSupplements.appendChild(deckSupplementNode({where: {code: ""}, max_count: 1}));
            sync();
        });
        root.querySelector("[data-effect-add-combo-rule]").addEventListener("click", () => {
            comboRules.appendChild(comboRuleNode({}));
            sync();
        });
        root.querySelector("[data-effect-add-zone-limit]").addEventListener("click", () => {
            zoneLimits.appendChild(zoneLimitNode({zone: "lumen", max: 1, where: {name_contains: ""}}));
            sync();
        });
        root.querySelector("[data-effect-add-defense-rule]").addEventListener("click", () => {
            defenseRules.appendChild(defenseRuleNode({}));
            sync();
        });
        noEffect.addEventListener("change", sync);
        draft.addEventListener("change", sync);
        reviewed.addEventListener("change", sync);
        rootPages.addEventListener("input", sync);
        rootQnas.addEventListener("input", sync);
        tokenKey.addEventListener("input", sync);
        tokenUsageToken.addEventListener("change", sync);
        tokenUsageCounter.addEventListener("change", sync);
        [deckMainMin, deckMainMax, deckCharacterMin, deckImportTypes, deckImportMax, deckImportExcluded].forEach((input) => input.addEventListener("input", sync));
        [deckBaseExcludes, deckImportNoUltimate, deckImportTreatOwn, deckImportNegate, deckImportBreak].forEach((input) => input.addEventListener("change", sync));
        playLimitScope.addEventListener("change", sync);
        playLimitKey.addEventListener("input", sync);
        playLimitMax.addEventListener("input", sync);
        immunityScope.addEventListener("change", sync);
        immunityZones.addEventListener("input", sync);
        breakZones.addEventListener("input", sync);
        breakOwnerDirect.addEventListener("change", sync);
        breakOpponentEffect.addEventListener("change", sync);
        breakAll.addEventListener("change", sync);
        breakAllState.addEventListener("input", sync);
        // Initial rendering must never rewrite a definition. In particular,
        // unsupported/static commands and trigger-less functions must survive a
        // load-and-save round trip until the reviewer actually edits a field.
        preview.textContent = JSON.stringify(definition, null, 2);
    }

    function boot() { document.querySelectorAll("[data-effect-editor]").forEach(init); }
    document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
}());
