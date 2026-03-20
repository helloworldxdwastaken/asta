import React from "react";
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import { IconMenu, IconBrain, IconChevronDown } from "../Icons";

interface ChatHeaderProps {
  topInset: number;
  thinkingLevel: string;
  isThinkingDropdownOpen: boolean;
  onOpenDrawer?: () => void;
  onToggleThinkingDropdown: () => void;
}

export default function ChatHeader({
  topInset,
  thinkingLevel,
  isThinkingDropdownOpen,
  onOpenDrawer,
  onToggleThinkingDropdown,
}: ChatHeaderProps) {
  return (
    <View style={[styles.header, { paddingTop: topInset + 4 }]}>
      <TouchableOpacity style={styles.menuBtn} onPress={onOpenDrawer} activeOpacity={0.7}>
        <IconMenu size={18} color={colors.label} />
      </TouchableOpacity>

      {/* Centered thinking level selector */}
      <View style={{ flex: 1, alignItems: "center" }}>
        <TouchableOpacity
          style={[styles.thinkingSelector, isThinkingDropdownOpen && { borderColor: "rgba(139,92,246,0.3)" }]}
          onPress={onToggleThinkingDropdown}
          activeOpacity={0.7}
        >
          <IconBrain size={14} color={thinkingLevel !== "off" ? colors.violet : colors.labelTertiary} />
          <Text style={[styles.thinkingSelectorText, thinkingLevel !== "off" && { color: colors.violet }]}>
            {thinkingLevel === "off" ? "Thinking" : thinkingLevel === "xhigh" ? "Maximum" : thinkingLevel.charAt(0).toUpperCase() + thinkingLevel.slice(1)}
          </Text>
          <IconChevronDown size={10} color={thinkingLevel !== "off" ? colors.violet : colors.labelTertiary} />
        </TouchableOpacity>
      </View>

      {/* Spacer to balance menu button */}
      <View style={{ width: 36 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row", alignItems: "center",
    paddingBottom: 8, paddingHorizontal: spacing.md,
    zIndex: 5,
  },
  menuBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: colors.white05,
    borderWidth: 1, borderColor: colors.separator,
    alignItems: "center", justifyContent: "center",
  },
  thinkingSelector: {
    flexDirection: "row", alignItems: "center", gap: 5,
    backgroundColor: colors.white05,
    borderRadius: radius.full,
    paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: colors.separator,
  },
  thinkingSelectorText: { fontSize: 13, fontWeight: "600", color: colors.labelSecondary },
});
