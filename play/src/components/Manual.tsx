import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { PHASE_LABELS, PHASE_ORDER, ZONE_LABELS } from "../labels";
import { currentTarget, sendManual } from "../net/live";
import type { BoardCard, PlayEnvelope, PlayerState, Side, VisibleCard, ZoneName } from "../protocol";
import { useCardView } from "../catalog";
import { perspective, usePlay } from "../store";
import { CharacterPassive, characterPanel } from "./CharacterPassive";

/**
 * 수동 모드(샌드박스) 조작. 규칙 판정 없이 서버가 행동을 그대로 적용한다.
 * 서버 행동 이름은 battlelog/simulator_services.py의 _apply_event를 따른다.
 */

/** 공개 존: 들어가면 공개되고 비공개로 돌릴 수 없다(PUBLIC_ON_ENTER_ZONES) */
const PUBLIC_ZONES = new Set<ZoneName>(["character", "passive", "list", "break", "ultimate"]);
const MOVE_ZONES: ZoneName[] = ["battle", "hand", "list", "side", "lumen", "break", "ultimate"];
/** 상대에게 보낼 수 있는 존(CROSS_PLAYER_ZONES) */
const CROSS_ZONES: ZoneName[] = ["battle", "lumen"];
const SIGNALS = [
  ["effect", "효과 발동"],
  ["combo", "콤보 타임"],
  ["catch", "캐치 타임"],
] as const;
const QUICK_LOGS = ["히트", "카운터", "방어", "회피", "상쇄", "대응 없음"];

const other = (side: Side): Side => (side === "p1" ? "p2" : "p1");

export function canControl(envelope: PlayEnvelope): boolean {
  return !!envelope.can_control && envelope.role !== "viewer";
}

// ---------------------------------------------------------------------------
// 카드: 확대 보기 안의 이동·공개 버튼

export function ManualCardActions({
  envelope,
  card,
  zone,
  onDone,
}: {
  envelope: PlayEnvelope;
  card: BoardCard;
  zone: ZoneName;
  onDone: () => void;
}) {
  const { me } = perspective(envelope);
  if (!canControl(envelope) || card.hidden) return null;
  const visible = card as VisibleCard;
  const owner = (visible.owner ?? me) as Side;
  if (owner !== me || visible.kind === "character" || zone === "passive" || zone === "character") return null;
  const move = (toZone: ZoneName, toPlayer: Side = owner) => {
    sendManual("move_card", { card_instance_id: visible.instance_id, to_zone: toZone, to_player: toPlayer });
    onDone();
  };
  return (
    <div className="manual-card-actions">
      <SpecialCardActions envelope={envelope} card={visible} zone={zone} onDone={onDone} />
      <span className="muted">이동</span>
      <div className="menu-buttons">
        {MOVE_ZONES.filter((target) => target !== zone).map((target) => (
          <button key={target} type="button" className="btn-secondary" onClick={() => move(target)}>
            {ZONE_LABELS[target]}
          </button>
        ))}
        {CROSS_ZONES.map((target) => (
          <button key={`opp-${target}`} type="button" className="btn-secondary" onClick={() => move(target, other(owner))}>
            상대 {ZONE_LABELS[target]}
          </button>
        ))}
      </div>
      {!PUBLIC_ZONES.has(zone) && (
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            sendManual("set_visibility", { card_instance_id: visible.instance_id, face_up: !visible.face_up });
            onDone();
          }}
        >
          {visible.face_up ? "비공개로" : "공개하기"}
        </button>
      )}
    </div>
  );
}

/**
 * 캐릭터·카드 전용 조작(예전 시뮬레이터의 카드 효과 버튼과 CMYK 세트 끌어 놓기).
 * - 블랙아웃(공개 상태): 상대 리스트에서 무작위 1장을 손패로 (blackout_random_get)
 * - CMYK, 레디 페이즈: 배틀존의 다른 기술에 세트 (attach_card)
 * 조건은 서버가 다시 확인한다.
 */
function SpecialCardActions({
  envelope,
  card,
  zone,
  onDone,
}: {
  envelope: PlayEnvelope;
  card: VisibleCard;
  zone: ZoneName;
  onDone: () => void;
}) {
  const view = useCardView(card);
  const { me } = perspective(envelope);
  const name = String(view?.name ?? card.name ?? "");
  const blackout = card.face_up && name.includes("블랙아웃");
  const isCmyk = String(envelope.state.players[me].character?.name ?? "") === "CMYK";
  const hosts =
    isCmyk && envelope.state.phase === "ready" && zone === "battle" && !card.attached_to
      ? (envelope.state.players[me].zones.battle.filter(
          (other) => !other.hidden && other.instance_id !== card.instance_id && !other.attached_to,
        ) as VisibleCard[])
      : [];
  if (!blackout && !hosts.length) return null;
  return (
    <div className="menu-buttons">
      {blackout && (
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            sendManual("blackout_random_get", { source_card_instance_id: card.instance_id });
            onDone();
          }}
        >
          암전 · 상대 리스트 무작위 1장
        </button>
      )}
      {hosts.map((host) => (
        <HostButton
          key={host.instance_id}
          host={host}
          onPress={() => {
            sendManual("attach_card", { card_instance_id: card.instance_id, host_card_instance_id: host.instance_id });
            onDone();
          }}
        />
      ))}
    </div>
  );
}

function HostButton({ host, onPress }: { host: VisibleCard; onPress: () => void }) {
  const view = useCardView(host);
  return (
    <button type="button" className="btn-primary" onClick={onPress}>
      세트 → {String(view?.name ?? host.name ?? "기술")}
    </button>
  );
}

// ---------------------------------------------------------------------------
// 보드 아래 오른쪽: 차례 표시와 자주 쓰는 버튼, 나머지는 도구 시트

function useTimerSeconds(timer: Record<string, unknown> | undefined): number | null {
  const startedAt = timer?.started_at ? Date.parse(String(timer.started_at)) : NaN;
  const duration = Number(timer?.duration_seconds ?? 10);
  const running = Number.isFinite(startedAt);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [running]);
  if (!running) return null;
  return Math.max(0, Math.ceil((startedAt + duration * 1000 - now) / 1000));
}

export function manualStatusText(envelope: PlayEnvelope): string {
  const status = (envelope.state.status ?? {}) as Record<Side, { requested?: boolean; done?: boolean }>;
  const { me, opp } = perspective(envelope);
  if (envelope.role === "viewer") return "관전 중 · 수동 대전";
  if (status[me]?.requested) return "내 차례입니다";
  if (status[opp]?.requested) return "상대 차례입니다";
  if (status[me]?.done && status[opp]?.done) return "양쪽 모두 완료";
  return "수동 대전";
}

export function ManualDock({ envelope }: { envelope: PlayEnvelope }) {
  const [toolsOpen, setToolsOpen] = useState(false);
  const { me } = perspective(envelope);
  const status = (envelope.state.status ?? {}) as Record<Side, { requested?: boolean; done?: boolean }>;
  const timer = envelope.state.timer as Record<string, unknown> | undefined;
  const seconds = useTimerSeconds(timer);
  if (!canControl(envelope)) return null;
  const done = !!status[me]?.done;
  return (
    <>
      <div className="action-dock manual-dock">
        <button type="button" className={`btn-secondary manual-timer ${seconds != null ? "is-running" : ""}`} onClick={() => sendManual("timer")}>
          {seconds != null ? `${seconds}초` : "10초"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setToolsOpen(true)}>
          도구
        </button>
        <button
          type="button"
          className={`btn-primary ${done ? "is-quiet" : ""}`}
          onClick={() => sendManual("set_done", { target: me, done: !done })}
        >
          {done ? "완료 취소" : "완료"}
        </button>
      </div>
      <ManualTools envelope={envelope} open={toolsOpen} onClose={() => setToolsOpen(false)} />
    </>
  );
}

function ManualTools({ envelope, open, onClose }: { envelope: PlayEnvelope; open: boolean; onClose: () => void }) {
  const { me, opp } = perspective(envelope);
  const [note, setNote] = useState("");
  const [cardName, setCardName] = useState("");
  const player = envelope.state.players[me];
  const handOpen = player.zones.hand.some((card) => !card.hidden && card.face_up);
  const run = (action: string, payload: Record<string, unknown> = {}, close = true) => {
    sendManual(action, payload);
    if (close) onClose();
  };
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="zone-sheet game-menu"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2>수동 대전 도구</h2>
              <button type="button" className="btn-ghost" onClick={onClose}>
                닫기
              </button>
            </header>
            <section>
              <div className="menu-row">
                <span>페이즈 · 턴 {envelope.state.turn}</span>
                <div className="menu-buttons">
                  {PHASE_ORDER.map((phase) => (
                    <button
                      key={phase}
                      type="button"
                      className={`btn-secondary ${envelope.state.phase === phase ? "is-current" : ""}`}
                      onClick={() => run("set_phase", { phase })}
                    >
                      {PHASE_LABELS[phase]}
                    </button>
                  ))}
                  <button type="button" className="btn-secondary" onClick={() => run("phase_advance")}>
                    다음 페이즈
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => run("next_turn")}>
                    다음 턴
                  </button>
                </div>
              </div>
              <div className="menu-row">
                <span>차례</span>
                <div className="menu-buttons">
                  <button type="button" className="btn-secondary" onClick={() => run("request_action", { target: opp })}>
                    상대에게 차례 넘기기
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => run("request_action", { target: me })}>
                    내 차례로
                  </button>
                </div>
              </div>
            </section>
            <section>
              <div className="menu-row">
                <span>배틀존 · 손패</span>
                <div className="menu-buttons">
                  <button type="button" className="btn-secondary" onClick={() => run("bulk_move", { player: me, from_zone: "battle", to_zone: "list" })}>
                    배틀존 → 리스트
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => run("bulk_move", { player: me, from_zone: "battle", to_zone: "hand" })}>
                    배틀존 → 손패
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => run("shuffle_hand", { player: me })}>
                    손패 섞기
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => run("set_hand_visibility", { target: me, face_up: !handOpen })}>
                    손패 {handOpen ? "비공개" : "공개"}
                  </button>
                </div>
              </div>
              <div className="menu-row">
                <span>신호</span>
                <div className="menu-buttons">
                  {SIGNALS.map(([signal, label]) => (
                    <button key={signal} type="button" className="btn-secondary" onClick={() => run("signal", { signal })}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </section>
            <section>
              <div className="menu-row">
                <span>기록</span>
                <div className="menu-buttons">
                  {QUICK_LOGS.map((text) => (
                    <button key={text} type="button" className="btn-secondary" onClick={() => run("log_note", { text })}>
                      {text}
                    </button>
                  ))}
                </div>
                <form
                  className="menu-inline-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!note.trim()) return;
                    run("log_note", { text: note.trim() }, false);
                    setNote("");
                  }}
                >
                  <input value={note} maxLength={300} placeholder="기록할 내용" onChange={(event) => setNote(event.target.value)} />
                  <button type="submit" className="btn-secondary" disabled={!note.trim()}>
                    기록
                  </button>
                </form>
              </div>
              <div className="menu-row">
                <span>카드 생성(루멘 존)</span>
                <form
                  className="menu-inline-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!cardName.trim()) return;
                    run("import_card", { card_name: cardName.trim() }, false);
                    setCardName("");
                  }}
                >
                  <input value={cardName} maxLength={100} placeholder="카드 이름" onChange={(event) => setCardName(event.target.value)} />
                  <button type="submit" className="btn-secondary" disabled={!cardName.trim()}>
                    생성
                  </button>
                </form>
              </div>
            </section>
            <section>
              <button type="button" className="btn-danger" onClick={() => run("undo")}>
                마지막 행동 되돌리기
              </button>
            </section>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// 플레이어: HP·FP 조정과 패시브

interface PassiveControl {
  type: string;
  key: string;
  label?: string;
  description?: string;
  default?: unknown;
  initial?: unknown;
  max?: number | null;
  unit?: string;
  choices?: { value: unknown; label?: string }[];
}

function passiveValue(player: PlayerState, key: string, fallback: unknown): unknown {
  const entry = player.passive_state?.[key];
  if (entry?.value !== undefined) return entry.value;
  if (entry?.count !== undefined) return entry.count;
  return fallback;
}

const isOn = (value: unknown) => value === true || value === "true" || value === "on" || value === "ON";

/** 캐릭터 설정의 패시브 컨트롤(토글·카운터·선택). 상태류는 값만 보여 준다. */
function PassiveControls({ side, player, enabled, mine }: { side: Side; player: PlayerState; enabled: boolean; mine: boolean }) {
  const panel = characterPanel(player);
  if (panel) return <CharacterPassive panel={panel} side={side} player={player} enabled={enabled} mine={mine} />;
  const ui = (player.character?.passive_ui ?? {}) as { options?: { title?: string; controls?: PassiveControl[] }; html?: string; js?: string };
  const controls = ui.options?.controls ?? [];
  const set = (control: PassiveControl, value: unknown) =>
    sendManual("passive", { target: side, key: control.key, value, label: control.label ?? control.key });
  if (!controls.length) {
    if (ui.html || ui.js) {
      const target = currentTarget();
      const legacy = target?.seat ? `/battlelog/simulator/${target.view}/${target.seat}/${target.token}/?legacy=1` : null;
      return (
        <p className="muted">
          이 캐릭터의 전용 패시브는 예전 화면에서 조작합니다.{" "}
          {legacy && <a href={legacy}>예전 화면 열기</a>}
        </p>
      );
    }
    return null;
  }
  return (
    <div className="passive-controls">
      {ui.options?.title && <strong>{ui.options.title}</strong>}
      {controls.map((control) => {
        const value = passiveValue(player, control.key, control.default ?? control.initial ?? (control.type === "counter" ? 0 : false));
        if (control.type === "toggle") {
          return (
            <div key={control.key} className="passive-row">
              <span>{control.label ?? control.key}</span>
              <button type="button" className={`btn-secondary ${isOn(value) ? "is-current" : ""}`} disabled={!enabled} onClick={() => set(control, !isOn(value))}>
                {isOn(value) ? "켜짐" : "꺼짐"}
              </button>
            </div>
          );
        }
        if (control.type === "counter") {
          const number = Math.max(0, Number(value) || 0);
          const max = control.max == null ? null : Number(control.max);
          return (
            <div key={control.key} className="passive-row">
              <span>{control.label ?? control.key}</span>
              <div className="menu-buttons">
                <button type="button" className="btn-secondary" disabled={!enabled || number <= 0} onClick={() => set(control, number - 1)}>
                  −
                </button>
                <b className="passive-value">
                  {number}
                  {max != null ? `/${max}` : ""}
                  {control.unit ?? ""}
                </b>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={!enabled || (max != null && number >= max)}
                  onClick={() => set(control, max == null ? number + 1 : Math.min(max, number + 1))}
                >
                  +
                </button>
              </div>
            </div>
          );
        }
        if (control.type === "choice") {
          return (
            <div key={control.key} className="passive-row">
              <span>{control.label ?? control.key}</span>
              <div className="menu-buttons">
                {(control.choices ?? []).map((choice) => (
                  <button
                    key={String(choice.value)}
                    type="button"
                    className={`btn-secondary ${String(value) === String(choice.value) ? "is-current" : ""}`}
                    disabled={!enabled}
                    onClick={() => set(control, choice.value)}
                  >
                    {choice.label ?? String(choice.value)}
                  </button>
                ))}
              </div>
            </div>
          );
        }
        return (
          <div key={control.key} className="passive-row">
            <span>{control.label ?? control.key}</span>
            <b className="passive-value">{typeof value === "boolean" ? (value ? "켜짐" : "꺼짐") : String(value ?? "-")}</b>
          </div>
        );
      })}
    </div>
  );
}

const HP_STEPS = [-500, -100, 100, 500];

export function PlayerSheet({ envelope }: { envelope: PlayEnvelope }) {
  const side = usePlay((s) => s.playerSheet);
  const close = () => usePlay.getState().setPlayerSheet(null);
  const [custom, setCustom] = useState("");
  const { me } = perspective(envelope);
  const player = side ? envelope.state.players[side] : null;
  const enabled = canControl(envelope);
  return (
    <AnimatePresence>
      {side && player && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close}>
          <motion.div
            className="zone-sheet game-menu"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2>
                {side === me ? "나" : "상대"} · {String(player.character?.name ?? player.name)}
              </h2>
              <button type="button" className="btn-ghost" onClick={close}>
                닫기
              </button>
            </header>
            <section>
              <div className="menu-row">
                <span>HP {player.hp}</span>
                <div className="menu-buttons">
                  {HP_STEPS.map((amount) => (
                    <button key={amount} type="button" className="btn-secondary" disabled={!enabled} onClick={() => sendManual("hp", { target: side, amount })}>
                      {amount > 0 ? `+${amount}` : amount}
                    </button>
                  ))}
                </div>
                <form
                  className="menu-inline-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const amount = Math.trunc(Number(custom));
                    if (!amount) return;
                    sendManual("hp", { target: side, amount });
                    setCustom("");
                  }}
                >
                  <input inputMode="numeric" value={custom} placeholder="예: -300, 200" onChange={(event) => setCustom(event.target.value)} disabled={!enabled} />
                  <button type="submit" className="btn-secondary" disabled={!enabled || !Math.trunc(Number(custom))}>
                    적용
                  </button>
                </form>
              </div>
              <div className="menu-row">
                <span>FP {player.fp}</span>
                <div className="menu-buttons">
                  <button type="button" className="btn-secondary" disabled={!enabled} onClick={() => sendManual("fp", { target: side, amount: -1 })}>
                    −1
                  </button>
                  <button type="button" className="btn-secondary" disabled={!enabled} onClick={() => sendManual("fp", { target: side, amount: 1 })}>
                    +1
                  </button>
                  <button type="button" className="btn-secondary" disabled={!enabled || !player.fp} onClick={() => sendManual("fp_reset", { target: side })}>
                    초기화
                  </button>
                </div>
              </div>
            </section>
            <section>
              <PassiveControls side={side} player={player} enabled={enabled} mine={side === me} />
            </section>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
