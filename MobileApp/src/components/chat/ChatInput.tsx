import React from "react";
import {
  View, Text, TextInput, TouchableOpacity, Image, StyleSheet,
} from "react-native";
import { colors, spacing, radius } from "../../theme/colors";
import {
  IconSend, IconStop, IconAttach, IconChevronDown, IconAgents, IconX,
} from "../Icons";
import { ProviderLogo } from "../ProviderIcon";
import type { Agent } from "../../lib/types";

const PROVIDERS = [
  { key: "claude", label: "Claude" },
  { key: "gemini", label: "Gemini" },
  { key: "openrouter", label: "OpenRouter" },
  { key: "ollama", label: "Local" },
];

interface ChatInputProps {
  input: string;
  onInputChange: (text: string) => void;
  onSend: () => void;
  onStop: () => void;
  streaming: boolean;
  pendingImage: { uri: string; base64: string; mime: string } | null;
  onAttach: () => void;
  onRemoveImage: () => void;
  activeAgent?: Agent;
  selectedAgent?: string;
  agents: Agent[];
  provider: string;
  bottomInset: number;
  isProviderDropdownOpen: boolean;
  isAgentDropdownOpen: boolean;
  onToggleProviderDropdown: () => void;
  onToggleAgentDropdown: () => void;
  inputFocused: boolean;
  onFocus: () => void;
  onBlur: () => void;
}

export default function ChatInput({
  input,
  onInputChange,
  onSend,
  onStop,
  streaming,
  pendingImage,
  onAttach,
  onRemoveImage,
  activeAgent,
  selectedAgent,
  agents,
  provider,
  bottomInset,
  isProviderDropdownOpen,
  isAgentDropdownOpen,
  onToggleProviderDropdown,
  onToggleAgentDropdown,
  inputFocused,
  onFocus,
  onBlur,
}: ChatInputProps) {
  return (
    <View style={[styles.inputBar, { paddingBottom: Math.max(bottomInset, 8) }]}>
      {/* Pending image preview */}
      {pendingImage && (
        <View style={styles.pendingImageRow}>
          <View style={styles.pendingImageWrap}>
            <Image source={{ uri: pendingImage.uri }} style={styles.pendingImageThumb} />
            <TouchableOpacity style={styles.pendingImageRemove} onPress={onRemoveImage} activeOpacity={0.7}>
              <IconX size={10} color="#fff" />
            </TouchableOpacity>
          </View>
        </View>
      )}
      {/* Main input container */}
      <View style={[styles.inputContainer, inputFocused && styles.inputContainerFocused]}>
        <TextInput
          style={styles.textInput}
          value={input}
          onChangeText={onInputChange}
          placeholder={activeAgent ? `Message @${activeAgent.name}...` : "Ask anything..."}
          placeholderTextColor={colors.labelTertiary}
          multiline
          maxLength={10000}
          editable={!streaming}
          onSubmitEditing={onSend}
          blurOnSubmit={false}
          onFocus={onFocus}
          onBlur={onBlur}
        />
        {/* Bottom toolbar row inside input container */}
        <View style={styles.inputToolbar}>
          {/* Left: attach + agent */}
          <View style={styles.inputToolbarLeft}>
            <TouchableOpacity style={styles.inputToolBtn} onPress={onAttach} disabled={streaming} activeOpacity={0.7}>
              <IconAttach size={18} color={pendingImage ? colors.accent : colors.labelTertiary} />
            </TouchableOpacity>
            {agents.length > 0 && (
              <TouchableOpacity
                style={[styles.inputToolBtn, selectedAgent ? { backgroundColor: colors.accentSubtle } : {}]}
                onPress={onToggleAgentDropdown}
                activeOpacity={0.7}>
                <IconAgents size={16} color={selectedAgent ? colors.accent : colors.labelTertiary} />
              </TouchableOpacity>
            )}
          </View>
          {/* Right: provider selector + send */}
          <View style={styles.inputToolbarRight}>
            <View style={{ position: "relative" }}>
              <TouchableOpacity
                style={styles.providerSelector}
                onPress={onToggleProviderDropdown}
                activeOpacity={0.7}>
                <ProviderLogo provider={provider} size={14} />
                <Text style={styles.providerSelectorText}>
                  {PROVIDERS.find(p => p.key === provider)?.label || provider}
                </Text>
                <IconChevronDown size={8} color={colors.labelTertiary} />
              </TouchableOpacity>
            </View>
            <TouchableOpacity
              style={[styles.sendBtn, streaming ? styles.stopBtn : (!input.trim() && !pendingImage ? styles.sendBtnDisabled : {})]}
              onPress={streaming ? onStop : onSend}
              disabled={!input.trim() && !pendingImage && !streaming}
              activeOpacity={0.7}>
              {streaming ? <IconStop size={16} color={colors.danger} /> : <IconSend size={16} color="#fff" />}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  inputBar: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.sm,
    zIndex: 5,
  },
  pendingImageRow: { flexDirection: "row", paddingBottom: spacing.sm },
  pendingImageWrap: { position: "relative" },
  pendingImageThumb: {
    width: 64, height: 64, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.separator,
  },
  pendingImageRemove: {
    position: "absolute", top: -6, right: -6,
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: colors.danger,
    alignItems: "center", justifyContent: "center",
  },
  inputContainer: {
    backgroundColor: colors.white05,
    borderRadius: 20,
    borderWidth: 1, borderColor: colors.separator,
    overflow: "hidden",
  },
  inputContainerFocused: { borderColor: "rgba(255,107,44,0.3)" },
  textInput: {
    paddingHorizontal: spacing.lg,
    paddingTop: 10, paddingBottom: 6,
    fontSize: 15, color: colors.label,
    maxHeight: 120, minHeight: 40,
  },
  inputToolbar: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 8, paddingBottom: 6, paddingTop: 0,
  },
  inputToolbarLeft: { flexDirection: "row", alignItems: "center", gap: 2 },
  inputToolbarRight: { flexDirection: "row", alignItems: "center", gap: 6 },
  inputToolBtn: {
    width: 32, height: 32, borderRadius: 8,
    alignItems: "center", justifyContent: "center",
  },
  providerSelector: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: 8, height: 30, borderRadius: 8,
  },
  providerSelectorText: { fontSize: 11, fontWeight: "600", color: colors.labelTertiary },
  sendBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: colors.accent,
    alignItems: "center", justifyContent: "center",
  },
  stopBtn: { backgroundColor: colors.dangerSubtle },
  sendBtnDisabled: { opacity: 0.3 },
});
