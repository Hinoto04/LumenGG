import { userMessage } from "../src/errors";
import React, { useState, useEffect } from "react";
import { ScrollView, View, Text, Alert, Linking } from "react-native";
import { useApp } from "../src/provider";
import { logIn, request, clearTokens, absoluteUrl } from "../src/api";
import { documents, importGuest, preference, eraseScope } from "../src/storage";
import { trimImages } from "../src/catalog";
import { styles, Button, Input, Choices, Notice } from "../src/ui";
import type { Language } from "../src/types";
export default function Settings() {
  const app = useApp(),
    { user, language, t } = app;
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [email, setEmail] = useState(""),
    [signup, setSignup] = useState(false),
    [message, setMessage] = useState(""),
    [checked, setChecked] = useState(0),
    [updated, setUpdated] = useState(0),
    [guest, setGuest] = useState<{ card_id: number; amount: number }[]>([]),
    [selected, setSelected] = useState<number[]>([]),
    [showImport, setShowImport] = useState(false),
    [busy, setBusy] = useState(false);
  const format = (n: number) =>
    n ? new Date(n).toLocaleString(language) : "—";
  async function loadDates() {
    setChecked(await preference("catalog-checked", 0));
    setUpdated(await preference("catalog-updated", 0));
  }
  useEffect(() => {
    loadDates();
    documents<{ card_id: number; amount: number }>("guest", "collection").then(
      (items) => {
        setGuest(items);
        setSelected(items.map((i) => i.card_id));
      },
    );
  }, []);
  async function authenticate() {
    setBusy(true);
    try {
      const response = await logIn(username, password, signup, email);
      await app.setUser(response.user);
      setPassword("");
      setMessage(t("로그인"));
      await app.sync();
    } catch (error) {
      setMessage(userMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Text style={styles.title}>{t("언어")}</Text>
      <Choices
        value={language}
        onChange={(value) => app.setLanguage(value as Language)}
        values={[
          { key: "ko", label: "한국어" },
          { key: "en", label: "English" },
          { key: "ja", label: "日本語" },
        ]}
      />
      <View style={styles.panel}>
        <Text style={styles.title}>{t("계정")}</Text>
        {user ? (
          <>
            <Text style={styles.text}>{user.username}</Text>
            <Notice text={app.status} />
            <View style={styles.row}>
              <Button label="동기화" onPress={app.sync} />
              <Button label="로그아웃" onPress={app.signOut} />
              <Button
                label="로컬 데이터 가져오기"
                onPress={() => setShowImport(!showImport)}
              />
            </View>
            {showImport && (
              <View style={{ marginTop: 12 }}>
                <Notice text="로컬 수량으로 계정 수량을 교체합니다." />
                {guest.map((item) => {
                  const card = app.catalog?.collection.find(
                    (c) => c.id === item.card_id,
                  );
                  return (
                    <Button
                      key={item.card_id}
                      label={`${selected.includes(item.card_id) ? "✓ " : ""}${card?.name || item.card_id}: ${app.amounts[item.card_id] || 0} → ${item.amount}`}
                      onPress={() =>
                        setSelected((ids) =>
                          ids.includes(item.card_id)
                            ? ids.filter((id) => id !== item.card_id)
                            : [...ids, item.card_id],
                        )
                      }
                    />
                  );
                })}
                <Button
                  label="선택 항목 가져오기"
                  disabled={busy}
                  onPress={async () => {
                    setBusy(true);
                    try {
                      await importGuest(app.scope, selected);
                      await app.reload();
                      await app.sync();
                      setShowImport(false);
                      setMessage(t("가져오기 완료"));
                    } catch (err) {
                      setMessage(userMessage(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              </View>
            )}
            <Input
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder={t("비밀번호")}
            />
            <Button
              label="계정 삭제"
              danger
              disabled={busy || !password}
              onPress={() =>
                Alert.alert(
                  t("계정 삭제"),
                  t("계정과 저장된 데이터를 삭제합니다."),
                  [
                    { text: t("취소") },
                    {
                      text: t("계정 삭제"),
                      style: "destructive",
                      onPress: async () => {
                        try {
                          await request("/auth/account", {
                            method: "DELETE",
                            body: JSON.stringify({ password }),
                          });
                          await eraseScope(app.scope);
                          await clearTokens();
                          await app.setUser(null);
                          setPassword("");
                        } catch (err) {
                          setMessage(userMessage(err));
                        }
                      },
                    },
                  ],
                )
              }
            />
          </>
        ) : (
          <>
            <Input
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              placeholder={t("아이디")}
            />
            <Input
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder={t("비밀번호")}
            />
            {signup && (
              <Input
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                placeholder={t("이메일")}
              />
            )}
            <View style={styles.row}>
              <Button
                label={signup ? "가입" : "로그인"}
                disabled={busy}
                onPress={authenticate}
              />
              <Button
                label={signup ? "로그인" : "가입"}
                onPress={() => setSignup(!signup)}
              />
              <Button
                label="비밀번호 재설정"
                onPress={() => Linking.openURL(absoluteUrl("/password_reset/"))}
              />
            </View>
          </>
        )}
        <Notice text={message} />
      </View>
      <View style={styles.panel}>
        <Text style={styles.title}>{t("DB 버전")}</Text>
        <Text style={styles.text}>{app.catalog?.version || "—"}</Text>
        <Text style={styles.muted}>
          {t("마지막 확인")}: {format(checked)}
        </Text>
        <Text style={styles.muted}>
          {t("마지막 갱신")}: {format(updated)}
        </Text>
        <Notice text={app.error} />
        <View style={styles.row}>
          <Button
            label="DB 확인"
            disabled={busy}
            onPress={async () => {
              setBusy(true);
              try {
                await app.refresh();
                await loadDates();
              } finally {
                setBusy(false);
              }
            }}
          />
          <Button
            label="이미지 캐시 정리"
            onPress={() =>
              trimImages(true)
                .then(() => setMessage(t("저장 완료")))
                .catch((err) => setMessage(userMessage(err)))
            }
          />
        </View>
      </View>
      <Notice text={app.online ? "인터넷 연결됨" : "오프라인"} />
      <Text style={styles.muted}>LumenDB 1.0.5</Text>
    </ScrollView>
  );
}
