import type {
  Action,
  Card,
  Catalog,
  Character,
  Condition,
  Deck,
  PassiveDefinition,
  Player,
  CalcState,
} from "./types";

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

export function normalizeSearch(value: string): string {
  // The exporter writes Python NFKC+casefold values. These replacements cover
  // casefold differences used by the current ko/en/ja catalog.
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/ß/g, "ss")
    .replace(/ς/g, "σ")
    .replace(/[^\p{L}\p{N}]/gu, "");
}
export function localized(
  value: { localized: any },
  language: string,
  key = "name",
): any {
  return value.localized?.[language]?.[key] || value.localized?.ko?.[key] || "";
}
export function deckError(deck: Deck, catalog: Catalog): string | null {
  if (!deck.name.trim()) return "덱 이름을 입력해주세요.";
  if (!catalog.characters.some((c) => c.id === deck.character_id))
    return "캐릭터를 선택해주세요.";
  let main = 0,
    hand = 0,
    ultimate = 0;
  const seen = new Set<number>();
  for (const entry of deck.cards) {
    const card = catalog.cards.find((c) => c.id === entry.card_id);
    if (!card) return "사용할 수 없는 카드가 있습니다.";
    if (seen.has(entry.card_id)) return "중복 카드 항목이 있습니다.";
    seen.add(entry.card_id);
    if (
      ![entry.count, entry.hand, entry.side].every(
        (n) => Number.isInteger(n) && n >= 0 && n <= 32767,
      )
    )
      return "수량이 올바르지 않습니다.";
    if (entry.hand + entry.side > entry.count)
      return "손패와 사이드 수량이 전체 수량보다 많습니다.";
    if (card.ultimate) ultimate += entry.count;
    else main += entry.count;
    hand += entry.hand;
  }
  if (ultimate > 1) return "얼티밋 카드는 1장까지만 넣을 수 있습니다.";
  if (hand > catalog.rules.max_hand) return "손패 매수는 최대 5장입니다.";
  if (main < catalog.rules.min_deck_size) return "덱 매수가 너무 적습니다.";
  if (main > (catalog.rules.max_deck_sizes[String(deck.character_id)] ?? 21))
    return "덱 매수가 너무 많습니다.";
  return null;
}
export function adjustEntry(
  deck: Deck,
  card: Card,
  field: "count" | "hand" | "side",
  delta: number,
  copyLimits: Record<string, number>,
): Deck {
  const entries = deck.cards.map((e) => ({ ...e }));
  let entry = entries.find((e) => e.card_id === card.id);
  if (!entry) {
    entry = {
      card_id: card.id,
      count: 0,
      hand: 0,
      side: 0,
      name: card.localized.ko.name || card.code || String(card.id),
    };
    entries.push(entry);
  }
  const forcedSide = !card.ultimate && card.type.includes("특수");
  if (field === "count") {
    const maximum = card.ultimate
      ? 1
      : Number(copyLimits[String(card.id)] || 1);
    entry.count = Math.max(0, Math.min(maximum, entry.count + delta));
    entry.hand = Math.min(entry.hand, entry.count);
    entry.side = Math.min(entry.side, entry.count - entry.hand);
  } else if (!card.ultimate && !forcedSide) {
    if (
      field === "hand" &&
      delta > 0 &&
      entries.reduce((sum, e) => sum + e.hand, 0) >= 5
    )
      return deck;
    entry[field] = Math.max(
      0,
      Math.min(
        entry.count - entry[field === "hand" ? "side" : "hand"],
        entry[field] + delta,
      ),
    );
  }
  if (card.ultimate) {
    entry.hand = 0;
    entry.side = 0;
  }
  if (forcedSide) {
    entry.hand = 0;
    entry.side = entry.count;
  }
  return { ...deck, cards: entries.filter((e) => e.count > 0) };
}
export function passiveGet(player: Player, key = "", fallback: any = 0): any {
  const entry = player.passive_state[key];
  return entry?.value ?? entry?.count ?? fallback;
}
export function conditionMet(
  condition: Condition | undefined,
  player: Player,
): boolean {
  if (!condition) return false;
  if (condition.all) return condition.all.every((c) => conditionMet(c, player));
  if (condition.any) return condition.any.some((c) => conditionMet(c, player));
  const v = passiveGet(player, condition.key);
  switch (condition.type) {
    case "all":
      return (condition.conditions || []).every((c) => conditionMet(c, player));
    case "any":
      return (condition.conditions || []).some((c) => conditionMet(c, player));
    case "hpAtMost":
      return player.hp <= Number(condition.value);
    case "counterAtLeast":
      return Number(v) >= Number(condition.value);
    case "counterAtMost":
      return Number(v) <= Number(condition.value);
    case "active":
    case "truthy":
    case "keyActive":
      return v === true || v === "true" || v === "on" || v === "ON";
    case "equals":
    case "valueEquals":
    case "keyEquals":
      return v === condition.value;
    case "allEquals":
      return (condition.keys || []).every(
        (k) => Number(passiveGet(player, k)) === Number(condition.value),
      );
    case "allAtLeast":
      return (condition.keys || []).every(
        (k) => Number(passiveGet(player, k)) >= Number(condition.value),
      );
    case "not":
      return !conditionMet(condition.conditions?.[0], player);
    default:
      return false;
  }
}
export function passiveActions(
  player: Player,
  definition: PassiveDefinition,
  target: "p1" | "p2",
  key: string,
  value: any,
  label: string,
): Action {
  const action = (k: string, v: any, l = k): Action => ({
    action: "passive",
    target,
    key: k,
    value: v,
    label: l,
    passive_action: "set",
  });
  const actions: Action[] = [action(key, value, label)];
  const next: Player = {
    ...player,
    passive_state: { ...player.passive_state, [key]: { value } },
  };
  for (const status of definition.latchedStatuses || []) {
    const stored = Boolean(passiveGet(player, status.key, false));
    const active = conditionMet(status.activateWhen, next);
    const keep = conditionMet(status.keepWhile || status.activateWhen, next);
    if (active && !stored) actions.push(action(status.key, true, status.label));
    else if (stored && !keep)
      actions.push(action(status.key, false, status.label));
  }
  if (
    definition.adapter === "tao" &&
    ["yang_counter", "yin_counter"].includes(key)
  ) {
    const yang = Number(passiveGet(next, "yang_counter")),
      yin = Number(passiveGet(next, "yin_counter"));
    const harmony = Boolean(passiveGet(player, "harmony", false));
    if (yang === 4 && yin === 4 && !harmony)
      actions.push(action("harmony", true, "조화"));
    else if (harmony && (yang < 3 || yin < 3))
      actions.push(
        action("harmony_effect", "", "조화 효과"),
        action("harmony", false, "조화"),
      );
  }
  return actions.length === 1 ? actions[0]! : { action: "batch", actions };
}
export function newCalculator(
  p1: Character,
  p2: Character,
  language: string,
): CalcState {
  const player = (c: Character): Player => ({
    name: localized(c, language),
    hp: c.initial_hp,
    initial_hp: c.initial_hp,
    fp: 0,
    passive_state: clone(c.initial_passive_state),
    character: {
      id: c.id,
      name: localized(c, language),
      img: c.img,
      hand_table: c.hand_table,
      initial_passive_state: c.initial_passive_state,
      passive: localized(c, language, "passive"),
    },
  });
  return {
    version: 1,
    players: { p1: player(p1), p2: player(p2) },
    timer: { is_running: false, duration_seconds: 10 },
    events: [],
    sudden_death: false,
    sudden_death_turns_remaining: 0,
    can_control: true,
  };
}
export function reduceCalculator(
  state: CalcState,
  action: Action,
  now = Date.now(),
): CalcState {
  if (action.action === "batch")
    return (action.actions || []).reduce(
      (s, a) => reduceCalculator(s, a, now),
      state,
    );
  const next = clone(state),
    player = action.target ? next.players[action.target] : undefined;
  const amount = action.amount || 0;
  let event: any = {
    id: `${now}-${state.version}`,
    type: action.action,
    target: action.target,
    amount,
    created_at: new Date(now).toISOString(),
  };
  switch (action.action) {
    case "hp":
      if (player) {
        event.hp_before = player.hp;
        player.hp += amount;
        event.hp_after = player.hp;
      }
      break;
    case "fp":
      if (player) player.fp += amount;
      break;
    case "fp_reset":
      if (player) player.fp = 0;
      break;
    case "passive":
      if (player && action.key)
        player.passive_state[action.key] = {
          value: action.value,
          label: action.label,
        };
      break;
    case "timer":
      next.timer =
        next.timer.ends_at && Date.parse(next.timer.ends_at) > now
          ? { is_running: false, duration_seconds: 10, ends_at: null }
          : {
              is_running: true,
              duration_seconds: 10,
              ends_at: new Date(now + 10000).toISOString(),
            };
      break;
    case "undo": {
      const prior = [...next.events]
        .reverse()
        .find((e) => e.type === "hp" && !e.undone);
      if (prior && (prior.target === "p1" || prior.target === "p2")) {
        next.players[prior.target as "p1" | "p2"].hp = prior.hp_before;
        prior.undone = true;
      }
      break;
    }
    case "reset_session":
      for (const p of Object.values(next.players)) {
        p.hp = p.initial_hp;
        p.fp = 0;
        p.passive_state = clone(p.character.initial_passive_state || {});
      }
      next.events = [];
      next.timer = { is_running: false, duration_seconds: 10 };
      next.sudden_death = false;
      next.sudden_death_turns_remaining = 0;
      break;
    case "sudden_death":
      next.sudden_death = !!action.enabled;
      next.sudden_death_turns_remaining = action.enabled ? 3 : 0;
      if (action.enabled) {
        for (const p of Object.values(next.players)) {
          p.hp = 1000;
          p.fp = 0;
          p.passive_state = clone(p.character.initial_passive_state || {});
        }
        next.timer = { is_running: false, duration_seconds: 10 };
      }
      break;
    case "sudden_turn":
      next.sudden_death_turns_remaining = Math.max(
        0,
        next.sudden_death_turns_remaining - 1,
      );
      break;
    default:
      return state;
  }
  next.version++;
  next.events.push(event);
  return next;
}
export function shouldOverlayPending(
  item: { entity: string; entity_id: string | number },
  pending: { entity: string; entity_id: string | number }[],
): boolean {
  return pending.some(
    (p) => p.entity === item.entity && p.entity_id === item.entity_id,
  );
}
