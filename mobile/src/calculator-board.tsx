import React, { useState } from "react";
import {
  Alert,
  Keyboard,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { router } from "expo-router";
import type { Action, CalcState, Player } from "./types";
import { useApp } from "./provider";
import { localized } from "./core";
import { PassivePanel } from "./passive-panel";
import { Button, CachedImage, Input, Notice, colors, styles } from "./ui";

export function CalculatorBoard({
  state,
  mode,
  disabled,
  connected,
  now,
  error,
  ready,
  setupOpen,
  onSetup,
  onCloseSetup,
  onShare,
  setup,
  onAction,
}: {
  state: CalcState | null;
  mode: string;
  disabled: boolean;
  connected: boolean;
  now: number;
  error: string;
  ready: boolean;
  setupOpen: boolean;
  onSetup: () => void;
  onCloseSetup: () => void;
  onShare: () => void;
  setup: React.ReactNode;
  onAction: (action: Action) => Promise<void>;
}) {
  const { catalog, language, t } = useApp();
  const { width, height } = useWindowDimensions();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [damageTarget, setDamageTarget] = useState<"p1" | "p2" | null>(null);
  const [damage, setDamage] = useState("100");
  const compact = height < 390;
  const centerWidth = width < 730 ? 120 : 144;
  function confirmReset(sudden: boolean) {
    if (!state) return;
    Alert.alert(
      t(sudden ? "서든 데스" : "전체 초기화"),
      t(
        sudden
          ? "HP·FP·패시브를 초기화합니다."
          : "HP·FP·패시브·기록을 초기화합니다.",
      ),
      [
        { text: t("취소"), style: "cancel" },
        {
          text: t("확인"),
          onPress: () =>
            onAction(
              sudden
                ? { action: "sudden_death", enabled: !state.sudden_death }
                : { action: "reset_session" },
            ),
        },
      ],
    );
  }
  function playerPanel(target: "p1" | "p2") {
    if (!state) return null;
    const stored = state.players[target];
    const character =
      mode === "local"
        ? catalog?.characters.find((c) => c.id === stored.character?.id)
        : undefined;
    const player: Player = character
      ? {
          ...stored,
          name: localized(character, language),
          character: {
            ...stored.character,
            passive: localized(character, language, "passive"),
            hand_table: character.hand_table,
          },
        }
      : stored;
    const table = player.character?.hand_table || {};
    const thresholds = Object.keys(table)
      .map(Number)
      .sort((a, b) => a - b);
    const threshold =
      thresholds.find((n) => player.hp <= n) ?? thresholds.at(-1);
    const hand = threshold === undefined ? "—" : table[threshold];
    const label = t(target === "p1" ? "플레이어1" : "플레이어2");
    const hpColor =
      player.hp <= 0
        ? colors.danger
        : player.hp <= 1000
          ? colors.accent
          : "#72cbbf";
    return (
      <View style={[board.player, { borderColor: hpColor + "80" }]}>
        {!!player.character?.img && (
          <View
            pointerEvents="none"
            style={[
              board.portrait,
              target === "p2" && { left: -6, right: undefined },
            ]}
          >
            <CachedImage
              url={player.character.img}
              fill
              height={Math.max(180, height - 70)}
            />
          </View>
        )}
        <View
          style={[
            board.playerHead,
            target === "p2" && { flexDirection: "row-reverse" },
          ]}
        >
          <View style={{ flex: 1 }}>
            <Text
              style={[
                board.playerLabel,
                target === "p2" && { textAlign: "right" },
              ]}
            >
              {label}
            </Text>
            <Text
              numberOfLines={1}
              style={[
                board.playerName,
                target === "p2" && { textAlign: "right" },
              ]}
            >
              {player.name}
            </Text>
          </View>
          <Text style={board.hand}>
            {t("손패")} {hand}
          </Text>
        </View>
        <View
          style={[
            board.hpAndFp,
            target === "p2" && { flexDirection: "row-reverse" },
          ]}
        >
          <View style={{ flex: 1, gap: 5 }}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${label} HP ${player.hp}, ${t("대미지 적용")}`}
              disabled={disabled}
              onPress={() => setDamageTarget(target)}
              style={[board.hp, compact && { minHeight: 64 }]}
            >
              <Text style={board.hpLabel}>HP</Text>
              <Text
                adjustsFontSizeToFit
                numberOfLines={1}
                style={[
                  board.hpValue,
                  { color: hpColor },
                  compact && { fontSize: 42 },
                ]}
              >
                {player.hp}
              </Text>
            </Pressable>
            <View style={board.hpButtons}>
              {[-500, -100, 100, 500].map((amount) => (
                <Pressable
                  key={amount}
                  accessibilityRole="button"
                  accessibilityLabel={`${label} HP ${amount > 0 ? "+" : ""}${amount}`}
                  accessibilityState={{ disabled }}
                  disabled={disabled}
                  onPress={() => onAction({ action: "hp", target, amount })}
                  style={[
                    board.hpButton,
                    {
                      backgroundColor: amount < 0 ? "#3c2028dd" : "#193b35dd",
                      opacity: disabled ? 0.4 : 1,
                    },
                  ]}
                >
                  <Text
                    adjustsFontSizeToFit
                    numberOfLines={1}
                    style={[
                      board.hpButtonText,
                      { color: amount < 0 ? colors.danger : "#72cbbf" },
                    ]}
                  >
                    {amount > 0 ? "+" : "−"}
                    {Math.abs(amount)}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
          <View style={board.fp}>
            <SmallButton
              label={`${label} FP -1`}
              icon="−"
              disabled={disabled}
              onPress={() => onAction({ action: "fp", target, amount: -1 })}
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${label} FP ${player.fp}, ${t("초기화")}`}
              disabled={disabled}
              onPress={() => onAction({ action: "fp_reset", target })}
              style={board.fpValue}
            >
              <Text style={board.hpLabel}>FP</Text>
              <Text style={board.fpNumber}>{player.fp}</Text>
            </Pressable>
            <SmallButton
              label={`${label} FP +1`}
              icon="+"
              disabled={disabled}
              onPress={() => onAction({ action: "fp", target, amount: 1 })}
            />
          </View>
        </View>
        <ScrollView
          style={board.passives}
          contentContainerStyle={{ paddingTop: 9, paddingBottom: 8 }}
          keyboardShouldPersistTaps="handled"
        >
          <PassivePanel
            player={player}
            target={target}
            definition={player.character?.passive || {}}
            disabled={disabled}
            onAction={onAction}
          />
        </ScrollView>
      </View>
    );
  }
  const seconds = state?.timer.ends_at
    ? Math.max(0, Math.ceil((Date.parse(state.timer.ends_at) - now) / 1000))
    : state?.timer.duration_seconds || 10;
  return (
    <SafeAreaView style={board.screen}>
      <StatusBar hidden />
      {!!error && !setupOpen && <Notice text={error} />}
      <View style={board.layout}>
        {state ? (
          playerPanel("p1")
        ) : (
          <View style={board.placeholder}>
            <Text style={styles.text}>{t("플레이어1")}</Text>
          </View>
        )}
        <View style={[board.center, { width: centerWidth }]}>
          <View style={board.centerTop}>
            <SmallButton
              label={t("메뉴")}
              icon="‹"
              onPress={() => router.dismissTo("/")}
            />
            <Text
              numberOfLines={1}
              style={[
                board.mode,
                mode === "shared" && {
                  color: connected ? "#72cbbf" : colors.danger,
                },
              ]}
            >
              {t(mode === "shared" ? "공유" : "로컬")}
            </Text>
            <SmallButton label={t("계산기 설정")} icon="⚙" onPress={onSetup} />
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("타이머")}
            accessibilityState={{ disabled }}
            disabled={disabled}
            onPress={() => onAction({ action: "timer" })}
            style={[
              board.timer,
              state?.timer.is_running && { borderColor: colors.accent },
              compact && { minHeight: 94 },
            ]}
          >
            <Text style={board.timerLabel}>{t("10초 타이머")}</Text>
            <Text style={[board.timerValue, compact && { fontSize: 52 }]}>
              {seconds}
            </Text>
          </Pressable>
          <View style={board.centerActions}>
            <SmallButton
              label={t("되돌리기")}
              icon="↶"
              disabled={disabled}
              onPress={() => onAction({ action: "undo" })}
            />
            <SmallButton
              label={t("기록")}
              icon="≡"
              onPress={() => setHistoryOpen(true)}
            />
            <SmallButton label={t("공유")} icon="↗" onPress={onShare} />
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("서든 데스")}
            disabled={disabled}
            onPress={() => confirmReset(true)}
            style={[
              board.sudden,
              state?.sudden_death && { backgroundColor: "#592631" },
              disabled && { opacity: 0.4 },
            ]}
          >
            <Text style={board.suddenText}>{t("서든 데스")}</Text>
          </Pressable>
          {!!state?.sudden_death && (
            <Button
              label={`${t("남은 턴")} ${state.sudden_death_turns_remaining}`}
              disabled={disabled || !state.sudden_death_turns_remaining}
              onPress={() => onAction({ action: "sudden_turn" })}
            />
          )}
          {!ready && <Notice text="DB를 불러오는 중입니다." />}
        </View>
        {state ? (
          playerPanel("p2")
        ) : (
          <View style={board.placeholder}>
            <Text style={styles.text}>{t("플레이어2")}</Text>
          </View>
        )}
      </View>
      <LandscapeModal
        visible={setupOpen}
        title={t("계산기 설정")}
        onClose={onCloseSetup}
      >
        <Notice text={error} />
        {setup}
        {!!state && (
          <View style={{ marginTop: 14 }}>
            <Button
              label="전체 초기화"
              disabled={disabled}
              danger
              onPress={() => confirmReset(false)}
            />
          </View>
        )}
      </LandscapeModal>
      <LandscapeModal
        visible={historyOpen}
        title={t("기록")}
        onClose={() => setHistoryOpen(false)}
      >
        {!state?.events.length && <Notice text="기록이 없습니다." />}
        {(state?.events || [])
          .slice(-100)
          .reverse()
          .map((event, i) => (
            <Text
              key={event.id || i}
              style={[
                styles.text,
                {
                  paddingVertical: 9,
                  borderBottomWidth: 1,
                  borderColor: colors.line,
                },
              ]}
            >
              {event.target} · {event.type} · {event.amount ?? ""}{" "}
              {event.undone ? "↩" : ""}
            </Text>
          ))}
      </LandscapeModal>
      <LandscapeModal
        visible={!!damageTarget}
        title={t("대미지 적용")}
        onClose={() => setDamageTarget(null)}
      >
        <Text style={[styles.text, { marginBottom: 12 }]}>
          {damageTarget && state?.players[damageTarget].name}
        </Text>
        <Input
          accessibilityLabel={t("대미지")}
          value={damage}
          onChangeText={setDamage}
          keyboardType="numeric"
          placeholder={t("대미지")}
        />
        <Button
          label="대미지 적용"
          disabled={
            disabled ||
            !Number.isInteger(Number(damage)) ||
            !Number(damage) ||
            Math.abs(Number(damage)) > 50000
          }
          onPress={async () => {
            if (!damageTarget) return;
            Keyboard.dismiss();
            await onAction({
              action: "hp",
              target: damageTarget,
              amount: -Math.abs(Number(damage)),
            });
            setDamageTarget(null);
          }}
        />
      </LandscapeModal>
    </SafeAreaView>
  );
}

function SmallButton({
  label,
  icon,
  onPress,
  disabled = false,
}: {
  label: string;
  icon: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={4}
      style={[board.smallButton, disabled && { opacity: 0.4 }]}
    >
      <Text style={board.smallIcon}>{icon}</Text>
    </Pressable>
  );
}
function LandscapeModal({
  visible,
  title,
  onClose,
  children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <Modal
      visible={visible}
      onRequestClose={onClose}
      presentationStyle="fullScreen"
      animationType="fade"
      supportedOrientations={["landscape", "landscape-left", "landscape-right"]}
    >
      <SafeAreaView style={board.modal}>
        <View style={board.modalHead}>
          <Text style={board.modalTitle}>{title}</Text>
          <SmallButton label={t("닫기")} icon="×" onPress={onClose} />
        </View>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        >
          {children}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const board = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 8 },
  layout: { flex: 1, flexDirection: "row", gap: 8 },
  player: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderRadius: 12,
    backgroundColor: colors.panel,
    padding: 8,
    overflow: "hidden",
  },
  portrait: {
    position: "absolute",
    right: -6,
    top: 30,
    width: "85%",
    opacity: 0.16,
  },
  playerHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 8,
  },
  playerLabel: { color: colors.muted, fontSize: 10 },
  playerName: { color: colors.text, fontSize: 19, fontWeight: "800" },
  hand: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "700",
    borderWidth: 1,
    borderColor: colors.line,
    padding: 5,
    borderRadius: 6,
  },
  hpAndFp: { flexDirection: "row", gap: 6 },
  hp: {
    minHeight: 84,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111111bb",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
  },
  hpLabel: { color: colors.muted, fontSize: 10, fontWeight: "700" },
  hpValue: {
    fontSize: 54,
    lineHeight: 60,
    fontWeight: "900",
    fontVariant: ["tabular-nums"],
  },
  hpButtons: { flexDirection: "row", gap: 4 },
  hpButton: {
    flex: 1,
    minWidth: 0,
    minHeight: 42,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 7,
    paddingHorizontal: 2,
    borderWidth: 1,
    borderColor: colors.line,
  },
  hpButtonText: { fontWeight: "800", fontSize: 16 },
  fp: {
    width: 44,
    alignItems: "center",
    justifyContent: "space-between",
    gap: 4,
  },
  fpValue: {
    flex: 1,
    alignSelf: "stretch",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#111111bb",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 7,
  },
  fpNumber: { color: colors.accent, fontSize: 23, fontWeight: "800" },
  passives: { flex: 1, marginTop: 4 },
  center: { gap: 8 },
  centerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 2,
  },
  mode: { flex: 1, color: colors.muted, fontSize: 10, textAlign: "center" },
  smallButton: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 7,
    backgroundColor: colors.panel,
  },
  smallIcon: { color: colors.accent, fontSize: 24, fontWeight: "600" },
  timer: {
    minHeight: 118,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 10,
    backgroundColor: colors.panel,
  },
  timerLabel: { fontSize: 12, color: colors.muted },
  timerValue: {
    fontSize: 64,
    fontWeight: "900",
    color: colors.accent,
    fontVariant: ["tabular-nums"],
  },
  centerActions: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 4,
  },
  sudden: {
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#64333c",
    borderRadius: 8,
    backgroundColor: "#2b1b20",
  },
  suddenText: { color: colors.danger, fontSize: 13, fontWeight: "700" },
  placeholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 12,
  },
  modal: { flex: 1, backgroundColor: colors.bg },
  modalHead: {
    minHeight: 52,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderColor: colors.line,
  },
  modalTitle: { color: colors.text, fontSize: 21, fontWeight: "700" },
});
