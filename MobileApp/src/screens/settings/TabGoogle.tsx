import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity } from "react-native";
import { colors } from "../../theme/colors";
import { getKeyStatus, setKeys } from "../../lib/api";
import { st, GoogleTabProps } from "./shared";

export default function TabGoogle({ keyStatus, setKeyStatus }: GoogleTabProps) {
  const [saJson, setSaJson] = useState("");
  const [savingSa, setSavingSa] = useState(false);
  const [savedSa, setSavedSa] = useState(false);
  const [saError, setSaError] = useState("");
  const hasSa = !!keyStatus.google_service_account;
  const hasGemini = !!keyStatus.gemini_api_key;

  async function saveSa() {
    const raw = saJson.trim();
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (!parsed.client_email || !parsed.private_key) {
        setSaError("JSON must contain client_email and private_key."); return;
      }
    } catch {
      setSaError("Invalid JSON."); return;
    }
    setSaError("");
    setSavingSa(true);
    await setKeys({ google_service_account: raw } as any).catch(() => {});
    setSavingSa(false); setSavedSa(true);
    getKeyStatus().then(setKeyStatus).catch(() => {});
    setTimeout(() => setSavedSa(false), 2000);
  }

  return (
    <>
      <Text style={st.desc}>Connect Google services — Gemini AI, Search Console, Calendar, and more.</Text>

      {/* Gemini key status */}
      <View style={st.keyBlock}>
        <View style={st.keyHead}>
          <Text style={st.keyName}>Gemini API Key</Text>
          <View style={[st.keyDot, { backgroundColor: hasGemini ? colors.success : "rgba(255,255,255,0.12)" }]} />
          <Text style={{ fontSize: 11, fontWeight: "600", color: hasGemini ? colors.success : colors.labelTertiary }}>
            {hasGemini ? "Active" : "Set in API Keys tab"}
          </Text>
        </View>
      </View>

      {/* Service Account JSON */}
      <View style={st.keyBlock}>
        <View style={st.keyHead}>
          <Text style={st.keyName}>Service Account JSON</Text>
          <View style={[st.keyDot, { backgroundColor: hasSa ? colors.success : "rgba(255,255,255,0.12)" }]} />
          <Text style={{ fontSize: 11, fontWeight: "600", color: hasSa ? colors.success : colors.labelTertiary }}>
            {hasSa ? "Active" : "Not set"}
          </Text>
        </View>
        <Text style={[st.desc, { marginBottom: 8 }]}>
          Enables Indexing API, Calendar, Search Console, and Drive access.
        </Text>
        <TextInput
          style={[st.keyInput, { height: 120, textAlignVertical: "top", paddingTop: 10 }]}
          value={saJson}
          onChangeText={(v) => { setSaJson(v); setSaError(""); }}
          placeholder='Paste service account JSON...'
          placeholderTextColor={colors.labelTertiary}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
        />
        {saError ? <Text style={{ color: "#ef4444", fontSize: 12, marginTop: 4 }}>{saError}</Text> : null}
        <TouchableOpacity style={[st.accentBtn, { marginTop: 8 }]} onPress={saveSa} disabled={savingSa || !saJson.trim()} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{savedSa ? "Saved!" : savingSa ? "Saving..." : "Save"}</Text>
        </TouchableOpacity>
      </View>

      {/* Setup instructions */}
      <View style={{ marginTop: 12 }}>
        <Text style={[st.keyName, { marginBottom: 8 }]}>Setup Guide</Text>
        <Text style={[st.desc, { lineHeight: 20 }]}>
          1. Go to console.cloud.google.com and create a project{"\n\n"}
          2. Enable the APIs you need (Indexing API, Calendar API, Drive API, Search Console API){"\n\n"}
          3. Go to IAM & Admin {">"} Service Accounts, create one, then Keys {">"} Add Key {">"} JSON — a .json file downloads{"\n\n"}
          4. Paste the JSON contents above{"\n\n"}
          5. For Search Console: add the service account email as Owner in search.google.com/search-console{"\n\n"}
          6. For Calendar: share your calendar with the service account email{"\n\n"}
          The service account email looks like: name@project.iam.gserviceaccount.com
        </Text>
      </View>
    </>
  );
}
