import React from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { MessageSquare, Plus, Trash2, X } from "lucide-react-native";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";
import type { SessionIndexEntry } from "../../storage/sessionIndex";

interface SessionListSheetProps {
  visible: boolean;
  onClose: () => void;
  sessions: SessionIndexEntry[];
  activeSessionId: string | null;
  onSwitchSession: (conversationId: string) => void;
  onDeleteSession: (conversationId: string) => void;
  onNewChat: () => void;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return "just now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function SessionListSheet({
  visible,
  onClose,
  sessions,
  activeSessionId,
  onSwitchSession,
  onDeleteSession,
  onNewChat,
}: SessionListSheetProps) {
  const handleDelete = (entry: SessionIndexEntry) => {
    Alert.alert(
      "Delete conversation?",
      `"${entry.preview.slice(0, 40)}..."`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => onDeleteSession(entry.conversationId),
        },
      ]
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <View style={styles.sheet} onStartShouldSetResponder={() => true}>
          <View style={styles.header}>
            <Text style={styles.title}>Conversations</Text>
            <Pressable onPress={onClose} style={styles.closeBtn}>
              <X size={18} color={COLORS.text.secondary} />
            </Pressable>
          </View>

          <ScrollView style={styles.list} showsVerticalScrollIndicator={false}>
            {sessions.length === 0 ? (
              <View style={styles.emptyWrap}>
                <MessageSquare size={28} color={COLORS.text.dim} />
                <Text style={styles.emptyText}>No saved conversations yet</Text>
              </View>
            ) : (
              sessions.map((entry) => {
                const isActive = entry.conversationId === activeSessionId;
                return (
                  <Pressable
                    key={entry.conversationId}
                    onPress={() => onSwitchSession(entry.conversationId)}
                    onLongPress={() => handleDelete(entry)}
                    style={[styles.sessionRow, isActive && styles.sessionRowActive]}
                  >
                    <View style={styles.sessionInfo}>
                      <Text style={styles.sessionPreview} numberOfLines={1}>
                        {entry.preview || "Empty conversation"}
                      </Text>
                      <View style={styles.sessionMeta}>
                        <Text style={styles.sessionMetaText}>
                          {entry.messageCount} msgs
                        </Text>
                        {entry.totalCost > 0 && (
                          <Text style={styles.sessionMetaText}>
                            ${entry.totalCost.toFixed(4)}
                          </Text>
                        )}
                        <Text style={styles.sessionMetaText}>
                          {relativeTime(entry.updatedAt)}
                        </Text>
                      </View>
                    </View>
                    <Pressable
                      onPress={() => handleDelete(entry)}
                      hitSlop={8}
                      style={styles.deleteBtn}
                    >
                      <Trash2 size={14} color={COLORS.text.dim} />
                    </Pressable>
                  </Pressable>
                );
              })
            )}
          </ScrollView>

          <Pressable
            onPress={() => {
              onNewChat();
              onClose();
            }}
            style={styles.newChatBtn}
          >
            <Plus size={16} color={COLORS.accent.primary} />
            <Text style={styles.newChatText}>New Chat</Text>
          </Pressable>
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(4,12,28,0.7)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: COLORS.panel,
    borderTopLeftRadius: RADIUS.l,
    borderTopRightRadius: RADIUS.l,
    borderWidth: 1,
    borderBottomWidth: 0,
    borderColor: COLORS.border,
    maxHeight: "65%",
    paddingBottom: 30,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  title: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
  closeBtn: { padding: 4 },
  list: {
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    flexGrow: 0,
  },
  emptyWrap: {
    alignItems: "center",
    paddingVertical: SPACING.xl,
    gap: SPACING.s,
  },
  emptyText: {
    color: COLORS.text.dim,
    fontSize: 14,
  },
  sessionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: SPACING.s,
    borderRadius: RADIUS.s,
    marginBottom: 2,
  },
  sessionRowActive: {
    backgroundColor: `${COLORS.accent.primary}15`,
  },
  sessionInfo: { flex: 1, marginRight: SPACING.s },
  sessionPreview: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "500",
  },
  sessionMeta: {
    flexDirection: "row",
    gap: 8,
    marginTop: 3,
  },
  sessionMetaText: {
    color: COLORS.text.dim,
    fontSize: 11,
  },
  deleteBtn: {
    padding: 6,
  },
  newChatBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginHorizontal: SPACING.m,
    marginTop: SPACING.s,
    paddingVertical: 12,
    borderRadius: RADIUS.m,
    borderWidth: 1,
    borderColor: `${COLORS.accent.primary}44`,
    backgroundColor: `${COLORS.accent.primary}0d`,
  },
  newChatText: {
    color: COLORS.accent.primary,
    fontSize: 14,
    fontWeight: "600",
  },
});
