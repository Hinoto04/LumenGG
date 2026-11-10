import { useEffect, useState } from "react";
import { liveUrl } from "./mode";
import { getJson, postJson } from "./net/http";
import { lastGame } from "./net/live";

interface DeckRow {
  id: number;
  name: string;
  author: string;
  character: string;
  character_id: number;
  is_owner?: boolean;
}

interface NewGame {
  view_token: string;
  seats: { p1: string; p2?: string };
  /** 전용 패시브 캐릭터가 있는 수동 대전은 예전 화면 주소가 온다 */
  legacy?: boolean;
  urls: { p1: string; p2?: string; viewer: string };
}

const TIMER_CHOICES = [0, 15, 30, 45, 60, 90, 120];
const RECENT_KEY = "lumen-play-recent-decks";

function recentDecks(): DeckRow[] {
  try {
    const rows = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as DeckRow[];
    return Array.isArray(rows) ? rows.slice(0, 8) : [];
  } catch {
    return [];
  }
}

function rememberDeck(deck: DeckRow) {
  try {
    const rows = [deck, ...recentDecks().filter((row) => row.id !== deck.id)].slice(0, 8);
    localStorage.setItem(RECENT_KEY, JSON.stringify(rows));
  } catch {
    /* 최근 목록은 편의 기능일 뿐이다 */
  }
}

function TimerSelect({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
        {TIMER_CHOICES.map((seconds) => (
          <option key={seconds} value={seconds}>
            {seconds ? `${seconds}초` : "제한 없음"}
          </option>
        ))}
      </select>
    </label>
  );
}

/** 덱 고르기: 내 덱(로그인), 최근에 쓴 덱, 검색(이름·작성자·캐릭터 2글자 이상 또는 덱 ID) */
function DeckPicker({
  label,
  value,
  onChange,
  mine,
  loginRequired,
}: {
  label: string;
  value: DeckRow | null;
  onChange: (deck: DeckRow) => void;
  mine: DeckRow[];
  loginRequired: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DeckRow[] | null>(null);
  const [open, setOpen] = useState(!value);
  const recent = recentDecks();

  useEffect(() => {
    const text = query.trim();
    if (text.length < 2 && !/^\d+$/.test(text)) {
      setResults(null);
      return;
    }
    const timer = setTimeout(() => {
      getJson<{ decks: DeckRow[] }>(`/battlelog/play/api/decks/?q=${encodeURIComponent(text)}`)
        .then((data) => setResults(data.decks))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  const choose = (deck: DeckRow) => {
    rememberDeck(deck);
    onChange(deck);
    setOpen(false);
    setQuery("");
  };

  const list = (rows: DeckRow[]) =>
    rows.map((deck) => (
      <li key={deck.id}>
        <button type="button" className={value?.id === deck.id ? "is-active" : ""} onClick={() => choose(deck)}>
          <b>{deck.character}</b>
          <span>{deck.name}</span>
          <small>
            {deck.author} · #{deck.id}
          </small>
        </button>
      </li>
    ));

  return (
    <div className="deck-picker">
      <div className="deck-picker-head">
        <span className="deck-picker-label">{label}</span>
        {value && !open && (
          <button type="button" className="deck-chosen" onClick={() => setOpen(true)}>
            <b>{value.character}</b> {value.name} <small>바꾸기</small>
          </button>
        )}
      </div>
      {open && (
        <div className="deck-picker-body">
          <input
            type="search"
            value={query}
            placeholder="덱 이름·작성자·캐릭터 또는 덱 번호"
            onChange={(event) => setQuery(event.target.value)}
            aria-label={`${label} 검색`}
          />
          {results ? (
            <ul className="deck-list">{results.length ? list(results) : <li className="muted">찾은 덱이 없습니다.</li>}</ul>
          ) : (
            <>
              {mine.length > 0 && (
                <>
                  <p className="deck-group">내 덱</p>
                  <ul className="deck-list">{list(mine)}</ul>
                </>
              )}
              {recent.length > 0 && (
                <>
                  <p className="deck-group">최근 사용</p>
                  <ul className="deck-list">{list(recent)}</ul>
                </>
              )}
              {loginRequired && (
                <p className="muted">
                  <a href={`/login/?next=${encodeURIComponent(location.pathname)}`}>로그인</a>하면 비공개 덱을 포함한 내 덱을 고를 수
                  있습니다.
                </p>
              )}
            </>
          )}
          {value && (
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              취소
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** 새 대전 만들기. 사이트(/battlelog/play/)와 개발 서버 모두 같은 API를 쓴다. */
export function Lobby() {
  const [mine, setMine] = useState<DeckRow[]>([]);
  const [loginRequired, setLoginRequired] = useState(false);
  const [p1, setP1] = useState<DeckRow | null>(null);
  const [p2, setP2] = useState<DeckRow | null>(null);
  const [opponent, setOpponent] = useState<"ai" | "human">("ai");
  const [mode, setMode] = useState<"automatic" | "manual">("automatic");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [rivalUrl, setRivalUrl] = useState<{ mine: string; rival: string; watch: string } | null>(null);
  const [readyTimer, setReadyTimer] = useState(0);
  const [effectTimer, setEffectTimer] = useState(0);
  const [resume] = useState(lastGame);

  useEffect(() => {
    getJson<{ decks: DeckRow[]; login_required?: boolean }>("/battlelog/play/api/decks/?mine=1")
      .then((data) => {
        setMine(data.decks);
        setLoginRequired(!!data.login_required);
      })
      .catch(() => setError("서버에 연결하지 못했습니다."));
  }, []);

  // 사람과 대전할 때만 기본 제한 시간을 둔다. AI는 기다려 주므로 없음.
  const chooseOpponent = (value: "ai" | "human") => {
    setOpponent(value);
    if (value === "ai") setMode("automatic");
    setReadyTimer(value === "human" ? 30 : 0);
    setEffectTimer(value === "human" ? 60 : 0);
  };

  const start = async () => {
    if (!p1 || !p2) return;
    setCreating(true);
    setError(null);
    try {
      const data = await postJson<NewGame>("/battlelog/play/api/new/", {
        p1_deck: p1.id,
        p2_deck: p2.id,
        opponent,
        mode,
        ready_timeout_seconds: readyTimer,
        effect_timeout_seconds: effectTimer,
      });
      // 예전 화면이 필요한 수동 대전은 서버가 준 주소를, 나머지는 이 클라이언트 주소를 쓴다.
      const mineUrl = data.legacy ? data.urls.p1 : liveUrl({ view: data.view_token, seat: "p1", token: data.seats.p1 });
      if (data.seats.p2) {
        setRivalUrl({
          mine: mineUrl,
          rival: data.legacy && data.urls.p2 ? data.urls.p2 : liveUrl({ view: data.view_token, seat: "p2", token: data.seats.p2 }),
          watch: data.legacy ? data.urls.viewer : liveUrl({ view: data.view_token, seat: "", token: "" }),
        });
        return;
      }
      location.assign(mineUrl);
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="lobby">
      <h1>루멘콘덴서 대전</h1>
      {resume && !rivalUrl && (
        <section className="lobby-card lobby-resume">
          <p>진행 중이던 대전이 있습니다.</p>
          <a className="btn-primary" href={liveUrl(resume)}>
            이어하기
          </a>
        </section>
      )}
      {rivalUrl ? (
        <section className="lobby-card">
          <p>상대 좌석 주소입니다. 상대에게 보내거나 다른 창·기기에서 여세요.</p>
          <code className="lobby-link">{location.origin + rivalUrl.rival}</code>
          <p className="muted">관전 주소</p>
          <code className="lobby-link">{location.origin + rivalUrl.watch}</code>
          <div className="lobby-row">
            <a className="btn-secondary" href={rivalUrl.rival} target="_blank" rel="noreferrer">
              상대 좌석 새 창
            </a>
            <a className="btn-primary" href={rivalUrl.mine}>
              내 좌석으로
            </a>
          </div>
        </section>
      ) : (
        <section className="lobby-card">
          <DeckPicker label="내 덱" value={p1} onChange={setP1} mine={mine} loginRequired={loginRequired} />
          <DeckPicker label="상대 덱" value={p2} onChange={setP2} mine={mine} loginRequired={false} />
          <div className="lobby-row segmented" role="radiogroup" aria-label="상대">
            {(
              [
                ["ai", "AI와 대전"],
                ["human", "사람과 대전"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={opponent === value}
                className={opponent === value ? "is-active" : ""}
                onClick={() => chooseOpponent(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {opponent === "human" && (
            <div className="lobby-row segmented" role="radiogroup" aria-label="대전 방식">
              {(
                [
                  ["automatic", "자동 판정"],
                  ["manual", "수동(샌드박스)"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={mode === value}
                  className={mode === value ? "is-active" : ""}
                  onClick={() => setMode(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          {mode === "manual" && <p className="muted">수동 대전은 규칙을 판정하지 않습니다. 카드 이동과 HP·FP를 직접 조작합니다.</p>}
          <div className="lobby-row lobby-timers" hidden={mode === "manual"}>
            <TimerSelect label="레디 제한" value={readyTimer} onChange={setReadyTimer} />
            <TimerSelect label="효과 선택 제한" value={effectTimer} onChange={setEffectTimer} />
          </div>
          <button type="button" className="btn-primary lobby-start" disabled={creating || !p1 || !p2} onClick={start}>
            {creating ? "만드는 중…" : "대전 시작"}
          </button>
        </section>
      )}
      {error && <p className="lobby-error">{error}</p>}
      {import.meta.env.DEV && (
        <p className="muted">
          <a href="?fixtures">픽스처 보기</a> · <a href="/play-dev/login/">개발 사용자로 로그인</a>
        </p>
      )}
    </main>
  );
}
