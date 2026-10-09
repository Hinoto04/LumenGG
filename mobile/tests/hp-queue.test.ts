import { test } from "node:test";
import assert from "node:assert/strict";
import { HpQueue } from "../src/hp-queue";
import type { Action } from "../src/types";

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
  advance(amount: number) {
    const end = this.time + amount;
    for (;;) {
      const next = [...this.tasks]
        .filter(([, task]) => task.at <= end)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.time = next[1].at;
      this.tasks.delete(next[0]);
      next[1].fn();
    }
    this.time = end;
  }
}
const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
};
test("FP taps aggregate for 700ms and mixed HP/FP deadlines remain independent", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  const fpTotals: number[] = [];
  const queue = new HpQueue(
    async (action) => {
      sent.push(action);
    },
    (_hp, fp) => fpTotals.push(fp.p1),
    clock,
  );
  queue.add("p1", -500);
  queue.add("p1", 1, "fp");
  clock.advance(200);
  queue.add("p1", 1, "fp");
  clock.advance(699);
  assert.equal(sent.length, 0);
  assert.equal(fpTotals.at(-1), 2);
  clock.advance(1);
  await settle();
  assert.equal(sent.length, 1);
  assert.equal(sent[0]!.action, "batch");
  assert.deepEqual(
    sent[0]!.actions?.map((action) => [action.action, action.amount]),
    [
      ["hp", -500],
      ["fp", 2],
    ],
  );
});
test("FP reset cancels only that player's pending FP and leaves HP and the other player intact", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  const queue = new HpQueue(
    async (action) => {
      sent.push(action);
    },
    () => {},
    clock,
  );
  queue.add("p1", 2, "fp");
  queue.add("p2", -1, "fp");
  queue.add("p1", -100);
  queue.clear("fp", "p1");
  clock.advance(700);
  await settle();
  clock.advance(200);
  await settle();
  assert.deepEqual(
    sent.map((action) => [action.action, action.target, action.amount]),
    [
      ["fp", "p2", -1],
      ["hp", "p1", -100],
    ],
  );
});
test("rapid HP taps keep the displayed HP unchanged until 900ms after the last tap and submit one sum", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  const amounts: number[] = [];
  const queue = new HpQueue(
    async (action) => {
      sent.push(action);
    },
    (p) => amounts.push(p.p1),
    clock,
  );
  queue.add("p1", -500);
  clock.advance(500);
  queue.add("p1", -100);
  clock.advance(899);
  assert.equal(sent.length, 0);
  assert.equal(amounts.at(-1), -600);
  clock.advance(1);
  await settle();
  assert.deepEqual(sent, [{ action: "hp", target: "p1", amount: -600 }]);
  assert.equal(amounts.at(-1), 0);
});
test("opposite taps cancel and disconnect discards unsent shared HP without a later retry", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  const queue = new HpQueue(
    async (a) => {
      sent.push(a);
    },
    () => {},
    clock,
  );
  queue.add("p1", -500);
  queue.add("p1", 500);
  clock.advance(1000);
  await settle();
  assert.equal(sent.length, 0);
  queue.add("p2", -100);
  queue.setAvailable(false);
  clock.advance(5000);
  await settle();
  assert.equal(sent.length, 0);
  queue.add("p2", -500);
  queue.setAvailable(true);
  clock.advance(1000);
  await settle();
  assert.equal(sent.length, 0);
});
test("two players with an in-flight shared action are serialized using their own deadlines", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  let acknowledge!: () => void;
  const queue = new HpQueue(
    (a) => {
      sent.push(a);
      return sent.length === 1
        ? new Promise<void>((r) => {
            acknowledge = r;
          })
        : Promise.resolve();
    },
    () => {},
    clock,
  );
  queue.add("p1", -100);
  clock.advance(400);
  queue.add("p2", -500);
  clock.advance(500);
  assert.equal(sent.length, 1);
  clock.advance(1000);
  assert.equal(sent.length, 1);
  acknowledge();
  await settle();
  clock.advance(0);
  await settle();
  assert.deepEqual(
    sent.map((a) => [a.target, a.amount]),
    [
      ["p1", -100],
      ["p2", -500],
    ],
  );
});
test("local screen exit flushes both pending players atomically and dispose cancels future work", async () => {
  const clock = new Clock();
  const sent: Action[] = [];
  const queue = new HpQueue(
    async (a) => {
      sent.push(a);
    },
    () => {},
    clock,
  );
  queue.add("p1", -500);
  queue.add("p2", 100);
  await queue.flush();
  assert.deepEqual(sent, [
    {
      action: "batch",
      actions: [
        { action: "hp", target: "p1", amount: -500 },
        { action: "hp", target: "p2", amount: 100 },
      ],
    },
  ]);
  queue.add("p1", -100);
  queue.dispose();
  clock.advance(5000);
  await settle();
  assert.equal(sent.length, 1);
});
