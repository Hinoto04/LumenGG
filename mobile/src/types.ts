export type Language = "ko" | "en" | "ja";
export type Localized = Record<Language, Record<string, any>>;
export interface RegulationVersion {
  id: number;
  regulation_id?: number;
  name: string;
  version: string;
  owner_id?: number | null;
  rules: {
    bans: { card_ids: number[]; scope: "registered" | "active" }[];
    combinations: { card_ids: number[]; scope: "registered" | "active" }[];
    reserve_limit: number;
    technique_swap_limit: number;
    trait_swap_limit: number;
    ultimate_swap_limit: number;
    reserve_public: boolean;
    swaps_public: boolean;
  };
}
export interface TraitOption {
  id: number;
  name: string;
  code?: string;
  img?: string;
  trait_config: Record<string, any>;
  deck_rules: Record<string, any>;
  initial_hp: number;
  hand_table: Record<string, number>;
  initial_passive_state: Record<string, PassiveValue>;
  localized: Localized;
}
export interface ValidationIssue {
  code: string;
  severity: "error" | "warning";
  card_ids: number[];
  message: string;
}
export interface Card {
  original_name?: string;
  setup_rules?: Record<string, any>;
  deck_limit?: number;
  token_key?: string;
  character_key?: string;
  id: number;
  code: string | null;
  character_id: number;
  type: string;
  ultimate: boolean;
  frame: number | null;
  damage: number | null;
  pos: string;
  body: string;
  special: string;
  hit: string;
  guard: string;
  counter: string;
  g_top: string;
  g_mid: string;
  g_bot: string;
  img: string;
  img_mid: string;
  img_sm: string;
  localized: Localized;
  search?: string;
}
export interface CalculatorTheme {
  theme_key: string;
  accent: string;
  secondary: string;
  motif: string;
  passive_variant?: string;
  background?: string;
  emblem?: string;
}
export interface Character {
  traits?: TraitOption[];
  base_deck_rules?: Record<string, any>;
  id: number;
  img: string;
  img_sm: string;
  color: string;
  calculator_ui?: CalculatorTheme | null;
  localized: Localized;
  initial_hp: number;
  hand_table: Record<string, number>;
  initial_passive_state: Record<string, PassiveValue>;
}
export interface Pack {
  id: number;
  code: string;
  released: string | null;
  localized: Localized;
}
export interface CollectionItem {
  id: number;
  name: string;
  code: string;
  rare: string;
  item_type: string;
  card_id: number | null;
  character_id: number | null;
  pack_id: number | null;
  image: string;
  img_sm: string;
}
export interface Qna {
  id: number;
  title: string;
  question: string;
  answer: string;
  tags: string;
  faq: boolean;
  card_ids: number[];
  search?: string;
}
export interface Rules {
  regulations?: RegulationVersion[];
  max_deck_sizes: Record<string, number>;
  copy_limits: Record<string, number>;
  min_deck_size: number;
  max_hand: number;
  max_ultimate: number;
  ui: Record<Language, Record<string, string>>;
}
export interface Catalog {
  schema_version?: number;
  cards: Card[];
  characters: Character[];
  packs: Pack[];
  collection: CollectionItem[];
  qna: Qna[];
  rules: Rules;
  version: string;
}
export interface DeckEntry {
  card_id: number;
  count: number;
  hand: number;
  side: number;
  name?: string;
}
export interface Deck {
  regulation?: RegulationVersion | null;
  imported_regulation?: RegulationVersion;
  snapshot_catalog?: Record<string, any>;
  validation?: { is_valid?: boolean | null; issues?: ValidationIssue[] };
  schema_version?: number;
  trait_card_id?: number | null;
  regulation_version_id?: number | null;
  regulation_rules?: RegulationVersion["rules"];
  reserve_cards?: { card_id: number; count: number }[];
  uuid: string;
  id?: number;
  name: string;
  character_id: number;
  description: string;
  keyword: string;
  tags: string;
  visibility: "public" | "unlisted" | "private";
  cards: DeckEntry[];
  deleted?: boolean;
  locked?: boolean;
  version?: string;
  author?: User;
}
export interface Operation {
  schema_version?: number;
  operation_id: string;
  entity: "deck" | "collection";
  entity_id: string | number;
  action: "upsert" | "delete";
  data?: any;
}
export interface QueueItem {
  seq: number;
  operation: Operation;
  error?: string;
}
export interface User {
  id: number;
  username: string;
}
export interface SyncResponse {
  user: User;
  results: { operation_id: string; ok: boolean; error?: unknown }[];
  decks: Deck[];
  collection: { card_id: number; amount: number }[];
}
export interface Manifest {
  release_version: string;
  schema_version: number;
  min_client_version: string;
  published_at: string;
  download_url: string;
  size_bytes: number;
  sha256: string;
}
export interface PassiveValue {
  value?: any;
  count?: number;
  label?: string;
}
export interface Condition {
  type?: string;
  key?: string;
  keys?: string[];
  value?: any;
  all?: Condition[];
  any?: Condition[];
  conditions?: Condition[];
}
export interface PassiveControl {
  type: string;
  key: string;
  label: string;
  max?: number;
  default?: any;
  initial?: any;
  choices?: { value?: any; key?: any; label: string }[];
  visibleWhen?: Condition;
  enableWhen?: Condition;
  activateWhen?: Condition;
  keepWhile?: Condition;
  resetKeys?: string[];
  condition?: Condition;
  requires?: Condition;
  activeText?: string;
  inactiveText?: string;
}
export interface PassiveDefinition {
  controls?: PassiveControl[];
  badges?: PassiveControl[];
  latchedStatuses?: PassiveControl[];
  adapter?: string;
  title?: string;
  description?: string;
}
export interface Player {
  name: string;
  hp: number;
  fp: number;
  initial_hp: number;
  passive_state: Record<string, PassiveValue>;
  character: any;
}
export interface CalcState {
  preparation?: any;
  type?: string;
  tournament?: {
    id: number | null;
    name: string;
    match_id: number | null;
    match_status?: string;
    round_number?: number;
    table?: string;
  };
  round_timer?: {
    ends_at: string | null;
    remaining_seconds: number | null;
    is_over: boolean;
  };
  set?: {
    current_number: number;
    max_sets: number;
    required_wins: number;
    score: { p1: number; p2: number };
    winner_candidate: string;
    can_report: boolean;
    report_side: string;
    player1_confirmed: boolean;
    player2_confirmed: boolean;
    status: string;
  };
  character_choices?: Record<
    "p1" | "p2",
    {
      can_choose: boolean;
      options: { id: number; name: string; color: string }[];
    }
  >;
  party?: {
    code: string;
    return_url: string;
    exchanges: number;
    completed: boolean;
    status: string;
  } | null;
  version: number;
  players: { p1: Player; p2: Player };
  timer: {
    ends_at?: string | null;
    is_running: boolean;
    duration_seconds: number;
  };
  events: any[];
  sudden_death: boolean;
  sudden_death_turns_remaining: number;
  can_control: boolean;
  is_expired?: boolean;
  view_url?: string;
  control_url?: string;
}
export interface Action {
  expected_exchange?: number;
  action: string;
  target?: "p1" | "p2";
  amount?: number;
  key?: string;
  value?: any;
  label?: string;
  passive_action?: string;
  enabled?: boolean;
  character_id?: number;
  preparation_version?: number;
  preparation_action?: string;
  request_id?: string;
  submission_id?: number;
  active?: any;
  actions?: Action[];
  action_id?: string;
  expected_version?: number;
}
