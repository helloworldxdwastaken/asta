import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity } from "react-native";
import { colors } from "../../theme/colors";
import { getKeyStatus, setKeys } from "../../lib/api";
import { st, KEY_FIELDS, TabProps } from "./shared";

export default function TabKeys(_props: TabProps) {
  const [keyStatus, setKeyStatusState] = useState<Record<string, boolean>>({});
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [keyVis, setKeyVis] = useState<Record<string, boolean>>({});
  const [keySaving, setKeySaving] = useState(false);
  const [keySaved, setKeySaved] = useState(false);

  useEffect(() => {
    getKeyStatus().then(setKeyStatusState).catch(() => {});
  }, []);

  async function saveKeys() {
    setKeySaving(true);
    const toSave: Record<string, string> = {};
    for (const f of KEY_FIELDS) { if (keyInputs[f.key]) toSave[f.key] = keyInputs[f.key]; }
    await setKeys(toSave).catch(() => {});
    setKeySaving(false); setKeySaved(true);
    getKeyStatus().then(setKeyStatusState).catch(() => {});
    setTimeout(() => setKeySaved(false), 2000);
  }

  return (
    <>
      <Text style={st.desc}>Manage API keys for AI providers and services.</Text>
      {KEY_FIELDS.map((f) => {
        const isSet = keyStatus[f.key];
        return (
          <View key={f.key} style={st.keyBlock}>
            <View style={st.keyHead}>
              <Text style={st.keyName}>{f.label}</Text>
              <View style={[st.keyDot, { backgroundColor: isSet ? colors.success : "rgba(255,255,255,0.12)" }]} />
              <Text style={{ fontSize: 11, fontWeight: "600", color: isSet ? colors.success : colors.labelTertiary }}>
                {isSet ? "Active" : "Not set"}
              </Text>
            </View>
            <View style={st.keyRow}>
              <TextInput
                style={st.keyInput}
                value={keyInputs[f.key] || ""}
                onChangeText={(v) => setKeyInputs({ ...keyInputs, [f.key]: v })}
                placeholder={isSet ? "Leave blank to keep" : f.ph || "Enter key..."}
                placeholderTextColor={colors.labelTertiary}
                secureTextEntry={!keyVis[f.key]}
                autoCapitalize="none" autoCorrect={false}
              />
              <TouchableOpacity style={st.keyShowBtn}
                onPress={() => setKeyVis({ ...keyVis, [f.key]: !keyVis[f.key] })}>
                <Text style={st.keyShowText}>{keyVis[f.key] ? "Hide" : "Show"}</Text>
              </TouchableOpacity>
            </View>
          </View>
        );
      })}
      <TouchableOpacity style={st.accentBtn} onPress={saveKeys} disabled={keySaving} activeOpacity={0.7}>
        <Text style={st.accentBtnText}>{keySaved ? "Saved!" : keySaving ? "Saving..." : "Save Keys"}</Text>
      </TouchableOpacity>
    </>
  );
}
