import { userMessage } from "./errors";
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
} from "react";
import { AppState } from "react-native";
import NetInfo from "@react-native-community/netinfo";
import type {
  Catalog,
  CollectionDocument,
  Deck,
  Language,
  User,
} from "./types";
import { normalizeCategory } from "./collection-data";
import { mergeBookmarks } from "./deck-display";
import { bootstrapCatalog, updateCatalog, cacheThumbnails } from "./catalog";
import {
  preference,
  setPreference,
  documents,
  pending,
  mergeSnapshot,
  saveDocument,
  disableDeckWrites,
} from "./storage";
import { request, ApiError, logOut } from "./api";
import { uiTranslation } from "./i18n";

interface AppContextValue {
  catalog: Catalog | null;
  language: Language;
  setLanguage: (l: Language) => Promise<void>;
  user: User | null;
  scope: string;
  decks: Deck[];
  amounts: Record<number, number>;
  /** 컬렉션 항목별 하트 분류(1~5). 분류가 없으면 키가 없다. */
  categories: Record<number, number>;
  /** 로그인한 계정이 북마크한 덱 ID. */
  bookmarks: number[];
  syncErrors: Record<number, string>;
  status: string;
  loading: boolean;
  online: boolean;
  error: string;
  refresh: () => Promise<void>;
  sync: () => Promise<void>;
  setUser: (u: User | null) => Promise<void>;
  reload: () => Promise<void>;
  saveDeck: (deck: Deck) => Promise<void>;
  setAmount: (
    id: number,
    n: number | ((current: number) => number),
  ) => Promise<void>;
  setCategory: (id: number, category: number) => Promise<void>;
  setBookmark: (deckId: number, bookmarked: boolean) => Promise<boolean>;
  /** 서버 덱 목록·상세의 bookmarked 값을 로컬 북마크 목록에 반영한다. */
  rememberBookmarks: (
    decks: readonly { id?: number; bookmarked?: boolean }[],
  ) => Promise<void>;
  t: (key: string) => string;
  signOut: () => Promise<void>;
}
const Context = createContext<AppContextValue>(null as any);
export const useApp = () => useContext(Context);
export function AppProvider({ children }: { children: React.ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [language, setLang] = useState<Language>("ko");
  const [user, setAccount] = useState<User | null>(null),
    [decks, setDecks] = useState<Deck[]>([]),
    [amounts, setAmounts] = useState<Record<number, number>>({}),
    [categories, setCategories] = useState<Record<number, number>>({}),
    [bookmarks, setBookmarks] = useState<number[]>([]);
  const [loading, setLoading] = useState(true),
    [online, setOnline] = useState(true),
    [status, setStatus] = useState(""),
    [error, setError] = useState("");
  const [syncErrors, setSyncErrors] = useState<Record<number, string>>({});
  const amountsRef = useRef(amounts),
    // 예전 문서에는 category가 없으므로, 아는 값만 보내 서버의 분류를 덮지 않는다.
    categoriesRef = useRef<Record<number, number | undefined>>({}),
    editEpoch = useRef(0);
  amountsRef.current = amounts;
  const scope = user ? "user:" + user.id : "guest";
  const scopeRef = useRef(scope),
    userRef = useRef(user),
    syncFlight = useRef<Promise<void> | null>(null);
  scopeRef.current = scope;
  userRef.current = user;
  const reload = useCallback(async () => {
    const current = scopeRef.current;
    const epoch = editEpoch.current;
    const ds = await documents<Deck>(current, "deck"),
      cs = await documents<CollectionDocument>(current, "collection"),
      marks = await preference<number[]>("deck-bookmarks:" + current, []);
    if (current !== scopeRef.current || epoch !== editEpoch.current) return;
    setDecks(ds);
    setAmounts(Object.fromEntries(cs.map((c) => [c.card_id, c.amount])));
    categoriesRef.current = Object.fromEntries(
      cs.map((c) => [
        c.card_id,
        c.category === undefined || c.category === null
          ? undefined
          : normalizeCategory(c.category),
      ]),
    );
    setCategories(
      Object.fromEntries(
        cs
          .map((c) => [c.card_id, normalizeCategory(c.category)] as const)
          .filter(([, category]) => category > 0),
      ),
    );
    setBookmarks(Array.isArray(marks) ? marks : []);
    setSyncErrors(
      Object.fromEntries(
        cs
          .filter((c: any) => c.sync_error)
          .map((c: any) => [c.card_id, c.sync_error]),
      ),
    );
  }, []);
  const sync = useCallback(async () => {
    if (syncFlight.current) return syncFlight.current;
    const owner = userRef.current,
      current = scopeRef.current;
    if (!owner) return;
    syncFlight.current = (async () => {
      try {
        await disableDeckWrites();
        if (current === scopeRef.current) setStatus("동기화 중");
        let more = true,
          failed = 0;
        while (more) {
          const sent = await pending(current);
          if (current !== scopeRef.current) return;
          const response = await request(
            "/sync",
            {
              method: "POST",
              body: JSON.stringify({
                operations: sent.map((q) => q.operation),
              }),
            },
            true,
            false,
            owner.id,
          );
          if (response.user.id !== owner.id)
            throw new Error("Account mismatch.");
          await mergeSnapshot(current, response, sent);
          if (Array.isArray(response.deck_bookmarks))
            await setPreference(
              "deck-bookmarks:" + current,
              response.deck_bookmarks.filter((id: unknown) =>
                Number.isInteger(id),
              ),
            );
          failed += (response.results || []).filter((r: any) => !r.ok).length;
          more = sent.length === 100;
        }
        if (current === scopeRef.current) {
          setStatus(failed ? "일부 변경을 확인해주세요." : "동기화 완료");
          await reload();
        }
      } catch (err) {
        if (current === scopeRef.current) {
          setStatus(
            err instanceof ApiError && err.status === 401
              ? "다시 로그인해주세요."
              : "오프라인 저장 · 동기화 대기",
          );
        }
      }
    })().finally(() => {
      syncFlight.current = null;
    });
    return syncFlight.current;
  }, [reload]);
  const refresh = useCallback(async () => {
    try {
      const next = await updateCatalog(true);
      if (next) {
        setCatalog(next);
        cacheThumbnails(next).catch(() => undefined);
      }
      setError("");
    } catch (err) {
      setError(userMessage(err));
    }
  }, []);
  useEffect(() => {
    (async () => {
      try {
        const [c, lang, u] = await Promise.all([
          bootstrapCatalog(),
          preference<Language>("language", "ko"),
          preference<User | null>("user", null),
        ]);
        setCatalog(c);
        setLang(lang);
        editEpoch.current++;
        setDecks([]);
        setAmounts({});
        amountsRef.current = {};
        setCategories({});
        categoriesRef.current = {};
        setBookmarks([]);
        setSyncErrors({});
        setAccount(u);
        userRef.current = u;
        scopeRef.current = u ? "user:" + u.id : "guest";
        await disableDeckWrites();
        await reload();
        cacheThumbnails(c).catch(() => undefined);
        refresh().catch(() => undefined);
        sync().catch(() => undefined);
      } catch (err) {
        setError(userMessage(err));
      } finally {
        setLoading(false);
      }
    })();
    const net = NetInfo.addEventListener((state) => {
      const connected = !!state.isConnected;
      setOnline(connected);
      if (connected) {
        sync();
        updateCatalog()
          .then((c) => {
            if (c) {
              setCatalog(c);
              cacheThumbnails(c);
            }
          })
          .catch(() => undefined);
      }
    });
    const app = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        sync();
        updateCatalog()
          .then((c) => {
            if (c) {
              setCatalog(c);
              cacheThumbnails(c);
            }
          })
          .catch(() => undefined);
      }
    });
    const timer = setInterval(() => {
      if (AppState.currentState === "active") sync();
    }, 30000);
    return () => {
      net();
      app.remove();
      clearInterval(timer);
    };
  }, [refresh, reload, sync]);
  async function setUser(u: User | null) {
    await setPreference("user", u);
    userRef.current = u;
    scopeRef.current = u ? "user:" + u.id : "guest";
    editEpoch.current++;
    setDecks([]);
    setAmounts({});
    amountsRef.current = {};
    setCategories({});
    categoriesRef.current = {};
    setBookmarks([]);
    setSyncErrors({});
    setAccount(u);
    await reload();
  }
  async function setAmount(
    id: number,
    n: number | ((current: number) => number),
  ) {
    if (scope !== scopeRef.current) return;
    editEpoch.current++;
    const amount = Math.max(
      0,
      Math.min(
        32767,
        typeof n === "function" ? n(amountsRef.current[id] || 0) : n,
      ),
    );
    amountsRef.current = { ...amountsRef.current, [id]: amount };
    setAmounts(amountsRef.current);
    await saveCollection(id);
  }
  async function setCategory(id: number, value: number) {
    if (scope !== scopeRef.current) return;
    editEpoch.current++;
    const category = normalizeCategory(value);
    categoriesRef.current = { ...categoriesRef.current, [id]: category };
    setCategories((current) => {
      const next = { ...current };
      if (category) next[id] = category;
      else delete next[id];
      return next;
    });
    await saveCollection(id);
  }
  async function saveCollection(id: number) {
    const category = categoriesRef.current[id];
    const document: CollectionDocument = {
      card_id: id,
      amount: amountsRef.current[id] || 0,
    };
    if (category !== undefined) document.category = category;
    try {
      await saveDocument(scopeRef.current, "collection", String(id), document);
      await reload();
      sync();
    } catch (error) {
      setStatus(userMessage(error));
      await reload();
    }
  }
  async function setBookmark(deckId: number, value: boolean) {
    const owner = userRef.current,
      current = scopeRef.current;
    if (!owner) return false;
    const result = await request(
      `/decks/${deckId}/bookmark`,
      { method: "PUT", body: JSON.stringify({ bookmarked: value }) },
      true,
      false,
      owner.id,
    );
    const marked = !!result?.bookmarked;
    if (current !== scopeRef.current) return marked;
    const saved = await preference<number[]>("deck-bookmarks:" + current, []);
    const next = new Set(Array.isArray(saved) ? saved : []);
    if (marked) next.add(deckId);
    else next.delete(deckId);
    const list = [...next].sort((a, b) => a - b);
    await setPreference("deck-bookmarks:" + current, list);
    if (current === scopeRef.current) setBookmarks(list);
    return marked;
  }
  async function rememberBookmarks(
    items: readonly { id?: number; bookmarked?: boolean }[],
  ) {
    const current = scopeRef.current;
    if (!userRef.current) return;
    const saved = await preference<number[]>("deck-bookmarks:" + current, []);
    const list = mergeBookmarks(Array.isArray(saved) ? saved : [], items);
    if (!list || current !== scopeRef.current) return;
    await setPreference("deck-bookmarks:" + current, list);
    if (current === scopeRef.current) setBookmarks(list);
  }
  const t = (key: string) =>
    uiTranslation(key, language) || catalog?.rules.ui?.[language]?.[key] || key;
  return (
    <Context.Provider
      value={{
        catalog,
        language,
        setLanguage: async (l) => {
          await setPreference("language", l);
          setLang(l);
        },
        user,
        scope,
        decks,
        amounts,
        categories,
        bookmarks,
        syncErrors,
        status,
        loading,
        online,
        error,
        refresh,
        sync,
        setUser,
        reload,
        saveDeck: async (deck) => {
          editEpoch.current++;
          await saveDocument(scopeRef.current, "deck", deck.uuid, {
            ...deck,
            schema_version: 2,
          });
          await reload();
          void sync();
        },
        setAmount,
        setCategory,
        setBookmark,
        rememberBookmarks,
        t,
        signOut: async () => {
          const revocation = logOut();
          await setUser(null);
          await revocation;
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
