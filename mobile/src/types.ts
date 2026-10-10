export type Language = "ko" | "en" | "ja";
export type Localized = Record<Language, Record<string, any>>;
export interface Card {
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
export interface Character {
  id: number;
  img: string;
  img_sm: string;
  color: string;
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
  max_deck_sizes: Record<string, number>;
  copy_limits: Record<string, number>;
  min_deck_size: number;
  max_hand: number;
  max_ultimate: number;
  ui: Record<Language, Record<string, string>>;
}
export interface Catalog {
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
  action: string;
  target?: "p1" | "p2";
  amount?: number;
  key?: string;
  value?: any;
  label?: string;
  passive_action?: string;
  enabled?: boolean;
  character_id?: number;
  actions?: Action[];
  action_id?: string;
  expected_version?: number;
}
