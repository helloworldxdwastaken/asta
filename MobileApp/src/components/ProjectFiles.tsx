import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet, Alert, Platform,
  ActivityIndicator,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { colors, spacing, radius } from "../theme/colors";
import {
  uploadProjectFile, listProjectFiles, deleteProjectFile,
  type ProjectFile,
} from "../lib/api";
import { IconPlus, IconTrash, IconX } from "./Icons";

interface Props {
  folderId: string;
}

export default function ProjectFiles({ folderId }: Props) {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const r = await listProjectFiles(folderId);
      setFiles(r.files ?? []);
    } catch {}
    setLoading(false);
  }, [folderId]);

  useEffect(() => { refresh(); }, [refresh]);

  async function pickAndUpload() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: "*/*",
        copyToCacheDirectory: true,
      });
      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];
      setUploading(true);
      await uploadProjectFile(
        folderId,
        asset.uri,
        asset.name || "file",
        asset.mimeType || "application/octet-stream",
      );
      await refresh();
    } catch {
      Alert.alert("Upload Error", "Failed to upload file");
    } finally {
      setUploading(false);
    }
  }

  function confirmDelete(filename: string) {
    if (Platform.OS === "web") {
      if (confirm(`Delete "${filename}"?`)) doDelete(filename);
      return;
    }
    Alert.alert("Delete File", `Delete "${filename}"?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => doDelete(filename) },
    ]);
  }

  async function doDelete(filename: string) {
    try {
      await deleteProjectFile(folderId, filename);
      setFiles((prev) => prev.filter((f) => f.name !== filename));
    } catch {}
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <View style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.sectionLabel}>PROJECT FILES</Text>
        <TouchableOpacity
          style={styles.uploadBtn}
          onPress={pickAndUpload}
          disabled={uploading}
          activeOpacity={0.7}
        >
          {uploading ? (
            <ActivityIndicator size="small" color={colors.accent} />
          ) : (
            <IconPlus size={12} color={colors.accent} />
          )}
          <Text style={styles.uploadText}>
            {uploading ? "Uploading..." : "Upload"}
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator size="small" color={colors.labelTertiary} style={{ paddingVertical: 12 }} />
      ) : files.length === 0 ? (
        <Text style={styles.emptyText}>
          Upload documents to give Asta context for this project.
        </Text>
      ) : (
        files.map((f) => (
          <View key={f.name} style={styles.fileRow}>
            <Text style={styles.fileIcon}>{"\u{1F4C4}"}</Text>
            <View style={styles.fileInfo}>
              <Text style={styles.fileName} numberOfLines={1}>{f.name}</Text>
              <Text style={styles.fileSize}>{fmtSize(f.size)}</Text>
            </View>
            <TouchableOpacity
              onPress={() => confirmDelete(f.name)}
              style={styles.deleteBtn}
              activeOpacity={0.7}
            >
              <IconTrash size={12} color={colors.danger} />
            </TouchableOpacity>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.separator,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.sm,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.labelTertiary,
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
  uploadBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.sm,
  },
  uploadText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.accent,
  },
  emptyText: {
    fontSize: 12,
    color: colors.labelTertiary,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8,
  },
  fileRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8,
    borderRadius: radius.sm,
  },
  fileIcon: { fontSize: 14 },
  fileInfo: { flex: 1, gap: 1 },
  fileName: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.label,
  },
  fileSize: {
    fontSize: 10,
    color: colors.labelTertiary,
  },
  deleteBtn: {
    padding: 6,
    borderRadius: 6,
  },
});
