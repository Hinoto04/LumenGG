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
import type { Catalog, Deck, Language, User } from "./types";
import { bootstrapCatalog, updateCatalog, cacheThumbnails } from "./catalog";
import {
  preference,
  setPreference,
  documents,
  pending,
  mergeSnapshot,
  saveDocument,
} from "./storage";
import { request, ApiError, logOut } from "./api";
import { deckError } from "./core";
import { uiTranslation } from "./i18n";

interface AppContextValue {
  catalog: Catalog | null;
  language: Language;
  setLanguage: (l: Language) => Promise<void>;
  user: User | null;
  scope: string;
  decks: Deck[];
  amounts: Record<number, number>;
  syncErrors: Record<number, string>;
  status: string;
  loading: boolean;
  online: boolean;
  error: string;
  refresh: () => Promise<void>;
  sync: () => Promise<void>;
  setUser: (u: User | null) => Promise<void>;
  reload: () => Promise<void>;
  saveDeck: (d: Deck) => Promise<string | null>;
  deleteDeck: (d: Deck) => Promise<void>;
  setAmount: (
    id: number,
    n: number | ((current: number) => number),
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
    [amounts, setAmounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true),
    [online, setOnline] = useState(true),
    [status, setStatus] = useState(""),
    [error, setError] = useState("");
  const [syncErrors, setSyncErrors] = useState<Record<number, string>>({});
  const amountsRef = useRef(amounts),
    editEpoch = useRef(0);
  amountsRef.current = amounts;
  const scope = user ? "user:" + user.id : "guest";
  const scopeRef = useRef(scope),
    userRef = useRef(user),
    catalogRef = useRef(catalog),
    syncFlight = useRef<Promise<void> | null>(null);
  scopeRef.current = scope;
  userRef.current = user;
  catalogRef.current = catalog;
  const reload = useCallback(async () => {
    const current = scopeRef.current;
    const epoch = editEpoch.current;
    const ds = await documents<Deck>(current, "deck"),
      cs = await documents<{ card_id: number; amount: number }>(
        current,
        "collection",
      );
    if (current !== scopeRef.current || epoch !== editEpoch.current) return;
    setDecks(ds);
    setAmounts(Object.fromEntries(cs.map((c) => [c.card_id, c.amount])));
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
        setSyncErrors({});
        setAccount(u);
        userRef.current = u;
        scopeRef.current = u ? "user:" + u.id : "guest";
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
    setSyncErrors({});
    setAccount(u);
    await reload();
  }
  async function saveDeck(deck: Deck) {
    if (scope !== scopeRef.current) return "계정이 변경되었습니다.";
    editEpoch.current++;
    const issue = catalogRef.current
      ? deckError(deck, catalogRef.current)
      : "DB를 불러오는 중입니다.";
    await saveDocument(scopeRef.current, "deck", deck.uuid, deck, !issue);
    await reload();
    if (!issue) sync();
    return issue;
  }
  async function deleteDeck(deck: Deck) {
    if (scope !== scopeRef.current) return;
    editEpoch.current++;
    await saveDocument(
      scopeRef.current,
      "deck",
      deck.uuid,
      { ...deck, deleted: true },
      true,
      "delete",
    );
    await reload();
    sync();
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
    try {
      await saveDocument(scopeRef.current, "collection", String(id), {
        card_id: id,
        amount,
      });
      await reload();
      sync();
    } catch (error) {
      setStatus(userMessage(error));
      await reload();
    }
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
        syncErrors,
        status,
        loading,
        online,
        error,
        refresh,
        sync,
        setUser,
        reload,
        saveDeck,
        deleteDeck,
        setAmount,
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
