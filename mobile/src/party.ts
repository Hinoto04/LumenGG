import * as SecureStore from "expo-secure-store";
import { ApiError, request } from "./api";

export interface PartyTile {
  id: number;
  kind: string;
  label: string;
  icon: string;
  background_img?: string;
  description: string;
  x: number;
  y: number;
  exits: number[];
  ring: string;
  clockwise?: number;
  transfer_to?: number;
  shared?: boolean;
}
export interface PartyPlayer {
  seat: number;
  name: string;
  hp: number;
  max_hp: number;
  fp: number;
  prepared_fp: number;
  coins: number;
  crystals: number;
  position: number;
  forward_exits?: number[];
  ready: boolean;
  is_host: boolean;
  home: number;
  poison_turns: number;
  double_dice: boolean;
  cloaked?: boolean;
  shielded?: boolean;
  revenge_ready?: boolean;
  free_direction?: boolean;
  smart_dice?: boolean;
  ko_status?: "knocked_out" | "resting" | null;
  hand_limit?: number | null;
  character: {
    id: number;
    name: string;
    img: string;
    body_img?: string;
    sd_img?: string;
    icon_img?: string;
  };
}
export interface PartyState {
  supplies: PartySupply[];
  supply_encounter: PartySupply | null;
  code: string;
  name: string;
  status: string;
  test_controls?: boolean;
  version: number;
  server_time?: number;
  dice_roll?: PartyRollResult | null;
  expired: boolean;
  url: string;
  round: number;
  turn_number: number;
  turn_order?: number[];
  order_change?: {
    round: number;
    from: number[];
    to: number[];
    version: number;
  } | null;
  movement_power: number;
  attacker_bonus: number;
  turn: number;
  landed: boolean;
  can_act: boolean;
  can_use_items: boolean;
  can_auto_end_turn: boolean;
  shop_offers: string[];
  roadblocks: { node: number; owner: number }[];
  counter_prompt: { seat: number; target: number; battle_id: number } | null;
  item_targets: Record<string, number[]>;
  hand_task: { reason: string; count: number | null; version: number } | null;
  move: {
    dice: number;
    dice_values?: number[];
    bonus?: number;
    roll_version?: number;
    remaining: number;
    free_direction?: boolean;
    reveal_pending?: boolean;
  } | null;
  move_path?: {
    seat: number;
    nodes: number[];
    version: number;
    teleport?: boolean;
  } | null;
  movement_preview: {
    origin: number;
    remaining: number;
    nodes: number[];
    edges: string[];
    routes: Record<string, { nodes: number[]; edges: string[] }>;
  } | null;
  can_buy_crystal?: boolean;
  camp_gift?: { seat: number; turn: number; items: string[] } | null;
  camp_stop_shortfall?: number;
  camp_purchase_done?: boolean;
  challenge_declined?: boolean;
  can_buy_item: boolean;
  can_charge: boolean;
  can_transfer?: boolean;
  transfer_to?: number | null;
  challenge_targets: number[];
  move_prompt: {
    targets: number[];
    own_camp: boolean;
    shared_camp?: boolean;
    shop?: boolean;
    shop_open?: boolean;
    supply?: string;
  } | null;
  arrival: "dash" | "charge" | "transfer" | null;
  item_reward?: string | null;
  event: {
    id: string;
    label: string;
    description: string;
    seat: number;
    version: number;
    image?: string;
    show_at?: number;
    reveal_until?: number;
    pending?: boolean;
    applied_at?: number;
    effect_until?: number;
    card_id?: string;
    effect_box?: PartyCardEffectBox;
  } | null;
  last_action: { seat: number; action: string; version: number } | null;
  winners: number[];
  players: PartyPlayer[];
  log: { text: string; at: string }[];
  me: { seat: number; is_host: boolean; items: string[] } | null;
  board: {
    version?: number;
    bounds?: { min: number; max: number };
    name: string;
    nodes: PartyTile[];
    shop: Record<string, PartyItem>;
    crystal_costs: number[];
    events: { id: string; label: string; description: string }[];
  };
  battle: {
    id: number;
    p1: number;
    p2: number;
    version: number;
    exchanges: number;
    completed: boolean;
    result: { confirmed?: number[] };
    can_confirm: boolean;
    view_token: string;
    control_token?: string;
    calculator_url: string;
  } | null;
}
export interface PartySupply {
  id: string;
  node: number;
  hp: number;
  max_hp: number;
  spawn_round: number;
}
export interface PartyRollResult {
  seat: number;
  turn_number: number;
  version: number;
  dice_values: number[];
  bonus: number;
  total: number;
  started_at: number;
  settle_at?: number;
  number_at?: number;
  add_at: number;
  count_at?: number;
  total_at?: number;
  end_at: number;
}
export interface PartyItem {
  label: string;
  price: number;
  description: string;
  image?: string;
  target: "self" | "player" | "tile" | "number";
  range?: number;
  damage?: number;
  card_id?: string;
  effect_box?: PartyCardEffectBox;
}
export interface PartyCardEffectBox {
  left: number;
  top: number;
  width: number;
  height: number;
  fontPt: number;
  lineHeight: number;
  verticalAlign?: string;
}
export interface PartyCardDisplay {
  label: string;
  description: string;
  image?: string;
  card_id?: string;
  effect_box?: PartyCardEffectBox;
}
export interface PartySeat {
  code: string;
  token: string;
  openedBattle?: number;
}
export async function storedParty(): Promise<PartySeat | null> {
  const value = await SecureStore.getItemAsync("lumendb.party");
  return value ? JSON.parse(value) : null;
}
export async function saveParty(value: PartySeat) {
  await SecureStore.setItemAsync("lumendb.party", JSON.stringify(value));
}
export async function partyRequest(
  path: string,
  token = "",
  data?: Record<string, unknown>,
) {
  try {
    return await request(
      "/party/" + path,
      {
        method: data ? "POST" : "GET",
        headers: { "X-Party-Player": token },
        body: data ? JSON.stringify(data) : undefined,
      },
      false,
    );
  } catch (error) {
    if (error instanceof ApiError && error.detail?.error)
      throw new Error(error.detail.error);
    throw error;
  }
}
export function partyNearby(
  nodes: PartyTile[],
  origin: number,
  destination: number,
  distance: number,
) {
  const visited = new Set([origin]);
  let frontier = [origin];
  for (let step = 0; step < distance; step++) {
    const next = new Set<number>();
    frontier.forEach((here) =>
      nodes.forEach((tile) => {
        if (tile.exits.includes(here) || nodes[here]!.exits.includes(tile.id))
          next.add(tile.id);
      }),
    );
    frontier = [...next].filter((id) => !visited.has(id));
    frontier.forEach((id) => visited.add(id));
  }
  return visited.has(destination);
}
