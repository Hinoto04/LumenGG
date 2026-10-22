import test from "node:test";
import assert from "node:assert/strict";
import {
  PassiveInputQueue,
  compactPassiveActions,
  projectPassiveInputs,
  isPassiveInput,
} from "../src/calculator-passive-queue";
import { newCalculator, reduceCalculator, passiveGet } from "../src/core";
import {
  visualAction,
  visualDefinition,
  harmonyState,
  taoInputLocked,
} from "../src/calculator-visual-model";
import type { Action, Character } from "../src/types";

class Clock {
  time = 0;
  serial = 0;
  tasks = new Map<number, { at: number; fn: () => void }>();
  now = () => this.time;
  later = (fn: () => void, delay: number) => {
    const id = ++this.serial;
    this.tasks.set(id, { at: this.time + delay, fn });
    return id;
  };
  cancel = (id: unknown) => {
    this.tasks.delete(id as number);
  };
  advance(ms: number) {
    const end = this.time + ms;
    for (;;) {
      const next = [...this.tasks]
        .filter(([, v]) => v.at <= end)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.time = next[1].at;
      this.tasks.delete(next[0]);
      next[1].fn();
    }
    this.time = end;
  }
}
const settle = () => new Promise<void>((resolve) => setImmediate(resolve));
function harness(theme = "viola") {
  const c = {
    id: 1,
    initial_hp: 5000,
    initial_passive_state: {},
    hand_table: { 5000: 6 },
    localized: { ko: { name: theme, passive: visualDefinition(theme) } },
  } as unknown as Character;
  let saved = newCalculator(c, c, "ko"),
    pending: Action[] = [];
  const sent: Action[] = [];
  const clock = new Clock();
  const queue = new PassiveInputQueue(
    async (action) => {
      sent.push(action);
      saved = reduceCalculator(saved, action);
    },
    (actions) => {
      pending = actions;
    },
    clock,
  );
  const view = () => projectPassiveInputs(saved, pending)!;
  return {
    queue,
    clock,
    sent,
    view,
    saved: () => saved,
    set(key: string, value: unknown, target: "p1" | "p2" = "p1") {
      const a = visualAction(theme, view().players[target], target, key, value);
      assert(a, key);
      queue.add(a);
    },
  };
}
test("counter preview is immediate; last input +900ms stores one final value and one record", async () => {
  const h = harness();
  h.set("silver_counter", 1);
  h.clock.advance(300);
  h.set("silver_counter", 2);
  h.clock.advance(300);
  h.set("silver_counter", 3);
  assert.equal(passiveGet(h.view().players.p1, "silver_counter"), 3);
  assert.equal(h.saved().events.length, 0);
  h.clock.advance(899);
  await settle();
  assert.equal(h.sent.length, 0);
  h.clock.advance(1);
  await settle();
  assert.equal(h.sent.length, 1);
  assert.equal(h.saved().events.length, 1);
  assert.equal(passiveGet(h.saved().players.p1, "silver_counter"), 3);
});
test("players have independent input deadlines", async () => {
  const h = harness();
  h.set("silver_counter", 1);
  h.clock.advance(200);
  h.set("silver_counter", 2, "p2");
  h.clock.advance(700);
  await settle();
  assert.equal(h.sent.length, 1);
  assert.equal(h.sent[0]!.target, "p1");
  h.clock.advance(200);
  await settle();
  assert.equal(h.sent.length, 2);
  assert.equal(h.sent[1]!.target, "p2");
});
test("Tao harmony, choice lock, retention and clearing follow the preview and commit atomically", async () => {
  const h = harness("tao");
  for (let n = 1; n <= 4; n++) h.set("yang_counter", n);
  for (let n = 1; n <= 4; n++) h.set("yin_counter", n);
  assert(harmonyState(h.view().players.p1));
  assert(taoInputLocked(h.view().players.p1));
  h.set("harmony_effect", "damage_100");
  assert(!taoInputLocked(h.view().players.p1));
  h.set("yin_counter", 3);
  assert(harmonyState(h.view().players.p1));
  h.set("yin_counter", 2);
  assert(!harmonyState(h.view().players.p1));
  h.clock.advance(900);
  await settle();
  assert.equal(h.sent.length, 1);
  assert.equal(passiveGet(h.saved().players.p1, "harmony_effect"), "");
  assert.equal(passiveGet(h.saved().players.p1, "harmony"), false);
  assert.equal(passiveGet(h.saved().players.p1, "yin_counter"), 2);
  const all = h.sent[0]!.actions!;
  assert.equal(new Set(all.map((a) => a.key)).size, all.length);
});
test("Wolf activation, token consumption and subsequent gain keep their meaning", async () => {
  const h = harness("wolf");
  for (let n = 1; n <= 5; n++) h.set("howling_counter", n);
  h.set("pressure", true);
  h.set("howling_counter", 1);
  assert.equal(passiveGet(h.view().players.p1, "howling_counter"), 1);
  assert.equal(passiveGet(h.view().players.p1, "pressure"), true);
  await h.queue.flush();
  assert.equal(h.sent.length, 1);
  assert.equal(passiveGet(h.saved().players.p1, "howling_counter"), 1);
});
test("toggles and role choices store the final selection once per key", async () => {
  const h = harness("rita");
  h.set("light_lumen", true);
  h.set("light_lumen", false);
  h.set("light_lumen", true);
  h.set("rita_role", "guardian");
  h.set("rita_role", "assassin");
  h.set("rita_role", "paladin");
  await h.queue.flush();
  assert.equal(h.sent[0]!.actions!.length, 2);
  assert.equal(passiveGet(h.saved().players.p1, "rita_role"), "paladin");
});
test("reset cancels unsent input and disconnect never replays it", async () => {
  const h = harness();
  h.set("silver_counter", 1);
  h.queue.clear();
  h.clock.advance(1000);
  await settle();
  assert.equal(h.sent.length, 0);
  h.set("silver_counter", 2);
  h.queue.setAvailable(false);
  h.queue.setAvailable(true);
  h.clock.advance(1000);
  await settle();
  assert.equal(h.sent.length, 0);
  assert.equal(passiveGet(h.view().players.p1, "silver_counter"), 0);
});
test("flush commits before a following action; dispose leaves no delayed work", async () => {
  const h = harness();
  h.set("silver_counter", 2);
  await h.queue.flush();
  assert.equal(passiveGet(h.saved().players.p1, "silver_counter"), 2);
  h.set("silver_counter", 3);
  h.queue.dispose();
  h.clock.advance(1000);
  await settle();
  assert.equal(h.sent.length, 1);
});
test("new input during a slow send keeps the newest preview and commits afterwards", async () => {
  const clock = new Clock();
  let pending: Action[] = [];
  let release: () => void = () => {};
  const sent: Action[] = [];
  const q = new PassiveInputQueue(
    async (a) => {
      sent.push(a);
      if (sent.length === 1)
        await new Promise<void>((r) => {
          release = r;
        });
    },
    (a) => {
      pending = a;
    },
    clock,
  );
  const set = (value: number) =>
    q.add({ action: "passive", target: "p1", key: "counter", value });
  set(1);
  clock.advance(900);
  set(2);
  assert.equal(pending.at(-1)?.value, 2);
  release();
  await settle();
  clock.advance(900);
  await settle();
  assert.equal(sent.length, 2);
  assert.equal(sent[1]!.value, 2);
});
test("rejected send removes the preview without changing saved state", async () => {
  let pending: Action[] = [];
  const errors: unknown[] = [];
  const q = new PassiveInputQueue(
    async () => {
      throw Error("rejected");
    },
    (a) => {
      pending = a;
    },
    undefined,
    (e) => errors.push(e),
  );
  q.add({ action: "passive", target: "p1", key: "counter", value: 3 });
  await q.flush();
  assert.equal(pending.length, 0);
  assert.equal(errors.length, 1);
  q.dispose();
});
test("compaction never crosses HP, shield, relative increments or memo barriers", () => {
  const set = (value: number): Action => ({
    action: "passive",
    target: "p1",
    key: "counter",
    value,
  });
  const actions: Action[] = [
    set(1),
    set(2),
    { action: "hp", target: "p1", amount: -100 },
    set(3),
    { action: "shield", target: "p1", amount: 100 },
    set(4),
    { action: "passive", target: "p1", key: "counter", delta: 1 } as any,
    set(5),
  ];
  assert.deepEqual(compactPassiveActions(actions), actions.slice(1));
  assert(
    !isPassiveInput({
      action: "batch",
      actions: [set(1), { action: "hp", target: "p1", amount: -100 }],
    }),
  );
});
