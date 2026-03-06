import React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Archive, Mail, RefreshCw, Search, Send } from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { GmailMessageRef, GmailMessage } from "../types/gmail";

interface GmailScreenProps {
  messages: GmailMessageRef[];
  messageDetails: Map<string, GmailMessage>;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  googleConnected: boolean;
  onRefresh: () => void;
  onSearch: (query: string) => void;
  onOpenMessage: (messageId: string) => void;
  onArchiveMessage: (messageId: string) => void;
  onCompose: (to: string, subject: string, body: string) => void;
}

function extractHeader(message: GmailMessage, name: string): string {
  const headers = message.payload?.headers || [];
  const found = headers.find(
    (h) => h.name.toLowerCase() === name.toLowerCase()
  );
  return found?.value || "";
}

function formatDate(internalDate?: string): string {
  if (!internalDate) return "";
  const ms = parseInt(internalDate, 10);
  if (isNaN(ms)) return "";
  const date = new Date(ms);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function GmailScreen({
  messages,
  messageDetails,
  isLoading,
  isRefreshing,
  error,
  googleConnected,
  onRefresh,
  onSearch,
  onOpenMessage,
  onArchiveMessage,
  onCompose,
}: GmailScreenProps) {
  const [searchQuery, setSearchQuery] = React.useState("");
  const [composing, setComposing] = React.useState(false);
  const [composeTo, setComposeTo] = React.useState("");
  const [composeSubject, setComposeSubject] = React.useState("");
  const [composeBody, setComposeBody] = React.useState("");
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const handleSearch = () => {
    const trimmed = searchQuery.trim();
    onSearch(trimmed);
  };

  const handleSend = () => {
    if (!composeTo.trim() || !composeSubject.trim()) return;
    onCompose(composeTo.trim(), composeSubject.trim(), composeBody.trim());
    setComposing(false);
    setComposeTo("");
    setComposeSubject("");
    setComposeBody("");
  };

  const handleExpand = (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    onOpenMessage(id);
  };

  if (!googleConnected) {
    return (
      <ScreenLayout>
        <View style={styles.centerWrap}>
          <Mail size={48} color={COLORS.text.tertiary} />
          <Text style={styles.emptyTitle}>Google not connected</Text>
          <Text style={styles.emptySubtitle}>
            Connect Google Workspace in Settings to use Gmail.
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <Text style={styles.screenTitle}>GMAIL</Text>
          <Pressable onPress={onRefresh} disabled={isRefreshing}>
            <RefreshCw
              size={18}
              color={isRefreshing ? COLORS.text.tertiary : COLORS.accent.primary}
            />
          </Pressable>
        </View>

        <View style={styles.searchRow}>
          <View style={styles.searchInputWrap}>
            <Search size={16} color={COLORS.text.tertiary} />
            <TextInput
              style={styles.searchInput}
              value={searchQuery}
              onChangeText={setSearchQuery}
              placeholder="Search emails..."
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              autoCorrect={false}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
          </View>
          <Pressable style={styles.composeButton} onPress={() => setComposing((v) => !v)}>
            <Send size={18} color={COLORS.accent.primary} />
          </Pressable>
        </View>

        {composing && (
          <GlassCard style={styles.composeCard} variant="soft">
            <Text style={styles.composeTitle}>New Email</Text>
            <View style={styles.inputWrap}>
              <TextInput
                style={styles.input}
                value={composeTo}
                onChangeText={setComposeTo}
                placeholder="To"
                placeholderTextColor={COLORS.text.tertiary}
                autoCapitalize="none"
                keyboardType="email-address"
              />
            </View>
            <View style={styles.inputWrap}>
              <TextInput
                style={styles.input}
                value={composeSubject}
                onChangeText={setComposeSubject}
                placeholder="Subject"
                placeholderTextColor={COLORS.text.tertiary}
              />
            </View>
            <View style={[styles.inputWrap, styles.bodyInputWrap]}>
              <TextInput
                style={[styles.input, styles.bodyInput]}
                value={composeBody}
                onChangeText={setComposeBody}
                placeholder="Message body"
                placeholderTextColor={COLORS.text.tertiary}
                multiline
                numberOfLines={4}
              />
            </View>
            <View style={styles.composeActions}>
              <GlassButton
                onPress={() => setComposing(false)}
                title="Cancel"
                variant="ghost"
                style={styles.composeActionBtn}
              />
              <GlassButton
                onPress={handleSend}
                title="Send"
                variant="primary"
                disabled={!composeTo.trim() || !composeSubject.trim()}
                style={styles.composeActionBtn}
              />
            </View>
          </GlassCard>
        )}

        {error && (
          <GlassCard style={styles.errorCard} variant="critical">
            <Text style={styles.errorText}>{error}</Text>
          </GlassCard>
        )}

        {isLoading && !messages.length ? (
          <View style={styles.centerWrap}>
            <ActivityIndicator color={COLORS.accent.primary} size="large" />
            <Text style={styles.loadingText}>Loading inbox...</Text>
          </View>
        ) : messages.length === 0 ? (
          <View style={styles.centerWrap}>
            <Mail size={32} color={COLORS.text.tertiary} />
            <Text style={styles.emptyTitle}>No messages</Text>
          </View>
        ) : (
          messages.map((ref) => {
            const detail = messageDetails.get(ref.id);
            const isExpanded = expandedId === ref.id;
            const from = detail ? extractHeader(detail, "From") : "";
            const subject = detail ? extractHeader(detail, "Subject") : "";
            const snippet = detail?.snippet || "";
            const dateStr = detail ? formatDate(detail.internalDate) : "";
            const isUnread = detail?.labelIds?.includes("UNREAD") ?? false;

            return (
              <Pressable key={ref.id} onPress={() => handleExpand(ref.id)}>
                <GlassCard
                  style={[styles.messageCard, isUnread && styles.unreadCard]}
                  variant="soft"
                >
                  <View style={styles.messageHeader}>
                    <View style={styles.messageLeft}>
                      {isUnread && <View style={styles.unreadDot} />}
                      <Text style={styles.messageFrom} numberOfLines={1}>
                        {from || ref.id.slice(0, 8)}
                      </Text>
                    </View>
                    <Text style={styles.messageDate}>{dateStr}</Text>
                  </View>
                  <Text
                    style={[styles.messageSubject, isUnread && styles.unreadSubject]}
                    numberOfLines={1}
                  >
                    {subject || "(no subject)"}
                  </Text>
                  {!isExpanded && (
                    <Text style={styles.messageSnippet} numberOfLines={2}>
                      {snippet}
                    </Text>
                  )}
                  {isExpanded && detail && (
                    <View style={styles.expandedContent}>
                      <Text style={styles.expandedSnippet}>{snippet}</Text>
                      <View style={styles.messageActions}>
                        <Pressable
                          style={styles.messageActionBtn}
                          onPress={() => onArchiveMessage(ref.id)}
                        >
                          <Archive size={16} color={COLORS.text.secondary} />
                          <Text style={styles.messageActionText}>Archive</Text>
                        </Pressable>
                      </View>
                    </View>
                  )}
                </GlassCard>
              </Pressable>
            );
          })
        )}
      </ScrollView>
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: LAYOUT.tabBarHeight + 70,
  },
  headerRow: {
    marginTop: SPACING.s,
    marginBottom: SPACING.m,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  screenTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 1.8,
  },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    marginBottom: SPACING.m,
  },
  searchInputWrap: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(8, 20, 43, 0.78)",
    paddingHorizontal: SPACING.m,
  },
  searchInput: {
    flex: 1,
    color: COLORS.text.primary,
    paddingVertical: SPACING.s + 2,
    fontSize: 14,
  },
  composeButton: {
    width: 44,
    height: 44,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(8, 20, 43, 0.78)",
    alignItems: "center",
    justifyContent: "center",
  },
  composeCard: {
    marginBottom: SPACING.m,
  },
  composeTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
    marginBottom: SPACING.s,
  },
  inputWrap: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(8, 20, 43, 0.78)",
    marginBottom: SPACING.s,
  },
  input: {
    color: COLORS.text.primary,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s + 2,
    fontSize: 14,
  },
  bodyInputWrap: {
    minHeight: 100,
  },
  bodyInput: {
    textAlignVertical: "top",
    minHeight: 80,
  },
  composeActions: {
    flexDirection: "row",
    gap: SPACING.s,
    marginTop: SPACING.xs,
  },
  composeActionBtn: {
    flex: 1,
    minHeight: 46,
  },
  errorCard: {
    marginBottom: SPACING.m,
  },
  errorText: {
    color: COLORS.accent.error,
    fontSize: 13,
  },
  centerWrap: {
    marginTop: SPACING.xxl * 2,
    alignItems: "center",
    gap: SPACING.m,
  },
  loadingText: {
    color: COLORS.text.secondary,
    fontSize: 13,
  },
  emptyTitle: {
    color: COLORS.text.primary,
    fontSize: 18,
    fontWeight: "600",
  },
  emptySubtitle: {
    color: COLORS.text.secondary,
    fontSize: 13,
    textAlign: "center",
    paddingHorizontal: SPACING.xl,
  },
  messageCard: {
    marginBottom: SPACING.s,
  },
  unreadCard: {
    borderColor: "rgba(47, 107, 255, 0.35)",
  },
  messageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: SPACING.xxs,
  },
  messageLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    flex: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.accent.primary,
  },
  messageFrom: {
    color: COLORS.text.primary,
    fontSize: 13,
    fontWeight: "600",
    flex: 1,
  },
  messageDate: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    marginLeft: SPACING.s,
  },
  messageSubject: {
    color: COLORS.text.secondary,
    fontSize: 14,
    marginBottom: SPACING.xxs,
  },
  unreadSubject: {
    color: COLORS.text.primary,
    fontWeight: "700",
  },
  messageSnippet: {
    color: COLORS.text.tertiary,
    fontSize: 12,
    lineHeight: 17,
  },
  expandedContent: {
    marginTop: SPACING.s,
    paddingTop: SPACING.s,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  expandedSnippet: {
    color: COLORS.text.secondary,
    fontSize: 13,
    lineHeight: 19,
    marginBottom: SPACING.s,
  },
  messageActions: {
    flexDirection: "row",
    gap: SPACING.m,
  },
  messageActionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    paddingVertical: SPACING.xs,
  },
  messageActionText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "600",
  },
});
