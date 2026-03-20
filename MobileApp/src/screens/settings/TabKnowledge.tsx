import React, { useState, useEffect } from "react";
import { View, Text, TouchableOpacity, Alert, Platform } from "react-native";
import { colors, radius } from "../../theme/colors";
import { ragStatus, ragLearned, getMemoryHealth, ragDeleteTopic } from "../../lib/api";
import { IconTrash } from "../../components/Icons";
import { Label, CardRow, st, TabProps } from "./shared";

export default function TabKnowledge(_props: TabProps) {
  const [ragInfo, setRagInfo] = useState<any>(null);
  const [ragTopics, setRagTopics] = useState<any[]>([]);
  const [memHealth, setMemHealth] = useState<any>(null);

  useEffect(() => {
    ragStatus().then(setRagInfo).catch(() => {});
    ragLearned().then((r) => setRagTopics(r.topics || r.learned || [])).catch(() => {});
    getMemoryHealth().then(setMemHealth).catch(() => {});
  }, []);

  async function handleDeleteTopic(topic: string) {
    const doDelete = async () => {
      await ragDeleteTopic(topic).catch(() => {});
      const r = await ragLearned().catch(() => ({ topics: [], learned: [] }));
      setRagTopics(r.topics || r.learned || []);
      getMemoryHealth().then(setMemHealth).catch(() => {});
    };
    if (Platform.OS === "web") {
      if (confirm(`Delete topic "${topic}"?`)) await doDelete();
      return;
    }
    Alert.alert("Delete Topic", `Remove "${topic}" from knowledge base?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: doDelete },
    ]);
  }

  const ragOk = ragInfo?.ok;

  return (
    <>
      <Text style={st.desc}>Knowledge base for context-aware responses.</Text>

      {/* RAG status */}
      <View style={st.card}>
        <CardRow label="Status" value={ragOk ? "Active" : "Inactive"}
          valueColor={ragOk ? colors.success : colors.labelTertiary} />
        {ragInfo?.provider && <CardRow label="Provider" value={ragInfo.provider} />}
        {ragInfo?.store_error && <CardRow label="Error" value={ragInfo.store_error} valueColor={colors.danger} />}
      </View>

      {/* Memory health */}
      {memHealth && (
        <>
          <Label text="Memory Health" />
          <View style={st.card}>
            {memHealth.vector_count != null && <CardRow label="Vectors" value={String(memHealth.vector_count)} />}
            {memHealth.chunk_count != null && <CardRow label="Chunks" value={String(memHealth.chunk_count)} />}
            {memHealth.store_size_mb != null && <CardRow label="Store Size" value={`${memHealth.store_size_mb} MB`} />}
          </View>
        </>
      )}

      {/* Learned topics */}
      <Label text="Learned Topics" />
      {ragTopics.length === 0 ? (
        <Text style={st.emptyText}>
          No topics learned yet. Use learning mode in chat to teach Asta.
        </Text>
      ) : (
        ragTopics.map((t: any) => {
          const name = typeof t === "string" ? t : t.topic || t.name || "";
          const chunks = typeof t === "object" ? t.chunks || t.chunk_count : undefined;
          return (
            <View key={name} style={st.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={st.toggleName}>{name}</Text>
                {chunks != null && (
                  <Text style={st.toggleDesc}>{chunks} chunk{chunks !== 1 ? "s" : ""}</Text>
                )}
              </View>
              <TouchableOpacity onPress={() => handleDeleteTopic(name)} activeOpacity={0.7}>
                <IconTrash size={16} color={colors.danger} />
              </TouchableOpacity>
            </View>
          );
        })
      )}
    </>
  );
}
