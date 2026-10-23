import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { deckIssues, characterWithTrait, isTrait } from "../src/deck-rules";
import { newCalculator } from "../src/core";
import { supportsShield } from "../src/calculator-shield";
import type { Catalog, Deck } from "../src/types";

const cases = JSON.parse(
  readFileSync(
    new URL(
      "../../LumenGG/content/deck-validation-cases.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
for (const fixture of cases)
  test(`server/app validation: ${fixture.name}`, () => {
    const s = fixture.snapshot;
    const catalog: Catalog = {
      version: "fixture",
      schema_version: 2,
      cards: Object.values(s.catalog).map((c: any) => ({
        ...c,
        original_name: c.name,
        localized: { ko: { name: c.name, text: c.text } },
        setup_rules: c.effect_definition.deck_rules_when_included,
      })),
      characters: [
        {
          id: 2,
          localized: { ko: { name: "Fixture" } },
          initial_hp: 5000,
          hand_table: { 5000: 5 },
          initial_passive_state: {},
          traits: Object.values(s.catalog)
            .filter((c: any) => isTrait(c))
            .map((c: any) => ({
              ...c,
              deck_rules: c.effect_definition.deck_rules,
              initial_hp: 5000,
              hand_table: { 5000: 5 },
              initial_passive_state: {},
              localized: { ko: { name: c.name } },
            })),
        } as any,
      ],
      packs: [],
      collection: [],
      qna: [],
      rules: { regulations: [] },
    } as any;
    const deck: Deck = {
      uuid: "fixture",
      name: "Fixture",
      description: "",
      keyword: "",
      tags: "",
      visibility: "private",
      ...s,
    };
    const issues = deckIssues(
      deck,
      catalog,
      fixture.stage,
      fixture.active || deck,
    );
    assert.equal(
      !issues.some((i) => i.severity === "error"),
      fixture.valid,
      JSON.stringify(issues),
    );
    assert.deepEqual(
      [...new Set(issues.map((i) => i.code))].sort(),
      fixture.codes.sort(),
    );
  });
test("selected trait preserves theme while owning its counters and shield support", () => {
  const character: any = {
    id: 1,
    localized: {
      ko: { name: "핀프", passive: { controls: [{ key: "old" }] } },
    },
    initial_hp: 5000,
    hand_table: { 5000: 5 },
    initial_passive_state: { old: { count: 5 } },
    traits: [
      {
        id: 10,
        trait_config: { supports_shield: false },
        initial_hp: 4000,
        hand_table: { 4000: 4 },
        initial_passive_state: { fresh: { count: 2 } },
        localized: {
          ko: { name: "New", passive: { controls: [{ key: "fresh" }] } },
        },
      },
    ],
  };
  const selected = characterWithTrait(character, 10),
    state = newCalculator(selected, selected, "ko");
  assert.equal(state.players.p1.initial_hp, 4000);
  assert.deepEqual(state.players.p1.passive_state, { fresh: { count: 2 } });
  assert.equal(supportsShield(state.players.p1), false);
  assert.equal(state.players.p1.character.trait_card_id, 10);
});
