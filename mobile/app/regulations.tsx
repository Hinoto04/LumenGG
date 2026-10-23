import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { useApp } from "../src/provider";
import { request } from "../src/api";
import { setPreference } from "../src/storage";
import { defaultPolicy } from "../src/deck-rules";
import { localized } from "../src/core";
import { userMessage } from "../src/errors";
import type { RegulationVersion } from "../src/types";
import { Button, Choices, Input, Notice, styles } from "../src/ui";

export default function Regulations() {
  const { catalog, user, scope, language, online } = useApp();
  const [versions, setVersions] = useState<RegulationVersion[]>([]),
    [source, setSource] = useState<RegulationVersion | null>(null),
    [name, setName] = useState(""),
    [version, setVersion] = useState(""),
    [sourceUrl, setSourceUrl] = useState(""),
    [date, setDate] = useState("");
  const [rules, setRules] = useState<RegulationVersion["rules"]>({
      ...defaultPolicy,
    }),
    [query, setQuery] = useState(""),
    [mode, setMode] = useState("bans"),
    [combo, setCombo] = useState<number[]>([]),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    request("/regulations", {}, !!user)
      .then((r) => {
        if (live) setVersions(r.versions);
      })
      .catch((e) => live && setMessage(userMessage(e)));
    return () => {
      live = false;
    };
  }, [scope]);
  const cardName = (id: number) => {
    const card = catalog?.cards.find((c) => c.id === id);
    return card ? localized(card, language) : String(id);
  };
  const edit = (
    group: "bans" | "combinations",
    index: number,
    scope: "registered" | "active",
  ) =>
    setRules({
      ...rules,
      [group]: rules[group].map((r, n) => (n === index ? { ...r, scope } : r)),
    });
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 50 }}
    >
      <Text style={styles.title}>대회 규정</Text>
      <Notice text={message} />
      <Text style={styles.muted}>
        게시한 규정은 새 버전으로 변경합니다. 시작한 대회에는 기존 버전이
        유지됩니다.
      </Text>
      <View style={styles.row}>
        {versions.map((v) => (
          <Button
            key={v.id}
            label={`${v.name} / ${v.version} 복사`}
            onPress={() => {
              setSource(v);
              setName(v.name);
              setVersion("");
              setRules(JSON.parse(JSON.stringify(v.rules)));
              setCombo([]);
            }}
          />
        ))}
      </View>
      <Button
        label="새 규정 작성"
        onPress={() => {
          setSource(null);
          setName("");
          setVersion("");
          setRules(JSON.parse(JSON.stringify(defaultPolicy)));
        }}
      />
      <Input
        accessibilityLabel="규정 이름"
        placeholder="규정 이름"
        value={name}
        onChangeText={setName}
      />
      <Input
        accessibilityLabel="새 버전 이름"
        placeholder="새 버전 이름"
        value={version}
        onChangeText={setVersion}
      />
      <Input
        accessibilityLabel="시행일"
        placeholder="시행일 (YYYY-MM-DD, 선택)"
        value={date}
        onChangeText={setDate}
      />
      <Input
        accessibilityLabel="규정 출처"
        placeholder="규정 출처 URL (선택)"
        value={sourceUrl}
        onChangeText={setSourceUrl}
      />
      {(
        [
          "reserve_limit",
          "technique_swap_limit",
          "trait_swap_limit",
          "ultimate_swap_limit",
        ] as const
      ).map((key, index) => (
        <View key={key}>
          <Text style={styles.text}>
            {
              [
                "교체 덱 등록 한도",
                "기술 교체 한도",
                "특성 교체 횟수",
                "얼티밋 교체 횟수",
              ][index]
            }
          </Text>
          <Input
            accessibilityLabel={key}
            keyboardType="number-pad"
            value={String(rules[key])}
            onChangeText={(v) => setRules({ ...rules, [key]: Number(v) })}
          />
        </View>
      ))}
      {(["reserve_public", "swaps_public"] as const).map((key) => (
        <View key={key}>
          <Text style={styles.text}>
            {key === "reserve_public"
              ? "확정 후 교체 덱 공개"
              : "확정 후 교체 내역 공개"}
          </Text>
          <Choices
            value={String(rules[key])}
            onChange={(v) => setRules({ ...rules, [key]: v === "true" })}
            values={[
              { key: "false", label: "비공개" },
              { key: "true", label: "공개" },
            ]}
          />
        </View>
      ))}
      {(["bans", "combinations"] as const).map((group) => (
        <View key={group}>
          <Text style={styles.title}>
            {group === "bans" ? "금지 카드" : "제한 조합"}
          </Text>
          {rules[group].map((rule, index) => (
            <View key={index} style={styles.panel}>
              <Text style={styles.text}>
                {rule.card_ids.map(cardName).join(" + ")}
              </Text>
              <Choices
                value={rule.scope}
                onChange={(v) =>
                  edit(group, index, v as "registered" | "active")
                }
                values={[
                  { key: "registered", label: "전체 등록 구성" },
                  { key: "active", label: "게임 사용 구성" },
                ]}
              />
              <Button
                label="삭제"
                onPress={() =>
                  setRules({
                    ...rules,
                    [group]: rules[group].filter((_, n) => n !== index),
                  })
                }
              />
            </View>
          ))}
        </View>
      ))}
      <Choices
        value={mode}
        onChange={setMode}
        values={[
          { key: "bans", label: "금지 카드 추가" },
          { key: "combinations", label: "제한 조합 만들기" },
        ]}
      />
      {!!combo.length && (
        <>
          <Text style={styles.text}>{combo.map(cardName).join(" + ")}</Text>
          <Button
            label="이 조합을 제한"
            disabled={combo.length < 2}
            onPress={() => {
              setRules({
                ...rules,
                combinations: [
                  ...rules.combinations,
                  { card_ids: combo, scope: "registered" },
                ],
              });
              setCombo([]);
            }}
          />
        </>
      )}
      <Input
        accessibilityLabel="규정 카드 검색"
        placeholder="카드명·번호 검색"
        value={query}
        onChangeText={setQuery}
      />
      {(catalog?.cards || [])
        .filter((c) =>
          `${localized(c, language)} ${c.code}`
            .toLowerCase()
            .includes(query.toLowerCase()),
        )
        .slice(0, 20)
        .map((c) => (
          <View key={c.id} style={styles.row}>
            <Text style={[styles.text, { flex: 1 }]}>
              {localized(c, language)} · {c.code}
            </Text>
            <Button
              label={combo.includes(c.id) ? "선택 취소" : "추가"}
              onPress={() =>
                mode === "bans"
                  ? setRules({
                      ...rules,
                      bans: [
                        ...rules.bans,
                        { card_ids: [c.id], scope: "registered" },
                      ],
                    })
                  : setCombo(
                      combo.includes(c.id)
                        ? combo.filter((id) => id !== c.id)
                        : [...combo, c.id],
                    )
              }
            />
          </View>
        ))}
      <Button
        label="규정 게시"
        disabled={busy || !user || !online || !name.trim() || !version.trim()}
        onPress={async () => {
          setBusy(true);
          try {
            await request("/regulations", {
              method: "POST",
              body: JSON.stringify({
                name,
                version,
                rules,
                regulation_id:
                  source?.owner_id === user?.id
                    ? (source as any).regulation_id
                    : undefined,
                source: sourceUrl,
                effective_date: date || null,
              }),
            });
            const result = await request("/regulations");
            setVersions(result.versions);
            await setPreference(`regulations:${scope}`, result.versions);
            setMessage(
              "규정을 게시했습니다. 덱 작성 또는 대회 설정에서 선택해주세요.",
            );
            setVersion("");
          } catch (e) {
            setMessage(userMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      />
    </ScrollView>
  );
}
