import type { Action } from "./types";

export type HpTarget = "p1" | "p2";
export type PendingHp = Record<HpTarget, number>;
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
  private entries = new Map<HpTarget, { amount: number; deadline: number }>();
  private timer: unknown;
  private sending = false;
  private busy = false;
  private available = true;
  private disposed = false;
  private forced = false;
  private waiters: (() => void)[] = [];
  constructor(
    private send: (action: Action) => Promise<void>,
    private changed: (pending: PendingHp) => void,
    private clock: Scheduler = systemScheduler,
    private failed: (error: unknown) => void = () => {},
  ) {}
  get hasPending() {
    return this.entries.size > 0;
  }
  add(target: HpTarget, amount: number) {
    if (
      this.disposed ||
      !this.available ||
      this.busy ||
      !Number.isSafeInteger(amount)
    )
      return;
    const total = (this.entries.get(target)?.amount || 0) + amount;
    if (total)
      this.entries.set(target, {
        amount: total,
        deadline: this.clock.now() + 900,
      });
    else this.entries.delete(target);
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
  clear() {
    this.entries.clear();
    this.stopTimer();
    this.forced = false;
    this.notify();
    this.finishWaiters();
  }
  flush(): Promise<void> {
    if (this.disposed || (!this.entries.size && !this.sending))
      return Promise.resolve();
    this.forced = true;
    const result = new Promise<void>((resolve) => this.waiters.push(resolve));
    void this.drain();
    return result;
  }
  dispose() {
    this.disposed = true;
    this.entries.clear();
    this.stopTimer();
    this.waiters.splice(0).forEach((resolve) => resolve());
  }
  private notify() {
    if (!this.disposed)
      this.changed({
        p1: this.entries.get("p1")?.amount || 0,
        p2: this.entries.get("p2")?.amount || 0,
      });
  }
  private stopTimer() {
    if (this.timer !== undefined) this.clock.cancel(this.timer);
    this.timer = undefined;
  }
  private finishWaiters() {
    if (!this.entries.size && !this.sending) {
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
      !this.entries.size
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
      this.forced ? 0 : Math.max(0, deadline - this.clock.now()),
    );
  }
  private async drain() {
    if (this.disposed || !this.available || this.busy || this.sending) return;
    this.stopTimer();
    const actions: Action[] = [];
    for (const [target, entry] of this.entries) {
      if (this.forced || entry.deadline <= this.clock.now()) {
        actions.push({ action: "hp", target, amount: entry.amount });
        this.entries.delete(target);
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
