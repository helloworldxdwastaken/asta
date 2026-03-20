import React, { useState, useEffect } from "react";
import { View, Text, TextInput, TouchableOpacity, Platform } from "react-native";
import { colors, radius } from "../../theme/colors";
import { getTelegramUsername, setTelegramUsername, getKeyStatus, setKeys, getPingram, setPingram, testPingramCall } from "../../lib/api";
import { st, TabProps } from "./shared";

const TG_COMMANDS = [
  { cmd: "/start", desc: "Start chatting with Asta" },
  { cmd: "/status", desc: "Show backend status" },
  { cmd: "/exec_mode", desc: "Toggle exec mode on/off" },
  { cmd: "/thinking", desc: "Set thinking level" },
  { cmd: "/reasoning", desc: "Set reasoning mode" },
];

export default function TabChannels(_props: TabProps) {
  const [tgUser, setTgUser] = useState("");
  const [tgToken, setTgToken] = useState("");
  const [tgTokenSet, setTgTokenSet] = useState(false);
  const [pgPhone, setPgPhone] = useState("");
  const [pgToken, setPgToken] = useState("");
  const [pgClientId, setPgClientId] = useState("");
  const [pgClientSecret, setPgClientSecret] = useState("");
  const [pgNotifId, setPgNotifId] = useState("");
  const [channelSaving, setChannelSaving] = useState<string | null>(null);
  const [testCallResult, setTestCallResult] = useState<"ok" | "fail" | null>(null);

  useEffect(() => {
    getTelegramUsername().then(r => setTgUser(r.username ?? "")).catch(() => {});
    getKeyStatus().then(r => setTgTokenSet(!!r.telegram_bot_token)).catch(() => {});
    getPingram().then(r => {
      setPgToken(r.api_key ?? "");
      setPgPhone(r.phone_number ?? "");
      setPgClientId(r.client_id ?? "");
      setPgClientSecret(r.client_secret ?? "");
      setPgNotifId(r.notification_id ?? "");
    }).catch(() => {});
  }, []);

  async function saveTgToken() {
    if (!tgToken.trim()) return;
    setChannelSaving("tg-token");
    try {
      await setKeys({ telegram_bot_token: tgToken.trim() });
      setTgTokenSet(true);
    } catch {}
    setChannelSaving(null);
  }

  async function saveTgUsername() {
    setChannelSaving("tg-user");
    try { await setTelegramUsername(tgUser); } catch {}
    setChannelSaving(null);
  }

  async function savePingram() {
    setChannelSaving("pg");
    try {
      await setPingram({ api_key: pgToken, phone_number: pgPhone, client_id: pgClientId, client_secret: pgClientSecret, notification_id: pgNotifId });
    } catch {}
    setChannelSaving(null);
  }

  async function doTestCall() {
    if (!pgPhone.trim()) { setTestCallResult("fail"); setTimeout(() => setTestCallResult(null), 3000); return; }
    try {
      const r: any = await testPingramCall(pgPhone.trim());
      setTestCallResult(r.ok ? "ok" : "fail");
    } catch { setTestCallResult("fail"); }
    setTimeout(() => setTestCallResult(null), 3000);
  }

  return (
    <>
      {/* Telegram section */}
      <Text style={st.sectionTitle}>Telegram</Text>
      <Text style={[st.desc, { marginBottom: 12 }]}>Connect a Telegram bot to chat with Asta.</Text>

      <Text style={st.fieldLabel}>Bot Token</Text>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 }}>
        {tgTokenSet && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.success }} />}
        {tgTokenSet && <Text style={{ fontSize: 11, color: colors.success }}>Set</Text>}
      </View>
      <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
        <TextInput style={[st.input, { flex: 1, marginBottom: 0 }]} value={tgToken}
          onChangeText={setTgToken} placeholder={tgTokenSet ? "Leave blank to keep existing" : "123456:ABC-DEF..."}
          placeholderTextColor={colors.labelTertiary} secureTextEntry />
        <TouchableOpacity style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16, paddingVertical: 11 }]}
          onPress={saveTgToken} disabled={channelSaving === "tg-token"} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{channelSaving === "tg-token" ? "..." : "Save"}</Text>
        </TouchableOpacity>
      </View>

      <Text style={st.fieldLabel}>Bot Username</Text>
      <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
        <TextInput style={[st.input, { flex: 1, marginBottom: 0 }]} value={tgUser}
          onChangeText={setTgUser} placeholder="@YourBotUsername"
          placeholderTextColor={colors.labelTertiary} autoCapitalize="none" />
        <TouchableOpacity style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16, paddingVertical: 11 }]}
          onPress={saveTgUsername} disabled={channelSaving === "tg-user"} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{channelSaving === "tg-user" ? "..." : "Save"}</Text>
        </TouchableOpacity>
      </View>

      {/* Commands reference */}
      <View style={{ backgroundColor: colors.white05, borderRadius: radius.md, padding: 12, marginBottom: 20 }}>
        <Text style={{ fontSize: 11, fontWeight: "700", color: colors.labelTertiary, marginBottom: 8 }}>AVAILABLE COMMANDS</Text>
        {TG_COMMANDS.map((c) => (
          <View key={c.cmd} style={{ flexDirection: "row", gap: 12, marginBottom: 4 }}>
            <Text style={{ fontSize: 12, color: colors.accent, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", width: 100 }}>{c.cmd}</Text>
            <Text style={{ fontSize: 12, color: colors.labelTertiary, flex: 1 }}>{c.desc}</Text>
          </View>
        ))}
      </View>

      {/* Pingram section */}
      <Text style={st.sectionTitle}>Pingram (Voice Calls)</Text>
      <Text style={[st.desc, { marginBottom: 12 }]}>Configure voice call integration.</Text>

      <Text style={st.fieldLabel}>Phone Number</Text>
      <TextInput style={st.input} value={pgPhone} onChangeText={setPgPhone}
        placeholder="+1234567890" placeholderTextColor={colors.labelTertiary} keyboardType="phone-pad" />

      <Text style={st.fieldLabel}>API Token</Text>
      <TextInput style={st.input} value={pgToken} onChangeText={setPgToken}
        placeholder="API token" placeholderTextColor={colors.labelTertiary} secureTextEntry />

      <Text style={st.fieldLabel}>Client ID</Text>
      <TextInput style={st.input} value={pgClientId} onChangeText={setPgClientId}
        placeholder="Client ID" placeholderTextColor={colors.labelTertiary} />

      <Text style={st.fieldLabel}>Client Secret</Text>
      <TextInput style={st.input} value={pgClientSecret} onChangeText={setPgClientSecret}
        placeholder="Client secret" placeholderTextColor={colors.labelTertiary} secureTextEntry />

      <Text style={st.fieldLabel}>Notification ID (optional)</Text>
      <TextInput style={st.input} value={pgNotifId} onChangeText={setPgNotifId}
        placeholder="Notification ID" placeholderTextColor={colors.labelTertiary} />

      <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
        <TouchableOpacity style={[st.accentBtn, { flex: 1, marginTop: 0 }]}
          onPress={savePingram} disabled={channelSaving === "pg"} activeOpacity={0.7}>
          <Text style={st.accentBtnText}>{channelSaving === "pg" ? "Saving..." : "Save"}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[st.accentBtn, { marginTop: 0, paddingHorizontal: 16,
            backgroundColor: testCallResult === "ok" ? colors.success : testCallResult === "fail" ? colors.danger : colors.white08 }]}
          onPress={doTestCall} activeOpacity={0.7}>
          <Text style={[st.accentBtnText, { color: testCallResult ? "#fff" : colors.label }]}>
            {testCallResult === "ok" ? "Sent!" : testCallResult === "fail" ? "Failed" : "Test Call"}
          </Text>
        </TouchableOpacity>
      </View>
    </>
  );
}
