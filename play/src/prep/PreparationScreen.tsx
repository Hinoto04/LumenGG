import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { PlayEnvelope, PrepActive, PrepCatalogCard } from "../protocol";
import { perspective, usePlay } from "../store";
import {
  addCard,
  available,
  checkPreparation,
  isTrait,
  isUltimate,
  placementOf,
  removeCard,
  sendPreparation,
  setPlacement,
  swapCounts,
  totals,
  traitChoices,
  type Placement,
  type ValidationReport,
} from "./model";

const PLACEMENT_LABELS: Record<Placement, string> = { list: "리스트", hand: "손패", side: "사이드" };

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

      <section className="prep-section">
        <h2>덱 · 시작 배치</h2>
        <div className="prep-grid">
          {techniqueRows.map((row) => {
            const card = catalog[row.card_id];
            const single = row.count === 1;
            return (
              <div key={row.card_id} className={`prep-tile ${problemCards.has(row.card_id) ? "is-problem" : ""}`}>
                <Thumb card={card} onPreview={setPreview} />
                <span className="prep-tile-name">
                  {card?.name}
                  {row.count > 1 ? ` ×${row.count}` : ""}
                </span>
                {single ? (
                  <div className="prep-placement" role="radiogroup" aria-label={`${card?.name} 시작 위치`}>
                    {(Object.keys(PLACEMENT_LABELS) as Placement[]).map((place) => (
                      <button
                        key={place}
                        type="button"
                        role="radio"
                        aria-checked={placementOf(row) === place}
                        className={placementOf(row) === place ? "is-active" : ""}
                        disabled={ready}
                        onClick={() =>
                          edit(setPlacement(draft, row.card_id, place === "hand" ? 1 : 0, place === "side" ? 1 : 0))
                        }
                      >
                        {PLACEMENT_LABELS[place]}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="prep-steppers">
                    {(["hand", "side"] as const).map((key) => (
                      <label key={key}>
                        {PLACEMENT_LABELS[key]}
                        <input
                          type="number"
                          min={0}
                          max={row.count}
                          value={row[key] ?? 0}
                          disabled={ready}
                          onChange={(event) =>
                            edit(
                              setPlacement(
                                draft,
                                row.card_id,
                                key === "hand" ? Number(event.target.value) : row.hand ?? 0,
                                key === "side" ? Number(event.target.value) : row.side ?? 0,
                              ),
                            )
                          }
                        />
                      </label>
                    ))}
                  </div>
                )}
                {spare.length > 0 && (
                  <button type="button" className="prep-remove" disabled={ready} onClick={() => edit(removeCard(draft, row.card_id))}>
                    빼기
                  </button>
                )}
              </div>
            );
          })}
          {ultimateRows.map((row) => (
            <div key={row.card_id} className="prep-tile is-ultimate">
              <Thumb card={catalog[row.card_id]} onPreview={setPreview} />
              <span className="prep-tile-name">얼티밋 · {catalog[row.card_id]?.name}</span>
              {spare.some(([id]) => isUltimate(catalog[id])) && (
                <button type="button" className="prep-remove" disabled={ready} onClick={() => edit(removeCard(draft, row.card_id))}>
                  빼기
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {spare.length > 0 && (
        <section className="prep-section">
          <h2>교체 덱</h2>
          <div className="prep-grid">
            {spare.map(([id, left]) => (
              <div key={id} className="prep-tile is-spare">
                <Thumb card={catalog[id]} onPreview={setPreview} />
                <span className="prep-tile-name">
                  {isUltimate(catalog[id]) ? "얼티밋 · " : ""}
                  {catalog[id]?.name}
                  {left > 1 ? ` ×${left}` : ""}
                </span>
                <button type="button" className="prep-add" disabled={ready} onClick={() => edit(addCard(draft, id))}>
                  넣기
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

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
    </main>
  );
}

