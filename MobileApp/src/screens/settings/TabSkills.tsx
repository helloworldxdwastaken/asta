import React, { useState, useEffect } from "react";
import { View, Text } from "react-native";
import { colors } from "../../theme/colors";
import { getSkills, toggleSkill } from "../../lib/api";
import Toggle from "../../components/Toggle";
import { st, TabProps } from "./shared";

const SKILL_COLORS: Record<string, string> = {
  "after-effects-assistant": "#00005b", "apple-notes": "#f5c518", "competitor": "#e74c3c",
  "docx": "#2b579a", "esimo-copywriter": "#8e44ad", "index-crawl": "#27ae60",
  "index-manager": "#2980b9", "index-status": "#16a085", "index-submit": "#e67e22",
  "knowledge-curator": "#9b59b6", "librarian": "#8d6e63", "math": "#3498db",
  "notes": "#f39c12", "notion": "#000", "notion-operator": "#1a1a2e",
  "pdf": "#c0392b", "pptx": "#d04423", "seo-strategist": "#2ecc71",
  "skill-creator": "#7f8c8d", "things-mac": "#4a90d9", "xlsx": "#217346",
  "youtube-creator": "#c4302b", "youtube-edit": "#c4302b", "youtube-script": "#c4302b",
  "youtube-source": "#c4302b", "youtube-trends": "#c4302b", "youtube-upload": "#c4302b",
};

const SKILL_LABELS: Record<string, string> = {
  "after-effects-assistant": "Ae", "apple-notes": "N", "competitor": "C",
  "docx": "W", "esimo-copywriter": "E", "index-crawl": "IC",
  "index-manager": "IM", "index-status": "IS", "index-submit": "IS",
  "knowledge-curator": "K", "librarian": "L", "math": "M",
  "notes": "N", "notion": "N", "notion-operator": "NO",
  "pdf": "P", "pptx": "P", "seo-strategist": "SE",
  "skill-creator": "SC", "things-mac": "T", "xlsx": "X",
  "youtube-creator": "YT", "youtube-edit": "YE", "youtube-script": "YS",
  "youtube-source": "YS", "youtube-trends": "YT", "youtube-upload": "YU",
};

function skillHashColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return `hsl(${Math.abs(h) % 360}, 45%, 40%)`;
}

export default function TabSkills(_props: TabProps) {
  const [skills, setSkills] = useState<any[]>([]);

  useEffect(() => {
    getSkills().then((r) => setSkills(r.skills || r || [])).catch(() => {});
  }, []);

  const pairs: any[][] = [];
  for (let i = 0; i < skills.length; i += 2) {
    pairs.push(skills.slice(i, i + 2));
  }

  return (
    <>
      <Text style={st.desc}>Enable or disable workspace skills.</Text>
      {skills.length === 0 && <Text style={st.emptyText}>No skills found</Text>}
      {pairs.map((pair, pi) => (
        <View key={pi} style={{ flexDirection: "row", gap: 8, marginBottom: 8 }}>
          {pair.map((sk: any) => {
            const sid = sk.id || sk.name;
            const bg = SKILL_COLORS[sid] || skillHashColor(sid);
            const lbl = SKILL_LABELS[sid] || sid.charAt(0).toUpperCase();
            return (
              <View key={sid} style={{
                flex: 1, flexDirection: "row", alignItems: "center", gap: 10,
                backgroundColor: "rgba(255,255,255,0.04)",
                borderWidth: 1, borderColor: sk.enabled ? colors.accent + "33" : colors.separator,
                borderRadius: 12, paddingHorizontal: 10, paddingVertical: 10,
              }}>
                <View style={{
                  width: 30, height: 30, borderRadius: 8, backgroundColor: bg,
                  alignItems: "center", justifyContent: "center",
                }}>
                  <Text style={{ color: "#fff", fontWeight: "700", fontSize: 11 }}>{lbl}</Text>
                </View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text numberOfLines={1} style={{ color: colors.label, fontSize: 12, fontWeight: "600" }}>{sk.name || sid}</Text>
                  {sk.description ? <Text numberOfLines={1} style={{ color: colors.labelTertiary, fontSize: 9, marginTop: 1 }}>{sk.description}</Text> : null}
                </View>
                <Toggle value={sk.enabled}
                  onValueChange={(v) => { setSkills(prev => prev.map((x: any) => (x.id || x.name) === sid ? { ...x, enabled: v } : x)); toggleSkill(sid, v).catch(() => {}); }}
                />
              </View>
            );
          })}
          {pair.length === 1 && <View style={{ flex: 1 }} />}
        </View>
      ))}
    </>
  );
}
