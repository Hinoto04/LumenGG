import test from "node:test";
import assert from "node:assert/strict";
import { cardCrop, cropBackground, hpBar, hpButtonRows, passiveGroups, passiveLayout, withCalculatorExtras } from "../src/calculator-layout";
import { calculatorAppearance } from "../src/calculator-appearance";
import { passiveTray, type TrayItem } from "../src/calculator-passive-tray";

const item = (key: string, kind: TrayItem["kind"], extra: Partial<TrayItem> = {}): TrayItem => ({
  key,
  kind,
  label: key,
  active: false,
  enabled: true,
  hint: "",
  ...extra,
});

test("HP buttons: 4 or 4x2, shield characters always 4 with mirrored order for P2", () => {
  assert.deepEqual(hpButtonRows("4", false), [[-500, -100, 100, 500]]);
  assert.deepEqual(hpButtonRows(null, false), [[-500, -100, 100, 500]]);
  assert.deepEqual(hpButtonRows("8", false), [
    [-600, -500, -400, -300],
    [-200, -100, 100, 200],
  ]);
  assert.deepEqual(hpButtonRows("8", true), [[-500, -100, 100, 500]]);
  assert.deepEqual(hpButtonRows("4", false, true), [[500, 100, -100, -500]]);
});

test("HP bar puts the shield after health and fills to the right end at full health", () => {
  assert.deepEqual(hpBar(2500, 5000, 0), { hp: 0.5, shield: 0, ratio: 0.5 });
  const full = hpBar(5500, 5500, 300);
  assert.ok(Math.abs(full.hp + full.shield - 1) < 1e-9);
  assert.ok(full.shield > 0 && full.hp < 1);
  const partial = hpBar(4000, 5000, 500);
  assert.equal(partial.hp, 0.8);
  assert.equal(partial.shield, 0.1);
});

test("passive layout: one large card, two cards, or a list with paired counters and status-choice rows", () => {
  assert.equal(passiveLayout([item("over_limit", "toggle")]), "hero");
  assert.equal(passiveLayout([item("howling", "counter", { max: 5 }), item("pressure", "trigger")]), "split");
  const tao = [
    item("yang_counter", "counter", { max: 4 }),
    item("yin_counter", "counter", { max: 4 }),
    item("harmony", "status"),
    item("harmony_effect", "choice"),
  ];
  assert.equal(passiveLayout(tao), "list");
  assert.deepEqual(
    passiveGroups(tao).map((group) => group.kind),
    ["pair", "status-choice"],
  );
});

test("card crops keep their aspect and the appearance keeps an unset HP button choice", () => {
  const crop = cardCrop("unknown", "a", 0);
  assert.deepEqual(cropBackground({ x: 0.2, y: 0.1, w: 0.5, h: 0.3 }), { size: "200.00% auto", position: "40.00% 14.29%" });
  assert.ok(crop.w > 0 && crop.w < 1);
  assert.notDeepEqual(cardCrop("unknown", "b", 1), crop);
  assert.equal(calculatorAppearance({}).hpButtons, null);
  assert.equal(calculatorAppearance({ hpButtons: "8" }).hpButtons, "8");
  assert.equal(calculatorAppearance({ hpButtons: "6" }).hpButtons, null);
});

test("token counters carry their token card image", () => {
  const player: any = { hp: 5000, fp: 0, passive_state: {}, character: { initial_passive_state: {} } };
  const definition: any = {
    controls: [
      { type: "counter", key: "garage_token", label: "개러지 토큰", max: 3, token: { code: "CB04-TK-001", img: "garage.webp" } },
      { type: "counter", key: "plain", label: "plain", max: 3 },
    ],
  };
  const [garage, plain] = passiveTray(player, definition);
  assert.equal(garage!.token, "garage.webp");
  assert.equal("token" in plain!, false);
});

test("app catalog fills token card images and the foresight max like the server", () => {
  const cards: any[] = [
    { id: 1, character_id: 4, type: "토큰", img: "garage.webp", code: "CB04-TK-001", localized: { ko: { name: "「개러지」" } } },
    { id: 2, character_id: 8, type: "토큰", img: "yang.webp", localized: { ko: { name: "「양」 토큰" } } },
    { id: 3, character_id: 4, type: "공격", img: "attack.webp", localized: { ko: { name: "개러지 어택" } } },
  ];
  const delphy = withCalculatorExtras({ controls: [{ type: "counter", key: "garage_token", label: "Garage" }] }, 4, cards, { garage_token: "개러지 토큰" });
  assert.equal(delphy.controls[0].token.img, "garage.webp");
  const yohan = withCalculatorExtras({ controls: [{ type: "counter", key: "foresight_counter", label: "예지 카운터", max: 10 }] }, 12, cards);
  assert.equal(yohan.controls[0].max, 5);
  assert.equal(yohan.controls[0].token, undefined);
  const untouched = { controls: [{ type: "toggle", key: "x", label: "x" }] };
  assert.equal(withCalculatorExtras(untouched, 4, cards), untouched);
});
