import { AnimatePresence, motion } from "motion/react";
import { useFx, type Float } from "../anim/fx";
import type { Side } from "../protocol";

/** 화면 가운데 배너(페이즈, 판정, 콤보)와 위쪽 효과 띠 */
export function FxLayer({ me }: { me: Side }) {
  const banner = useFx((s) => s.banner);
  const ribbon = useFx((s) => s.ribbon);
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
            {banner.kind === "judge" ? (
              <>
                <strong>{banner.mine}</strong>
                <span className="fx-judge-sub">
                  상대 {banner.theirs}
                  {banner.speeds ? ` · 속도 ${banner.speeds[0]} : ${banner.speeds[1]}` : ""}
                </span>
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
