import { userMessage } from "../src/errors";
import React, { useEffect, useRef, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  Pressable,
  Share,
  AppState,
} from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import type { Action, CalcState } from "../src/types";
import { localized, newCalculator, reduceCalculator } from "../src/core";
import { preference, saveCalculator } from "../src/storage";
import { request, absoluteUrl } from "../src/api";
import {
  SharedCalculator,
  SharedSession,
  saveShared,
  storedShared,
  parseShareLink,
} from "../src/shared";
import { CalculatorBoard } from "../src/calculator-board";
import { HpQueue, type PendingHp } from "../src/hp-queue";
import { styles, Button, Input, Choices, Notice, colors } from "../src/ui";

export default function Calculator() {
  const { catalog, language, t, online } = useApp();
  const [local, setLocal] = useState<CalcState | null>(null),
    [shared, setShared] = useState<CalcState | null>(null),
    [session, setSession] = useState<SharedSession | null>(null),
    [mode, setMode] = useState("local");
  const [connected, setConnected] = useState(false),
    [busy, setBusy] = useState(false),
    [link, setLink] = useState(""),
    [error, setError] = useState(""),
    [p1, setP1] = useState(""),
    [p2, setP2] = useState(""),
    [now, setNow] = useState(Date.now()),
    [settings, setSettings] = useState(false),
    [ready, setReady] = useState(false);
  const [pendingHp, setPendingHp] = useState<PendingHp>({ p1: 0, p2: 0 });
  const [pendingFp, setPendingFp] = useState<PendingHp>({ p1: 0, p2: 0 });
  const hpQueue = useRef<HpQueue | null>(null);
  const sharedBusy = useRef(false);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const client = useRef<SharedCalculator | null>(null),
    localRef = useRef(local);
  localRef.current = local;
  useEffect(() => {
    let live = true;
    Promise.all([
      preference<CalcState | null>("local-calculator", null),
      storedShared(),
    ])
      .then(([saved, sharedSession]) => {
        if (!live) return;
        localRef.current = saved;
        setLocal(saved);
        setSession(sharedSession);
        setReady(true);
      })
      .catch((err) => {
        if (live) {
          setError(userMessage(err));
          setReady(true);
        }
      });
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (session) {
      client.current = new SharedCalculator(
        session,
        language,
        setShared,
        setConnected,
      );
    }
    return () => {
      client.current?.dispose();
      client.current = null;
      setConnected(false);
    };
  }, [session, language]);
  const state = mode === "shared" ? shared : local;
  async function action(value: Action) {
    if (mode === "shared" && sharedBusy.current) return;
    const sharedAction = mode === "shared";
    try {
      setError("");
      if (value.action === "undo") {
        const pending = hpQueue.current?.hasPendingHp;
        hpQueue.current?.clear("hp");
        if (pending) return;
      }
      if (["reset_session", "sudden_death"].includes(value.action))
        hpQueue.current?.clear();
      if (value.action === "fp_reset")
        hpQueue.current?.clear("fp", value.target);
      if (mode === "shared") {
        sharedBusy.current = true;
        hpQueue.current?.setBusy(true);
        setBusy(true);
        await client.current?.send(value);
      } else if (localRef.current) {
        const next = reduceCalculator(localRef.current, value);
        localRef.current = next;
        setLocal(next);
        await saveCalculator(next);
      }
    } catch (err) {
      setError(userMessage(err));
    } finally {
      if (sharedAction) {
        sharedBusy.current = false;
        setBusy(false);
        hpQueue.current?.setBusy(false);
      }
    }
  }
  const actionRef = useRef(action);
  actionRef.current = action;
  useEffect(() => {
    const queue = new HpQueue(
      (value) => actionRef.current(value),
      (hp, fp) => {
        setPendingHp(hp);
        setPendingFp(fp);
      },
      undefined,
      (err) => setError(userMessage(err)),
    );
    hpQueue.current = queue;
    const subscription = AppState.addEventListener("change", (phase) => {
      if (phase !== "active") {
        if (modeRef.current === "local") void queue.flush();
        else queue.clear();
      }
    });
    return () => {
      subscription.remove();
      if (modeRef.current === "local")
        void queue.flush().finally(() => queue.dispose());
      else queue.dispose();
    };
  }, []);
  const available =
    !!state?.can_control &&
    !state.is_expired &&
    (mode !== "shared" || (connected && online));
  const availableRef = useRef(available);
  availableRef.current = available;
  useEffect(() => {
    hpQueue.current?.setAvailable(available);
  }, [available]);
  const hpScope = `${mode}:${session?.view_token || ""}:${state?.players.p1.character?.id || ""}:${state?.players.p2.character?.id || ""}`;
  useEffect(() => {
    hpQueue.current?.clear();
  }, [hpScope]);
  async function changeMode(next: string) {
    if (modeRef.current === "local") await hpQueue.current?.flush();
    else hpQueue.current?.clear();
    setMode(next);
  }
  function selected() {
    const a = catalog?.characters.find(
        (c) => String(c.id) === (p1 || String(catalog.characters[0]?.id)),
      ),
      b = catalog?.characters.find(
        (c) => String(c.id) === (p2 || String(catalog.characters[0]?.id)),
      );
    if (!a || !b) throw new Error("캐릭터를 선택해주세요.");
    return [a, b] as const;
  }
  async function create(sharedMode: boolean) {
    try {
      hpQueue.current?.clear();
      const [a, b] = selected();
      if (sharedMode) {
        const result = await request(
          "/calculators/",
          {
            method: "POST",
            body: JSON.stringify({
              player1_character: a.id,
              player2_character: b.id,
            }),
          },
          false,
        );
        const next = {
          view_token: result.view_token,
          control_token: result.control_token,
        };
        await saveShared(next);
        setSession(next);
        setShared(result.state);
        setMode("shared");
      } else {
        const next = newCalculator(a, b, language);
        localRef.current = next;
        setLocal(next);
        await saveCalculator(next);
        setMode("local");
      }
      setError("");
      return true;
    } catch (err) {
      setError(userMessage(err));
      return false;
    }
  }
  const disabled =
    busy ||
    !state?.can_control ||
    (mode === "shared" && (!connected || !online)) ||
    !!state?.is_expired;
  function openSettings() {
    setP1(
      String(
        state?.players.p1.character?.id || catalog?.characters[0]?.id || "",
      ),
    );
    setP2(
      String(
        state?.players.p2.character?.id || catalog?.characters[0]?.id || "",
      ),
    );
    setSettings(true);
  }
  const choices = (catalog?.characters || []).map((c) => ({
    key: String(c.id),
    label: localized(c, language),
  }));
  return (
    <CalculatorBoard
      state={state}
      mode={mode}
      disabled={disabled}
      connected={connected && online}
      now={now}
      error={error}
      ready={ready}
      setupOpen={ready && (settings || !state)}
      onSetup={openSettings}
      onCloseSetup={() => {
        if (!state && local) {
          setMode("local");
          setSettings(false);
        } else if (!state) router.dismissTo("/");
        else setSettings(false);
      }}
      onShare={() => {
        openSettings();
        void changeMode("shared");
      }}
      onAction={action}
      pendingHp={pendingHp}
      pendingFp={pendingFp}
      onFp={(target, amount) => {
        if (availableRef.current) {
          hpQueue.current?.setAvailable(true);
          hpQueue.current?.add(target, amount, "fp");
        }
      }}
      onHp={(target, amount) => {
        if (availableRef.current) {
          hpQueue.current?.setAvailable(true);
          hpQueue.current?.add(target, amount);
        }
      }}
      setup={
        <>
          <Choices
            value={mode}
            onChange={changeMode}
            values={[
              { key: "local", label: t("로컬") },
              { key: "shared", label: t("공유") },
            ]}
          />
          <View style={{ flexDirection: "row", gap: 16 }}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{t("플레이어1")}</Text>
              <CharacterStrip
                value={p1 || String(catalog?.characters[0]?.id || "")}
                onChange={setP1}
                values={choices}
                label={t("플레이어1")}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{t("플레이어2")}</Text>
              <CharacterStrip
                value={p2 || String(catalog?.characters[0]?.id || "")}
                onChange={setP2}
                values={choices}
                label={t("플레이어2")}
              />
            </View>
          </View>
          <Button
            label={state ? "새 계산기 시작" : "시작"}
            disabled={
              !ready ||
              !catalog?.characters.length ||
              (mode === "shared" && !online)
            }
            onPress={async () => {
              if (await create(mode === "shared")) setSettings(false);
            }}
          />
          {mode === "shared" && (
            <View style={[styles.panel, { marginTop: 16 }]}>
              {!!session && (
                <Notice
                  text={
                    connected && online ? "연결됨" : "재연결 중 · 제어 잠금"
                  }
                />
              )}
              <Input
                accessibilityLabel={t("공유 링크")}
                value={link}
                onChangeText={setLink}
                placeholder={t("공유 링크")}
              />
              <View style={styles.row}>
                <Button
                  label="참여"
                  disabled={!online}
                  onPress={async () => {
                    try {
                      const next = parseShareLink(link);
                      await saveShared(next);
                      setSession(next);
                      setShared(null);
                      setError("");
                    } catch (err) {
                      setError(userMessage(err));
                    }
                  }}
                />
                {session && (
                  <>
                    <Button
                      label="조회 링크"
                      onPress={() =>
                        Share.share({
                          message: absoluteUrl(
                            "/battlelog/session/" + session.view_token + "/",
                          ),
                        })
                      }
                    />
                    {!!session.control_token && (
                      <Button
                        label="제어 링크"
                        onPress={() =>
                          Share.share({
                            message: absoluteUrl(
                              "/battlelog/session/" +
                                session.view_token +
                                "/control/" +
                                session.control_token +
                                "/",
                            ),
                          })
                        }
                      />
                    )}
                    <Button
                      label="나가기"
                      onPress={async () => {
                        await saveShared(null);
                        setSession(null);
                        setShared(null);
                      }}
                    />
                  </>
                )}
              </View>
            </View>
          )}
        </>
      }
    />
  );
}

function CharacterStrip({
  value,
  values,
  onChange,
  label,
}: {
  value: string;
  values: { key: string; label: string }[];
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <ScrollView
      horizontal
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ gap: 8, paddingBottom: 14 }}
    >
      {values.map((item) => (
        <Pressable
          key={item.key}
          accessibilityRole="radio"
          accessibilityState={{ checked: value === item.key }}
          accessibilityLabel={`${label}: ${item.label}`}
          onPress={() => onChange(item.key)}
          style={[
            styles.button,
            {
              minHeight: 44,
              justifyContent: "center",
              backgroundColor: value === item.key ? "#4b3d24" : colors.panel,
            },
          ]}
        >
          <Text style={styles.buttonText}>{item.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
