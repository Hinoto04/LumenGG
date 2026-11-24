import type { Side } from "../protocol";
import { playSound, type SoundName } from "../sound/sfx";

/**
 * 배틀 판정 연출: 배틀존의 두 카드가 서로에게 돌진한다.
 *
 * hit      공격이 수비를 뚫음. 맞은 카드는 흑백이 된다.
 * counter  빠른 공격이 상대 공격을 끊음. 끊긴 공격 카드는 흑백이 된다.
 * grab     잡기. 히트와 같고 소리만 다르다.
 * trade    같은 속도의 공격끼리 서로 맞는다(둘 다 히트).
 * clash    상쇄. 두 카드가 가운데에서 부딪혀 튕겨 난다.
 * guarded  방어당함. 공격 카드가 수비 카드에 부딪혀 튕겨 나온다.
 * dodge    회피. 공격이 지나가고 수비 카드는 옆으로 비킨다.
 *
 * 보드 카드(Card.tsx의 data-instance-id)를 Web Animations로 움직인다. motion이 쓰는 transform이 아니라
 * 개별 속성(translate·rotate·filter)만 건드리므로 레이아웃 애니메이션과 겹치지 않는다.
 * 흑백은 카드가 배틀존을 떠날 때까지 남고, 새 페이즈·초기화 때 clearClash()로 지운다.
 */

export type ClashKind = "hit" | "counter" | "grab" | "trade" | "clash" | "guarded" | "dodge" | "double_dodge";

export interface ClashPlan {
  kind: ClashKind;
  /** 돌진하는 쪽(clash·trade·double_dodge는 양쪽) */
  attacker: Side;
}

/** 판정 결과(side → result)에서 연출을 고른다. 둘 다 수비 등 부딪힘이 없으면 null. */
export function clashPlan(result: Partial<Record<Side, string>>): ClashPlan | null {
  const p1 = result.p1 ?? "";
  const p2 = result.p2 ?? "";
  const pair = (a: string, b: string): Side | null => (p1 === a && p2 === b ? "p1" : p2 === a && p1 === b ? "p2" : null);
  if (p1 === "clash" || p2 === "clash") return { kind: "clash", attacker: "p1" };
  if (p1 === "hit" && p2 === "hit") return { kind: "trade", attacker: "p1" };
  if (p1 === "dodge" && p2 === "dodge") return { kind: "double_dodge", attacker: "p1" };
  const counter = pair("counter", "countered");
  if (counter) return { kind: "counter", attacker: counter };
  const guarded = pair("guarded", "guard");
  if (guarded) return { kind: "guarded", attacker: guarded };
  const dodged = pair("opponent_dodge", "dodge");
  if (dodged) return { kind: "dodge", attacker: dodged };
  const grabbed = pair("hit", "grabbed");
  if (grabbed) return { kind: "grab", attacker: grabbed };
  const hit = pair("hit", "failed_defense") ?? pair("hit", "none") ?? pair("counter", "failed_defense") ?? pair("counter", "none");
  if (hit) return { kind: p1 === "counter" || p2 === "counter" ? "counter" : "hit", attacker: hit };
  return null;
}

/** 이 연출 전체 길이(×1 기준, ms). 재생기는 이만큼 기다린다. */
export const CLASH_MS = 1100;

const IMPACT_SOUND: Record<ClashKind, SoundName> = {
  hit: "hit",
  counter: "counter",
  grab: "grab",
  trade: "hit",
  clash: "clash",
  guarded: "guard",
  dodge: "dodge",
  double_dodge: "dodge",
};

let running: Animation[] = [];
let lifted: HTMLElement[] = [];
let timers: ReturnType<typeof setTimeout>[] = [];

function cardElement(instanceId: string | undefined): HTMLElement | null {
  if (!instanceId) return null;
  return document.querySelector<HTMLElement>(`.battle-zone [data-instance-id="${CSS.escape(instanceId)}"]`);
}

function center(element: HTMLElement) {
  const rect = element.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, h: rect.height };
}

/** 돌진하는 카드가 상대 필드 위로 지나가도록 잠시 위로 올린다. */
function lift(element: HTMLElement) {
  for (const node of [element, element.closest<HTMLElement>(".field")]) {
    if (!node) continue;
    // .card·.field는 이미 position: relative다.
    node.style.zIndex = "40";
    lifted.push(node);
  }
}

function run(element: HTMLElement, keyframes: Keyframe[], duration: number, options: KeyframeAnimationOptions = {}) {
  const animation = element.animate(keyframes, { duration, easing: "linear", ...options });
  running.push(animation);
  return animation;
}

function px(x: number, y: number) {
  return `${Math.round(x)}px ${Math.round(y)}px`;
}

/** 맞은 카드: 하얗게 번쩍이고 흔들린 뒤 흑백으로 남는다. */
function struck(element: HTMLElement, duration: number, strong: boolean) {
  const amp = strong ? 9 : 6;
  run(
    element,
    [
      { translate: "0px 0px", rotate: "0deg" },
      { translate: px(amp, -amp / 2), rotate: strong ? "-3deg" : "-1.5deg", offset: 0.15 },
      { translate: px(-amp, amp / 2), rotate: strong ? "2.5deg" : "1deg", offset: 0.35 },
      { translate: px(amp / 2, 0), rotate: "-1deg", offset: 0.55 },
      { translate: "0px 0px", rotate: "0deg" },
    ],
    duration * 0.5,
  );
  run(
    element,
    [
      { filter: "brightness(2.4) saturate(0.6)" },
      { filter: "brightness(1.2) grayscale(0.6)", offset: 0.25 },
      { filter: "brightness(0.85) grayscale(1)" },
    ],
    duration * 0.45,
    { fill: "forwards" },
  );
}

/**
 * 연출을 시작한다. ids: side → 배틀 카드 instance_id. speed: 재생 배속.
 * 카드가 화면에 없으면(좁은 화면에서 접힘 등) 소리만 낸다.
 */
export function playClash(plan: ClashPlan, ids: Partial<Record<Side, string>>, speed: number, quiet = false) {
  const scale = 1 / Math.max(speed, 1);
  const total = CLASH_MS * scale;
  const attackerSide = plan.attacker;
  const targetSide: Side = attackerSide === "p1" ? "p2" : "p1";
  const attacker = cardElement(ids[attackerSide]);
  const target = cardElement(ids[targetSide]);
  const impactAt = total * 0.3;
  const soundTimer = (ms: number, name: SoundName) => {
    if (!quiet) timers.push(setTimeout(() => playSound(name), ms));
  };
  soundTimer(0, "rush");
  soundTimer(impactAt, IMPACT_SOUND[plan.kind]);
  if (!attacker) return;

  const from = center(attacker);
  const to = target ? center(target) : { x: from.x, y: from.y + (from.y > window.innerHeight / 2 ? -1 : 1) * from.h * 1.4, h: from.h };
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy) || 1;
  // 카드가 겹치기 직전(카드 높이의 약 0.55배 앞)에서 멈춘다.
  const reach = Math.max(0, 1 - (from.h * 0.55) / distance);
  const back = (k: number) => px(-dx * k, -dy * k);
  const toward = (k: number) => px(dx * k, dy * k);
  const rushEasing = "cubic-bezier(.5,0,.9,.6)";

  lift(attacker);
  switch (plan.kind) {
    case "clash": {
      // 두 카드가 가운데에서 만나 서로 튕겨 난다.
      const meet = Math.max(0, 0.5 - (from.h * 0.28) / distance);
      for (const [element, sign] of [
        [attacker, 1],
        [target, -1],
      ] as const) {
        if (!element) continue;
        lift(element);
        const go = (k: number) => px(dx * k * sign, dy * k * sign);
        run(
          element,
          [
            { translate: "0px 0px", rotate: "0deg", easing: rushEasing },
            { translate: go(-0.06), offset: 0.12, easing: rushEasing },
            { translate: go(meet), rotate: `${sign * 2}deg`, offset: 0.3, easing: "ease-out" },
            { translate: go(meet - 0.18), rotate: `${-sign * 6}deg`, offset: 0.48, easing: "ease-in-out" },
            { translate: go(0.03), rotate: `${sign * 1.5}deg`, offset: 0.75 },
            { translate: "0px 0px", rotate: "0deg" },
          ],
          total,
        );
        run(element, [{ filter: "brightness(1)" }, { filter: "brightness(2)", offset: 0.3 }, { filter: "brightness(1)", offset: 0.55 }], total);
      }
      return;
    }
    case "trade": {
      // 같은 속도: 둘 다 돌진해 서로 맞는다.
      for (const [element, sign] of [
        [attacker, 1],
        [target, -1],
      ] as const) {
        if (!element) continue;
        lift(element);
        const go = (k: number) => px(dx * k * sign, dy * k * sign);
        run(
          element,
          [
            { translate: "0px 0px", easing: rushEasing },
            { translate: go(-0.06), offset: 0.12, easing: rushEasing },
            { translate: go(Math.max(0, 0.5 - (from.h * 0.2) / distance)), offset: 0.3, easing: "ease-out" },
            { translate: "0px 0px" },
          ],
          total * 0.75,
        );
        timers.push(setTimeout(() => struck(element, total, false), impactAt));
      }
      return;
    }
    case "double_dodge": {
      // 서로 비켜 지나간다.
      for (const [element, sign] of [
        [attacker, 1],
        [target, -1],
      ] as const) {
        if (!element) continue;
        run(
          element,
          [
            { translate: "0px 0px", opacity: 1 },
            { translate: px(sign * from.h * 0.45, 0), opacity: 0.55, offset: 0.35 },
            { translate: "0px 0px", opacity: 1 },
          ],
          total * 0.8,
          { easing: "ease-in-out" },
        );
      }
      return;
    }
    case "guarded": {
      // 부딪힌 뒤 크게 튕겨 나온다. 방어한 카드는 살짝 밀렸다 버틴다.
      run(
        attacker,
        [
          { translate: "0px 0px", rotate: "0deg", easing: rushEasing },
          { translate: back(0.08), offset: 0.12, easing: rushEasing },
          { translate: toward(reach), rotate: "0deg", offset: 0.3, easing: "cubic-bezier(.2,.8,.3,1)" },
          { translate: back(0.22), rotate: "-7deg", offset: 0.55, easing: "ease-in-out" },
          { translate: toward(0.04), rotate: "2deg", offset: 0.75 },
          { translate: "0px 0px", rotate: "0deg" },
        ],
        total,
      );
      if (target) {
        run(
          target,
          [
            { translate: "0px 0px", filter: "brightness(1)" },
            { translate: "0px 0px", filter: "brightness(1)", offset: 0.29 },
            { translate: toward(0.05), filter: "brightness(1.8)", offset: 0.36 },
            { translate: "0px 0px", filter: "brightness(1)", offset: 0.6 },
            { translate: "0px 0px", filter: "brightness(1)" },
          ],
          total,
        );
      }
      return;
    }
    case "dodge": {
      // 공격이 지나쳐 가고, 수비 카드는 옆으로 비켜 반투명해진다.
      run(
        attacker,
        [
          { translate: "0px 0px", easing: rushEasing },
          { translate: back(0.08), offset: 0.12, easing: rushEasing },
          { translate: toward(Math.min(1, reach + 0.15)), offset: 0.34, easing: "ease-out" },
          { translate: toward(Math.min(1, reach + 0.2)), offset: 0.5, easing: "ease-in-out" },
          { translate: "0px 0px" },
        ],
        total,
      );
      if (target) {
        run(
          target,
          [
            { translate: "0px 0px", opacity: 1 },
            { translate: "0px 0px", opacity: 1, offset: 0.2 },
            { translate: px(from.h * 0.55, 0), opacity: 0.45, offset: 0.36 },
            { translate: px(from.h * 0.55, 0), opacity: 0.45, offset: 0.55 },
            { translate: "0px 0px", opacity: 1 },
          ],
          total,
          { easing: "ease-in-out" },
        );
      }
      return;
    }
    default: {
      // hit·counter·grab: 돌진해 맞히고 돌아온다. 맞은 카드는 흑백으로 남는다.
      const strong = plan.kind === "counter";
      run(
        attacker,
        [
          { translate: "0px 0px", rotate: "0deg", easing: rushEasing },
          { translate: back(strong ? 0.12 : 0.08), rotate: strong ? "-4deg" : "0deg", offset: 0.12, easing: rushEasing },
          { translate: toward(reach), rotate: strong ? "3deg" : "0deg", offset: 0.3, easing: "ease-out" },
          { translate: toward(reach - 0.06), rotate: "0deg", offset: 0.45, easing: "ease-in-out" },
          { translate: "0px 0px", rotate: "0deg" },
        ],
        total,
      );
      if (target) timers.push(setTimeout(() => struck(target, total, strong), impactAt));
    }
  }
}

/** 남은 연출(흑백 포함)과 예약된 소리를 지운다. */
export function clearClash() {
  timers.forEach(clearTimeout);
  timers = [];
  running.forEach((animation) => animation.cancel());
  running = [];
  for (const node of lifted) node.style.zIndex = "";
  lifted = [];
}

/** 끝난 돌진의 z-index만 되돌린다(흑백은 남긴다). */
export function settleClash() {
  for (const node of lifted) node.style.zIndex = "";
  lifted = [];
  running = running.filter((animation) => animation.playState !== "finished" || animation.effect?.getTiming().fill === "forwards");
}
