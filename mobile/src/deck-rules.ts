import type {
  Card,
  Catalog,
  Deck,
  RegulationVersion,
  ValidationIssue,
} from "./types";

export const defaultPolicy: RegulationVersion["rules"] = {
  bans: [],
  combinations: [],
  reserve_limit: 0,
  technique_swap_limit: 0,
  trait_swap_limit: 0,
  ultimate_swap_limit: 0,
  reserve_public: false,
  swaps_public: false,
};
export const isTrait = (card: Pick<Card, "type" | "code">) =>
  card.type === "특성" || (card.code || "").toUpperCase().includes("PS");
export function mergeRules(...rules: Record<string, any>[]) {
  const result: Record<string, any> = {};
  for (const rule of rules)
    for (const [key, value] of Object.entries(rule || {})) {
      if (key === "supplements")
        result[key] = [...(result[key] || []), ...value];
      else if (key === "other_character_cards")
        result[key] = { ...result[key], ...value };
      else result[key] = value;
    }
  return result;
}
function matches(card: Card, where: any): boolean {
  return Object.entries(where || {}).every(([key, value]: [string, any]) => {
    const c: any = {
      ...card,
      name: card.original_name || card.localized.ko?.name || "",
    };
    if (key === "all" || key === "any")
      return (
        value.length > 0 &&
        (key === "all"
          ? value.every((w: any) => matches(card, w))
          : value.some((w: any) => matches(card, w)))
      );
    if (key === "type_contains") return c.type.includes(value);
    if (key === "type_not_contains") return !c.type.includes(value);
    if (key === "name_contains")
      return c.name.toLowerCase().includes(String(value).toLowerCase());
    if (key === "name_not_contains")
      return !c.name.toLowerCase().includes(String(value).toLowerCase());
    if (key === "type_in") return value.includes(c.type);
    if (key === "code_in") return value.includes(c.code);
    if (key === "is_technique")
      return (
        ["공격", "수비", "특수"].some((t) => c.type.includes(t)) === !!value
      );
    if (key.endsWith("_gte")) return Number(c[key.slice(0, -4)] || 0) >= value;
    if (key.endsWith("_lte")) return Number(c[key.slice(0, -4)] || 0) <= value;
    if (key.endsWith("_in")) return value.includes(c[key.slice(0, -3)]);
    if (key.endsWith("_not")) return c[key.slice(0, -4)] !== value;
    return Array.isArray(value) ? value.includes(c[key]) : c[key] === value;
  });
}
/** 같은 이름 제한에 쓰는 카드 이름(한국어 원문). */
const cardName = (c: Card) =>
  c.original_name || c.localized.ko?.name || String(c.id);

/** 캐릭터·특성·덱에 넣은 카드의 편성 규칙을 합친다. */
export function deckRulesFor(
  catalog: Catalog,
  characterId: number,
  traitId: number | null | undefined,
  entries: { card_id: number; count: number }[],
): Record<string, any> {
  const character = catalog.characters.find((c) => c.id === characterId);
  const trait = character?.traits?.find((t) => t.id === traitId);
  const cards = new Map(catalog.cards.map((c) => [c.id, c]));
  return mergeRules(
    character?.base_deck_rules || {},
    trait?.trait_config.deck_rules || {},
    trait?.deck_rules || {},
    ...entries
      .filter((e) => e.count > 0)
      .map((e) => cards.get(e.card_id)?.setup_rules || {}),
  );
}

/** 같은 이름 카드를 덱에 넣을 수 있는 최대 매수. */
export function sameNameLimit(c: Card, rules: Record<string, any>): number {
  const printed = (c.localized.ko?.text || "").match(
    /이 (?:기술|카드)은\s*(?:(\d+)장까지\s*덱에|덱에\s*(\d+)장까지)\s*넣을 수 있다/,
  );
  return Math.max(
    c.deck_limit || rules.same_name_limit || 1,
    Number(printed?.[1] || printed?.[2] || 0),
    ...(rules.supplements || [])
      .filter((s: any) => matches(c, s.where))
      .map((s: any) => s.same_name_limit || 0),
  );
}

/**
 * 기술 덱(교체 덱 제외)에 카드를 몇 장 더 넣을 수 있는지 알려 주는 함수를 만든다.
 * 얼티밋은 얼티밋 전체 매수, 그 밖의 카드는 같은 이름 카드 매수 제한을 따른다.
 * 검색 결과 전체에 쓰므로 덱 쪽 집계는 한 번만 한다.
 */
export function copyAvailability(deck: Deck, catalog: Catalog) {
  const cards = new Map(catalog.cards.map((c) => [c.id, c]));
  const base = deckRulesFor(
    catalog,
    deck.character_id,
    deck.trait_card_id,
    deck.cards,
  );
  const names = new Map<string, number>();
  let ultimates = 0;
  for (const e of deck.cards) {
    const c = cards.get(e.card_id);
    if (!c) continue;
    if (c.ultimate) ultimates += e.count;
    else names.set(cardName(c), (names.get(cardName(c)) || 0) + e.count);
  }
  return (card: Card) => {
    // 넣으려는 카드 자체의 편성 규칙(매수 제한 완화 등)도 반영한다.
    const rules = card.setup_rules ? mergeRules(base, card.setup_rules) : base;
    if (card.ultimate) return (rules.ultimate_maximum ?? 1) - ultimates;
    return sameNameLimit(card, rules) - (names.get(cardName(card)) || 0);
  };
}

export const remainingCopies = (card: Card, deck: Deck, catalog: Catalog) =>
  copyAvailability(deck, catalog)(card);

/** 덱 작성 화면에 보여 주는 편성 수치. 기준은 deckIssues의 검사와 같다. */
export interface DeckStats {
  /** 얼티밋을 뺀 기술 카드 매수와 허용 범위. */
  total: number;
  minimum: number;
  maximum: number;
  /** 캐릭터 마크 기술 매수(보충 카드 제외)와 최소 매수. */
  own: number;
  ownMinimum: number;
  /** 시작 배치(얼티밋·특수 기술 제외). */
  hand: number;
  handTarget: number;
  list: number;
  listTarget: number;
}

export function deckIssues(
  deck: Deck,
  catalog: Catalog,
  stage: "draft" | "registration" | "replacement" | "setup" = "registration",
  active: Pick<Deck, "character_id" | "trait_card_id" | "cards"> = deck,
): ValidationIssue[] {
  return analyzeDeck(deck, catalog, stage, active).issues;
}

/** 덱 작성 화면의 매수 표시용 수치. */
export function deckStats(deck: Deck, catalog: Catalog): DeckStats {
  return analyzeDeck(deck, catalog, "draft", deck).stats;
}

function analyzeDeck(
  deck: Deck,
  catalog: Catalog,
  stage: "draft" | "registration" | "replacement" | "setup",
  active: Pick<Deck, "character_id" | "trait_card_id" | "cards">,
): { issues: ValidationIssue[]; stats: DeckStats } {
  const stats: DeckStats = {
    total: 0,
    minimum: 20,
    maximum: 20,
    own: 0,
    ownMinimum: 10,
    hand: 0,
    handTarget: 5,
    list: 0,
    listTarget: 9,
  };
  const issues: ValidationIssue[] = [],
    cards = new Map(catalog.cards.map((c) => [c.id, c]));
  const add = (code: string, message: string, ids: number[] = []) =>
    issues.push({
      code,
      message,
      card_ids: ids,
      severity:
        stage === "draft" &&
        ![
          "invalid_count",
          "unknown_card",
          "invalid_placement",
          "duplicate_entry",
        ].includes(code)
          ? "warning"
          : "error",
    });
  const character = catalog.characters.find((c) => c.id === deck.character_id);
  const trait = character?.traits?.find((t) => t.id === active.trait_card_id);
  const policy = {
    ...defaultPolicy,
    ...(deck.regulation_rules ||
      catalog.rules.regulations?.find(
        (r) => r.id === deck.regulation_version_id,
      )?.rules),
  };
  if (active.character_id !== deck.character_id)
    add("character_fixed", "등록한 캐릭터는 교체할 수 없습니다.");
  for (const id of [deck.trait_card_id, active.trait_card_id]) {
    const c = cards.get(id || 0);
    if (!c || !isTrait(c) || c.character_id !== deck.character_id)
      add(
        "trait_required",
        "선택한 캐릭터의 특성 1장을 지정해주세요.",
        id ? [id] : [],
      );
  }
  const count = (
    rows: { card_id: number; count: number; hand?: number; side?: number }[],
    placement = false,
  ) => {
    const result = new Map<number, number>(),
      seen = new Set<number>();
    for (const e of rows) {
      if (!cards.has(e.card_id)) {
        add("unknown_card", "등록되지 않은 카드입니다.");
        continue;
      }
      if (seen.has(e.card_id))
        add("duplicate_entry", "카드 항목이 중복되었습니다.", [e.card_id]);
      seen.add(e.card_id);
      if (!Number.isInteger(e.count) || e.count <= 0 || e.count > 1000) {
        add("invalid_count", "수량이 올바르지 않습니다.", [e.card_id]);
        continue;
      }
      if (
        placement &&
        (![e.hand || 0, e.side || 0].every(
          (n) => Number.isInteger(n) && n >= 0,
        ) ||
          (e.hand || 0) + (e.side || 0) > e.count)
      )
        add("invalid_placement", "시작 배치 수량이 올바르지 않습니다.", [
          e.card_id,
        ]);
      result.set(e.card_id, (result.get(e.card_id) || 0) + e.count);
    }
    return result;
  };
  const base = count(deck.cards),
    reserve = count(deck.reserve_cards || []),
    used = count(active.cards, true),
    registered = new Map(base),
    activeCounts = new Map(used);
  reserve.forEach((n, id) => registered.set(id, (registered.get(id) || 0) + n));
  if (deck.trait_card_id)
    registered.set(
      deck.trait_card_id,
      (registered.get(deck.trait_card_id) || 0) + 1,
    );
  if (active.trait_card_id)
    activeCounts.set(
      active.trait_card_id,
      (activeCounts.get(active.trait_card_id) || 0) + 1,
    );
  if ([...reserve.values()].reduce((a, b) => a + b, 0) > policy.reserve_limit)
    add("reserve_limit", "교체 덱 등록 한도를 초과했습니다.", [
      ...reserve.keys(),
    ]);
  activeCounts.forEach((n, id) => {
    if (n > (registered.get(id) || 0))
      add("unregistered_card", "등록한 카드 수량을 초과했습니다.", [id]);
  });
  used.forEach((_, id) => {
    if (isTrait(cards.get(id)!))
      add("trait_in_techniques", "특성은 기술 카드 구성에 넣을 수 없습니다.", [
        id,
      ]);
  });
  reserve.forEach((_, id) => {
    const c = cards.get(id)!;
    if (isTrait(c) && c.character_id !== deck.character_id)
      add("foreign_trait", "같은 캐릭터의 특성만 등록할 수 있습니다.", [id]);
    else if (
      !isTrait(c) &&
      !["공격", "수비", "특수"].some((t) => c.type.includes(t))
    )
      add("invalid_reserve_type", "교체 덱에 등록할 수 없는 카드입니다.", [id]);
  });
  const diff = (a: Map<number, number>, b: Map<number, number>) =>
    [...a].reduce(
      (sum, [id, n]) =>
        sum +
        (!cards.get(id)!.ultimate && !isTrait(cards.get(id)!)
          ? Math.max(0, n - (b.get(id) || 0))
          : 0),
      0,
    );
  const ult = (pool: Map<number, number>) =>
    JSON.stringify(
      [...pool]
        .filter(([id]) => cards.get(id)!.ultimate)
        .sort(([a], [b]) => a - b),
    );
  if (stage === "replacement" || stage === "setup") {
    const changes = {
      technique: Math.max(diff(base, used), diff(used, base)),
      trait: Number(deck.trait_card_id !== active.trait_card_id),
      ultimate: Number(ult(base) !== ult(used)),
    };
    for (const [kind, n] of Object.entries(changes))
      if (n > Number(policy[`${kind}_swap_limit` as keyof typeof policy]))
        add(`${kind}_swap_limit`, `${kind}: 교체 한도를 초과했습니다.`);
  }
  for (const key of ["bans", "combinations"] as const)
    for (const rule of policy[key]) {
      const pool = rule.scope === "registered" ? registered : activeCounts,
        matched = rule.card_ids.filter((id) => (pool.get(id) || 0) > 0);
      if (
        matched.length &&
        (key === "bans" || matched.length === rule.card_ids.length)
      )
        add(
          key === "bans" ? "banned_card" : "restricted_combination",
          `${key === "bans" ? "금지 카드" : "제한 조합"}: ${matched.map((id) => cards.get(id)?.original_name || cards.get(id)?.localized.ko?.name || id).join(" + ")}`,
          matched,
        );
    }
  if (
    issues.some((i) =>
      ["invalid_count", "unknown_card", "invalid_placement"].includes(i.code),
    )
  )
    return { issues, stats };
  const rules = deckRulesFor(
    catalog,
    deck.character_id,
    active.trait_card_id,
    active.cards,
  );
  const configured = rules.main_size,
    minimum =
      typeof configured === "number" ? configured : (configured?.min ?? 20),
    maximum =
      typeof configured === "number"
        ? configured
        : (configured?.max ?? minimum);
  const supplements = rules.supplements || [],
    supplementCounts = supplements.map(() => 0),
    supplementOwn = supplements.map(() => 0),
    imported = new Map<number, number>(),
    names = new Map<string, { n: number; limit: number; ids: number[] }>();
  let total = 0,
    own = 0,
    ultimate = 0,
    hand = 0,
    list = 0;
  for (const e of active.cards) {
    const c = cards.get(e.card_id)!,
      matching = supplements
        .map((s: any, i: number) => (matches(c, s.where) ? i : -1))
        .filter((i: number) => i >= 0),
      supplement = matching.length ? supplements[matching[0]] : {};
    for (const i of matching) {
      supplementCounts[i] += e.count;
      if (c.character_id === deck.character_id) supplementOwn[i] += e.count;
    }
    const allowed = rules.allowed_character_ids || [deck.character_id, 1],
      foreign = rules.other_character_cards || {};
    const isImported =
      !allowed.includes(c.character_id) &&
      !(foreign.exclude_character_ids || []).includes(c.character_id) &&
      (foreign.allowed_types || []).includes(c.type) &&
      (!foreign.exclude_ultimate || !c.ultimate);
    if (
      !allowed.includes(c.character_id) &&
      !isImported &&
      !supplement.allow_foreign_mark
    )
      add(
        "deck_composition",
        "사용할 수 없는 캐릭터 마크가 포함되어 있습니다.",
        [c.id],
      );
    if (isImported)
      imported.set(
        c.character_id,
        (imported.get(c.character_id) || 0) + e.count,
      );
    if (c.ultimate) {
      ultimate += e.count;
      if (stage === "setup" && (e.hand || e.side))
        add(
          "deck_composition",
          "얼티밋은 패·사이드 대신 얼티밋 영역에 배치해주세요.",
          [c.id],
        );
      continue;
    }
    if (
      (isTrait(c) ||
        !["공격", "수비", "특수"].some((t) => c.type.includes(t))) &&
      !supplement.allow_non_technique
    )
      add(
        "deck_composition",
        "기술 덱에는 공격·수비·특수 기술만 넣을 수 있습니다.",
        [c.id],
      );
    total += e.count;
    if (c.character_id === deck.character_id) own += e.count;
    const name = cardName(c),
      limit = sameNameLimit(c, rules);
    const previous = names.get(name) || { n: 0, limit: 0, ids: [] };
    names.set(name, {
      n: previous.n + e.count,
      limit: Math.max(previous.limit, limit),
      ids: [...previous.ids, c.id],
    });
    if (c.type.includes("특수")) {
      if (
        rules.special_allowed_character_ids &&
        !rules.special_allowed_character_ids.includes(c.character_id)
      )
        add("deck_composition", "허용되지 않은 캐릭터의 특수 기술입니다.", [
          c.id,
        ]);
      if (stage === "setup" && (e.hand || e.side !== e.count))
        add("deck_composition", "특수 기술은 전부 사이드 덱에 있어야 합니다.", [
          c.id,
        ]);
    } else {
      hand += e.hand;
      list += e.count - e.hand - e.side;
    }
  }
  if (total < minimum || total > maximum)
    add(
      "deck_composition",
      `기술 카드는 ${minimum === maximum ? minimum : `${minimum}~${maximum}`}장이어야 합니다. (현재 ${total}장)`,
    );
  const allocated = supplements.map((s: any, i: number) =>
    s.allow_base_copies ? 0 : supplementCounts[i],
  );
  let extra = Math.max(
    0,
    total - minimum - allocated.reduce((a: number, b: number) => a + b, 0),
  );
  supplements.forEach((s: any, i: number) => {
    if (s.allow_base_copies) {
      allocated[i] = Math.min(supplementCounts[i], s.max_count || 0, extra);
      extra -= allocated[i];
    } else if (supplementCounts[i] > (s.max_count || 0))
      add("deck_composition", "보충 카드 제한을 초과했습니다.");
  });
  if (
    configured?.base_excludes_supplements &&
    total - allocated.reduce((a: number, b: number) => a + b, 0) !== minimum
  )
    add(
      "deck_composition",
      "보충 카드를 제외한 기본 기술 덱 매수가 올바르지 않습니다.",
    );
  const ownBase =
    own -
    allocated.reduce(
      (sum: number, n: number, i: number) =>
        sum + Math.min(n, supplementOwn[i]),
      0,
    );
  if (ownBase < (rules.character_card_minimum ?? 10))
    add(
      "deck_composition",
      `캐릭터 마크 기술은 최소 ${rules.character_card_minimum ?? 10}장이어야 합니다. (현재 ${ownBase}장)`,
    );
  names.forEach((row) => {
    if (row.n > row.limit)
      add("deck_composition", "동일 이름 카드 제한을 초과했습니다.", row.ids);
  });
  if (
    typeof rules.other_character_cards?.max_per_character === "number" &&
    [...imported.values()].some(
      (n) => n > rules.other_character_cards.max_per_character,
    )
  )
    add("deck_composition", "타 캐릭터 마크별 카드 제한을 초과했습니다.");
  if (ultimate > (rules.ultimate_maximum ?? 1))
    add("deck_composition", "얼티밋 카드는 1장까지만 허용됩니다.");
  if (stage === "setup") {
    if (hand !== (rules.opening_hand_size ?? 5))
      add(
        "deck_composition",
        `시작 패는 ${rules.opening_hand_size ?? 5}장이어야 합니다.`,
      );
    if (list !== (rules.opening_list_size ?? 9))
      add(
        "deck_composition",
        `시작 리스트는 ${rules.opening_list_size ?? 9}장이어야 합니다.`,
      );
  }
  Object.assign(stats, {
    total,
    minimum,
    maximum,
    own: ownBase,
    ownMinimum: rules.character_card_minimum ?? 10,
    hand,
    handTarget: rules.opening_hand_size ?? 5,
    list,
    listTarget: rules.opening_list_size ?? 9,
  });
  return { issues, stats };
}

export function characterWithTrait(
  character: import("./types").Character,
  id?: number | null,
): import("./types").Character {
  const choices = character.traits;
  if (!choices) return character;
  const trait =
    choices.find((t) => t.id === id) ||
    (choices.length === 1 ? choices[0] : undefined);
  if (!trait) throw new Error("사용할 특성을 선택해주세요.");
  return {
    ...character,
    initial_hp: trait.initial_hp,
    hand_table: trait.hand_table,
    initial_passive_state: trait.initial_passive_state,
    localized: Object.fromEntries(
      Object.entries(character.localized).map(([lang, fields]) => [
        lang,
        {
          ...fields,
          passive: trait.localized[lang as "ko" | "en" | "ja"]?.passive || {
            controls: [],
          },
        },
      ]),
    ),
    ...({
      selected_trait_id: trait.id,
      selected_trait_config: trait.trait_config,
    } as any),
  };
}
