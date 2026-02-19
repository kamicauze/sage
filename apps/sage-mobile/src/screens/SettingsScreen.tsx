import React from "react";
import {
  Alert,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  Cpu,
  Shield,
  TrendingUp,
  Wallet,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { AppSettings } from "../storage/settings";

interface SettingsScreenProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => Promise<void>;
  onTestConnection: (settings: AppSettings) => Promise<void>;
  isLoading: boolean;
  isTesting: boolean;
}

export function SettingsScreen({
  settings,
  onSave,
  onTestConnection,
  isLoading,
  isTesting,
}: SettingsScreenProps) {
  const [draft, setDraft] = React.useState<AppSettings>(settings);
  const [requireDeployApproval, setRequireDeployApproval] = React.useState(true);
  const [killSwitchEnabled, setKillSwitchEnabled] = React.useState(false);
  const [wakeOnLanEnabled, setWakeOnLanEnabled] = React.useState(true);
  const [fanOverrideEnabled, setFanOverrideEnabled] = React.useState(false);

  const handleSave = () => {
    if (!draft.baseUrl.trim()) {
      Alert.alert("Error", "Architect API URL is required");
      return;
    }
    void onSave(draft);
  };

  React.useEffect(() => {
    setDraft(settings);
  }, [settings]);

  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <Text style={styles.screenTitle}>SYSTEM GUARDRAILS</Text>
          <View style={styles.activePill}>
            <View style={styles.activeDot} />
            <Text style={styles.activeText}>ACTIVE</Text>
          </View>
        </View>

        <Text style={styles.sectionHeader}>BUDGET AUTHORITY</Text>
        <GlassCard style={styles.card} variant="soft">
          <View style={styles.cardTopRow}>
            <View>
              <Text style={styles.cardTitle}>Daily Cloud Spend Cap</Text>
              <Text style={styles.cardSub}>Hard limit per 24h rolling window</Text>
            </View>
            <View style={styles.capPill}>
              <Text style={styles.capText}>$50</Text>
            </View>
          </View>

          <View style={styles.sliderWrap}>
            <View style={styles.sliderTrack}>
              <View style={styles.sliderFill} />
              <View style={styles.sliderThumb} />
            </View>
            <View style={styles.sliderLabels}>
              <Text style={styles.sliderLabel}>$0</Text>
              <Text style={styles.sliderLabel}>$75</Text>
              <Text style={styles.sliderLabel}>$150</Text>
            </View>
          </View>

          <View style={styles.metricRow}>
            <GlassCard style={styles.metricCard} variant="outline">
              <View style={styles.metricHeader}>
                <Wallet size={16} color={COLORS.text.secondary} />
                <Text style={styles.metricLabel}>CURRENT SPEND</Text>
              </View>
              <Text style={styles.metricValue}>$342.12</Text>
              <View style={styles.progressTrack}>
                <View style={styles.progressFill} />
              </View>
            </GlassCard>

            <GlassCard style={styles.metricCard} variant="outline">
              <View style={styles.metricHeader}>
                <TrendingUp size={16} color={COLORS.text.secondary} />
                <Text style={styles.metricLabel}>PROJECTED</Text>
              </View>
              <Text style={styles.metricValue}>$480.00</Text>
              <Text style={styles.metricSub}>EST EOM</Text>
            </GlassCard>
          </View>
        </GlassCard>

        <Text style={styles.sectionHeader}>SAFETY PROTOCOLS</Text>
        <GlassCard style={styles.card} variant="soft">
          <View style={styles.toggleRow}>
            <View style={styles.toggleTextWrap}>
              <Text style={styles.toggleTitle}>Require Approval for Production Deploys</Text>
              <Text style={styles.toggleSub}>
                Stops autonomous agents from pushing to production without a human key.
              </Text>
            </View>
            <Switch
              value={requireDeployApproval}
              onValueChange={setRequireDeployApproval}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>

          <View style={styles.separator} />

          <View style={styles.toggleRow}>
            <View style={styles.toggleTextWrap}>
              <Text style={styles.toggleTitle}>Kill Switch Enabled</Text>
              <Text style={styles.toggleSub}>Allow emergency system shutdown via external API.</Text>
            </View>
            <Switch
              value={killSwitchEnabled}
              onValueChange={setKillSwitchEnabled}
              trackColor={{ false: "#2b3853", true: COLORS.accent.error }}
              thumbColor="#f4f7ff"
            />
          </View>
        </GlassCard>

        <Text style={styles.sectionHeader}>HARDWARE ACCESS</Text>
        <GlassCard style={styles.card} variant="soft">
          <View style={styles.toggleRow}>
            <View style={styles.toggleTextWrap}>
              <Text style={styles.toggleTitle}>Allow Auto-Wake for GPU PC</Text>
              <Text style={styles.toggleSub}>Permits Wake-on-LAN for distributed training jobs.</Text>
            </View>
            <Switch
              value={wakeOnLanEnabled}
              onValueChange={setWakeOnLanEnabled}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>

          <View style={styles.separator} />

          <View style={styles.toggleRow}>
            <View style={styles.toggleTextWrap}>
              <Text style={styles.toggleTitle}>Max Fan Speed Override</Text>
              <Text style={styles.toggleSub}>Prevents thermal throttling during heavy jobs.</Text>
            </View>
            <Switch
              value={fanOverrideEnabled}
              onValueChange={setFanOverrideEnabled}
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>
        </GlassCard>

        <Text style={styles.sectionHeader}>API CONNECTIVITY</Text>
        <GlassCard style={styles.card} variant="soft">
          <View style={styles.configHeader}>
            <Cpu size={16} color={COLORS.text.secondary} />
            <Shield size={16} color={COLORS.text.secondary} />
            <Text style={styles.metricLabel}>MOBILE CONTROL CHANNEL</Text>
          </View>

          <Text style={styles.inputLabel}>Architect API URL</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={draft.baseUrl}
              onChangeText={(baseUrl) => setDraft((prev) => ({ ...prev, baseUrl }))}
              placeholder="http://192.168.1.40:8000"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />
          </View>

          <Text style={styles.inputLabel}>API Token</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={draft.apiToken}
              onChangeText={(apiToken) => setDraft((prev) => ({ ...prev, apiToken }))}
              placeholder="Optional bearer token"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              secureTextEntry
            />
          </View>

          <Text style={styles.inputLabel}>Reviewer Name</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={draft.reviewer}
              onChangeText={(reviewer) => setDraft((prev) => ({ ...prev, reviewer }))}
              placeholder="mobile_user"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
            />
          </View>

          <View style={styles.actionsRow}>
            <GlassButton
              onPress={() => onTestConnection(draft)}
              title={isTesting ? "Testing..." : "Test Connection"}
              variant="secondary"
              disabled={isLoading || isTesting}
              style={styles.actionButton}
            />
            <GlassButton
              onPress={handleSave}
              title={isLoading ? "Saving..." : "Save Settings"}
              variant="primary"
              disabled={isLoading || isTesting}
              style={styles.actionButton}
            />
          </View>
        </GlassCard>

        <Text style={styles.footerMeta}>SYS-ID: 4920-ALPHA | LATENCY: 12ms</Text>
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
    marginBottom: SPACING.l,
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
  activePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    borderWidth: 1,
    borderColor: "rgba(32, 214, 143, 0.35)",
    backgroundColor: "rgba(7, 71, 46, 0.35)",
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.xs + 1,
  },
  activeDot: {
    width: 10,
    height: 10,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.status.online,
  },
  activeText: {
    color: COLORS.status.online,
    fontSize: 11,
    letterSpacing: 1.4,
    fontWeight: "700",
  },
  sectionHeader: {
    color: COLORS.text.secondary,
    fontSize: 12,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: SPACING.s,
    marginTop: SPACING.s,
  },
  card: {
    marginBottom: SPACING.l,
  },
  cardTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: SPACING.m,
    gap: SPACING.s,
  },
  cardTitle: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: SPACING.xs,
  },
  cardSub: {
    color: COLORS.text.secondary,
    fontSize: 13,
  },
  capPill: {
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    backgroundColor: "rgba(7, 18, 42, 0.65)",
  },
  capText: {
    color: COLORS.accent.primary,
    fontSize: 16,
    fontWeight: "800",
  },
  sliderWrap: {
    marginBottom: SPACING.m,
  },
  sliderTrack: {
    height: 6,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(86, 107, 148, 0.45)",
    marginBottom: SPACING.s,
    overflow: "visible",
  },
  sliderFill: {
    height: "100%",
    width: "35%",
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.accent.primary,
  },
  sliderThumb: {
    position: "absolute",
    left: "33%",
    top: -8,
    width: 22,
    height: 22,
    borderRadius: RADIUS.full,
    backgroundColor: "#f4f7ff",
    borderWidth: 2,
    borderColor: COLORS.accent.primary,
  },
  sliderLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  sliderLabel: {
    color: COLORS.text.tertiary,
    fontSize: 12,
  },
  metricRow: {
    flexDirection: "row",
    gap: SPACING.s,
  },
  metricCard: {
    flex: 1,
    minHeight: 140,
    justifyContent: "space-between",
  },
  metricHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  metricLabel: {
    color: COLORS.text.secondary,
    fontSize: 12,
    letterSpacing: 1,
    fontWeight: "700",
  },
  metricValue: {
    color: COLORS.text.primary,
    fontSize: 20,
    fontWeight: "700",
    marginTop: SPACING.s,
  },
  metricSub: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  progressTrack: {
    height: 6,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(86, 107, 148, 0.45)",
    marginTop: SPACING.s,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    width: "60%",
    backgroundColor: COLORS.status.attention,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.m,
  },
  toggleTextWrap: {
    flex: 1,
  },
  toggleTitle: {
    color: COLORS.text.primary,
    fontSize: 17,
    fontWeight: "700",
    marginBottom: SPACING.xs,
  },
  toggleSub: {
    color: COLORS.text.secondary,
    fontSize: 14,
    lineHeight: 20,
  },
  separator: {
    height: 1,
    backgroundColor: COLORS.line,
    marginVertical: SPACING.m,
  },
  configHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    marginBottom: SPACING.s,
  },
  inputLabel: {
    color: COLORS.text.secondary,
    fontSize: 12,
    letterSpacing: 1,
    marginBottom: SPACING.xs,
    marginTop: SPACING.s,
  },
  inputWrap: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(8, 18, 40, 0.72)",
  },
  input: {
    color: COLORS.text.primary,
    fontSize: 15,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s + 2,
  },
  actionsRow: {
    marginTop: SPACING.m,
    flexDirection: "row",
    gap: SPACING.s,
  },
  actionButton: {
    flex: 1,
  },
  footerMeta: {
    marginTop: SPACING.m,
    color: COLORS.text.dim,
    textAlign: "center",
    fontSize: 12,
    marginBottom: SPACING.s,
  },
});
