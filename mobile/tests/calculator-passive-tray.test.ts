import test from "node:test";
import assert from "node:assert/strict";
import { passiveGet } from "../src/core";
import {
  conditionText,
  passiveTray,
  pipValue,
  trayAction,
} from "../src/calculator-passive-tray";
import type { Action, PassiveDefinition, Player } from "../src/types";

function player(state: Record<string, unknown> = {}, hp = 5000): Player {
  return {
    name: "A",
    hp,
    fp: 0,
    initial_hp: 5000,
    passive_state: Object.fromEntries(
      Object.entries(state).map(([k, v]) => [k, { value: v } as any]),
    ),
    character: { calculator_ui: { theme_key: "wolf" } },
  };
}
function apply(p: Player, action: Action | null): Player {
  assert.ok(action, "action expected");
  const list = action.action === "batch" ? (action as any).actions : [action];
  const next = { ...p, passive_state: { ...p.passive_state } };
  for (const a of list) next.passive_state[a.key] = { value: a.value } as any;
  return next;
}

const wolf: PassiveDefinition = {
  controls: [
    { type: "counter", key: "howling_counter", label: "하울링 카운터", max: 5 },
    {
      type: "thresholdAction",
      key: "pressure",
      label: "위압",
      requires: { type: "counterAtLeast", key: "howling_counter", value: 5 },
      resetKeys: ["howling_counter"],
    },
  ],
};
const tao: PassiveDefinition = {
  adapter: "tao",
  controls: [
    { type: "counter", key: "yang_counter", label: "양", max: 4 },
    { type: "counter", key: "yin_counter", label: "음", max: 4 },
    {
      type: "latchedStatus",
      key: "harmony",
      label: "조화",
      activateWhen: { type: "allEquals", keys: ["yang_counter", "yin_counter"], value: 4 },
      keepWhile: { type: "allAtLeast", keys: ["yang_counter", "yin_counter"], value: 3 },
    },
    {
      type: "choice",
      key: "harmony_effect",
      label: "조화 효과",
      enableWhen: { type: "active", key: "harmony" },
      choices: [
        { value: "damage_100", label: "+100DMG" },
        { value: "fp_1", label: "+1FP" },
      ],
    },
  ],
};

test("threshold actions explain their requirement and reset the counter when used", () => {
  let p = player();
  let [, pressure] = passiveTray(p, wolf);
  assert.equal(pressure!.kind, "trigger");
  assert.equal(pressure!.enabled, false);
  assert.equal(pressure!.hint, "하울링 카운터 5 이상 필요");
  assert.equal(trayAction(p, wolf, "p1", "pressure", true), null);
  p = player({ howling_counter: 5 });
  [, pressure] = passiveTray(p, wolf);
  assert.ok(pressure!.ready && pressure!.enabled);
  assert.equal(pressure!.attention, true);
  assert.equal(pressure!.hint, "사용 시 하울링 카운터 초기화");
  p = apply(p, trayAction(p, wolf, "p1", "pressure", true));
  assert.equal(passiveGet(p, "howling_counter"), 0);
  assert.equal(passiveGet(p, "pressure"), true);
  // 발동 중에는 카운터가 0이어도 끌 수 있다.
  assert.ok(passiveTray(p, wolf)[1]!.enabled);
});

test("counters clamp to their range and pips toggle the last filled cell", () => {
  const p = player({ howling_counter: 3 });
  assert.deepEqual(trayAction(p, wolf, "p1", "howling_counter", 9)?.value, 5);
  assert.deepEqual(trayAction(p, wolf, "p1", "howling_counter", -2)?.value, 0);
  assert.equal(pipValue(3, 2), 2);
  assert.equal(pipValue(3, 0), 1);
  assert.equal(pipValue(0, 4), 5);
  assert.equal(passiveTray(p, wolf)[0]!.symbol, "claw");
  assert.equal(passiveTray(p, wolf)[0]!.art, "claw");
  assert.equal(passiveTray(p, wolf)[1]!.art, "pressure");
});

test("tao harmony becomes an automatic status and locks counters until an effect is chosen", () => {
  let p = player({ yang_counter: 4, yin_counter: 3 });
  let [yang, , harmony, effect] = passiveTray(p, tao);
  assert.equal(harmony!.kind, "status");
  assert.equal(harmony!.active, false);
  assert.equal(harmony!.hint, "자동 · 양·음 모두 4");
  assert.equal(effect!.enabled, false);
  assert.equal(effect!.hint, "조화일 때 선택");
  p = apply(p, trayAction(p, tao, "p1", "yin_counter", 4));
  assert.equal(passiveGet(p, "harmony"), true);
  [yang, , harmony, effect] = passiveTray(p, tao);
  assert.ok(harmony!.active);
  assert.equal(harmony!.hint, "자동 · 유지 양·음 모두 3 이상");
  assert.equal(yang!.enabled, false);
  assert.equal(yang!.hint, "조화 효과를 먼저 선택");
  assert.equal(effect!.attention, true);
  p = apply(p, trayAction(p, tao, "p1", "harmony_effect", "fp_1"));
  assert.equal(passiveGet(p, "harmony_effect"), "fp_1");
  assert.ok(passiveTray(p, tao)[0]!.enabled);
  // 같은 효과를 다시 누르면 선택이 풀린다.
  p = apply(p, trayAction(p, tao, "p1", "harmony_effect", "fp_1"));
  assert.equal(passiveGet(p, "harmony_effect"), "");
});

test("status conditions read naturally in every language", () => {
  const def: PassiveDefinition = {
    controls: [{ type: "status", key: "blue_flame", label: "청염", condition: { type: "hpAtMost", value: 2500 } }],
  };
  assert.equal(passiveTray(player({}, 3000), def)[0]!.hint, "자동 · HP 2500 이하");
  assert.equal(passiveTray(player({}, 2500), def)[0]!.active, true);
  assert.equal(conditionText({ type: "hpAtMost", value: 2500 }, def, "en"), "HP ≤ 2500");
  assert.equal(conditionText({ type: "hpAtMost", value: 2500 }, def, "ja"), "HP 2500以下");
  assert.equal(trayAction(player(), def, "p1", "blue_flame", true), null);
});

test("choices clear when the selected value is chosen again", () => {
  const def: PassiveDefinition = {
    controls: [
      {
        type: "choice",
        key: "role",
        label: "레기온",
        choices: [
          { value: "guardian", label: "가디언" },
          { value: "assassin", label: "어쌔신" },
        ],
      },
    ],
  };
  let p = apply(player(), trayAction(player(), def, "p1", "role", "guardian"));
  assert.equal(passiveTray(p, def)[0]!.choices![0]!.selected, true);
  p = apply(p, trayAction(p, def, "p1", "role", "guardian"));
  assert.equal(passiveGet(p, "role"), "");
});
