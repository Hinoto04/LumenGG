import type { PartyState } from "./party";

export function partyEventStage(
  state: Pick<PartyState, "event" | "status" | "expired"> | null,
  now: number,
): "waiting" | "card" | "effect" | null {
  const event = state?.event;
  if (!event || state?.expired || state?.status !== "running") return null;
  if (event.pending)
    return now >= (event.show_at ?? 0) && now < (event.reveal_until ?? 0)
      ? "card"
      : "waiting";
  return now < (event.effect_until ?? 0) ? "effect" : null;
}
