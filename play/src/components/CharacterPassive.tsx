import { sendManual } from "../net/live";
import type { PlayerState, Side } from "../protocol";

/**
 * 캐릭터 전용 패시브(수동 모드). 예전 시뮬레이터의 static/battlelog/passive_ui/*_simulator.js를 옮겼다.
 * 서버가 주는 passive_ui.html의 표식(data-*-panel)으로 어떤 패널인지 고른다.
 * - 패시브 값은 passive {target, key, value, label}
 * - 전용 행동(니아 루멘 정리, CMYK 뉴 싱글, 요한 선언·예지)은 자기 캐릭터에만 쓸 수 있다(서버가 확인).
 */

export type CharacterPanel = "nia" | "cmyk" | "yohan" | "tao";

const MARKERS: [CharacterPanel, string][] = [
  ["nia", "data-nia-panel"],
  ["cmyk", "data-cmyk-panel"],
  ["yohan", "data-yohan-panel"],
  ["tao", "data-tao-panel"],
];

export function characterPanel(player: PlayerState): CharacterPanel | null {
  const html = String((player.character?.passive_ui as { html?: string } | undefined)?.html ?? "");
  return MARKERS.find(([, marker]) => html.includes(marker))?.[0] ?? null;
}

const isOn = (value: unknown) => value === true || value === "true" || value === "on" || value === "ON";

function read(player: PlayerState, key: string, fallback: unknown): unknown {
  const entry = player.passive_state?.[key];
  if (entry?.value !== undefined) return entry.value;
  if (entry?.count !== undefined) return entry.count;
  return fallback;
}

const num = (value: unknown) => (Number.isFinite(Number(value)) ? Number(value) : 0);

interface PanelProps {
  side: Side;
  player: PlayerState;
  /** 보드를 조작할 수 있는 접속인지 */
  enabled: boolean;
  /** 이 플레이어가 나인지(전용 행동은 자기 캐릭터만) */
  mine: boolean;
}

function setPassive(side: Side, key: string, value: unknown, label: string) {
  sendManual("passive", { target: side, key, value, label });
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="passive-row">
      <span>{label}</span>
      <div className="menu-buttons">{children}</div>
    </div>
  );
}

function Nia({ enabled, mine }: PanelProps) {
  return (
    <Row label="루멘 정리">
      <button type="button" className="btn-secondary" disabled={!enabled || !mine} onClick={() => sendManual("nia_lumen_cards_to_list")}>
        공격/수비 → 리스트
      </button>
    </Row>
  );
}

function Cmyk({ player, enabled, mine }: PanelProps) {
  const created = isOn(read(player, "new_single_created", false));
  return (
    <Row label="뉴 싱글">
      <button
        type="button"
        className={`btn-secondary ${created ? "is-current" : ""}`}
        disabled={!enabled || !mine || created}
        onClick={() => sendManual("cmyk_new_single")}
      >
        {created ? "생성됨" : "10장 생성"}
      </button>
    </Row>
  );
}

const FORESIGHT_MAX = 10;
const DECLARATIONS = [
  ["odd", "홀"],
  ["even", "짝"],
  ["attack", "공"],
  ["defense", "수"],
] as const;

function Yohan({ side, player, enabled, mine }: PanelProps) {
  const foresight = Math.max(0, Math.min(FORESIGHT_MAX, num(read(player, "foresight_counter", 2))));
  const disaster = isOn(read(player, "disaster_one", false));
  const setForesight = (value: number) =>
    setPassive(side, "foresight_counter", Math.max(0, Math.min(FORESIGHT_MAX, value)), "예지 카운터");
  return (
    <>
      <Row label="예지">
        <button type="button" className="btn-secondary" disabled={!enabled || foresight <= 0} onClick={() => setForesight(foresight - 1)}>
          −
        </button>
        <button type="button" className="btn-ghost passive-value" disabled={!enabled || foresight <= 0} title="0으로" onClick={() => setForesight(0)}>
          {foresight}/{FORESIGHT_MAX}
        </button>
        <button type="button" className="btn-secondary" disabled={!enabled || foresight >= FORESIGHT_MAX} onClick={() => setForesight(foresight + 1)}>
          +
        </button>
      </Row>
      <Row label="디제스터 원">
        <button
          type="button"
          className={`btn-secondary ${disaster ? "is-current" : ""}`}
          disabled={!enabled}
          onClick={() => setPassive(side, "disaster_one", !disaster, "디제스터 원")}
        >
          {disaster ? "켜짐" : "꺼짐"}
        </button>
      </Row>
      <Row label="선언">
        <button type="button" className="btn-secondary" disabled={!enabled || !mine} onClick={() => sendManual("yohan_foresight_reveal")}>
          예지
        </button>
        {DECLARATIONS.map(([declaration, label]) => (
          <button
            key={declaration}
            type="button"
            className="btn-secondary"
            disabled={!enabled || !mine}
            onClick={() => sendManual("yohan_declare_reveal", { declaration })}
          >
            {label}
          </button>
        ))}
      </Row>
    </>
  );
}

const TAO_MAX = 4;
const HARMONY_EFFECTS = [
  ["damage_100", "DMG+100"],
  ["fp_1", "FP+1"],
] as const;

function Tao({ side, player, enabled }: PanelProps) {
  const yang = Math.max(0, Math.min(TAO_MAX, num(read(player, "yang_counter", 0))));
  const yin = Math.max(0, Math.min(TAO_MAX, num(read(player, "yin_counter", 0))));
  const harmonyStored = isOn(read(player, "harmony", false));
  const harmony = harmonyStored || (yang === TAO_MAX && yin === TAO_MAX);
  const stored = String(read(player, "harmony_effect", "") || "");
  const effect =
    stored || (isOn(read(player, "harmony_damage", false)) ? "damage_100" : isOn(read(player, "harmony_fp", false)) ? "fp_1" : "");

  // 음양이 모두 4가 되면 조화가 켜지고, 어느 한쪽이 3 미만이 되면 꺼진다(효과 선택도 지운다).
  const setCounter = (counter: "yang" | "yin", value: number) => {
    const next = Math.max(0, Math.min(TAO_MAX, value));
    const nextYang = counter === "yang" ? next : yang;
    const nextYin = counter === "yin" ? next : yin;
    setPassive(side, `${counter}_counter`, next, counter === "yang" ? "양" : "음");
    if (nextYang === TAO_MAX && nextYin === TAO_MAX && !harmonyStored) {
      setPassive(side, "harmony", true, "조화");
    } else if (harmonyStored && !(nextYang >= 3 && nextYin >= 3)) {
      setPassive(side, "harmony_effect", "", "조화 효과");
      setPassive(side, "harmony", false, "조화");
    }
  };
  const chooseEffect = (value: string) => {
    if (!harmonyStored) setPassive(side, "harmony", true, "조화");
    setPassive(side, "harmony_effect", value, "조화 효과");
  };

  return (
    <>
      {(
        [
          ["yang", "양", yang],
          ["yin", "음", yin],
        ] as const
      ).map(([counter, label, value]) => (
        <Row key={counter} label={label}>
          <button type="button" className="btn-secondary" disabled={!enabled || value <= 0} onClick={() => setCounter(counter, value - 1)}>
            −
          </button>
          <b className={`passive-value ${!harmony && value > (counter === "yang" ? yin : yang) ? "is-dominant" : ""}`}>
            {value}/{TAO_MAX}
          </b>
          <button type="button" className="btn-secondary" disabled={!enabled || value >= TAO_MAX} onClick={() => setCounter(counter, value + 1)}>
            +
          </button>
          <button type="button" className="btn-ghost" disabled={!enabled || value <= 0} onClick={() => setCounter(counter, 0)}>
            0
          </button>
        </Row>
      ))}
      {harmony && (
        <Row label="조화">
          {HARMONY_EFFECTS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`btn-secondary ${effect === value ? "is-current" : ""}`}
              disabled={!enabled}
              onClick={() => chooseEffect(value)}
            >
              {label}
            </button>
          ))}
        </Row>
      )}
    </>
  );
}

const PANELS: Record<CharacterPanel, (props: PanelProps) => React.ReactElement> = {
  nia: Nia,
  cmyk: Cmyk,
  yohan: Yohan,
  tao: Tao,
};

export function CharacterPassive({ panel, ...props }: PanelProps & { panel: CharacterPanel }) {
  const Panel = PANELS[panel];
  return (
    <div className="passive-controls">
      <Panel {...props} />
    </div>
  );
}
