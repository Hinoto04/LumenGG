import React, { useRef } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "./provider";
import { Icon, colors, radius } from "./ui";
import {
  CARD_SORT_OPTIONS,
  type CardDisplay,
  type CardSort,
} from "./card-search";

export function CardSearchToolbar({
  display,
  onToggle,
  onSort,
  expanded,
}: {
  display: CardDisplay;
  onToggle: () => void;
  onSort: (bottom: number) => void;
  expanded: boolean;
}) {
  const { t } = useApp();
  const toolbar = useRef<View>(null);
  return (
    <View ref={toolbar} collapsable={false} style={controlStyles.toolbar}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("정렬")}
        accessibilityState={{ expanded }}
        onPress={() =>
          toolbar.current?.measureInWindow((_x, y, _width, height) =>
            onSort(y + height + 8),
          )
        }
        style={({ pressed }) => [
          controlStyles.button,
          (pressed || expanded) && controlStyles.buttonActive,
        ]}
      >
        <Icon name="swap-vertical" size={20} color={colors.text} />
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("표시 방식")}
        accessibilityHint={t(
          display === "grid" ? "자세히로 전환" : "바둑판으로 전환",
        )}
        onPress={onToggle}
        style={controlStyles.button}
      >
        <Icon
          name={display === "grid" ? "list-outline" : "grid-outline"}
          size={20}
          color={colors.text}
        />
      </Pressable>
    </View>
  );
}

export function CardSortMenu({
  visible,
  value,
  onSelect,
  onClose,
  anchorY,
}: {
  visible: boolean;
  value: CardSort;
  onSelect: (value: CardSort) => void;
  onClose: () => void;
  anchorY?: number;
}) {
  const { t } = useApp();
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  return (
    <Modal
      visible={visible}
      transparent
      statusBarTranslucent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View
        style={[
          controlStyles.overlay,
          {
            paddingTop: Math.min(
              anchorY ?? insets.top + 160,
              height - insets.bottom - 180,
            ),
          },
        ]}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("닫기")}
          onPress={onClose}
          style={StyleSheet.absoluteFill}
        />
        <View
          accessibilityViewIsModal
          style={[
            controlStyles.menu,
            {
              width: Math.min(340, width - 32),
              maxHeight: Math.min(
                650,
                height -
                  Math.min(
                    anchorY ?? insets.top + 160,
                    height - insets.bottom - 180,
                  ) -
                  insets.bottom -
                  16,
              ),
            },
          ]}
        >
          <View style={controlStyles.menuHeader}>
            <Text style={controlStyles.menuTitle}>{t("정렬")}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("닫기")}
              hitSlop={8}
              onPress={onClose}
            >
              <Icon name="close" size={20} color={colors.muted} />
            </Pressable>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled">
            {CARD_SORT_OPTIONS.map((option) => (
              <Pressable
                key={option.key}
                accessibilityRole="radio"
                accessibilityState={{ checked: option.key === value }}
                accessibilityLabel={t(option.label)}
                onPress={() => onSelect(option.key)}
                style={[
                  controlStyles.option,
                  option.key === value && controlStyles.selected,
                ]}
              >
                <Text style={controlStyles.optionText}>{t(option.label)}</Text>
                {option.key === value && (
                  <Icon name="checkmark" size={20} color={colors.accent} />
                )}
              </Pressable>
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
const controlStyles = StyleSheet.create({
  toolbar: { flexDirection: "row", gap: 8, alignItems: "center" },
  button: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  buttonActive: { borderColor: colors.accent },
  label: { color: colors.accent, fontWeight: "600", fontSize: 14 },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,.45)",
    alignItems: "flex-end",
    paddingHorizontal: 16,
  },
  menu: {
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.lg,
    padding: 8,
  },
  menuHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 8,
    marginBottom: 6,
  },
  menuTitle: { color: colors.text, fontSize: 18, fontWeight: "700" },
  option: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    minHeight: 48,
    paddingHorizontal: 14,
    borderRadius: radius.sm,
  },
  optionText: { color: colors.text, fontSize: 15 },
  selected: { backgroundColor: colors.accentSoft },
});
