import type { Catalog, Deck } from "./types";

export function importDeckCode(
  text: string,
  catalog: Catalog,
  uuid: string,
): Deck {
  const data = JSON.parse(text);
  if (
    !data ||
    data.schema_version !== 2 ||
    !catalog.characters.some((c) => c.id === data.character_id)
  )
    throw new Error("지원하는 캐릭터의 덱 코드를 입력해주세요.");
  function rows(value: unknown, placement: boolean) {
    if (!Array.isArray(value) || value.length > 1000)
      throw new Error("카드 목록이 올바르지 않습니다.");
    return value.map((row) => {
      if (
        !row ||
        !Number.isInteger(row.card_id) ||
        row.card_id < 1 ||
        !Number.isInteger(row.count) ||
        row.count < 1 ||
        row.count > 1000
      )
        throw new Error("카드 번호와 수량을 확인해주세요.");
      const hand = row.hand ?? 0,
        side = row.side ?? 0;
      if (
        placement &&
        (![hand, side].every((n) => Number.isInteger(n) && n >= 0) ||
          hand + side > row.count)
      )
        throw new Error("시작 배치 수량을 확인해주세요.");
      return placement
        ? { card_id: row.card_id, count: row.count, hand, side }
        : { card_id: row.card_id, count: row.count };
    });
  }
  return {
    uuid,
    schema_version: 2,
    name: typeof data.name === "string" ? data.name.slice(0, 255) : "가져온 덱",
    character_id: data.character_id,
    trait_card_id: data.trait_card_id ?? null,
    cards: rows(data.cards, true) as Deck["cards"],
    reserve_cards: rows(data.reserve_cards || [], false),
    regulation_version_id: data.regulation_version_id ?? null,
    regulation_rules: data.regulation_rules,
    regulation: data.regulation,
    imported_regulation: data.regulation,
    description:
      typeof data.description === "string"
        ? data.description.slice(0, 100000)
        : "",
    keyword: typeof data.keyword === "string" ? data.keyword.slice(0, 255) : "",
    tags: typeof data.tags === "string" ? data.tags.slice(0, 255) : "",
    visibility: "private",
  };
}
