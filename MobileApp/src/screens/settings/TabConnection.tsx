import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity } from "react-native";
import { colors, spacing } from "../../theme/colors";
import { getBackendUrl, setBackendUrl, checkHealth } from "../../lib/api";
import { IconWifi, IconWifiOff } from "../../components/Icons";
import { Label, st, ConnectionTabProps } from "./shared";

export default function TabConnection({ serverOk, serverVersion, setServerOk }: ConnectionTabProps) {
  const [backendUrl, setBackendUrlState] = useState("");
  const [connSaving, setConnSaving] = useState(false);

  useEffect(() => {
    getBackendUrl().then(setBackendUrlState);
  }, []);

  async function saveConnection() {
    setConnSaving(true);
    await setBackendUrl(backendUrl);
    checkHealth().then(() => setServerOk(true)).catch(() => setServerOk(false));
    setConnSaving(false);
  }

  return (
    <>
      <Text style={st.desc}>Configure backend server connection.</Text>
      <View style={st.card}>
        <View style={st.cardRow}>
          <Text style={st.cardLabel}>Status</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            {serverOk ? <IconWifi size={13} /> : <IconWifiOff size={13} />}
            <Text style={{ fontSize: 13, fontWeight: "600", color: serverOk ? colors.success : colors.danger }}>
              {serverOk === null ? "..." : serverOk ? "Connected" : "Unreachable"}
            </Text>
          </View>
        </View>
        {serverVersion ? (
          <View style={[st.cardRow, { borderTopWidth: 1, borderTopColor: colors.separator }]}>
            <Text style={st.cardLabel}>Version</Text>
            <Text style={st.cardVal}>{serverVersion}</Text>
          </View>
        ) : null}
      </View>
      <Label text="Backend URL" />
      <TextInput style={st.keyInput} value={backendUrl} onChangeText={setBackendUrlState}
        placeholder="https://asta.example.com" placeholderTextColor={colors.labelTertiary}
        autoCapitalize="none" autoCorrect={false} />
      <TouchableOpacity style={[st.accentBtn, { marginTop: 12 }]} onPress={saveConnection} disabled={connSaving} activeOpacity={0.7}>
        <Text style={st.accentBtnText}>{connSaving ? "Connecting..." : "Save & Test"}</Text>
      </TouchableOpacity>
    </>
  );
}
