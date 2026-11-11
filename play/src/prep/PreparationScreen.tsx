import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { PlayEnvelope, PrepActive, PrepCatalogCard } from "../protocol";
import { perspective, usePlay } from "../store";
import {
  available,
  canMove,
  checkPreparation,
  isTrait,
  isUltimate,
  moveCopy,
  sendPreparation,
  swapCounts,
  totals,
  traitChoices,
  type PrepZone,
  type ValidationReport,
} from "./model";

const ZONE_LABELS: Record<PrepZone, string> = {
  list: "리스트",
  hand: "손패",
  side: "사이드",
  ultimate: "얼티밋",
  reserve: "교체 덱",
};

/** 화면 좌표 아래의 영역 */
function zoneAt(x: number, y: number): PrepZone | null {
  const element = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-prep-zone]");
  return (element?.dataset.prepZone as PrepZone | undefined) ?? null;
}

interface DragState {
  cardId: number;
  from: PrepZone;
  x: number;
  y: number;
  over: PrepZone | null;
}

/** 영역 안의 카드 한 장. 끌어서 다른 영역으로 옮기고, 누르면 크게 본다. */
function CopyTile({
  card,
  zone,
  problem,
  dragging,
  onPointerDown,
  onPreview,
}: {
  card: PrepCatalogCard;
  zone: PrepZone;
  problem: boolean;
  dragging: boolean;
  onPointerDown: (event: React.PointerEvent) => void;
  onPreview: () => void;
}) {
  const image = card.img_mid || card.img_sm || card.img;
  return (
    <div
      className={`prep-copy is-${zone} ${problem ? "is-problem" : ""} ${dragging ? "is-dragging" : ""}`}
      onPointerDown={onPointerDown}
      onContextMenu={(event) => {
        event.preventDefault();
        onPreview();
      }}
      role="button"
      tabIndex={0}
      aria-label={`${card.name} (${ZONE_LABELS[zone]})`}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onPreview();
      }}
    >
      {image ? <img src={String(image)} alt="" draggable={false} loading="lazy" /> : <span>{card.name}</span>}
    </div>
  );
}

function cardText(card: PrepCatalogCard): string {
  return String(card.text ?? "").replace(/\[\[[a-z_]+:([^\]]+)\]\]/g, "「$1」");
}

function Thumb({ card, onPreview }: { card: PrepCatalogCard; onPreview: (card: PrepCatalogCard) => void }) {
  const image = card.img_sm || card.img_mid || card.img;
  return (
    <button type="button" className="prep-thumb" onClick={() => onPreview(card)} aria-label={`${card.name} 크게 보기`}>
      {image ? <img src={image} alt="" draggable={false} loading="lazy" /> : <span>{card.name.slice(0, 2)}</span>}
    </button>
  );
}

function Preview({ card, onClose }: { card: PrepCatalogCard | null; onClose: () => void }) {
  return (
    <AnimatePresence>
      {card && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div className="inspector" initial={{ scale: 0.92 }} animate={{ scale: 1 }} exit={{ scale: 0.92 }}>
            {(card.img || card.img_mid) && <img className="prep-preview-image" src={String(card.img || card.img_mid)} alt="" />}
            <div className="inspector-body">
              <h2>{card.name}</h2>
              <span className="inspector-code">{card.code}</span>
              <p className="inspector-meta">
                {[card.type, card.frame != null ? `속도 ${card.frame}` : null, card.damage != null ? `데미지 ${card.damage}` : null, card.pos]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {card.text && <p className="inspector-text">{cardText(card)}</p>}
              <button type="button" className="btn-ghost" onClick={onClose}>
                닫기
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function limitText(count: number, limit: number | undefined): string {
  return limit == null ? `${count}` : `${count}/${limit}`;
}

/**
 * 대전 전 덱 준비. 등록한 덱과 교체 덱 안에서 레귤레이션 한도만큼 바꾸고,
 * 손패·사이드 시작 배치를 정한 뒤 '준비 완료'를 누른다. 판정은 서버가 한다.
 */
export function PreparationScreen({ envelope }: { envelope: PlayEnvelope }) {
  const preparation = envelope.preparation!;
  const { me, opp } = perspective(envelope);
  const mine = envelope.role === "viewer" ? null : preparation.players[me];
  const rival = preparation.players[opp];
  const flash = usePlay((s) => s.flash);
  const registered = mine?.registered;
  const [draft, setDraft] = useState<PrepActive | null>(mine?.active ?? null);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [sending, setSending] = useState(false);
  const [preview, setPreview] = useState<PrepCatalogCard | null>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const checkSeq = useRef(0);

  // 서버의 준비 버전이 바뀌면(저장·준비·게임 번호) 서버 구성으로 다시 맞춘다.
  useEffect(() => {
    setDraft(mine?.active ?? null);
  }, [preparation.version, preparation.game_number]); // eslint-disable-line react-hooks/exhaustive-deps

  // 고칠 때마다 서버에 검사만 맡긴다(저장하지 않음).
  useEffect(() => {
    if (!draft || !registered || mine?.ready) return;
    const seq = ++checkSeq.current;
    const timer = setTimeout(() => {
      checkPreparation(draft)
        .then((result) => {
          if (seq === checkSeq.current) setReport(result);
        })
        .catch(() => undefined);
    }, 250);
    return () => clearTimeout(timer);
  }, [draft, registered, mine?.ready]);

  const derived = useMemo(() => {
    if (!registered || !draft) return null;
    return {
      swaps: swapCounts(registered, draft),
      spare: available(registered, draft),
      traits: traitChoices(registered),
      sum: totals(draft, registered),
    };
  }, [registered, draft]);

  const send = async (action: "ready" | "cancel") => {
    if (!draft) return;
    setSending(true);
    try {
      await sendPreparation(envelope, action, action === "ready" ? draft : undefined);
    } catch (error) {
      flash((error as Error).message);
    } finally {
      setSending(false);
    }
  };

  if (!mine || !registered || !draft || !derived) {
    return (
      <main className="prep">
        <header className="prep-head">
          <h1>게임 {preparation.game_number} 준비</h1>
          <p className="muted">
            P1 {preparation.players.p1.ready ? "준비 완료" : "준비 중"} · P2 {preparation.players.p2.ready ? "준비 완료" : "준비 중"}
          </p>
        </header>
      </main>
    );
  }

  const rules = registered.regulation_rules;
  const ready = mine.ready;
  const catalog = registered.catalog;
  const rows = [...draft.cards].sort((a, b) => String(catalog[a.card_id]?.code).localeCompare(String(catalog[b.card_id]?.code)));
  const techniqueRows = rows.filter((row) => !isUltimate(catalog[row.card_id]));
  const ultimateRows = rows.filter((row) => isUltimate(catalog[row.card_id]));
  const spare = [...derived.spare].filter(([id]) => !isTrait(catalog[id]));
  const errors = report?.issues.filter((issue) => issue.severity === "error") ?? [];
  const problemCards = new Set(errors.flatMap((issue) => issue.card_ids));
  const over = (count: number, limit?: number) => limit != null && count > limit;

  const edit = (next: PrepActive) => {
    if (!ready) setDraft(next);
  };

  const startDrag = (event: React.PointerEvent, cardId: number, from: PrepZone) => {
    if (event.button !== 0) return;
    const card = catalog[cardId];
    const sx = event.clientX;
    const sy = event.clientY;
    const touch = event.pointerType !== "mouse";
    let armed = !touch;
    let active = false;
    let cancelled = false;
    const hold = touch
      ? setTimeout(() => {
          armed = true;
          if (!ready) {
            active = true;
            setDrag({ cardId, from, x: sx, y: sy, over: from });
          }
        }, 220)
      : undefined;
    const block = (e: TouchEvent) => {
      if (active) e.preventDefault();
    };
    // 끄는 중 화면 위·아래 끝에 가면 저절로 스크롤한다(휴대폰에서 아래 영역으로 옮길 때).
    const scroller = (event.currentTarget as HTMLElement).closest<HTMLElement>(".prep");
    let lastY = sy;
    let lastX = sx;
    let frame = 0;
    const tick = () => {
      if (active && scroller) {
        const edge = 70;
        const step = lastY < edge ? -14 : lastY > window.innerHeight - edge ? 14 : 0;
        if (step) {
          scroller.scrollTop += step;
          setDrag({ cardId, from, x: lastX, y: lastY, over: zoneAt(lastX, lastY) });
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    const finish = () => {
      cancelAnimationFrame(frame);
      clearTimeout(hold);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
      window.removeEventListener("touchmove", block);
      setDrag(null);
    };
    const move = (e: PointerEvent) => {
      const far = Math.hypot(e.clientX - sx, e.clientY - sy) > 6;
      lastX = e.clientX;
      lastY = e.clientY;
      if (!armed) {
        // 길게 누르기 전에 움직였다: 스크롤로 본다.
        if (far) {
          cancelled = true;
          finish();
        }
        return;
      }
      if (!active && far && !ready) active = true;
      if (active) setDrag({ cardId, from, x: e.clientX, y: e.clientY, over: zoneAt(e.clientX, e.clientY) });
    };
    const up = (e: PointerEvent) => {
      finish();
      if (cancelled) return;
      if (!active) {
        setPreview(card);
        return;
      }
      const to = zoneAt(e.clientX, e.clientY);
      if (to && canMove(card, from, to)) setDraft((current) => (current ? moveCopy(current, cardId, from, to) : current));
    };
    const cancel = () => {
      cancelled = true;
      finish();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
    window.addEventListener("touchmove", block, { passive: false });
  };

  const dragCard = drag ? catalog[drag.cardId] : undefined;
  const zoneClass = (zone: PrepZone) => {
    if (!drag || !dragCard) return "";
    if (!canMove(dragCard, drag.from, zone)) return drag.from === zone ? "is-from" : "is-blocked";
    return drag.over === zone ? "is-over" : "is-target";
  };
  const copies = (zone: PrepZone, ids: number[]) =>
    ids.map((cardId, index) => (
      <CopyTile
        key={`${zone}-${cardId}-${index}`}
        card={catalog[cardId]}
        zone={zone}
        problem={problemCards.has(cardId)}
        dragging={!!drag && drag.cardId === cardId && drag.from === zone && index === ids.indexOf(cardId)}
        onPointerDown={(event) => startDrag(event, cardId, zone)}
        onPreview={() => setPreview(catalog[cardId])}
      />
    ));
  const repeat = (rows: { card_id: number; n: number }[]) => rows.flatMap((row) => Array<number>(Math.max(0, row.n)).fill(row.card_id));
  const listIds = repeat(techniqueRows.map((row) => ({ card_id: row.card_id, n: row.count - (row.hand ?? 0) - (row.side ?? 0) })));
  const handIds = repeat(techniqueRows.map((row) => ({ card_id: row.card_id, n: row.hand ?? 0 })));
  const sideIds = repeat(techniqueRows.map((row) => ({ card_id: row.card_id, n: row.side ?? 0 })));
  const ultimateIds = repeat(ultimateRows.map((row) => ({ card_id: row.card_id, n: row.count })));
  const reserveIds = repeat(spare.map(([id, left]) => ({ card_id: id, n: left })));
  const hasReserve = registered.reserve_cards.length > 0;
  const zone = (id: PrepZone, ids: number[], extra = "") => (
    <section className={`prep-zone prep-zone-${id} ${zoneClass(id)} ${extra}`} data-prep-zone={id}>
      <header className="prep-zone-head">
        <h2>{ZONE_LABELS[id]}</h2>
        <span>{ids.length}장</span>
      </header>
      <div className={`prep-zone-cards is-${id}`}>
        {copies(id, ids)}
        {!ids.length && <p className="prep-zone-empty">{ready ? "없음" : "여기로 끌어 놓기"}</p>}
      </div>
    </section>
  );

  return (
    <main className="prep">
      <header className="prep-head">
        <div>
          <h1>게임 {preparation.game_number} 준비</h1>
          <p className="muted">
            {registered.character?.name} · {registered.name}
          </p>
        </div>
        <div className="prep-status">
          <span className={`btn-chip is-static ${ready ? "is-online" : ""}`}>나 {ready ? "준비 완료" : "준비 중"}</span>
          <span className={`btn-chip is-static ${rival.ready ? "is-online" : ""}`}>
            상대 {envelope.controllers?.[opp] === "ai" ? "AI" : rival.ready ? "준비 완료" : "준비 중"}
          </span>
        </div>
      </header>

      <section className="prep-summary">
        <span className={over(derived.swaps.technique, rules?.technique_swap_limit) ? "is-over" : ""}>
          기술 교체 {limitText(derived.swaps.technique, rules?.technique_swap_limit)}
        </span>
        <span className={over(derived.swaps.trait, rules?.trait_swap_limit) ? "is-over" : ""}>
          특성 교체 {limitText(derived.swaps.trait, rules?.trait_swap_limit)}
        </span>
        <span className={over(derived.swaps.ultimate, rules?.ultimate_swap_limit) ? "is-over" : ""}>
          얼티밋 교체 {limitText(derived.swaps.ultimate, rules?.ultimate_swap_limit)}
        </span>
        <span>
          덱 {derived.sum.deck}장 · 손패 {derived.sum.hand} · 사이드 {derived.sum.side}
        </span>
        {!rules && <span className="muted">레귤레이션 없음</span>}
      </section>

      {derived.traits.length > 1 && (
        <section className="prep-section">
          <h2>특성</h2>
          <div className="prep-grid">
            {derived.traits.map((id) => (
              <div key={id} className={`prep-tile ${draft.trait_card_id === id ? "is-chosen" : ""}`}>
                <Thumb card={catalog[id]} onPreview={setPreview} />
                <button
                  type="button"
                  className="prep-tile-name"
                  disabled={ready}
                  onClick={() => edit({ ...draft, trait_card_id: id })}
                >
                  {draft.trait_card_id === id ? "사용 중" : "이 특성 사용"}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <p className="prep-help muted">
        카드를 끌어서 리스트·손패·사이드로 옮기세요{hasReserve ? ". 교체 덱과도 주고받을 수 있습니다" : ""}. 누르면 크게 봅니다.
      </p>
      <div className={`prep-board ${hasReserve ? "has-reserve" : ""} ${ultimateIds.length || spare.some(([id]) => isUltimate(catalog[id])) ? "has-ultimate" : ""}`}>
        {zone("list", listIds)}
        {zone("hand", handIds)}
        {zone("side", sideIds)}
        {(ultimateIds.length > 0 || spare.some(([id]) => isUltimate(catalog[id]))) && zone("ultimate", ultimateIds)}
        {hasReserve && zone("reserve", reserveIds)}
      </div>

      <footer className="prep-footer">
        <ul className="prep-issues" aria-live="polite">
          {errors.map((issue, index) => (
            <li key={`${issue.code}-${index}`}>{issue.message}</li>
          ))}
          {!errors.length && report && !ready && <li className="is-ok">시작할 수 있는 구성입니다.</li>}
        </ul>
        <div className="prep-actions">
          {ready ? (
            <>
              <span className="muted">{rival.ready ? "곧 시작합니다" : "상대의 준비를 기다리는 중"}</span>
              <button type="button" className="btn-ghost" disabled={sending} onClick={() => send("cancel")}>
                준비 철회
              </button>
            </>
          ) : (
            <>
              <button type="button" className="btn-ghost" disabled={sending} onClick={() => setDraft(mine.active ?? null)}>
                되돌리기
              </button>
              <button type="button" className="btn-primary" disabled={sending || errors.length > 0} onClick={() => send("ready")}>
                {sending ? "보내는 중…" : "준비 완료"}
              </button>
            </>
          )}
        </div>
      </footer>
      <Preview card={preview} onClose={() => setPreview(null)} />
      {drag && dragCard && (
        <div className="prep-drag-ghost" style={{ left: drag.x, top: drag.y }} aria-hidden>
          {(dragCard.img_mid || dragCard.img_sm || dragCard.img) && <img src={String(dragCard.img_mid || dragCard.img_sm || dragCard.img)} alt="" />}
        </div>
      )}
    </main>
  );
}

