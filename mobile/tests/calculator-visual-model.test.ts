import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { newCalculator, reduceCalculator, passiveGet } from "../src/core";
import {
  harmonyState,
  steppedCounter,
  taoInputLocked,
  visualAction,
  visualDefinition,
  visualEnabled,
  visualValue,
} from "../src/calculator-visual-model";
import type { Action, Character } from "../src/types";
function calculator(theme: string) {
  const c = {
    id: 1,
    color: "#fff",
    img: "",
    img_sm: "",
    initial_hp: 5000,
    initial_passive_state: {},
    hand_table: { "5000": 6 },
    localized: { ko: { name: theme, passive: visualDefinition(theme) } },
  } as unknown as Character;
  return newCalculator(c, c, "ko");
}
test("token clicks always change one token and never leave gaps or exceed the existing cap", () => {
  let state = calculator("viola");
  const control = visualDefinition("viola").controls[0]!;
  for (let i = 0; i < 4; i++) {
    const value = steppedCounter(state.players.p1, control, false);
    state = reduceCalculator(
      state,
      visualAction("viola", state.players.p1, "p1", control.key, value)!,
    );
  }
  assert.equal(passiveGet(state.players.p1, "silver_counter"), 3);
  state = reduceCalculator(
    state,
    visualAction(
      "viola",
      state.players.p1,
      "p1",
      control.key,
      steppedCounter(state.players.p1, control, true),
    )!,
  );
  assert.equal(passiveGet(state.players.p1, "silver_counter"), 2);
  assert.equal(state.players.p1.hp, 5000);
  assert.equal(state.players.p1.fp, 0);
});
test("Tao locks counters only while choosing; effect selection changes no HP or FP", () => {
  let state = calculator("tao");
  for (const key of ["yang_counter", "yin_counter"])
    state = reduceCalculator(
      state,
      visualAction("tao", state.players.p1, "p1", key, 4)!,
    );
  assert(harmonyState(state.players.p1));
  assert(taoInputLocked(state.players.p1));
  assert.equal(
    visualAction("tao", state.players.p1, "p1", "yang_counter", 3),
    null,
  );
  state = reduceCalculator(
    state,
    visualAction("tao", state.players.p1, "p1", "harmony_effect", "fp_1")!,
  );
  assert(!taoInputLocked(state.players.p1));
  assert.equal(state.players.p1.fp, 0);
  assert.equal(state.players.p1.hp, 5000);
  state = reduceCalculator(
    state,
    visualAction("tao", state.players.p1, "p1", "yang_counter", 3)!,
  );
  assert(harmonyState(state.players.p1));
  state = reduceCalculator(
    state,
    visualAction("tao", state.players.p1, "p1", "yang_counter", 2)!,
  );
  assert(!harmonyState(state.players.p1));
  assert.equal(passiveGet(state.players.p1, "harmony_effect"), "");
});
test("a restored 4/4 Tao state without the stored latch can still choose an effect", () => {
  const state = calculator("tao");
  state.players.p1.passive_state = {
    yang_counter: { value: 4 },
    yin_counter: { value: 4 },
  };
  const action = visualAction(
    "tao",
    state.players.p1,
    "p1",
    "harmony_effect",
    "damage_100",
  );
  assert(action);
  const next = reduceCalculator(state, action);
  assert.equal(passiveGet(next.players.p1, "harmony"), true);
  assert.equal(passiveGet(next.players.p1, "harmony_effect"), "damage_100");
});
test("Rita role can be selected, replaced and turned off without changing Lumen", () => {
  let state = calculator("rita");
  for (const value of ["guardian", "assassin", ""])
    state = reduceCalculator(
      state,
      visualAction("rita", state.players.p1, "p1", "rita_role", value)!,
    );
  assert.equal(passiveGet(state.players.p1, "rita_role"), "");
  assert.equal(passiveGet(state.players.p1, "light_lumen", false), false);
});
test("Wolf threshold still requires five counters and consumes them on activation", () => {
  let state = calculator("wolf");
  const pressure = visualDefinition("wolf").controls.find(
    (c) => c.key === "pressure",
  )!;
  assert(!visualEnabled(state.players.p1, pressure));
  assert.equal(
    visualAction("wolf", state.players.p1, "p1", "pressure", true),
    null,
  );
  state = reduceCalculator(
    state,
    visualAction("wolf", state.players.p1, "p1", "howling_counter", 5)!,
  );
  state = reduceCalculator(
    state,
    visualAction("wolf", state.players.p1, "p1", "pressure", true)!,
  );
  assert.equal(passiveGet(state.players.p1, "howling_counter"), 0);
  assert.equal(passiveGet(state.players.p1, "pressure"), true);
});
test("packaged web and native adapters produce identical actions", () => {
  const context: any = {};
  vm.runInNewContext(
    fs.readFileSync(
      new URL(
        "../../LumenGG/static/v2/calculator-visual-model.js",
        import.meta.url,
      ),
      "utf8",
    ),
    context,
  );
  const player = calculator("tao").players.p1;
  const web = context.CalculatorVisualModel.visualAction(
    "tao",
    player,
    "p1",
    "yang_counter",
    4,
    "ja",
  );
  const native = visualAction("tao", player, "p1", "yang_counter", 4, "ja");
  assert.deepEqual(JSON.parse(JSON.stringify(web)), native);
});

test("visual defaults never invent a different server resource value", () => {
  const state = calculator("yohan");
  const control = visualDefinition("yohan").controls[0]!;
  assert.equal(visualValue(state.players.p1, control), 0);
  state.players.p1.character.initial_passive_state = {
    foresight_counter: { value: 2 },
  };
  assert.equal(visualValue(state.players.p1, control), 2);
  state.players.p1.passive_state.foresight_counter = { value: 0 };
  assert.equal(visualValue(state.players.p1, control), 0);
});
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
test("supported offline passive keys and bounds remain available, excluding obsolete Iomong controls", () => {
  const db = new DatabaseSync(
    fileURLToPath(new URL("../assets/catalog.sqlite", import.meta.url)),
    { readOnly: true },
  );
  const themes = JSON.parse(
    fs.readFileSync(
      new URL("../src/calculator-themes.json", import.meta.url),
      "utf8",
    ),
  );
  try {
    for (const theme of themes) {
      const row = db
        .prepare("SELECT data FROM entries WHERE kind='character' AND id=?")
        .get(theme.id) as { data: string };
      const existing = JSON.parse(row.data).localized.ko.passive.controls || [];
      const visual = visualDefinition(theme.theme_key).controls;
      if (theme.theme_key === "iomong") {
        assert.deepEqual(visual, []);
        continue;
      }
      for (const control of existing) {
        const match = visual.find((c) => c.key === control.key);
        assert(match, theme.theme_key + ": missing " + control.key);
        assert.equal(match.type, control.type);
        assert.equal(match.max, control.max);
      }
    }
  } finally {
    db.close();
  }
});

test("Iomong leaves restored legacy data untouched without exposing a passive action", () => {
  const state = calculator("iomong");
  state.players.p1.passive_state = { "364": { value: 3 } };
  assert.deepEqual(visualDefinition("iomong").controls, []);
  assert.equal(visualAction("iomong", state.players.p1, "p1", "364", 4), null);
  assert.equal(passiveGet(state.players.p1, "364"), 3);
});
