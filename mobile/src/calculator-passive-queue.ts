import type { Action, CalcState, PassiveValue } from "./types";

export const PASSIVE_INPUT_DELAY = 900;
export function flattenActions(action: Action): Action[] {
  return action.action === "batch"
    ? (action.actions || []).flatMap(flattenActions)
    : [action];
}
export function isPassiveInput(action: Action): boolean {
  const actions = flattenActions(action);
  return actions.length > 0 && actions.every(a => a.action === "passive" && !!a.target && !!a.key);
}
/** Coalesce repeated absolute values, without crossing resource/opaque actions.
 * Keep the last occurrence order so effect selection and consumed tokens agree. */
export function compactPassiveActions(actions: Action[]): Action[] {
  const result: (Action | null)[] = [];
  const positions = new Map<string, number>();
  for (const action of actions.flatMap(flattenActions)) {
    if (action.action === "passive" && action.target && action.key &&
        Object.prototype.hasOwnProperty.call(action, "value") && !(action as any).note && !(action as any).delta) {
      const key = action.target + ":" + action.key;
      const prior = positions.get(key);
      if (prior !== undefined) result[prior] = null;
      positions.set(key, result.length);
    } else positions.clear();
    result.push(action);
  }
  return result.filter((a): a is Action => a !== null);
}

/** UI preview only: no history, version bump, persistence or network effects. */
export function projectPassiveInputs(state: CalcState | null, actions: Action[]): CalcState | null {
  if (!state || !actions.length) return state;
  const next = { ...state, players: { ...state.players } };
  for (const action of compactPassiveActions(actions)) {
    if (action.action !== "passive" || !action.target || !action.key) continue;
    const player = next.players[action.target];
    const entry: PassiveValue = { ...player.passive_state?.[action.key] };
    if (Object.prototype.hasOwnProperty.call(action, "value")) entry.value = action.value;
    if ((action as any).delta) entry.count = Math.max(0, Number(entry.count || 0) + Number((action as any).delta));
    if (action.label) entry.label = action.label;
    next.players[action.target] = { ...player, passive_state: { ...player.passive_state, [action.key]: entry } };
  }
  return next;
}

type Clock = { now: () => number; later: (fn: () => void, delay: number) => unknown; cancel: (id: unknown) => void };
const clock: Clock = { now: () => performance.now(), later: (fn, delay) => setTimeout(fn, delay), cancel: id => clearTimeout(id as ReturnType<typeof setTimeout>) };

/** Foreground 0.9s input window, independent per player. Never an offline outbox. */
export class PassiveInputQueue {
  private groups = new Map<string, { actions: Action[]; deadline: number }>();
  private inFlight: Action[] = [];
  private timer: unknown;
  private available = true;
  private busy = false;
  private disposed = false;
  private forced = false;
  private waiters: (() => void)[] = [];
  constructor(private send: (a: Action) => Promise<void>, private changed: (actions: Action[]) => void,
    private time: Clock = clock, private failed: (e: unknown) => void = () => {}) {}
  get hasPending() { return this.groups.size > 0 || this.inFlight.length > 0; }
  add(action: Action) {
    if (!this.available || this.disposed || !isPassiveInput(action)) return;
    for (const item of flattenActions(action)) {
      const group = this.groups.get(item.target!) || { actions: [], deadline: 0 };
      group.actions = compactPassiveActions([...group.actions, item]);
      group.deadline = this.time.now() + PASSIVE_INPUT_DELAY;
      this.groups.set(item.target!, group);
    }
    this.notify(); this.schedule();
  }
  setAvailable(available: boolean) { this.available = available; if (!available) this.clear(); else this.schedule(); }
  setBusy(busy: boolean) { this.busy = busy; this.schedule(); }
  clear() { this.groups.clear(); this.forced = false; this.stop(); this.notify(); this.finish(); }
  flush(): Promise<void> {
    if (this.disposed || !this.hasPending) return Promise.resolve();
    this.forced = true;
    const result = new Promise<void>(resolve => this.waiters.push(resolve));
    void this.drain(); return result;
  }
  dispose() { this.disposed = true; this.groups.clear(); this.inFlight = []; this.stop(); this.waiters.splice(0).forEach(resolve => resolve()); }
  private stop() { if (this.timer !== undefined) this.time.cancel(this.timer); this.timer = undefined; }
  private notify() { if (!this.disposed) this.changed(compactPassiveActions([...this.inFlight, ...[...this.groups.values()].flatMap(g => g.actions)])); }
  private finish() { if (!this.hasPending) { this.forced = false; this.waiters.splice(0).forEach(resolve => resolve()); } }
  private schedule() {
    this.stop();
    if (this.disposed || !this.available || this.busy || this.inFlight.length || !this.groups.size) { this.finish(); return; }
    const deadline = Math.min(...[...this.groups.values()].map(g => g.deadline));
    this.timer = this.time.later(() => { this.timer = undefined; void this.drain(); }, this.forced ? 0 : Math.max(0, deadline - this.time.now()));
  }
  private async drain() {
    if (this.disposed || !this.available || this.busy || this.inFlight.length) return;
    this.stop();
    const actions: Action[] = [];
    for (const [target, group] of this.groups) if (this.forced || group.deadline <= this.time.now()) {
      actions.push(...group.actions); this.groups.delete(target);
    }
    if (!actions.length) { this.schedule(); return; }
    this.inFlight = compactPassiveActions(actions); this.notify();
    try {
      for (let i = 0; i < this.inFlight.length; i += 100) {
        const batch = this.inFlight.slice(i, i + 100);
        await this.send(batch.length === 1 ? batch[0]! : { action: "batch", actions: batch });
      }
    } catch (error) { this.failed(error); }
    finally { this.inFlight = []; this.notify(); this.schedule(); }
  }
}
