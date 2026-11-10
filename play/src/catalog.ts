import { create } from "zustand";
import type { BoardCard, CardMeta, PlayEnvelope, VisibleCard } from "./protocol";

/**
 * card_id → 카드 메타데이터(이미지, 효과문). 상태 응답에는 이미지가 없으므로
 * 여기서 보충한다. 픽스처 모드는 cards.json, 실제 연결은 card-metadata 엔드포인트.
 */
interface CatalogStore {
  cards: Record<string, CardMeta>;
  merge: (cards: Record<string, CardMeta>) => void;
}

export const useCatalog = create<CatalogStore>((set) => ({
  cards: {},
  merge: (cards) => set((state) => ({ cards: { ...state.cards, ...cards } })),
}));

/** 상태의 카드 값(게임 중 바뀐 수치)이 우선이고, 비어 있는 것만 카탈로그로 채운다. */
export interface CardView extends Partial<CardMeta> {
  name?: string;
}

export function useCardView(card: BoardCard): CardView | null {
  const cardId = card.hidden ? undefined : (card as VisibleCard).card_id;
  const meta = useCatalog((state) => (cardId != null ? state.cards[String(cardId)] : undefined));
  if (card.hidden) return null;
  const view: CardView = { ...(meta ?? {}) };
  for (const [key, value] of Object.entries(card)) {
    if (value !== null && value !== undefined && value !== "") (view as Record<string, unknown>)[key] = value;
  }
  return view;
}

export type ImageSize = "sm" | "md" | "lg";

export function cardImage(view: CardView | null, size: ImageSize): string | null {
  if (!view) return null;
  if (size === "sm") return view.img_sm || view.img || null;
  if (size === "lg") return view.img_lg || view.img || null;
  return view.img || view.img_sm || null;
}

/** 서버가 렌더한 *_label을 우선 쓰고, 없을 때만 [[kind:slug]] → 「slug」로 최소 처리한다. */
function renderText(label: unknown, raw: unknown): string {
  const text = String(label || raw || "");
  return text.replace(/\[\[[a-z_]+:([^\]]+)\]\]/g, "「$1」").replace(/\r\n/g, "\n");
}

export function cardText(view: CardView | null): string {
  return view ? renderText(view.text_label, view.text) : "";
}

export function cardDetailText(view: CardView | null): string {
  return view ? renderText(view.detail_text_label, view.detail_text) : "";
}

// ---------------------------------------------------------------------------
// 실제 연결: 상태에 보이는 card_id 중 아직 없는 것만 card-metadata로 받는다.

const requested = new Set<string>();
let source: string | null = null;

function visibleCardIds(envelope: PlayEnvelope): string[] {
  const ids = new Set<string>();
  for (const player of Object.values(envelope.state.players)) {
    for (const cards of Object.values(player.zones)) {
      for (const card of cards) {
        if (!card.hidden && (card as VisibleCard).card_id != null) ids.add(String((card as VisibleCard).card_id));
      }
    }
  }
  return [...ids];
}

export function syncCatalog(viewToken: string, envelope: PlayEnvelope): void {
  source = viewToken;
  requestCards(visibleCardIds(envelope));
}

/** 이벤트로 처음 드러난 카드처럼 상태 밖에서 알게 된 card_id도 받아 둔다. */
export function requestCards(ids: (string | number | null | undefined)[]): void {
  const viewToken = source;
  if (!viewToken) return;
  const known = useCatalog.getState().cards;
  const missing = [...new Set(ids.filter((id) => id != null).map(String))].filter(
    (id) => !known[id] && !requested.has(id),
  );
  for (let start = 0; start < missing.length; start += 200) {
    const batch = missing.slice(start, start + 200);
    batch.forEach((id) => requested.add(id));
    fetch(`/battlelog/simulator/${encodeURIComponent(viewToken)}/card-metadata/?ids=${batch.join(",")}`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((data: { cards?: Record<string, CardMeta> }) => useCatalog.getState().merge(data.cards ?? {}))
      .catch(() => batch.forEach((id) => requested.delete(id)));
  }
}
