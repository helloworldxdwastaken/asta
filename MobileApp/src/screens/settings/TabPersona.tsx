import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity } from "react-native";
import { colors } from "../../theme/colors";
import { getPersona, setPersona } from "../../lib/api";
import { Chip, st, TabProps } from "./shared";

export default function TabPersona({ admin }: TabProps) {
  const [persona, setPersonaState] = useState({ soul: "", user_soul: "", user: "" });
  const [personaTab, setPersonaTab] = useState<"soul" | "user_soul" | "user">("user");
  const [personaSaving, setPersonaSaving] = useState(false);

  useEffect(() => {
    getPersona().then((r) => setPersonaState({ soul: r.soul || "", user_soul: r.user_soul || "", user: r.user || "" })).catch(() => {});
  }, []);

  async function savePersona() {
    setPersonaSaving(true);
    await setPersona(persona).catch(() => {});
    setPersonaSaving(false);
  }

  const tabs = admin
    ? [{ id: "soul" as const, l: "Soul" }, { id: "user_soul" as const, l: "User Soul" }, { id: "user" as const, l: "Memories" }]
    : [{ id: "user" as const, l: "Memories" }];

  return (
    <>
      <Text style={st.desc}>
        {personaTab === "soul" ? "Asta's personality, voice, and character."
          : personaTab === "user_soul" ? "Personality shown to regular users."
          : "Info about you — Asta uses this to personalize."}
      </Text>
      {tabs.length > 1 && (
        <View style={st.chipRow}>
          {tabs.map((t) => (
            <Chip key={t.id} label={t.l} active={personaTab === t.id} color={colors.accent}
              onPress={() => setPersonaTab(t.id)} />
          ))}
        </View>
      )}
      <TextInput
        style={st.textArea}
        value={persona[personaTab]}
        onChangeText={(v) => setPersonaState({ ...persona, [personaTab]: v })}
        placeholder="Enter content..."
        placeholderTextColor={colors.labelTertiary}
        multiline textAlignVertical="top"
      />
      <TouchableOpacity style={st.accentBtn} onPress={savePersona} disabled={personaSaving} activeOpacity={0.7}>
        <Text style={st.accentBtnText}>{personaSaving ? "Saving..." : "Save"}</Text>
      </TouchableOpacity>
    </>
  );
}
