import { AnimatePresence, motion } from "motion/react";
import { useLayoutEffect, useRef } from "react";
import { useFx, type Activation, type Float } from "../anim/fx";
import type { Side } from "../protocol";
import { Card } from "./Card";

/** 화면 가운데 배너(페이즈, 콤보 등)와 위쪽 효과 띠. 배틀 판정은 카드 돌진 연출(anim/clash.ts)로 보여 준다. */
export function FxLayer({ me }: { me: Side }) {
  const banner = useFx((s) => s.banner);
  const ribbon = useFx((s) => s.ribbon);
  const activation = useFx((s) => s.activation);
  return (
    <div className="fx-layer" aria-live="polite">
      <AnimatePresence>
        {banner && (
          <motion.div
            key={banner.id}
            className={`fx-banner kind-${banner.kind} ${"tone" in banner && banner.tone ? `tone-${banner.tone}` : ""}`}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.15, transition: { duration: 0.18 } }}
            transition={{ type: "spring", stiffness: 520, damping: 26 }}
          >
            {banner.kind === "card" ? (
              <>
                <span className="fx-banner-sub">{banner.title}</span>
                <div className="fx-banner-card">
                  <Card card={banner.card} size="large" detached />
                </div>
                {banner.sub && <strong>{banner.sub}</strong>}
              </>
            ) : (
              <>
                {"sub" in banner && banner.sub && <span className="fx-banner-sub">{banner.sub}</span>}
                <strong>{banner.title}</strong>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {activation && <ActivationPopup key={activation.id} activation={activation} me={me} />}
      </AnimatePresence>
      <AnimatePresence>
        {ribbon && (
          <motion.div
            key={ribbon.id}
            className={`fx-ribbon ${ribbon.side === me ? "is-mine" : ribbon.side === "system" ? "" : "is-theirs"}`}
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <b>{ribbon.card}</b>
            <span>{ribbon.text}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * 효과 발동 카드. 보드 위 그 카드 자리에서 커지며 발동한 쪽 편으로 날아와 빛나고,
 * 효과문을 곁들여 잠깐 머문 뒤 사라진다. 날아오르는 움직임은 안쪽 요소에 Web Animations로 준다
 * (motion은 바깥 요소의 나타남·사라짐만 맡는다).
 */
function ActivationPopup({ activation, me }: { activation: Activation; me: Side }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const from = activation.from;
  useLayoutEffect(() => {
    const element = cardRef.current;
    if (!element || !from || !element.animate) return;
    const rect = element.getBoundingClientRect();
    if (!rect.width) return;
    const dx = from.x - (rect.left + rect.width / 2);
    const dy = from.y - (rect.top + rect.height / 2);
    const scale = Math.min(1, Math.max(0.15, from.width / rect.width));
    element.animate(
      [
        { translate: `${dx}px ${dy}px`, scale: String(scale), opacity: 0.85 },
        { translate: "0 0", scale: "1.06", opacity: 1, offset: 0.75 },
        { translate: "0 0", scale: "1", opacity: 1 },
      ],
      { duration: 420, easing: "cubic-bezier(0.2, 0.8, 0.3, 1)" },
    );
    // 처음 그릴 때 한 번만 날아온다.
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const sideClass = activation.side === me ? "is-mine" : activation.side === "system" ? "is-system" : "is-theirs";
  return (
    <motion.div
      className={`fx-activation ${sideClass}`}
      initial={from ? { opacity: 1 } : { opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.88, transition: { duration: 0.2 } }}
      transition={{ type: "spring", stiffness: 460, damping: 26 }}
    >
      <div className="fx-activation-card" ref={cardRef}>
        <Card card={activation.card} size="large" detached />
        <span className="fx-activation-shine" aria-hidden />
      </div>
      {(activation.label || activation.text) && (
        <div className="fx-activation-text">
          {activation.label && <b>{activation.label}</b>}
          {activation.text && <span>{activation.text}</span>}
        </div>
      )}
    </motion.div>
  );
}

/** 초상 위에 떠오르는 숫자 */
export function Floats({ side }: { side: Side }) {
  const floats = useFx((s) => s.floats);
  const mine = floats.filter((item: Float) => item.side === side);
  return (
    <div className="fx-floats" aria-hidden>
      <AnimatePresence>
        {mine.map((item, index) => (
          <motion.span
            key={item.id}
            className={`fx-float tone-${item.tone}`}
            initial={{ opacity: 0, y: 10, scale: 0.6 }}
            animate={{ opacity: [0, 1, 1, 0], y: -14 - index * 18, scale: 1 }}
            transition={{ duration: 1.3, times: [0, 0.15, 0.7, 1] }}
          >
            {item.text}
          </motion.span>
        ))}
      </AnimatePresence>
    </div>
  );
}
