import { useEffect, useRef, useState } from "react";
import { pushEnvelope, pushEvents, resetPlayback } from "../anim/playback";
import { useCatalog } from "../catalog";
import type { CardMeta, PlayEnvelope, Role } from "../protocol";

type FixtureFile = Record<Role, PlayEnvelope>;
interface Position {
  step: number;
  role: Role;
}

const ROLES: { role: Role; label: string }[] = [
  { role: "p1", label: "P1" },
  { role: "p2", label: "P2" },
  { role: "viewer", label: "관전" },
];

function readHash(): Position {
  const params = new URLSearchParams(location.hash.slice(1));
  const role = params.get("role");
  return {
    step: Math.max(0, Number(params.get("step") ?? 0) || 0),
    role: role === "p2" || role === "viewer" ? role : "p1",
  };
}

export function hashFor({ step, role }: Position): string {
  return `#step=${step}&role=${role}`;
}

interface FixtureBarProps {
  /**
   * 기기 미리보기 바깥 페이지에서 쓸 때: 직접 불러오지 않고 iframe 해시만 바꾼다.
   */
  remote?: (hash: string) => void;
  /** iframe 안에서는 조작 UI를 숨기고 해시 변경만 따른다. */
  headless?: boolean;
}

/**
 * 개발용: play/fixtures의 envelope를 골라 보드에 띄운다.
 * ←/→ 단계 이동, 1/2/3 역할 전환. 위치는 URL 해시에 남는다.
 */
export function FixtureBar({ remote, headless }: FixtureBarProps) {
  /** 바로 다음 단계로 넘어갈 때만 그 사이 이벤트를 재생한다. */
  const shown = useRef<Position | null>(null);
  const mergeCards = useCatalog((state) => state.merge);
  const [files, setFiles] = useState<string[]>([]);
  const [position, setPosition] = useState(readHash);
  const [error, setError] = useState<string | null>(null);
  const { step, role } = position;

  useEffect(() => {
    if (remote) return;
    // card-metadata 엔드포인트와 같은 형태 { cards: {...} }
    fetch("/__fixtures/cards.json")
      .then((response) => (response.ok ? response.json() : { cards: {} }))
      .then((data: { cards?: Record<string, CardMeta> }) => mergeCards(data.cards ?? {}))
      .catch(() => undefined);
  }, [remote, mergeCards]);

  useEffect(() => {
    fetch("/__fixtures/index.json")
      .then((response) => response.json())
      .then((list: string[]) => {
        setFiles(list);
        if (!list.length) setError("픽스처가 없습니다. scripts/export-play-fixtures.ps1을 실행하세요.");
      })
      .catch(() => setError("픽스처 목록을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    const onHash = () => setPosition(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const file = files[Math.min(step, Math.max(files.length - 1, 0))];

  useEffect(() => {
    if (!file) return;
    const hash = hashFor(position);
    if (location.hash !== hash) history.replaceState(null, "", hash);
    if (remote) {
      remote(hash);
      return;
    }
    let cancelled = false;
    fetch(`/__fixtures/${file}`)
      .then((response) => response.json())
      .then((data: FixtureFile) => {
        if (cancelled) return;
        const envelope = data[role];
        const previous = shown.current;
        shown.current = { step, role };
        if (previous && previous.role === role && step === previous.step + 1) {
          pushEvents(envelope.events ?? []);
          pushEnvelope(envelope);
        } else {
          resetPlayback(envelope);
        }
      })
      .catch(() => setError(`${file}을 불러오지 못했습니다.`));
    return () => {
      cancelled = true;
    };
  }, [file, position, remote, role, step]);

  useEffect(() => {
    if (headless) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLSelectElement) return;
      const last = Math.max(files.length - 1, 0);
      if (event.key === "ArrowRight") setPosition((p) => ({ ...p, step: Math.min(p.step + 1, last) }));
      else if (event.key === "ArrowLeft") setPosition((p) => ({ ...p, step: Math.max(p.step - 1, 0) }));
      else if (event.key === "1") setPosition((p) => ({ ...p, role: "p1" }));
      else if (event.key === "2") setPosition((p) => ({ ...p, role: "p2" }));
      else if (event.key === "3") setPosition((p) => ({ ...p, role: "viewer" }));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [files.length, headless]);

  if (headless) return null;

  return (
    <div className={`fixture-bar ${remote ? "is-remote" : ""}`} aria-label="픽스처 선택">
      <span className="fixture-tag">FIXTURE</span>
      <button type="button" onClick={() => setPosition((p) => ({ ...p, step: Math.max(p.step - 1, 0) }))}>
        ◀
      </button>
      <select
        value={step}
        onChange={(event) => setPosition((p) => ({ ...p, step: Number(event.target.value) }))}
      >
        {files.map((name, index) => (
          <option key={name} value={index}>
            {name.replace(/^step-|\.json$/g, "")}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => setPosition((p) => ({ ...p, step: Math.min(p.step + 1, files.length - 1) }))}
      >
        ▶
      </button>
      <span className="fixture-roles">
        {ROLES.map((item) => (
          <button
            key={item.role}
            type="button"
            className={item.role === role ? "is-active" : ""}
            onClick={() => setPosition((p) => ({ ...p, role: item.role }))}
          >
            {item.label}
          </button>
        ))}
      </span>
      {error && <span className="fixture-error">{error}</span>}
    </div>
  );
}
