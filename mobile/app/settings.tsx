import { userMessage } from "../src/errors";
import Constants from "expo-constants";
import React, { useState, useEffect } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useApp } from "../src/provider";
import { logIn, request, clearTokens, absoluteUrl } from "../src/api";
import { documents, importGuest, preference, eraseScope } from "../src/storage";
import { trimImages } from "../src/catalog";
import {
  Button,
  Icon,
  Input,
  ListRow,
  ListSection,
  Notice,
  Segmented,
  colors,
  space,
  styles,
} from "../src/ui";
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
  async function checkCatalog() {
    setBusy(true);
    try {
      await app.refresh();
      await loadDates();
    } finally {
      setBusy(false);
    }
  }
  async function importSelected() {
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
  }
  function confirmDelete() {
    Alert.alert(t("계정 삭제"), t("계정과 저장된 데이터를 삭제합니다."), [
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
    ]);
  }
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 48 }}
    >
      <Text style={settingStyles.heading}>{t("언어")}</Text>
      <Segmented
        value={language}
        onChange={(value) => app.setLanguage(value as Language)}
        values={[
          { key: "ko", label: "한국어" },
          { key: "en", label: "English" },
          { key: "ja", label: "日本語" },
        ]}
      />

      {user ? (
        <>
          <ListSection title="계정" footer={app.status || undefined}>
            <ListRow
              icon="person-circle-outline"
              title={user.username}
              subtitle={app.online ? "인터넷 연결됨" : "오프라인"}
            />
            <ListRow icon="sync-outline" title="동기화" onPress={app.sync} />
            {guest.length > 0 && (
              <ListRow
                icon="download-outline"
                title="로컬 데이터 가져오기"
                value={String(guest.length)}
                chevron={false}
                right={
                  <Icon
                    name={showImport ? "chevron-up" : "chevron-down"}
                    size={18}
                    color={colors.subtle}
                  />
                }
                onPress={() => setShowImport(!showImport)}
              />
            )}
            <ListRow
              icon="log-out-outline"
              title="로그아웃"
              chevron={false}
              onPress={app.signOut}
            />
          </ListSection>
          {showImport && (
            <ListSection
              title="로컬 데이터 가져오기"
              footer="로컬 수량으로 계정 수량을 교체합니다."
            >
              {guest.map((item) => {
                const card = app.catalog?.collection.find(
                  (c) => c.id === item.card_id,
                );
                const on = selected.includes(item.card_id);
                return (
                  <ListRow
                    key={item.card_id}
                    title={card?.name || String(item.card_id)}
                    subtitle={
                      (app.amounts[item.card_id] || 0) + " → " + item.amount
                    }
                    chevron={false}
                    right={
                      <Icon
                        name={on ? "checkbox" : "square-outline"}
                        size={22}
                        color={on ? colors.accent : colors.subtle}
                      />
                    }
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
              <View style={{ padding: space.md }}>
                <Button
                  label="선택 항목 가져오기"
                  variant="primary"
                  block
                  loading={busy}
                  disabled={!selected.length}
                  onPress={importSelected}
                />
              </View>
            </ListSection>
          )}
        </>
      ) : (
        <>
          <Text style={settingStyles.heading}>
            {t(signup ? "가입" : "로그인")}
          </Text>
          <View style={styles.panel}>
            <Input
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoComplete="username"
              placeholder={t("아이디")}
            />
            <Input
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete={signup ? "new-password" : "current-password"}
              placeholder={t("비밀번호")}
            />
            {signup && (
              <Input
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                autoComplete="email"
                keyboardType="email-address"
                placeholder={t("이메일")}
              />
            )}
            <Button
              label={signup ? "가입" : "로그인"}
              icon={signup ? "person-add-outline" : "log-in-outline"}
              variant="primary"
              block
              loading={busy}
              onPress={authenticate}
            />
            <View style={settingStyles.authLinks}>
              <Button
                label={signup ? "로그인" : "가입"}
                variant="ghost"
                size="sm"
                onPress={() => setSignup(!signup)}
              />
              <Button
                label="비밀번호 재설정"
                variant="ghost"
                size="sm"
                onPress={() => Linking.openURL(absoluteUrl("/password_reset/"))}
              />
            </View>
          </View>
        </>
      )}
      <Notice text={message} />

      <ListSection title="DB 버전" footer={app.error || undefined}>
        <ListRow
          icon="server-outline"
          title={app.catalog?.version || "—"}
          subtitle={
            t("마지막 확인") +
            ": " +
            format(checked) +
            "\n" +
            t("마지막 갱신") +
            ": " +
            format(updated)
          }
        />
        <ListRow
          icon="refresh"
          title="DB 확인"
          chevron={false}
          onPress={busy ? undefined : checkCatalog}
          right={busy ? <ActivityIndicator color={colors.accent} /> : undefined}
        />
        <ListRow
          icon="trash-outline"
          title="이미지 캐시 정리"
          chevron={false}
          onPress={() =>
            trimImages(true)
              .then(() => setMessage(t("저장 완료")))
              .catch((err) => setMessage(userMessage(err)))
          }
        />
      </ListSection>

      {user && (
        <>
          <Text style={[settingStyles.heading, { color: colors.danger }]}>
            {t("계정 삭제")}
          </Text>
          <View style={[styles.panel, settingStyles.danger]}>
            <Text style={[styles.muted, { marginBottom: space.sm }]}>
              {t("계정과 저장된 데이터를 삭제합니다.")}
            </Text>
            <Input
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="current-password"
              placeholder={t("비밀번호")}
            />
            <Button
              label="계정 삭제"
              icon="warning-outline"
              danger
              block
              disabled={busy || !password}
              onPress={confirmDelete}
            />
          </View>
        </>
      )}

      <Text style={settingStyles.footer}>
        {"LumenDB " + (Constants.expoConfig?.version ?? "")}
        {user ? "" : "  ·  " + t(app.online ? "인터넷 연결됨" : "오프라인")}
      </Text>
    </ScrollView>
  );
}

const settingStyles = StyleSheet.create({
  heading: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: space.sm,
    marginLeft: space.xs,
  },
  authLinks: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: space.sm,
  },
  danger: { borderColor: colors.dangerSoft },
  footer: {
    color: colors.subtle,
    fontSize: 12,
    textAlign: "center",
    marginTop: space.md,
  },
});
