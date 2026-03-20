import React, { useState, useEffect } from "react";
import { View, Text } from "react-native";
import { colors, radius } from "../../theme/colors";
import { getSecurityAudit } from "../../lib/api";
import { IconCheck, IconWarning } from "../../components/Icons";
import { st, TabProps } from "./shared";

export default function TabPermissions(_props: TabProps) {
  const [auditFindings, setAuditFindings] = useState<any[] | null>(null);

  useEffect(() => {
    getSecurityAudit().then(r => setAuditFindings(r.findings ?? [])).catch(() => setAuditFindings([]));
  }, []);

  return (
    <>
      <Text style={st.desc}>Security audit of your Asta configuration.</Text>
      {auditFindings === null && <Text style={st.emptyText}>Loading...</Text>}
      {auditFindings && auditFindings.length === 0 && (
        <View style={{ backgroundColor: "rgba(52,199,89,0.1)", borderWidth: 1, borderColor: "rgba(52,199,89,0.2)", borderRadius: radius.md, padding: 14, flexDirection: "row", alignItems: "center", gap: 8 }}>
          <IconCheck size={14} color={colors.success} />
          <Text style={{ fontSize: 13, color: colors.success, fontWeight: "600" }}>All checks passed — no warnings</Text>
        </View>
      )}
      {auditFindings && auditFindings.length > 0 && auditFindings.map((w: any, i: number) => (
        <View key={i} style={{ backgroundColor: "rgba(255,159,10,0.1)", borderWidth: 1, borderColor: "rgba(255,159,10,0.2)", borderRadius: radius.md, padding: 14, flexDirection: "row", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
          <IconWarning size={14} color={colors.warning} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13, color: colors.warning, fontWeight: "600" }}>{w.title ?? (typeof w === "string" ? w : JSON.stringify(w))}</Text>
            {w.detail && <Text style={{ fontSize: 12, color: colors.labelTertiary, marginTop: 4 }}>{w.detail}</Text>}
          </View>
        </View>
      ))}
    </>
  );
}
