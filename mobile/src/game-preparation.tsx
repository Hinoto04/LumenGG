import React, { useEffect, useState, useRef } from "react";
import { View, Text } from "react-native";
import * as Crypto from "expo-crypto";
import type { Action, CalcState } from "./types";
import { Button, Choices, Input, Notice, styles } from "./ui";

export function GamePreparation({
  state,
  onAction,
  disabled,
}: {
  state: CalcState;
  onAction: (a: Action) => Promise<void>;
  disabled: boolean;
}) {
  const prep = state.preparation;
  const dirty = useRef(new Set<string>()),
    game = useRef(prep?.game_number);
  const [active, setActive] = useState<Record<string, any>>({}),
    [error, setError] = useState("");
  useEffect(() => {
    if (!prep) return;
    if (game.current !== prep.game_number || prep.status === "playing")
      dirty.current.clear();
    game.current = prep.game_number;
    setActive((previous) =>
      Object.fromEntries(
        Object.entries(prep.players)
          .filter(([, p]: any) => p.active)
          .map(([side, p]: any) => [
            side,
            dirty.current.has(side) ? previous[side] || p.active : p.active,
          ]),
      ),
    );
  }, [prep?.version]);
  const edit = (side: string, value: any) => {
    dirty.current.add(side);
    setActive((previous) => ({ ...previous, [side]: value }));
  };
  if (!prep) return null;
  const send = async (side: string, action: string, submission_id?: number) => {
    try {
      setError("");
      if (action === "select_deck") dirty.current.delete(side);
      await onAction({
        action: "preparation",
        target: side as "p1" | "p2",
        preparation_action: action,
        request_id: Crypto.randomUUID(),
        preparation_version: prep.version,
        active: active[side],
        submission_id,
      });
      dirty.current.delete(side);
    } catch (e) {
      setError(String(e));
    }
  };
  return (
    <View style={styles.panel}>
      <Text style={styles.title}>게임 {prep.game_number} 준비</Text>
      <Notice text={error} />
      <Text style={styles.text}>
        P1 {prep.players.p1.ready ? "준비 완료" : "편집 중"} · P2{" "}
        {prep.players.p2.ready ? "준비 완료" : "편집 중"}
      </Text>
      {Object.entries(prep.players).map(([side, row]: [string, any]) => {
        if (!row.registered && !row.submissions) return null;
        if (prep.status === "playing")
          return (
            <Notice
              key={side}
              text={`${side.toUpperCase()} · 이번 게임 구성 확정`}
            />
          );
        const snapshot = row.registered,
          current = active[side];
        const pool = new Map<number, number>();
        if (snapshot)
          [
            ...snapshot.cards,
            ...snapshot.reserve_cards,
            { card_id: snapshot.trait_card_id, count: 1 },
          ].forEach((e: any) => {
            if (e.card_id)
              pool.set(e.card_id, (pool.get(e.card_id) || 0) + e.count);
          });
        const trait = (c: any) =>
          c.type === "특성" || /(?:^|-)PS(?:-|$)/i.test(c.code || "");
        return (
          <View key={side}>
            <Text style={styles.title}>
              {side.toUpperCase()} · {snapshot?.name || "제출 덱 선택"}
            </Text>
            {!!row.submissions?.length && (
              <View style={styles.row}>
                {row.submissions.map((s: any) => (
                  <Button
                    key={s.id}
                    label={`${s.name} · ${s.trait_name || "특성 미지정"}`}
                    disabled={disabled || row.ready}
                    onPress={() => void send(side, "select_deck", s.id)}
                  />
                ))}
              </View>
            )}
            {!!snapshot && !!current && (
              <>
                <Text style={styles.text}>특성</Text>
                <Choices
                  value={String(current.trait_card_id)}
                  onChange={(id) =>
                    !row.ready &&
                    edit(side, { ...current, trait_card_id: Number(id) })
                  }
                  values={[...pool.keys()]
                    .filter((id) => trait(snapshot.catalog[id]))
                    .map((id) => ({
                      key: String(id),
                      label: snapshot.catalog[id].name,
                    }))}
                />
                {[...pool]
                  .filter(([id]) => !trait(snapshot.catalog[id]))
                  .map(([id, n]) => {
                    const card = snapshot.catalog[id],
                      e = current.cards.find((c: any) => c.card_id === id) || {
                        card_id: id,
                        count: 0,
                        hand: 0,
                        side: 0,
                      };
                    return (
                      <View key={id} style={styles.panel}>
                        <Text style={styles.text}>
                          {card.name} · 등록 {n}장
                        </Text>
                        <View style={styles.row}>
                          {(["count", "hand", "side"] as const).map((field) => (
                            <View key={field}>
                              <Text style={styles.muted}>
                                {field === "count"
                                  ? "사용"
                                  : field === "hand"
                                    ? "시작 패"
                                    : "사이드"}
                              </Text>
                              <Input
                                accessibilityLabel={`${card.name} ${field}`}
                                editable={!row.ready && !disabled}
                                keyboardType="number-pad"
                                style={{ width: 70 }}
                                value={String(e[field])}
                                onChangeText={(text) => {
                                  dirty.current.add(side);
                                  const rows = current.cards.filter(
                                    (r: any) => r.card_id !== id,
                                  );
                                  const next = { ...e, [field]: Number(text) };
                                  if (next.count > 0) rows.push(next);
                                  edit(side, { ...current, cards: rows });
                                }}
                              />
                            </View>
                          ))}
                        </View>
                      </View>
                    );
                  })}
                {row.ready ? (
                  <Button
                    label="준비 완료 철회"
                    disabled={disabled}
                    onPress={() => void send(side, "cancel")}
                  />
                ) : (
                  <View style={styles.row}>
                    <Button
                      label="배치 저장"
                      disabled={disabled}
                      onPress={() => void send(side, "save")}
                    />
                    <Button
                      label="준비 완료"
                      disabled={disabled}
                      onPress={() => void send(side, "ready")}
                    />
                  </View>
                )}
              </>
            )}
          </View>
        );
      })}
    </View>
  );
}
