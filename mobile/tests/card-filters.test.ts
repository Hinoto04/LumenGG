import { test } from "node:test";
import assert from "node:assert/strict";
import {
  activeCardFilters,
  emptyCardFilters,
  filterError,
  matchesCardFilters,
  rangeLabel,
  withoutCardFilter,
} from "../src/card-filters";
import type { Card } from "../src/types";

const card = (id: number, values: Partial<Card> = {}) =>
  ({
    id,
    character_id: 1,
    type: "공격",
    pos: "상단",
    frame: 5,
    damage: 400,
    ...values,
  }) as Card;

test("filter groups combine and numeric ranges include their endpoints", () => {
  const filters = {
    ...emptyCardFilters,
    character: "2",
    type: "공격",
    pos: "하단",
    frameMin: "3",
    frameMax: "5",
    damageMin: "300",
    damageMax: "500",
  };
  const cards = [
    card(1, { character_id: 2, pos: "하단", frame: 3, damage: 300 }),
    card(2, { character_id: 2, pos: "하단", damage: 500 }),
    card(3, { pos: "하단" }),
    card(4, { character_id: 2 }),
    card(5, { character_id: 2, pos: "하단", type: "수비" }),
    card(6, { character_id: 2, pos: "하단", frame: 6 }),
  ];
  assert.equal(filterError(filters), null);
  assert.deepEqual(
    cards.filter((c) => matchesCardFilters(c, filters)).map((c) => c.id),
    [1, 2],
  );
});
test("zero is a real bound and non-numeric card values only survive inactive ranges", () => {
  const filters = { ...emptyCardFilters, damageMax: "0" };
  assert.equal(matchesCardFilters(card(1, { damage: 0 }), filters), true);
  assert.equal(matchesCardFilters(card(2), filters), false);
  assert.equal(matchesCardFilters(card(3, { damage: null }), filters), false);
  assert.equal(
    matchesCardFilters(
      card(4, { damage: null, frame: null }),
      emptyCardFilters,
    ),
    true,
  );
});
test("invalid and reversed bounds cannot be applied as an empty result", () => {
  for (const value of ["NaN", "1.5", "1e3", "Infinity", "9007199254740992"])
    assert.ok(filterError({ ...emptyCardFilters, frameMin: value }));
  assert.ok(
    filterError({ ...emptyCardFilters, damageMin: "500", damageMax: "100" }),
  );
  assert.equal(
    filterError({ ...emptyCardFilters, damageMin: "100", damageMax: "100" }),
    null,
  );
});

test("active filter chips list only set conditions and clear ranges together", () => {
  const filters = {
    ...emptyCardFilters,
    character: "3",
    pos: "상단",
    frameMin: "2",
    damageMax: "4",
  };
  assert.deepEqual(activeCardFilters(emptyCardFilters), []);
  assert.deepEqual(
    activeCardFilters(filters).map((f) => f.key),
    ["character", "pos", "frame", "damage"],
  );
  const cleared = withoutCardFilter({ ...filters, frameMax: "5" }, "frame");
  assert.equal(cleared.frameMin, "");
  assert.equal(cleared.frameMax, "");
  assert.equal(cleared.character, "3");
  assert.equal(withoutCardFilter(filters, "pos").pos, "");
});

test("range labels collapse equal bounds and one-sided ranges", () => {
  const t = (key: string) => ({ 이상: "or more", 이하: "or less" })[key] ?? key;
  assert.equal(rangeLabel("3", "5", t), "3–5");
  assert.equal(rangeLabel("4", "4", t), "4");
  assert.equal(rangeLabel("2", "", t), "2 or more");
  assert.equal(rangeLabel("", "6", t), "6 or less");
});
