import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  Activity,
  ArrowRight,
  Bug,
  PauseCircle,
  Radar,
  TerminalSquare,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassButton } from "../components/ui/GlassButton";
import { GlassCard } from "../components/ui/GlassCard";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";

interface ChatScreenProps {
  messages: Array<{ id: string; role: "user" | "assistant"; text: string }>;
  onSend: (text: string) => void;
  isSending: boolean;
}

const QUICK_ACTIONS = [
  { label: "Summarize Project Atlas", icon: Activity },
  { label: "Scan for opportunities", icon: Radar },
  { label: "Pause all jobs", icon: PauseCircle, variant: "danger" as const },
  { label: "Debug Kernel", icon: Bug },
];

export function ChatScreen({ messages, onSend, isSending }: ChatScreenProps) {
  const [text, setText] = React.useState("");

  const send = React.useCallback(() => {
    const payload = text.trim();
    if (!payload || isSending) {
      return;
    }
    onSend(payload);
    setText("");
  }, [isSending, onSend, text]);

  const logs = messages.slice(-3).map((msg) => {
    const stamp = new Date().toLocaleTimeString(undefined, {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    return {
      id: msg.id,
      line: `${stamp} ${msg.role === "assistant" ? "[SYS]" : "[CMD]"} ${msg.text}`,
    };
  });

  return (
    <ScreenLayout>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 70 : 0}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.statusRow}>
            <View style={styles.statusGroup}>
              <View style={styles.onlineDot} />
              <Text style={styles.statusText}>SYSTEMS NOMINAL</Text>
            </View>
            <Text style={styles.latencyText}>12ms</Text>
            <View style={styles.divider} />
            <Text style={styles.linkText}>UPLINK ACTIVE</Text>
          </View>

          <View style={styles.hero}>
            <View style={styles.heroOrb}>
              <TerminalSquare size={38} color={COLORS.accent.info} />
            </View>
            <Text style={styles.heroTitle}>Command Center</Text>
            <Text style={styles.heroSubtitle}>Ready for input. Awaiting instructions.</Text>
          </View>

          <GlassCard style={styles.commandInputCard} variant="soft">
            <View style={styles.inputRow}>
              <Text style={styles.prompt}>{">"}</Text>
              <TextInput
                style={styles.input}
                value={text}
                onChangeText={setText}
                placeholder="Issue intent..."
                placeholderTextColor={COLORS.text.tertiary}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="send"
                onSubmitEditing={send}
              />
              <GlassButton
                onPress={send}
                disabled={!text.trim() || isSending}
                variant="ghost"
                style={styles.sendButton}
              >
                <ArrowRight size={28} color={COLORS.accent.primary} />
              </GlassButton>
            </View>
          </GlassCard>

          <View style={styles.quickActionsGrid}>
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon;
              return (
                <GlassButton
                  key={action.label}
                  onPress={() => undefined}
                  variant={action.variant ?? "ghost"}
                  style={styles.actionPill}
                >
                  <View style={styles.actionContent}>
                    <Icon
                      size={16}
                      color={action.variant === "danger" ? COLORS.accent.error : COLORS.text.secondary}
                    />
                    <Text
                      style={[
                        styles.actionText,
                        action.variant === "danger" && styles.actionTextDanger,
                      ]}
                    >
                      {action.label}
                    </Text>
                  </View>
                </GlassButton>
              );
            })}
          </View>

          <View style={styles.logBlock}>
            {logs.length === 0 ? (
              <>
                <Text style={styles.logLine}>14:02:22 [SYS] Handshake completed with Node_Alpha</Text>
                <Text style={styles.logLine}>14:02:20 [NET] Latency optimal. Packet loss 0.0%</Text>
                <Text style={styles.logLine}>14:01:58 [AUTH] Biometric verification passed</Text>
              </>
            ) : (
              logs.map((entry) => (
                <Text key={entry.id} style={styles.logLine}>
                  {entry.line}
                </Text>
              ))
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scroll: {
    paddingBottom: LAYOUT.tabBarHeight + 86,
    flexGrow: 1,
  },
  statusRow: {
    marginTop: SPACING.s,
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: SPACING.s,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.line,
  },
  statusGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  onlineDot: {
    width: 10,
    height: 10,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.status.online,
  },
  statusText: {
    fontSize: 12,
    color: COLORS.text.secondary,
    letterSpacing: 1.8,
    fontWeight: "700",
  },
  latencyText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginLeft: "auto",
    marginRight: SPACING.s,
  },
  divider: {
    height: 20,
    width: 1,
    backgroundColor: COLORS.line,
    marginHorizontal: SPACING.s,
  },
  linkText: {
    color: COLORS.accent.info,
    fontSize: 12,
    letterSpacing: 1.3,
  },
  hero: {
    marginTop: SPACING.xxl,
    alignItems: "center",
    marginBottom: SPACING.l,
  },
  heroOrb: {
    width: 116,
    height: 116,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: "rgba(71, 131, 255, 0.35)",
    backgroundColor: "rgba(24, 49, 96, 0.55)",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: COLORS.accent.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.32,
    shadowRadius: 26,
    elevation: 9,
    marginBottom: SPACING.l,
  },
  heroTitle: {
    color: COLORS.text.primary,
    fontSize: 20,
    fontWeight: "700",
    marginBottom: SPACING.s,
  },
  heroSubtitle: {
    color: COLORS.text.secondary,
    fontSize: 13,
  },
  commandInputCard: {
    borderColor: "rgba(54, 117, 255, 0.6)",
    shadowColor: COLORS.accent.primary,
    shadowOpacity: 0.45,
    shadowOffset: { width: 0, height: 0 },
    shadowRadius: 18,
    elevation: 9,
    marginBottom: SPACING.l,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 68,
    paddingHorizontal: SPACING.s,
    gap: SPACING.s,
  },
  prompt: {
    color: COLORS.accent.info,
    fontSize: 22,
    fontWeight: "500",
    marginLeft: SPACING.s,
  },
  input: {
    flex: 1,
    color: COLORS.text.primary,
    fontSize: 16,
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
    paddingVertical: SPACING.s,
  },
  sendButton: {
    width: 56,
    minHeight: 56,
    borderRadius: RADIUS.s,
    borderWidth: 0,
  },
  quickActionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: SPACING.s,
    marginBottom: SPACING.xl,
  },
  actionPill: {
    borderRadius: RADIUS.full,
    minHeight: 52,
    minWidth: 168,
    borderColor: COLORS.border,
  },
  actionContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  actionText: {
    color: COLORS.text.secondary,
    fontSize: 13,
    fontWeight: "600",
  },
  actionTextDanger: {
    color: COLORS.accent.error,
  },
  logBlock: {
    marginTop: "auto",
    paddingTop: SPACING.xl,
    gap: SPACING.s,
  },
  logLine: {
    color: "rgba(97, 117, 156, 0.62)",
    fontSize: 12,
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
  },
});
