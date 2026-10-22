import { useCallback, useRef, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { request } from "./api";
import { preference, setPreference } from "./storage";
import { userMessage } from "./errors";
import { useApp } from "./provider";

export interface TournamentSummary {
  id: number;
  name: string;
  status: string;
  format: string;
  event_date: string;
  venue: string;
  participant_name: string;
  dropped: boolean;
}
export interface TournamentMatch {
  id: number;
  tournament_id: number;
  round_id: number;
  round_number: number;
  stage: string;
  table: string;
  round_status: string;
  round_ends_at: string;
  set_count: number;
  status: string;
  is_bye: boolean;
  me: "p1" | "p2";
  players: {
    p1: { id: number; name: string };
    p2: { id: number; name: string } | null;
  };
  score: { p1: number; p2: number };
  winner: string;
  reported_at: string | null;
  can_report: boolean;
  can_open_calculator: boolean;
}
export interface TournamentDetail extends TournamentSummary {
  description: string;
  matches: TournamentMatch[];
  decks: { id: number; slot: number; name: string }[];
}
export const tournamentStatus: Record<string, string> = {
  registration: "참가 접수",
  running: "진행 중",
  finished: "종료",
};

/** Read snapshots are per account. Match mutations are never queued offline. */
export function useTournamentResource<T>(path: string) {
  const { user, online } = useApp();
  const [saved, setSaved] = useState<{ key: string; data: T } | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const key = `${user?.id}:${path}`;
  const generation = useRef(0);
  const flight = useRef(false);
  const refreshRef = useRef<() => Promise<void>>(async () => {});
  useFocusEffect(
    useCallback(() => {
      const ticket = ++generation.current;
      flight.current = false;
      setMessage("");
      if (!user) {
        setSaved(null);
        setBusy(false);
        return;
      }
      const owner = user.id;
      const cache = `tournament:${key}`;
      const refresh = async () => {
        if (flight.current || ticket !== generation.current) return;
        flight.current = true;
        setBusy(true);
        try {
          const data: T = await request(path, {}, true, false, owner);
          if (ticket !== generation.current) return;
          setSaved({ key, data });
          setMessage("");
          await setPreference(cache, data);
        } catch (err) {
          if (ticket === generation.current) setMessage(userMessage(err));
        } finally {
          if (ticket === generation.current) {
            flight.current = false;
            setBusy(false);
          }
        }
      };
      refreshRef.current = refresh;
      void (async () => {
        const data = await preference<T | null>(cache, null).catch(() => null);
        if (ticket !== generation.current) return;
        if (data) setSaved({ key, data });
        await refresh();
      })();
      const timer = setInterval(() => {
        if (online && AppState.currentState === "active") void refresh();
      }, 10000);
      const app = AppState.addEventListener("change", (phase) => {
        if (phase === "active") void refresh();
      });
      return () => {
        generation.current++;
        clearInterval(timer);
        app.remove();
      };
    }, [key, online]),
  );
  return {
    data: saved?.key === key ? saved.data : null,
    message,
    busy,
    refresh: () => refreshRef.current(),
  };
}
