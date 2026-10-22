import type { Action } from "./types";

export type HpTarget = "p1" | "p2";
export type PendingHp = Record<HpTarget, number>;
type ResourceKind = "hp" | "fp" | "shield";
type Scheduler = {
  now: () => number;
  later: (fn: () => void, delay: number) => unknown;
  cancel: (id: unknown) => void;
};
const systemScheduler: Scheduler = {
  now: () => performance.now(),
  later: (fn, delay) => setTimeout(fn, delay),
  cancel: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
};

/** Short foreground UI debounce; never an offline shared-action outbox. */
export class HpQueue {
  private entries = new Map<
    string,
    { target: HpTarget; kind: ResourceKind; amount: number; deadline: number }
  >();
  private staged: { target: HpTarget; kind: ResourceKind; amount: number }[] =
    [];
  private timer: unknown;
  private sending = false;
  private busy = false;
  private available = true;
  private disposed = false;
  private forced = false;
  private waiters: (() => void)[] = [];
  constructor(
    private send: (action: Action) => Promise<void>,
    private changed: (
      pending: PendingHp,
      fp: PendingHp,
      shield: PendingHp,
    ) => void,
    private clock: Scheduler = systemScheduler,
    private failed: (error: unknown) => void = () => {},
  ) {}
  get hasPending() {
    return this.entries.size > 0 || this.staged.length > 0;
  }
  get hasPendingHp() {
    return [...this.entries.values(), ...this.staged].some(
      (entry) => entry.kind === "hp",
    );
  }
  add(target: HpTarget, amount: number, kind: ResourceKind = "hp") {
    if (
      this.disposed ||
      !this.available ||
      this.busy ||
      !Number.isSafeInteger(amount)
    )
      return;
    // HP and shield edits cannot commute. Seal the preceding group before
    // accepting the opposite resource, even while an earlier send is in flight.
    if (kind !== "fp") {
      const otherKey = `${kind === "hp" ? "shield" : "hp"}:${target}`;
      const other = this.entries.get(otherKey);
      if (other) {
        this.staged.push(other);
        this.entries.delete(otherKey);
      }
    }
    const key = `${kind}:${target}`;
    const total = (this.entries.get(key)?.amount || 0) + amount;
    if (total)
      this.entries.set(key, {
        target,
        kind,
        amount: total,
        deadline: this.clock.now() + (kind === "fp" ? 700 : 900),
      });
    else this.entries.delete(key);
    this.notify();
    this.schedule();
  }
  setAvailable(value: boolean) {
    this.available = value;
    if (!value) this.clear();
    else this.schedule();
  }
  setBusy(value: boolean) {
    this.busy = value;
    this.schedule();
  }
  clear(kind?: ResourceKind, target?: HpTarget) {
    this.staged = this.staged.filter(
      (entry) =>
        !(
          (!kind || entry.kind === kind) &&
          (!target || entry.target === target)
        ),
    );
    for (const [key, entry] of this.entries)
      if (
        (!kind || entry.kind === kind) &&
        (!target || entry.target === target)
      )
        this.entries.delete(key);
    this.stopTimer();
    this.forced = false;
    this.notify();
    this.finishWaiters();
    this.schedule();
  }
  flush(): Promise<void> {
    if (this.disposed || (!this.hasPending && !this.sending))
      return Promise.resolve();
    this.forced = true;
    const result = new Promise<void>((resolve) => this.waiters.push(resolve));
    void this.drain();
    return result;
  }
  dispose() {
    this.disposed = true;
    this.entries.clear();
    this.staged = [];
    this.stopTimer();
    this.waiters.splice(0).forEach((resolve) => resolve());
  }
  private notify() {
    const total = (kind: ResourceKind, target: HpTarget) =>
      (this.entries.get(`${kind}:${target}`)?.amount || 0) +
      this.staged
        .filter((e) => e.kind === kind && e.target === target)
        .reduce((sum, e) => sum + e.amount, 0);
    if (!this.disposed)
      this.changed(
        {
          p1: total("hp", "p1"),
          p2: total("hp", "p2"),
        },
        {
          p1: total("fp", "p1"),
          p2: total("fp", "p2"),
        },
        { p1: total("shield", "p1"), p2: total("shield", "p2") },
      );
  }
  private stopTimer() {
    if (this.timer !== undefined) this.clock.cancel(this.timer);
    this.timer = undefined;
  }
  private finishWaiters() {
    if (!this.hasPending && !this.sending) {
      this.forced = false;
      this.waiters.splice(0).forEach((resolve) => resolve());
    }
  }
  private schedule() {
    this.stopTimer();
    if (
      this.disposed ||
      !this.available ||
      this.busy ||
      this.sending ||
      !this.hasPending
    ) {
      this.finishWaiters();
      return;
    }
    const deadline = Math.min(
      ...[...this.entries.values()].map((entry) => entry.deadline),
    );
    this.timer = this.clock.later(
      () => {
        this.timer = undefined;
        void this.drain();
      },
      this.forced || this.staged.length
        ? 0
        : Math.max(0, deadline - this.clock.now()),
    );
  }
  private async drain() {
    if (this.disposed || !this.available || this.busy || this.sending) return;
    this.stopTimer();
    const actions: Action[] = this.staged
      .splice(0)
      .map((entry) => ({
        action: entry.kind,
        target: entry.target,
        amount: entry.amount,
      }));
    for (const [key, entry] of this.entries) {
      if (this.forced || entry.deadline <= this.clock.now()) {
        actions.push({
          action: entry.kind,
          target: entry.target,
          amount: entry.amount,
        });
        this.entries.delete(key);
      }
    }
    if (!actions.length) {
      this.schedule();
      return;
    }
    this.sending = true;
    this.notify();
    try {
      await this.send(
        actions.length === 1 ? actions[0]! : { action: "batch", actions },
      );
    } catch (error) {
      this.failed(error);
    } finally {
      this.sending = false;
      this.schedule();
    }
  }
}
