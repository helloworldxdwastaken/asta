import React from "react";
import { View, Text, Image } from "react-native";
import { colors } from "../../theme/colors";
import { Label, CardRow, st, AboutTabProps } from "./shared";

export default function TabAbout({ serverOk, serverVersion, serverStatus, usage }: AboutTabProps) {
  return (
    <>
      <View style={{ alignItems: "center", marginBottom: 20 }}>
        <View style={st.aboutLogo}>
          <Image source={require("../../../assets/appicon.png")} style={{ width: 64, height: 64, borderRadius: 14 }} />
        </View>
        <Text style={{ fontSize: 24, fontWeight: "800", color: colors.label }}>Asta</Text>
        <Text style={{ fontSize: 13, color: colors.labelTertiary, marginTop: 2 }}>Mobile v1.0</Text>
      </View>
      <Label text="Server" />
      <View style={st.card}>
        <CardRow label="Status" value={serverOk ? "Online" : serverOk === false ? "Offline" : "..."} valueColor={serverOk ? colors.success : colors.danger} />
        {serverVersion ? <CardRow label="Version" value={serverVersion} /> : null}
        {serverStatus?.cpu_percent != null && <CardRow label="CPU" value={`${serverStatus.cpu_percent}%`} />}
        {serverStatus?.ram?.percent != null && <CardRow label="RAM" value={`${serverStatus.ram.percent}%`} />}
        {serverStatus?.uptime && <CardRow label="Uptime" value={serverStatus.uptime} />}
      </View>
      {usage && (
        <>
          <Label text="Usage (7 days)" />
          <View style={st.card}>
            {usage.total_messages != null && <CardRow label="Messages" value={usage.total_messages.toLocaleString()} />}
            {usage.total_tokens != null && <CardRow label="Tokens" value={
              usage.total_tokens >= 1_000_000 ? `${(usage.total_tokens / 1_000_000).toFixed(1)}M` : `${(usage.total_tokens / 1000).toFixed(0)}k`
            } />}
          </View>
        </>
      )}
    </>
  );
}
