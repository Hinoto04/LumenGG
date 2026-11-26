import { useEffect, useState } from "react";
import { liveUrl } from "./mode";
import { getJson, postJson } from "./net/http";
import { lastGame } from "./net/live";
import { QuickPanel, RoomPanel, rememberedRoom } from "./RoomLobby";
import { completedLessons, startTutorial } from "./components/TutorialCoach";
import { seconds as formatSeconds, t } from "./i18n";

export interface DeckRow {
  id: number;
  name: string;
  author: string;
  character: string;
  character_id: number;
  is_owner?: boolean;
}

/** 운영진이 관리자 화면에서 등록한 AI 상대(덱 + 성향·선호 카드·콤보 루트) */
export interface AIDeckRow {
  id: number;
  name: string;
  description: string;
  style: string;
  style_label: string;
  character: string;
  character_img: string;
  deck_id: number;
  deck_name: string;
}

interface NewGame {
  view_token: string;
  seats: { p1: string; p2?: string };
  /** 전용 패시브 캐릭터가 있는 수동 대전은 예전 화면 주소가 온다 */
  legacy?: boolean;
  urls: { p1: string; p2?: string; viewer: string };
}

const TIMER_CHOICES = [0, 10, 15, 30, 45, 60, 90, 120];
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

export function TimerSelect({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
        {TIMER_CHOICES.map((seconds) => (
          <option key={seconds} value={seconds}>
            {seconds ? formatSeconds(seconds) : t("제한 없음")}
          </option>
        ))}
      </select>
    </label>
  );
}

/** AI 상대 고르기: 등록된 AI 덱만 고를 수 있다 */
function AIDeckPicker({ value, onChange }: { value: AIDeckRow | null; onChange: (deck: AIDeckRow) => void }) {
  const [rows, setRows] = useState<AIDeckRow[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getJson<{ ai_decks: AIDeckRow[] }>("/battlelog/play/api/ai-decks/")
      .then((data) => setRows(data.ai_decks))
      .catch(() => setFailed(true));
  }, []);

  return (
    <div className="deck-picker">
      <span className="deck-picker-label">{t("AI 상대")}</span>
      {failed ? (
        <p className="muted">{t("AI 목록을 불러오지 못했습니다.")}</p>
      ) : rows === null ? (
        <p className="muted">{t("불러오는 중…")}</p>
      ) : rows.length === 0 ? (
        <p className="muted">{t("등록된 AI 덱이 없습니다.")}</p>
      ) : (
        <ul className="ai-deck-list">
          {rows.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                className={value?.id === row.id ? "is-active" : ""}
                aria-pressed={value?.id === row.id}
                onClick={() => onChange(row)}
              >
                {row.character_img ? <img src={row.character_img} alt="" loading="lazy" /> : <span className="ai-deck-face" />}
                <span className="ai-deck-text">
                  <b>{row.name}</b>
                  <small>
                    {row.character} · {row.style_label}
                  </small>
                  {row.description && <em>{row.description}</em>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 덱 고르기: 내 덱(로그인), 최근에 쓴 덱, 검색(이름·작성자·캐릭터 2글자 이상 또는 덱 ID) */
export function DeckPicker({
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
    // 한 글자 작성자명도 검색할 수 있다.
    if (!text) {
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
            <b>{value.character}</b> {value.name} <small>{t("바꾸기")}</small>
          </button>
        )}
      </div>
      {open && (
        <div className="deck-picker-body">
          <input
            type="search"
            value={query}
            placeholder={t("덱 이름·작성자·캐릭터 또는 덱 번호")}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={t("{label} 검색", { label })}
          />
          {results ? (
            <ul className="deck-list">{results.length ? list(results) : <li className="muted">{t("찾은 덱이 없습니다.")}</li>}</ul>
          ) : (
            <>
              {mine.length > 0 && (
                <>
                  <p className="deck-group">{t("내 덱")}</p>
                  <ul className="deck-list">{list(mine)}</ul>
                </>
              )}
              {recent.length > 0 && (
                <>
                  <p className="deck-group">{t("최근 사용")}</p>
                  <ul className="deck-list">{list(recent)}</ul>
                </>
              )}
              {loginRequired && (
                <p className="muted">
                  <a href={`/login/?next=${encodeURIComponent(location.pathname)}`}>{t("로그인")}</a>
                  {t("하면 비공개 덱을 포함한 내 덱을 고를 수 있습니다.")}
                </p>
              )}
            </>
          )}
          {value && (
            <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
              {t("취소")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

type LobbyTab = "ai" | "room" | "quick";

const TABS: [LobbyTab, string][] = [
  ["ai", t("AI와 대전")],
  ["room", t("방")],
  ["quick", t("퀵 매치")],
];

interface TutorialRow {
  id: string;
  title: string;
  summary?: string;
  steps: number;
  available: boolean;
  /** basic(기초) | intermediate(중급). 예전 서버는 보내지 않는다. */
  level?: string;
}

const TUTORIAL_LEVELS: [string, string][] = [
  ["basic", "기초"],
  ["intermediate", "중급"],
];
const TUTORIAL_FOLDERS_KEY = "lumen-play-tutorial-folders";

/** 사용자가 직접 접거나 편 단계 묶음(기기마다). 없으면 기본값(다음 단원이 있는 묶음만 펼침). */
function savedFolders(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(TUTORIAL_FOLDERS_KEY) || "{}") as Record<string, boolean>;
  } catch {
    return {};
  }
}

/**
 * 튜토리얼 과정 카드(docs/TUTORIAL.md). 준비된 단원 목록을 차례로 보여 주고, 마치지 않은 첫 단원을
 * 큰 버튼으로 권한다. 다른 단원은 줄을 눌러 바로 시작한다. 준비된 단원이 없으면 보이지 않는다.
 */
function TutorialPanel() {
  const [lessons, setLessons] = useState<TutorialRow[]>([]);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [folders, setFolders] = useState<Record<string, boolean>>(savedFolders);
  useEffect(() => {
    getJson<{ tutorials: TutorialRow[] }>("/battlelog/play/api/tutorials/")
      .then((data) => setLessons(data.tutorials.filter((row) => row.available)))
      .catch(() => setLessons([]));
  }, []);
  if (!lessons.length) return null;
  const completed = completedLessons();
  const next = lessons.find((row) => !completed[row.id]) ?? null;
  const allDone = !next;
  const start = async (lesson: string) => {
    setStarting(lesson);
    setError(null);
    try {
      await startTutorial(lesson);
    } catch (exception) {
      setError((exception as Error).message);
      setStarting(null);
    }
  };
  return (
    <aside className="lobby-aside" aria-label={t("튜토리얼")}>
      <section className="lobby-card lobby-tutorial">
        <span className="lobby-kicker">{t("튜토리얼")}</span>
        <p>
          {allDone
            ? t("모든 단원을 마쳤습니다. 언제든 다시 해 볼 수 있어요.")
            : t("처음이신가요? 단원마다 몇 분씩 직접 해 보며 기본 규칙을 배워 보세요.")}
        </p>
        {TUTORIAL_LEVELS.map(([level, label]) => {
          const rows = lessons.filter((row) => (row.level ?? "basic") === level);
          if (!rows.length) return null;
          const done = rows.filter((row) => completed[row.id]).length;
          const holdsNext = rows.some((row) => row.id === next?.id);
          const open = folders[level] ?? (allDone ? level === TUTORIAL_LEVELS[0][0] : holdsNext);
          const toggle = () => {
            const changed = { ...folders, [level]: !open };
            setFolders(changed);
            try {
              localStorage.setItem(TUTORIAL_FOLDERS_KEY, JSON.stringify(changed));
            } catch {
              /* 접힘 기억은 편의 기능일 뿐이다 */
            }
          };
          return (
            <div key={level} className={`tutorial-level ${open ? "is-open" : ""}`}>
              <button
                type="button"
                className="tutorial-level-title"
                aria-expanded={open}
                aria-controls={`tutorial-level-${level}`}
                onClick={toggle}
              >
                <span className="tutorial-level-chevron" aria-hidden="true">
                  ▸
                </span>
                <span>{t(label)}</span>
                <span className="tutorial-level-count">
                  {done} / {rows.length}
                </span>
              </button>
              <ol className="tutorial-lessons" id={`tutorial-level-${level}`} hidden={!open}>
                {rows.map((row, index) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      className={`${completed[row.id] ? "is-done" : ""} ${next?.id === row.id ? "is-next" : ""}`}
                      disabled={!!starting}
                      onClick={() => start(row.id)}
                    >
                      <span className="tutorial-lesson-no">{completed[row.id] ? "✓" : index + 1}</span>
                      <span className="tutorial-lesson-text">
                        <b>{row.title}</b>
                        {row.summary && <small>{row.summary}</small>}
                      </span>
                      {starting === row.id && <span className="muted">{t("만드는 중…")}</span>}
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          );
        })}
        {next && (
          <button type="button" className="btn-primary" disabled={!!starting} onClick={() => start(next.id)}>
            {next.id === lessons[0].id ? t("튜토리얼 시작") : t("이어서: {title}", { title: next.title })}
          </button>
        )}
        {error && <p className="lobby-error">{error}</p>}
      </section>
    </aside>
  );
}

function initialTab(): LobbyTab {
  if (new URLSearchParams(location.search).get("room") || rememberedRoom("room")) return "room";
  if (rememberedRoom("quick")) return "quick";
  return "ai";
}

/**
 * 대전 로비. 사이트의 시뮬레이터 시작 화면(/battlelog/simulator/)과 이 클라이언트(/battlelog/play/)가 같은 화면이다.
 * - AI와 대전: 내 덱과 등록된 AI 상대(관리자 화면의 AI 덱)를 고른다.
 * - 방: 방을 만들거나 코드로 들어가 각자 자기 덱을 고른다(RoomLobby.tsx).
 * - 퀵 매치: 내 덱만 정하면 기다리는 다른 플레이어와 짝을 짓는다.
 */
export function Lobby() {
  const [tab, setTab] = useState<LobbyTab>(initialTab);
  const [mine, setMine] = useState<DeckRow[]>([]);
  const [loginRequired, setLoginRequired] = useState(false);
  const [p1, setP1] = useState<DeckRow | null>(null);
  const [p2, setP2] = useState<AIDeckRow | null>(null);
  // 사람끼리는 방·퀵 매치에서 만든다. 이 탭은 AI 대전만 만든다.
  const opponent = "ai" as const;
  const mode = "automatic" as const;
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [rivalUrl, setRivalUrl] = useState<{
    mine: string;
    rival: string;
    watch: string;
  } | null>(null);
  const [readyTimer, setReadyTimer] = useState(10);
  const [effectTimer, setEffectTimer] = useState(30);
  const [resume] = useState(lastGame);

  useEffect(() => {
    getJson<{ decks: DeckRow[]; login_required?: boolean }>("/battlelog/play/api/decks/?mine=1")
      .then((data) => {
        setMine(data.decks);
        setLoginRequired(!!data.login_required);
      })
      .catch(() => setError(t("서버에 연결하지 못했습니다.")));
  }, []);

  const start = async () => {
    if (!p1 || !p2) return;
    setCreating(true);
    setError(null);
    try {
      const data = await postJson<NewGame>("/battlelog/play/api/new/", {
        p1_deck: p1.id,
        ai_deck: p2.id,
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
          rival:
            data.legacy && data.urls.p2
              ? data.urls.p2
              : liveUrl({
                  view: data.view_token,
                  seat: "p2",
                  token: data.seats.p2,
                }),
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
      <div className="lobby-layout">
        <div className="lobby-main">
          <header className="lobby-head">
            <span className="lobby-kicker">LUMEN CONDENSOR SIMULATOR</span>
            <h1>{t("루멘콘덴서 대전")}</h1>
          </header>
          {resume && !rivalUrl && (
            <section className="lobby-card lobby-resume">
              <p>{t("진행 중이던 대전이 있습니다.")}</p>
              <a className="btn-primary" href={liveUrl(resume)}>
                {t("이어하기")}
              </a>
            </section>
          )}
          <div className="lobby-row segmented lobby-tabs" role="tablist" aria-label={t("대전 종류")}>
            {TABS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                className={tab === value ? "is-active" : ""}
                onClick={() => setTab(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {tab === "room" && <RoomPanel mine={mine} loginRequired={loginRequired} />}
          {tab === "quick" && <QuickPanel mine={mine} loginRequired={loginRequired} />}
          {tab === "ai" && (
            <section className="lobby-card">
              <DeckPicker label={t("내 덱")} value={p1} onChange={setP1} mine={mine} loginRequired={loginRequired} />
              <AIDeckPicker value={p2} onChange={setP2} />
              <div className="lobby-row lobby-timers">
                <TimerSelect label={t("레디 제한")} value={readyTimer} onChange={setReadyTimer} />
                <TimerSelect label={t("효과 선택 제한")} value={effectTimer} onChange={setEffectTimer} />
              </div>
              <button type="button" className="btn-primary lobby-start" disabled={creating || !p1 || !p2} onClick={start}>
                {creating ? t("만드는 중…") : t("대전 시작")}
              </button>
            </section>
          )}
          {error && <p className="lobby-error">{error}</p>}
          {import.meta.env.DEV && (
            <p className="muted">
              <a href="?fixtures">픽스처 보기</a> · <a href="/play-dev/login/">개발 사용자로 로그인</a>
            </p>
          )}
        </div>
        {/* 넓은 화면은 오른쪽 옆 열에 늘 붙어 있고, 좁은 화면은 대전 설정 아래에 온다. */}
        {!rivalUrl && <TutorialPanel />}
      </div>
    </main>
  );
}
