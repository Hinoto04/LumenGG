import { create } from "zustand";
import type { DragPlan } from "./dragMoves";
import type { BoardCard, CardRef, LegalAction, PlayEnvelope, Side, ZoneName } from "./protocol";

export interface InspectTarget {
  card: BoardCard;
  ref: CardRef;
}

interface PlayStore {
  envelope: PlayEnvelope | null;
  inspect: InspectTarget | null;
  openZone: { owner: Side; zone: ZoneName } | null;
  notice: string | null;
  /** 선택 창을 접고 보드를 보는 중 */
  decisionCollapsed: boolean;
  setDecisionCollapsed: (collapsed: boolean) => void;
  /** 효과 선택에서 고른 선택지 id(선택 창과 보드가 함께 쓴다) */
  decisionPicks: string[];
  setDecisionPicks: (ids: string[]) => void;
  /** 펼친 더미 패널(ZoneDock)을 가렸는지 */
  dockHidden: boolean;
  setDockHidden: (hidden: boolean) => void;
  /** 끌고 있는 카드의 계획. active는 출발 영역 밖으로 나가 마스크를 보이는 중 */
  drag: (DragPlan & { active: boolean }) | null;
  setDrag: (drag: (DragPlan & { active: boolean }) | null) => void;
  /** PC: 한 번 누른 카드. 위에 사용 버튼, 왼쪽에 카드 정보가 뜬다. */
  selected: InspectTarget | null;
  setSelected: (target: InspectTarget | null) => void;
  /** PC: 우클릭한 카드. 사용 버튼 없이 왼쪽 정보 패널만 띄운다. */
  peek: InspectTarget | null;
  setPeek: (target: InspectTarget | null) => void;
  /** 수동 모드: HP·FP·패시브 조정 시트를 연 플레이어 */
  playerSheet: Side | null;
  setPlayerSheet: (side: Side | null) => void;
  setEnvelope: (envelope: PlayEnvelope | null) => void;
  setInspect: (target: InspectTarget | null) => void;
  setOpenZone: (zone: { owner: Side; zone: ZoneName } | null) => void;
  flash: (message: string) => void;
}

let noticeTimer: ReturnType<typeof setTimeout> | undefined;

export const usePlay = create<PlayStore>((set) => ({
  envelope: null,
  inspect: null,
  openZone: null,
  notice: null,
  decisionCollapsed: false,
  setDecisionCollapsed: (decisionCollapsed) => set({ decisionCollapsed }),
  decisionPicks: [],
  setDecisionPicks: (decisionPicks) => set({ decisionPicks }),
  dockHidden: false,
  setDockHidden: (dockHidden) => set({ dockHidden }),
  drag: null,
  setDrag: (drag) => set({ drag }),
  selected: null,
  setSelected: (selected) => set({ selected, peek: null }),
  peek: null,
  setPeek: (peek) => set({ peek }),
  playerSheet: null,
  setPlayerSheet: (playerSheet) => set({ playerSheet }),
  setEnvelope: (envelope) => set({ envelope }),
  setInspect: (inspect) => set({ inspect }),
  setOpenZone: (openZone) => set({ openZone }),
  flash: (notice) => {
    clearTimeout(noticeTimer);
    set({ notice });
    noticeTimer = setTimeout(() => set({ notice: null }), 2200);
  },
}));

/** 화면 아래쪽에 올 플레이어. 관전자는 p1 시점으로 본다. */
export function perspective(envelope: PlayEnvelope): { me: Side; opp: Side } {
  const me: Side = envelope.role === "p2" ? "p2" : "p1";
  return { me, opp: me === "p1" ? "p2" : "p1" };
}

export function refKey(ref: Pick<CardRef, "owner" | "zone" | "index">): string {
  return `${ref.owner}:${ref.zone}:${ref.index}`;
}

export interface ActionIndex {
  /** refKey → 그 카드에 묶인 행동들 */
  byCard: Map<string, LegalAction[]>;
  /** 카드 instance id → 그 카드에 묶인 행동들(화면에서 옮겨 둔 카드도 찾을 수 있다) */
  byInstance: Map<string, LegalAction[]>;
  primary: LegalAction[];
  secondary: LegalAction[];
  decision: LegalAction | null;
  system: LegalAction[];
}

export function indexActions(actions: LegalAction[]): ActionIndex {
  const index: ActionIndex = { byCard: new Map(), byInstance: new Map(), primary: [], secondary: [], decision: null, system: [] };
  for (const action of actions) {
    switch (action.ui.kind) {
      case "card":
        for (const ref of action.ui.cards) {
          const key = refKey(ref);
          index.byCard.set(key, [...(index.byCard.get(key) ?? []), action]);
          if (ref.instance_id) {
            const id = String(ref.instance_id);
            index.byInstance.set(id, [...(index.byInstance.get(id) ?? []), action]);
          }
        }
        break;
      case "primary":
        index.primary.push(action);
        break;
      case "decision":
        index.decision = action;
        break;
      case "system":
        index.system.push(action);
        break;
      default:
        index.secondary.push(action);
    }
  }
  return index;
}

/** 좁은 화면(세로 또는 760px 이하)은 정보를 모달로, 넓은 화면은 왼쪽 패널로 보여 준다. */
const COMPACT_INFO_QUERY = "(orientation: portrait), (max-width: 760px)";

/** 카드 우클릭: PC는 왼쪽 정보 패널(사용 버튼 없이), 모바일은 카드 정보 모달 */
export function showCardInfo(target: InspectTarget) {
  if (target.card.hidden) return;
  if (window.matchMedia(COMPACT_INFO_QUERY).matches) usePlay.getState().setInspect(target);
  else usePlay.setState({ peek: target });
}

/**
 * 보드 카드에 묶인 행동. 공개 카드는 instance id로 찾는다: 화면에서만 옮겨 둔 카드(콤보 첫 카드, 효과 선택)
 * 때문에 같은 존의 다른 카드 위치(index)가 서버와 달라질 수 있다.
 */
export function cardActions(index: ActionIndex, ref: Pick<CardRef, "owner" | "zone" | "index">, card?: BoardCard | null): LegalAction[] {
  if (card && !card.hidden && card.instance_id) {
    const found = index.byInstance.get(String(card.instance_id));
    if (found) return found;
    if (index.byInstance.size) return [];
  }
  return index.byCard.get(refKey(ref)) ?? [];
}
