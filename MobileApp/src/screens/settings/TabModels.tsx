import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView } from "react-native";
import { colors } from "../../theme/colors";
import { getModels, getAvailableModels, setModel } from "../../lib/api";
import { ProviderLogo } from "../../components/ProviderIcon";
import { st, PROVIDERS, TabProps } from "./shared";

const MODEL_PROVIDERS = ["claude", "gemini", "openrouter", "ollama"];

export default function TabModels(_props: TabProps) {
  const [models, setModels] = useState<Record<string, string>>({});
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({});
  const [modelSaving, setModelSaving] = useState<string | null>(null);

  useEffect(() => {
    getModels().then((r) => setModels(r.models || r || {})).catch(() => {});
    getAvailableModels().then((r) => setAvailableModels(r.models || r || {})).catch(() => {});
  }, []);

  async function handleSetModel(prov: string, model: string) {
    setModelSaving(prov);
    setModels((prev) => ({ ...prev, [prov]: model }));
    await setModel(prov, model).catch(() => {});
    setModelSaving(null);
  }

  return (
    <>
      <Text style={st.desc}>Select which model each provider uses.</Text>
      {MODEL_PROVIDERS.map((prov) => {
        const current = models[prov] || "";
        const available = availableModels[prov] || [];
        const provLabel = prov === "claude" ? "Claude" : prov === "gemini" ? "Gemini" : prov === "openrouter" ? "OpenRouter" : "Ollama";
        const provColor = PROVIDERS.find((p) => p.key === prov)?.color || colors.labelSecondary;

        return (
          <View key={prov} style={{ marginBottom: 16 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <ProviderLogo provider={prov} size={20} />
              <Text style={{ fontSize: 14, fontWeight: "600", color: colors.label }}>{provLabel}</Text>
              {modelSaving === prov && <Text style={{ fontSize: 11, color: colors.accent }}>Saving...</Text>}
            </View>
            {available.length > 0 ? (
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={{ flexDirection: "row", gap: 4 }}>
                  {available.map((m) => (
                    <TouchableOpacity
                      key={m}
                      style={[st.chip, current === m && { backgroundColor: provColor + "18", borderColor: provColor + "60" }]}
                      onPress={() => handleSetModel(prov, m)}
                      activeOpacity={0.7}
                    >
                      <Text style={[st.chipText, current === m && { color: provColor, fontWeight: "700" }]} numberOfLines={1}>
                        {m.replace(/^(claude-|gemini-|models\/)/, "")}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            ) : (
              <TextInput
                style={st.keyInput}
                value={current}
                onChangeText={(v) => setModels((prev) => ({ ...prev, [prov]: v }))}
                onBlur={() => { if (current) handleSetModel(prov, current); }}
                placeholder="Model name..."
                placeholderTextColor={colors.labelTertiary}
                autoCapitalize="none"
                autoCorrect={false}
              />
            )}
            {current ? (
              <Text style={{ fontSize: 11, color: colors.labelTertiary, marginTop: 4 }}>
                Current: {current}
              </Text>
            ) : null}
          </View>
        );
      })}
    </>
  );
}
