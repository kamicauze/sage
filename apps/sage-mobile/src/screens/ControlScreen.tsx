import React from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { ShieldAlert, SlidersHorizontal } from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import {
  BrainControlAuditEntry,
  BrainControlAuditFilter,
  BrainControlConfigRequest,
  BrainControlCommandRequest,
  BrainControlState,
} from "../types/control";

interface ControlScreenProps {
  controlState: BrainControlState | null;
  auditEntries: BrainControlAuditEntry[];
  auditFilter: BrainControlAuditFilter;
  mqttOnline: boolean;
  mqttError?: string | null;
  isLoading: boolean;
  isMutating: boolean;
  onAuditFilterChange: (filter: BrainControlAuditFilter) => void;
  onRefresh: () => void;
  onSaveConfig: (patch: BrainControlConfigRequest) => Promise<void>;
  onSendCommand: (command: BrainControlCommandRequest["command"]) => Promise<void>;
}

const AUDIT_FILTERS: Array<{ key: BrainControlAuditFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "config", label: "Config" },
  { key: "command", label: "Command" },
  { key: "error", label: "Error" },
];

export function ControlScreen({
  controlState,
  auditEntries,
  auditFilter,
  mqttOnline,
  mqttError,
  isLoading,
  isMutating,
  onAuditFilterChange,
  onRefresh,
  onSaveConfig,
  onSendCommand,
}: ControlScreenProps) {
  const [personality, setPersonality] = React.useState("");
  const [rawMode, setRawMode] = React.useState(false);
  const [voiceInputEnabled, setVoiceInputEnabled] = React.useState(true);
  const [voiceOutputEnabled, setVoiceOutputEnabled] = React.useState(true);

  React.useEffect(() => {
    if (!controlState) return;
    setPersonality(controlState.personality || "kenyan_babe");
    setRawMode(Boolean(controlState.raw_mode));
    setVoiceInputEnabled(Boolean(controlState.voice_input_enabled));
    setVoiceOutputEnabled(Boolean(controlState.voice_output_enabled));
  }, [controlState]);

  const disableActions = isLoading || isMutating;

  const handleSave = () => {
    const trimmed = personality.trim();
    if (!trimmed) {
      Alert.alert("Missing personality", "Set a personality value before saving.");
      return;
    }
    void onSaveConfig({
      personality: trimmed,
      raw_mode: rawMode,
      voice_input_enabled: voiceInputEnabled,
      voice_output_enabled: voiceOutputEnabled,
    });
  };

  const handleCommand = (command: BrainControlCommandRequest["command"], confirmText?: string) => {
    const run = () => void onSendCommand(command);
    if (confirmText) {
      Alert.alert("Confirm action", confirmText, [
        { text: "Cancel", style: "cancel" },
        { text: "Run", style: "destructive", onPress: run },
      ]);
      return;
    }
    run();
  };

  const renderAuditDetail = (entry: BrainControlAuditEntry): string => {
    const payload = entry.payload || {};
    if (typeof payload.command === "string") {
      return `command=${payload.command}`;
    }
    const keys = Object.keys(payload).filter((key) => key !== "source" && key !== "ts");
    if (!keys.length) {
      return "config update";
    }
    return keys.slice(0, 3).map((key) => `${key}=${String(payload[key])}`).join(" • ");
  };

  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <Text style={styles.screenTitle}>CONTROL PANEL</Text>
          <View style={styles.activePill}>
            <View
              style={[
                styles.statusDot,
                { backgroundColor: mqttOnline ? COLORS.status.online : COLORS.status.critical },
              ]}
            />
            <Text style={styles.activeText}>{mqttOnline ? "MQTT ONLINE" : "MQTT OFFLINE"}</Text>
          </View>
        </View>
        <Text style={styles.screenSubTitle}>
          Runtime controls for brain personality, raw mode, voice gates, and memory commands.
        </Text>

        <GlassCard style={styles.card} variant="soft">
          <View style={styles.cardTitleRow}>
            <SlidersHorizontal size={16} color={COLORS.text.secondary} />
            <Text style={styles.cardTitle}>Brain Config</Text>
          </View>
          <Text style={styles.inputLabel}>Personality</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={personality}
              onChangeText={setPersonality}
              placeholder="kenyan_babe"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleTitle}>Raw mode</Text>
            <Switch
              value={rawMode}
              onValueChange={setRawMode}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleTitle}>Voice input enabled</Text>
            <Switch
              value={voiceInputEnabled}
              onValueChange={setVoiceInputEnabled}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleTitle}>Voice output enabled</Text>
            <Switch
              value={voiceOutputEnabled}
              onValueChange={setVoiceOutputEnabled}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>
          <View style={styles.actionsRow}>
            <GlassButton
              onPress={onRefresh}
              title={isLoading ? "Refreshing..." : "Refresh"}
              variant="secondary"
              disabled={disableActions}
              style={styles.actionButton}
            />
            <GlassButton
              onPress={handleSave}
              title={isMutating ? "Saving..." : "Apply"}
              variant="primary"
              disabled={disableActions}
              style={styles.actionButton}
            />
          </View>
          {controlState ? (
            <Text style={styles.metaText}>
              Last update: {new Date(controlState.updated_at).toLocaleTimeString()} · Last command:{" "}
              {controlState.last_command || "none"}
            </Text>
          ) : null}
          {mqttError ? <Text style={styles.warningText}>{mqttError}</Text> : null}
        </GlassCard>

        <GlassCard style={styles.card} variant="outline">
          <View style={styles.cardTitleRow}>
            <ShieldAlert size={16} color={COLORS.accent.warning} />
            <Text style={styles.cardTitle}>Commands</Text>
          </View>
          <View style={styles.commandGrid}>
            <GlassButton
              onPress={() => handleCommand("clear_conversation")}
              title="Clear Conversation"
              variant="secondary"
              disabled={disableActions}
              style={styles.commandButton}
            />
            <GlassButton
              onPress={() => handleCommand("clear_episodes")}
              title="Clear Episodes"
              variant="secondary"
              disabled={disableActions}
              style={styles.commandButton}
            />
            <GlassButton
              onPress={() =>
                handleCommand(
                  "clear_memory",
                  "This clears long-term memory. Continue?"
                )
              }
              title="Clear All Memory"
              variant="danger"
              disabled={disableActions}
              style={styles.commandButton}
            />
            <GlassButton
              onPress={() =>
                handleCommand(
                  "kill_switch",
                  "This disables voice input/output immediately. Continue?"
                )
              }
              title="Kill Switch"
              variant="danger"
              disabled={disableActions}
              style={styles.commandButton}
            />
            <GlassButton
              onPress={() => handleCommand("resume_voice")}
              title="Resume Voice"
              variant="primary"
              disabled={disableActions}
              style={styles.commandButton}
            />
          </View>
        </GlassCard>

        <GlassCard style={styles.card} variant="soft">
          <View style={styles.cardTitleRow}>
            <Text style={styles.cardTitle}>Audit Trail</Text>
          </View>
          <View style={styles.filterRow}>
            {AUDIT_FILTERS.map((filter) => {
              const active = filter.key === auditFilter;
              return (
                <Pressable
                  key={filter.key}
                  onPress={() => onAuditFilterChange(filter.key)}
                  style={[styles.filterChip, active && styles.filterChipActive]}
                >
                  <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                    {filter.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {auditEntries.length === 0 ? (
            <Text style={styles.metaText}>No audit entries for this filter.</Text>
          ) : (
            <View style={styles.auditList}>
              {auditEntries.slice(0, 12).map((entry, index) => (
                <View key={`${entry.ts}-${entry.action}-${index}`} style={styles.auditItem}>
                  <View style={styles.auditHeader}>
                    <Text style={styles.auditTitle}>
                      {entry.action} · {entry.status}
                    </Text>
                    <Text style={styles.auditTime}>
                      {new Date(entry.ts).toLocaleTimeString()}
                    </Text>
                  </View>
                  <Text style={styles.auditSource}>{entry.source}</Text>
                  <Text style={styles.auditDetail}>{renderAuditDetail(entry)}</Text>
                  {entry.error ? <Text style={styles.warningText}>{entry.error}</Text> : null}
                </View>
              ))}
            </View>
          )}
        </GlassCard>
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
    marginBottom: SPACING.s,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  screenTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 1.8,
  },
  screenSubTitle: {
    color: COLORS.text.secondary,
    fontSize: 13,
    lineHeight: 19,
    marginBottom: SPACING.m,
  },
  activePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    borderWidth: 1,
    borderColor: "rgba(32, 214, 143, 0.35)",
    backgroundColor: "rgba(7, 71, 46, 0.35)",
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.xs + 1,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: RADIUS.full,
  },
  activeText: {
    color: COLORS.text.primary,
    fontSize: 11,
    letterSpacing: 0.8,
    fontWeight: "700",
  },
  card: {
    marginBottom: SPACING.m,
  },
  cardTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    marginBottom: SPACING.s,
  },
  cardTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
  },
  inputLabel: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginBottom: SPACING.xs,
    marginTop: SPACING.xs,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  inputWrap: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(8, 20, 43, 0.78)",
  },
  input: {
    color: COLORS.text.primary,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s + 2,
    fontSize: 15,
  },
  toggleRow: {
    marginTop: SPACING.s,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  toggleTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "600",
  },
  actionsRow: {
    flexDirection: "row",
    gap: SPACING.s,
    marginTop: SPACING.l,
  },
  actionButton: {
    flex: 1,
  },
  metaText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginTop: SPACING.s,
  },
  warningText: {
    color: COLORS.accent.warning,
    fontSize: 12,
    marginTop: SPACING.xs,
  },
  commandGrid: {
    gap: SPACING.s,
  },
  commandButton: {
    minHeight: 52,
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
    marginBottom: SPACING.s,
  },
  filterChip: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(12, 28, 56, 0.55)",
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
  },
  filterChipActive: {
    borderColor: "rgba(106, 159, 255, 0.9)",
    backgroundColor: "rgba(47, 107, 255, 0.22)",
  },
  filterChipText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  filterChipTextActive: {
    color: COLORS.text.primary,
  },
  auditList: {
    gap: SPACING.s,
  },
  auditItem: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(8, 20, 43, 0.52)",
    padding: SPACING.s,
  },
  auditHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: SPACING.s,
  },
  auditTitle: {
    color: COLORS.text.primary,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  auditTime: {
    color: COLORS.text.tertiary,
    fontSize: 11,
  },
  auditSource: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginTop: 2,
  },
  auditDetail: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginTop: SPACING.xs,
  },
});
