import React, { useState, useEffect } from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { colors } from "../../theme/colors";
import { setDefaultAI, setThinking, setMoodSetting, getReasoning, setReasoning as setReasoningApi, getFinalMode, setFinalMode as setFinalModeApi, getVision, setVision as setVisionApi } from "../../lib/api";
import { ProviderLogo } from "../../components/ProviderIcon";
import Toggle from "../../components/Toggle";
import { Label, Chip, st, PROVIDERS, THINKING_LEVELS, MOODS, GeneralTabProps } from "./shared";

export default function TabGeneral({ provider, thinkingLevel, mood, onProviderChange, onThinkingChange, onMoodChange, admin }: GeneralTabProps) {
  const [reasoningMode, setReasoningMode] = useState("off");
  const [finalMode, setFinalMode] = useState("off");
  const [visionEnabled, setVisionEnabled] = useState(true);

  useEffect(() => {
    getReasoning().then((r) => setReasoningMode(r.reasoning_mode || "off")).catch(() => {});
    getFinalMode().then((r) => setFinalMode(r.final_mode || "off")).catch(() => {});
    getVision().then((r) => setVisionEnabled(r.preprocess !== false)).catch(() => {});
  }, []);

  return (
    <>
      <Label text="AI Provider" />
      {PROVIDERS.map((p) => (
        <TouchableOpacity
          key={p.key}
          style={[st.radioRow, provider === p.key && st.radioRowActive]}
          onPress={() => { onProviderChange(p.key); setDefaultAI(p.key).catch(() => {}); }}
          activeOpacity={0.7}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <ProviderLogo provider={p.key} size={20} />
            <Text style={[st.radioText, provider === p.key && st.radioTextActive]}>{p.label}</Text>
          </View>
          <View style={[st.radio, provider === p.key && st.radioActive]}>
            {provider === p.key && <View style={st.radioFill} />}
          </View>
        </TouchableOpacity>
      ))}

      <Label text="Thinking Level" />
      <View style={st.chipRow}>
        {THINKING_LEVELS.map((t) => (
          <Chip key={t} label={t === "xhigh" ? "max" : t}
            active={thinkingLevel === t} color={colors.violet}
            onPress={() => { onThinkingChange(t); setThinking(t).catch(() => {}); }}
          />
        ))}
      </View>

      <Label text="Mood" />
      <View style={st.chipRow}>
        {MOODS.map((m) => (
          <Chip key={m} label={m} active={mood === m} color={colors.accent}
            onPress={() => { onMoodChange(m); setMoodSetting(m).catch(() => {}); }}
          />
        ))}
      </View>

      {admin && (
        <>
          <Label text="Reasoning Mode" />
          <View style={st.chipRow}>
            {["off", "on"].map((v) => (
              <Chip key={v} label={v} active={reasoningMode === v} color={colors.accent}
                onPress={() => { setReasoningMode(v); setReasoningApi(v).catch(() => {}); }}
              />
            ))}
          </View>

          <Label text="Final Mode" />
          <View style={st.chipRow}>
            {["off", "strict"].map((v) => (
              <Chip key={v} label={v} active={finalMode === v} color={colors.accent}
                onPress={() => { setFinalMode(v); setFinalModeApi(v).catch(() => {}); }}
              />
            ))}
          </View>

          <Label text="Vision / Image Understanding" />
          <View style={st.switchRow}>
            <Text style={st.switchLabel}>{visionEnabled ? "Enabled" : "Disabled"}</Text>
            <Toggle
              value={visionEnabled}
              onValueChange={(v) => { setVisionEnabled(v); setVisionApi({ preprocess: v }).catch(() => {}); }}
            />
          </View>
        </>
      )}
    </>
  );
}
