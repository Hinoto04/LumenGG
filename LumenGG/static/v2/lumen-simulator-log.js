(function () {
    "use strict";

    const HIDDEN_EVENT_TYPES = new Set([
        "command",
        "private_event",
        "clock_started",
        "decision_requested",
        "card_usage_recorded",
        "limited_use_consumed",
        "state_expiration_scheduled",
        "state_expiration_advanced",
        "scheduled_effect_expired",
        "modifier_added",
        "get_completed",
        "damage_dealt",
        "card_discarded",
    ]);

    const RESULT_LABELS = {
        none: "판정 없음",
        hit: "히트",
        counter: "카운터",
        countered: "카운터당함",
        guard: "방어",
        guarded: "방어당함",
        dodge: "회피",
        opponent_dodge: "상대 회피",
        clash: "상쇄",
        failed_defense: "방어 실패",
    };

    const REASON_LABELS = {
        ready: "레디",
        no_response: "대응하지 않음",
        effect: "효과",
        get: "획득",
        discard: "버리기",
        battle_cleanup: "배틀 정리",
        break: "브레이크",
        list_limit: "리스트 상한 초과",
        defense_over: "디펜스 오버",
        combo: "콤보",
        catch: "캐치",
        forced_get: "강제 획득",
        hand_limit: "패 매수 조정",
        special_destination: "특수 기술 이동",
    };

    const GENERIC_LABELS = {
        setup_completed: "게임 준비가 완료되었습니다.",
        automatic_game_started: "자동 대전을 시작했습니다.",
        combo_granted: "콤보 기회를 얻었습니다.",
        combo_proposed: "사용할 콤보를 제시했습니다.",
        combo_started: "콤보 타임을 시작했습니다.",
        combo_ended: "콤보를 종료했습니다.",
        combo_time_ended: "콤보 타임이 종료되었습니다.",
        mutual_combo_resolved: "서로의 콤보 판정을 처리했습니다.",
        combo_followup_required: "이어 사용할 콤보 기술을 선택해야 합니다.",
        combo_optional_grant_opened: "추가 콤보 기회를 사용할 수 있습니다.",
        catch_started: "캐치 타임을 시작했습니다.",
        catch_ended: "캐치 타임이 종료되었습니다.",
        catch_opportunity_resolved: "캐치 기회를 처리했습니다.",
        defense_over: "디펜스 오버가 발생했습니다.",
        grab_negated: "그랩을 무효로 했습니다.",
        rewind_requested: "직전 행동의 되감기를 요청했습니다.",
        rewind_expired: "되감기 요청 시간이 만료되었습니다.",
        sudden_death_started: "서든 데스를 시작합니다.",
        sudden_death_rebuilt: "서든 데스용 패와 리스트를 준비했습니다.",
        trait_temporary_effects_ended: "이번 배틀의 임시 특성 효과가 종료되었습니다.",
        scheduled_effect_skipped: "예약된 효과가 조건을 충족하지 못했습니다.",
        effect_choice_skipped: "선택할 수 있는 대상이 없어 효과를 건너뛰었습니다.",
        ability_target_skipped: "효과를 적용할 수 있는 대상이 없습니다.",
        effect_damage_capped: "효과 데미지 상한을 적용했습니다.",
        play_cost_unavailable: "기술 사용 비용을 지불할 수 없습니다.",
        play_cost_failed: "기술 사용 비용 지불에 실패했습니다.",
        defense_cost_unavailable: "수비 효과 비용을 지불할 수 없습니다.",
        combo_skipped: "콤보 기회를 사용할 수 없어 건너뛰었습니다.",
        catch_skipped: "캐치 기회를 사용하지 않았습니다.",
        flexible_use_granted: "기술 사용 가능 영역이 확장되었습니다.",
        phase_repeat_scheduled: "페이즈를 한 번 더 진행합니다.",
    };

    function call(helper, fallback, ...args) {
        return typeof helper === "function" ? helper(...args) : fallback;
    }

    function create(summary, category, options) {
        const extra = options || {};
        return {
            summary: summary || "게임 처리가 진행되었습니다.",
            category: category || "시스템",
            detail: extra.detail || "",
            tone: extra.tone || "",
            major: !!extra.major,
            hidden: !!extra.hidden,
        };
    }

    function format(event, helpers) {
        const current = event || {};
        const payload = current.payload || {};
        const type = String(current.type || "");
        const t = (value) => call(helpers && helpers.t, value, value);
        const player = (side) => call(
            helpers && helpers.playerLabel,
            side === "p1" ? "P1" : side === "p2" ? "P2" : t("시스템"),
            side,
        );
        const zone = (name) => call(helpers && helpers.zoneLabel, name || t("영역"), name);
        const phase = (name) => call(helpers && helpers.phaseLabel, name || t("페이즈"), name);
        const signed = (value) => call(
            helpers && helpers.formatSigned,
            Number(value) > 0 ? `+${value}` : String(value ?? 0),
            value,
        );
        const actorSide = ["p1", "p2"].includes(current.actor) ? current.actor : "";
        const actor = actorSide ? player(actorSide) : t("시스템");
        const cardLabel = (card) => {
            const data = card || {};
            return data.card_label || data.card_code || data.name || t("카드");
        };

        if (HIDDEN_EVENT_TYPES.has(type)) {
            return create("", "", { hidden: true });
        }

        if (type === "phase_started" || type === "phase_restarted") {
            const turn = Number(payload.turn || 0);
            return create(
                `${turn ? `${turn}${t("턴")} · ` : ""}${phase(payload.phase)} ${t("페이즈 시작")}`,
                t("페이즈"),
                { major: true, tone: "phase" },
            );
        }
        if (type === "phase_passed") {
            return create(
                `${actor}${t("이(가)")} ${phase(payload.phase)}${t("에서 행동을 마쳤습니다.")}`,
                t("페이즈"),
            );
        }
        if (type === "phase_auto_advanced") {
            const owner = payload.player
                ? `${player(payload.player)}${t("에게 ")}`
                : "";
            return create(
                `${owner}${t("가능한 행동이 없어 ")}${phase(payload.phase)}${t("를 자동으로 진행했습니다.")}`,
                t("페이즈"),
                { tone: "phase" },
            );
        }
        if (type === "phase_skipped") {
            const owner = payload.player ? `${player(payload.player)}${t("의 ")}` : "";
            return create(
                `${owner}${phase(payload.phase)}${t("를 건너뜁니다.")}`,
                t("페이즈"),
                { major: true, tone: "warning" },
            );
        }

        if (type === "battle_revealed") {
            const p1 = cardLabel(payload.p1);
            const p2 = cardLabel(payload.p2);
            return create(
                `${player("p1")} 「${p1}」  VS  ${player("p2")} 「${p2}」`,
                t("배틀"),
                { detail: t("양쪽의 레디 기술이 공개되었습니다."), major: true, tone: "battle" },
            );
        }
        if (type === "battle_judged") {
            const cards = payload.cards || {};
            const result = payload.result || {};
            const speed = payload.speed || {};
            const reference = payload.reference_speed || {};
            const sideResult = (side) => {
                const name = cardLabel(cards[side]);
                const resultLabel = t(RESULT_LABELS[result[side]] || "판정 없음");
                return `${player(side)} 「${name}」: ${resultLabel}`;
            };
            const speedDetail = ["p1", "p2"].map((side) => {
                if (
                    String((cards[side] || {}).card_type || "").includes("수비")
                    || ["guard", "dodge", "none", "failed_defense"].includes(result[side])
                ) {
                    return "";
                }
                const fixed = speed[side];
                const base = reference[side];
                if (fixed === undefined) return "";
                return base !== undefined && Number(base) !== Number(fixed)
                    ? `${player(side)} ${t("속도")} ${fixed} (${t("기준")} ${base})`
                    : `${player(side)} ${t("속도")} ${fixed}`;
            }).filter(Boolean).join(" · ");
            return create(
                `${sideResult("p1")} / ${sideResult("p2")}`,
                t("판정"),
                { detail: speedDetail, major: true, tone: "judgment" },
            );
        }
        if (type === "card_readied") {
            return create(
                `${actor}${t("이(가)")} 「${cardLabel(payload)}」${t("을(를) 레디했습니다.")}`,
                t("레디"),
                { tone: "card" },
            );
        }

        if (type === "decision_resolved") {
            const selected = (payload.selected_options || [])
                .map((option) => cardLabel({
                    card_label: option && (option.label || option.card_label),
                    card_code: option && option.card_code,
                }))
                .filter(Boolean);
            const choice = selected.length
                ? selected.map((label) => `「${label}」`).join(", ")
                : t("선택하지 않음");
            const timeout = payload.timed_out ? ` · ${t("시간 만료로 자동 선택")}` : "";
            return create(
                `${actor}: ${choice}${timeout}`,
                t("선택"),
                { detail: payload.prompt || t("효과 선택을 확정했습니다."), tone: "choice" },
            );
        }
        if (type === "effect_resolved") {
            const abilityId = String(payload.ability_id || "");
            const number = abilityId.match(/-n(\d+)/i);
            const effect = payload.effect_label
                || (number ? `${number[1]}${t("번 효과")}` : t("기능/효과"));
            return create(
                `${actor}${t("의 ")}「${cardLabel(payload)}」 ${effect}${t("를 처리했습니다.")}`,
                t("효과"),
                { tone: "effect" },
            );
        }
        if (type === "effect_log") {
            return create(payload.text || t("카드 효과를 처리했습니다."), t("효과"), { tone: "effect" });
        }

        if (type === "card_moved" || type === "move_card") {
            if (payload.reason === "ready") {
                return create("", "", { hidden: true });
            }
            const from = payload.from_player
                ? `${player(payload.from_player)} ${zone(payload.from_zone)}`
                : zone(payload.from_zone);
            const to = payload.to_player
                ? `${player(payload.to_player)} ${zone(payload.to_zone)}`
                : zone(payload.to_zone);
            const reason = REASON_LABELS[payload.reason];
            const name = `「${cardLabel(payload)}」`;
            if (payload.to_zone === "break") {
                return create(
                    `${name}${t("이(가) 브레이크되었습니다.")}`,
                    t("브레이크"),
                    {
                        detail: `${from} → ${to}${reason ? ` · ${t(reason)}` : ""}`,
                        tone: "warning",
                    },
                );
            }
            if (payload.reason === "get" || payload.reason === "forced_get") {
                return create(
                    `${actor}${t("이(가) ")}${name}${t("을(를) 획득했습니다.")}`,
                    t("획득"),
                    { detail: `${from} → ${to}`, tone: "card" },
                );
            }
            if (payload.reason === "discard") {
                return create(
                    `${actor}${t("이(가) ")}${name}${t("을(를) 버렸습니다.")}`,
                    t("버리기"),
                    { detail: `${from} → ${to}`, tone: "move" },
                );
            }
            if (payload.reason === "battle_cleanup") {
                return create(
                    `${name}${t("이(가) ")}${to}${t("로 돌아갔습니다.")}`,
                    t("배틀 정리"),
                    { detail: `${from} → ${to}`, tone: "move" },
                );
            }
            if (payload.reason === "no_response") {
                return create(
                    `${actor}${t("의 ")}${name}${t("이(가) 강제로 레디되었습니다.")}`,
                    t("대응 없음"),
                    { tone: "warning" },
                );
            }
            return create(
                `${name}: ${from} → ${to}`,
                t("카드 이동"),
                {
                    detail: reason ? `${t("이유")}: ${t(reason)}` : "",
                    tone: "move",
                },
            );
        }
        if (type === "card_broken") {
            if (payload.reason !== "list_limit") {
                return create("", "", { hidden: true });
            }
            return create(
                `「${cardLabel(payload)}」${t("이(가) 리스트 상한 초과로 브레이크되었습니다.")}`,
                t("브레이크"),
                { tone: "warning" },
            );
        }
        if (type === "card_discarded") {
            return create(
                `${actor}${t("이(가) 카드를 버렸습니다.")}`,
                t("버리기"),
                { detail: `${zone(payload.from_zone)} → ${zone(payload.to_zone)}`, tone: "move" },
            );
        }
        if (type === "card_attached" || type === "attach_card") {
            return create(
                `「${payload.card_label || t("카드")}」${t("을(를) ")}「${payload.host_card_label || t("카드")}」${t("에 세트했습니다.")}`,
                t("세트"),
                { tone: "card" },
            );
        }
        if (type === "card_visibility_changed" || type === "set_visibility") {
            return create(
                `「${cardLabel(payload)}」${t("을(를) ")}${payload.face_up ? t("공개했습니다.") : t("비공개로 전환했습니다.")}`,
                t("공개 정보"),
                { tone: "card" },
            );
        }
        if (["card_move_prevented", "card_break_prevented", "card_exchange_prevented"].includes(type)) {
            return create(
                `${actor}${t("의 카드 영역 이동이 효과로 막혔습니다.")}`,
                t("효과"),
                { tone: "warning" },
            );
        }
        if (type === "cards_exchanged") {
            return create(t("두 카드의 위치를 서로 바꿨습니다."), t("카드 이동"), { tone: "move" });
        }

        if (type === "hp_changed") {
            const amount = Number(payload.amount || 0);
            const verb = amount < 0 ? t("감소") : t("회복");
            return create(
                `${player(current.actor)} HP ${Math.abs(amount)} ${verb}`,
                "HP",
                { detail: `${payload.before} → ${payload.after}`, tone: amount < 0 ? "damage" : "recover" },
            );
        }
        if (type === "fp_changed") {
            return create(
                `${player(current.actor)} FP ${signed(payload.amount)}`,
                "FP",
                { detail: `${signed(payload.before)} → ${signed(payload.after)}`, tone: "fp" },
            );
        }
        if (type === "state_gained" || type === "state_lost") {
            return create(
                `${actor}${t("이(가) ")}${payload.state || t("상태")}${type === "state_gained" ? t(" 상태를 얻었습니다.") : t(" 상태를 잃었습니다.")}`,
                t("상태"),
            );
        }
        if (type === "counter_changed") {
            return create(
                `${actor} ${payload.counter || t("카운터")} ${signed(payload.amount)}`,
                t("카운터"),
                { detail: `${payload.before} → ${payload.count}` },
            );
        }
        if (type === "shield_gained") {
            return create(`${actor}${t("이(가) 보호 효과를 얻었습니다.")}`, t("효과"), { tone: "effect" });
        }
        if (type === "shield_absorbed") {
            return create(`${actor}${t("의 보호 효과가 데미지를 막았습니다.")}`, t("효과"), { tone: "effect" });
        }

        if (type === "no_response") {
            return create(
                `${actor}${t("이(가) 대응하지 않았습니다.")} (${payload.count || 1}/3)`,
                t("대응 없음"),
                { major: true, tone: "warning" },
            );
        }
        if (type === "priority_calculated") {
            return create(
                `${player(payload.priority_player)}${t("이(가) 우선권을 가집니다.")}`,
                t("우선권"),
                { tone: "phase" },
            );
        }
        if (type === "clock_paused" || type === "clock_resumed") {
            return create(
                `${actor}${t("이(가) 타이머를 ")}${type === "clock_paused" ? t("일시정지했습니다.") : t("재개했습니다.")}`,
                t("타이머"),
            );
        }
        if (type === "rewind_answered") {
            return create(
                `${actor}${t("이(가) 되감기 요청을 ")}${payload.accept ? t("수락했습니다.") : t("거절했습니다.")}`,
                t("되감기"),
                { tone: payload.accept ? "recover" : "warning" },
            );
        }
        if (type === "game_finished") {
            const winner = payload.winner ? player(payload.winner) : t("무승부");
            return create(
                payload.winner ? `${winner}${t(" 승리")}` : winner,
                t("게임 종료"),
                { detail: payload.reason || "", major: true, tone: "finish" },
            );
        }

        if (GENERIC_LABELS[type]) {
            const subject = actorSide && !["setup_completed", "automatic_game_started"].includes(type)
                ? `${actor}: `
                : "";
            return create(`${subject}${t(GENERIC_LABELS[type])}`, t("게임 진행"));
        }

        if (type === "log_note") {
            return create(payload.text || t("기록"), t("메모"));
        }
        if (type === "signal") {
            return create(`${actor}: ${payload.label || payload.signal || t("신호")}`, t("선언"));
        }

        return create(
            payload.text || t("게임 규칙에 따른 처리가 완료되었습니다."),
            t("시스템"),
        );
    }

    function prepare(events) {
        let revealedCards = null;
        return (events || []).map((event) => {
            const current = event || {};
            const payload = current.payload || {};
            if (current.type === "battle_revealed") {
                revealedCards = {
                    p1: { ...(payload.p1 || {}) },
                    p2: { ...(payload.p2 || {}) },
                };
            }
            if (
                current.type === "battle_judged"
                && !payload.cards
                && revealedCards
            ) {
                return {
                    ...current,
                    payload: { ...payload, cards: revealedCards },
                };
            }
            return current;
        });
    }

    window.LumenSimulatorLogFormatter = { format, prepare };
}());
