/**
 * 루멘 시뮬레이터 게임 클라이언트 프로토콜 v1.
 *
 * 서버 쪽 기준: LumenGG/battlelog/play_protocol.py (validate_play_envelope)
 * 설명 문서:   docs/PLAY_PROTOCOL.md
 *
 * 필드를 바꿀 때는 세 곳(이 파일, play_protocol.py, 문서)을 함께 고친다.
 * 서버는 필드 추가만 하므로, 여기 없는 필드는 무시해도 된다.
 */

export const PLAY_PROTOCOL_VERSION = 1;

export type Side = "p1" | "p2";
export type Role = Side | "viewer";

export type ZoneName =
  | "character"
  | "passive"
  | "battle"
  | "list"
  | "hand"
  | "side"
  | "break"
  | "lumen"
  | "ultimate";

export const ZONE_NAMES: readonly ZoneName[] = [
  "character",
  "passive",
  "battle",
  "list",
  "hand",
  "side",
  "break",
  "lumen",
  "ultimate",
];

export type Phase = "lumen" | "ready" | "battle" | "get" | "recovery" | (string & {});

// ---------------------------------------------------------------------------
// 보드 상태

/** 보이는 카드. 카드 상세(효과 텍스트 등)는 card_id로 카탈로그에서 찾는다. */
export interface VisibleCard {
  hidden: false;
  instance_id: string;
  kind: "card" | "character" | "token" | (string & {});
  owner: Side;
  zone: ZoneName;
  face_up: boolean;
  card_id?: number | null;
  code?: string | null;
  name?: string;
  type?: string | null;
  frame?: number | null;
  damage?: number | null;
  pos?: string | null;
  special?: string | null;
  text?: string | null;
  img?: string | null;
  img_sm?: string | null;
  /** 장착 대상 카드의 instance_id */
  attached_to?: string;
  set_order?: number;
  [extra: string]: unknown;
}

/** 이 역할에게 보이지 않는 카드. instance_id가 없으므로 위치(owner/zone/index)로만 가리킨다. */
export interface HiddenCard {
  hidden: true;
  kind: string;
  owner: Side;
  zone: ZoneName;
  face_up: false;
  name: string;
  [extra: string]: unknown;
}

export type BoardCard = VisibleCard | HiddenCard;

export interface PassiveEntry {
  label?: string;
  display_label?: string;
  /** 토글은 불, 카운터·선택은 숫자나 문자열 */
  value?: boolean | number | string;
  count?: number;
  visibility?: "public" | "private";
  owner?: Side;
  derived?: boolean;
  [extra: string]: unknown;
}

export interface PlayerState {
  name: string;
  hp: number;
  fp: number;
  initial_hp?: number;
  character?: {
    id?: number;
    name?: string;
    img?: string | null;
    icon_img?: string | null;
    color?: string | null;
    hand_limit?: number | null;
    [extra: string]: unknown;
  };
  passive_state: Record<string, PassiveEntry>;
  zones: Record<ZoneName, BoardCard[]>;
  [extra: string]: unknown;
}

export interface EngineStatus {
  status: "running" | "finished" | (string & {});
  step: string | null;
  winner: Side | null;
  reason: string;
}

export interface GameState {
  turn: number;
  phase: Phase;
  priority_player?: Side;
  players: Record<Side, PlayerState>;
  engine: Partial<EngineStatus>;
  [extra: string]: unknown;
}

// ---------------------------------------------------------------------------
// 카드 카탈로그  GET simulator/<view_token>/card-metadata/?ids=1,2 → { cards: { "<card_id>": CardMeta } }

export interface CardMeta {
  card_id: number;
  code: string | null;
  name: string;
  type: string;
  frame: number | null;
  damage: number | null;
  pos: string | null;
  special?: string | null;
  g_top?: string | null;
  g_mid?: string | null;
  g_bot?: string | null;
  ultimate?: boolean;
  character_id?: number | null;
  text: string;
  /** 마크업을 표시 문자열로 렌더한 효과문 */
  text_label?: string;
  detail_text?: string;
  detail_text_label?: string;
  /** 보드용(중간 크기) */
  img: string | null;
  /** 작은 썸네일 */
  img_sm: string | null;
  /** 원본 크기. 확대 보기용 */
  img_lg?: string | null;
  [extra: string]: unknown;
}

// ---------------------------------------------------------------------------
// 행동

/**
 * 보드 위 카드 위치. index는 같은 응답의 state.players[owner].zones[zone][index].
 * instance_id는 이 역할에게 보이는 카드일 때만 들어 있다.
 */
export interface CardRef {
  owner: Side;
  zone: ZoneName;
  index: number;
  instance_id?: string;
}

/**
 * card      보드 카드에 묶인 행동. 카드를 눌러 실행한다.
 * primary   진행 버튼 하나(페이즈 종료, 콤보 종료 등).
 * secondary primary 옆의 작은 버튼.
 * decision  pending_decision 선택 창을 연다.
 * system    메뉴나 시스템 대화상자(타이머, 되감기, 기권).
 */
export type ActionUiKind = "card" | "primary" | "secondary" | "decision" | "system";

export interface DecisionOption {
  id: string;
  label?: string;
  owner?: Side;
  zone?: ZoneName;
  /** 보드 위 카드를 고르는 선택지면 card가 있다. to_zone은 고른 카드가 옮겨 갈 존(끌어 놓기용 힌트) */
  ui: { card?: CardRef; to_zone?: ZoneName };
  [extra: string]: unknown;
}

export interface LegalAction {
  /** submit 시 그대로 돌려보낸다. 상태가 바뀌면 무효가 된다. */
  action_id: string;
  type: string;
  label: string;
  payload: Record<string, unknown>;
  ui: { kind: ActionUiKind; cards: CardRef[] };
  /** submit_decision 행동에만 있다. */
  options?: DecisionOption[];
  minimum?: number;
  maximum?: number;
  choice_speed?: number;
  [extra: string]: unknown;
}

export interface PendingDecision {
  owner: Side;
  prompt: string;
  /** 상대의 선택일 때는 owner와 prompt만 온다. */
  id?: string;
  kind?: string;
  options?: DecisionOption[];
  minimum?: number;
  maximum?: number;
  default?: string[];
  optional?: boolean;
  /** 대상이 없거나 막혀서 고를 수 없는 선택지(흐리게, 이유와 함께 보여 준다) */
  unavailable_options?: { id: string; label: string; reason: string }[];
  [extra: string]: unknown;
}

export interface Clock {
  /** both: 두 플레이어가 각자 행동해야 하는 창(시작 패 확인·페이즈 종료) */
  owner?: Side | "both" | null;
  /** ready · decision · rewind · action(레디가 아닌 행동) */
  kind?: string;
  /** 서버 시각 ISO. 일시정지 중에는 null */
  deadline?: string | null;
  duration_seconds?: number;
  paused?: boolean;
  /** 일시정지 중일 때 남은 초 */
  remaining_seconds?: number | null;
  /** 서버가 보낼 때의 남은 밀리초 */
  remaining_ms?: number;
  /** 받은 순간 + remaining_ms (클라이언트가 채운다) */
  local_deadline?: number;
  /** 차례인 플레이어 화면이 표시했다고 알렸는지. false면 아직 시간이 흐르지 않는다. */
  seen?: boolean;
  id?: string;
  pause_reason?: string;
  paused_by?: Side | null;
  [extra: string]: unknown;
}

// ---------------------------------------------------------------------------
// 이벤트

export interface GameEvent<P = Record<string, unknown>> {
  id: string;
  /** 1부터 증가하는 전역 순번. 재접속 시 이어받기 기준. */
  seq: number;
  type: string;
  actor: Side | "system" | (string & {});
  payload: P;
  visibility?: "public" | "private";
  created_at: string;
}

export interface CardMovedPayload {
  card_instance_id: string;
  from_player: Side;
  from_zone: ZoneName;
  to_player: Side;
  to_zone: ZoneName;
  reason?: string;
  card_id?: number | null;
  card_code?: string | null;
  card_label?: string;
}

/** 다른 플레이어의 비공개 이벤트. 정체는 가리고 애니메이션에 필요한 존 정보만 남는다. */
export interface PrivateEventPayload {
  redacted: true;
  event_type?: "card_moved" | "card_readied";
  from_player?: Side;
  from_zone?: ZoneName;
  to_player?: Side;
  to_zone?: ZoneName;
}

export interface HpChangedPayload {
  before: number;
  after: number;
  amount: number;
  source?: string;
}

export type FpChangedPayload = HpChangedPayload;

export interface DamageDealtPayload {
  target: Side;
  amount: number;
  source?: string;
}

export interface PhaseStartedPayload {
  phase: Phase;
  turn: number;
  restarted?: boolean;
}

// ---------------------------------------------------------------------------
// 응답 전체

// ---------------------------------------------------------------------------
// 덱 준비 (preparation_view). status가 editing인 동안은 보드 대신 준비 화면을 보여 준다.

export interface PrepCardRow {
  card_id: number;
  count: number;
  hand?: number;
  side?: number;
}

export interface PrepActive {
  character_id: number;
  trait_card_id: number | null;
  cards: PrepCardRow[];
}

export interface PrepCatalogCard {
  id: number;
  name: string;
  code: string;
  type?: string | null;
  ultimate?: boolean;
  character_id?: number | null;
  frame?: number | null;
  damage?: number | null;
  pos?: string | null;
  text?: string | null;
  img?: string | null;
  img_mid?: string | null;
  img_sm?: string | null;
  [extra: string]: unknown;
}

export interface RegulationRules {
  reserve_limit: number;
  technique_swap_limit: number;
  trait_swap_limit: number;
  ultimate_swap_limit: number;
  [extra: string]: unknown;
}

export interface PrepRegistered {
  deck_id?: number;
  name?: string;
  character_id: number;
  character?: { id?: number; name?: string; [extra: string]: unknown };
  trait_card_id: number | null;
  cards: PrepCardRow[];
  reserve_cards: { card_id: number; count: number }[];
  catalog: Record<string, PrepCatalogCard>;
  regulation_rules: RegulationRules | null;
}

export interface PrepPlayer {
  ready: boolean;
  /** 내 좌석에만 온다 */
  registered?: PrepRegistered;
  active?: PrepActive;
}

export interface PreparationView {
  version: number;
  game_number: number;
  status: "editing" | "playing";
  players: Record<Side, PrepPlayer>;
}

export interface PlayEnvelope {
  protocol_version: typeof PLAY_PROTOCOL_VERSION;
  id: number;
  /** 낙관적 동시성 버전. 명령의 expected_version으로 보낸다. */
  version: number;
  /** 엔진 오류로 수동 모드가 되면 manual */
  mode: "automatic" | "manual";
  role: Role;
  can_submit_commands: boolean;
  is_expired: boolean;
  controllers: Record<Side, "human" | "ai">;
  state: GameState;
  legal_actions: LegalAction[];
  pending_decision: PendingDecision | null;
  clocks: Clock | null;
  timer_settings: { ready_timeout_seconds: number; effect_timeout_seconds: number };
  engine_status: EngineStatus;
  event_count: number;
  events?: GameEvent[];
  phase_labels?: Record<string, string>;
  zone_labels?: Record<string, string>;
  ruleset_version?: string | null;
  /** 새 형식 덱으로 만든 대전에만 있다 */
  preparation?: PreparationView | null;
  /** 수동 모드: 이 접속이 보드를 조작할 수 있는지 */
  can_control?: boolean;
  /** 자동 엔진 오류로 수동 모드가 된 대전 */
  automation_failure?: { report_id?: string; message?: string } | null;
  [extra: string]: unknown;
}

/** 클라이언트 → 서버 명령 본문. WebSocket에서는 seat/seat_token을 생략하면 연결 값이 쓰인다. */
export interface PlayCommand {
  /** 재전송해도 한 번만 실행되도록 클라이언트가 만드는 고유 값(UUID). */
  command_id: string;
  action_id: string;
  expected_version: number;
  /** submit_decision은 selected, pause_clock은 reason */
  selections?: { selected?: string[]; reason?: string };
  seat?: Side;
  seat_token?: string;
}

// ---------------------------------------------------------------------------
// WebSocket  ws/battlelog/simulator/<view_token>/?seat=&seat_token=&language=

export type ClientMessage =
  | { type: "state"; request_id?: string }
  | { type: "presence" }
  | { type: "log_subscribe"; since_seq: number }
  | { type: "log_unsubscribe" }
  | { type: "clock_seen"; clock_id: string }
  | { type: "command"; request_id?: string; payload: PlayCommand }
  /** 수동 모드 행동. payload.action은 move_card, hp, set_phase 등 */
  | { type: "action"; request_id?: string; payload: { action: string; payload: Record<string, unknown> } };

export type ErrorCode = "stale_state" | "illegal_action" | "automatic_fallback";

export type ServerMessage =
  /** 접속 직후와 state 요청 응답. events는 포함되지 않는다. */
  | { type: "state"; request_id?: string | null; state: PlayEnvelope }
  /** 세션이 바뀌었다는 알림. version이 내 것보다 크면 state를 다시 요청한다. */
  | { type: "state_dirty"; version: number; event_count: number }
  /** log_subscribe 이후 since_seq보다 뒤의 이벤트. reset이면 처음부터 다시 받는다. */
  | { type: "log_events"; events: GameEvent[]; event_count: number; reset?: boolean; [extra: string]: unknown }
  | { type: "command_ack"; request_id?: string; ok: true }
  | { type: "action_ack"; request_id?: string; ok: true }
  | {
      type: "error";
      request_id?: string | null;
      ok: false;
      error: string;
      code?: ErrorCode;
      /** stale_state일 때 최신 상태 */
      state?: PlayEnvelope;
    }
  | { type: "presence"; presence: Record<Role, number> }
  | { type: "signal"; id: string; actor: Side; signal: string; label: string };
