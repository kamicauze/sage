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
import { Key, Shield, Trash2, Webhook } from "lucide-react-native";
import Constants from "expo-constants";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { AppSettings } from "../storage/settings";
import { GoogleStatusResponse } from "../types/google";
import { WebhookHook } from "../types/webhooks";

interface SettingsScreenProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => Promise<void>;
  onTestConnection: (settings: AppSettings) => Promise<void>;
  googleStatus: GoogleStatusResponse | null;
  googleLoading: boolean;
  googleConnecting: boolean;
  onRefreshGoogleStatus: () => Promise<void>;
  onConnectGoogle: () => Promise<void>;
  onDisconnectGoogle: () => Promise<void>;
  isLoading: boolean;
  isTesting: boolean;
  webhooks: WebhookHook[];
  webhooksLoading: boolean;
  onRefreshWebhooks: () => void;
  onDeleteWebhook: (hookId: string) => void;
  vaultKeys: string[];
  vaultLoading: boolean;
  onRefreshVault: () => void;
  onStoreVaultKey: (name: string, value: string) => void;
  onDeleteVaultKey: (name: string) => void;
}

export function SettingsScreen({
  settings,
  onSave,
  onTestConnection,
  googleStatus,
  googleLoading,
  googleConnecting,
  onRefreshGoogleStatus,
  onConnectGoogle,
  onDisconnectGoogle,
  isLoading,
  isTesting,
  webhooks,
  webhooksLoading,
  onRefreshWebhooks,
  onDeleteWebhook,
  vaultKeys,
  vaultLoading,
  onRefreshVault,
  onStoreVaultKey,
  onDeleteVaultKey,
}: SettingsScreenProps) {
  const [draft, setDraft] = React.useState<AppSettings>(settings);
  const googleStateLabel = !googleStatus
    ? "Unknown"
    : googleStatus.connected
      ? "Connected"
      : googleStatus.configured
        ? "Not connected"
        : "Not configured";

  const detectLanApiUrl = React.useCallback((): string | null => {
    const bag = Constants as unknown as {
      expoConfig?: { hostUri?: string };
      manifest2?: { extra?: { expoGo?: { debuggerHost?: string } } };
      manifest?: { debuggerHost?: string };
    };
    const candidates = [
      bag.expoConfig?.hostUri,
      bag.manifest2?.extra?.expoGo?.debuggerHost,
      bag.manifest?.debuggerHost,
    ].filter((item): item is string => Boolean(item && item.trim()));

    for (const raw of candidates) {
      const sanitized = raw.replace(/^https?:\/\//i, "").trim();
      const host = sanitized.split("/")[0]?.split(":")[0]?.trim();
      if (!host) continue;
      if (host === "localhost" || host === "127.0.0.1") continue;
      return `http://${host}:8000`;
    }
    return null;
  }, []);

  const useDetectedLanUrl = React.useCallback(() => {
    const detected = detectLanApiUrl();
    if (!detected) {
      Alert.alert(
        "Could not detect LAN host",
        "Run Expo with --lan and try again, or enter your API URL manually."
      );
      return;
    }
    setDraft((prev) => ({ ...prev, baseUrl: detected }));
    Alert.alert("LAN URL set", detected);
  }, [detectLanApiUrl]);

  const handleSave = () => {
    if (!draft.baseUrl.trim()) {
      Alert.alert("Missing API URL", "Enter an Architect API URL before saving.");
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
          <Text style={styles.screenTitle}>MOBILE CONNECTIVITY</Text>
          <View style={styles.activePill}>
            <Shield size={12} color={COLORS.status.online} />
            <Text style={styles.activeText}>MVP MODE</Text>
          </View>
        </View>

        <Text style={styles.screenSubTitle}>
          Configure how Sage Mobile reaches Architect API over LAN and Tailscale.
        </Text>

        <GlassCard style={styles.card} variant="soft">
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
          <View style={styles.quickFillRow}>
            <GlassButton
              onPress={useDetectedLanUrl}
              title="Use Expo LAN Host"
              variant="ghost"
              disabled={isLoading || isTesting}
              style={styles.quickFillButton}
            />
          </View>

          <Text style={styles.inputLabel}>Tailscale API URL (optional)</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={draft.tailscaleBaseUrl}
              onChangeText={(tailscaleBaseUrl) =>
                setDraft((prev) => ({ ...prev, tailscaleBaseUrl }))
              }
              placeholder="http://mini.tailnet.ts.net:8000"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />
          </View>

          <View style={styles.toggleRow}>
            <View style={styles.toggleTextWrap}>
              <Text style={styles.toggleTitle}>Prefer Tailscale Route</Text>
              <Text style={styles.toggleSub}>
                Try Tailnet first, then fallback to LAN if unreachable.
              </Text>
            </View>
            <Switch
              value={draft.preferTailscale}
              onValueChange={(preferTailscale) =>
                setDraft((prev) => ({ ...prev, preferTailscale }))
              }
              trackColor={{ false: "#2b3853", true: COLORS.accent.primaryStrong }}
              thumbColor="#f4f7ff"
            />
          </View>

          <Text style={styles.inputLabel}>API Token (optional)</Text>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={draft.apiToken}
              onChangeText={(apiToken) => setDraft((prev) => ({ ...prev, apiToken }))}
              placeholder="Bearer token"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
            />
          </View>
          <Text style={styles.helperText}>Stored in secure device storage when available.</Text>

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

          <Text style={styles.inputLabel}>Google Workspace</Text>
          <View style={styles.googleStatusBox}>
            <Text style={styles.googleStatusTitle}>Status: {googleStateLabel}</Text>
            <Text style={styles.googleStatusLine}>
              Redirect: {googleStatus?.redirect_uri || "not configured"}
            </Text>
            <Text style={styles.googleStatusLine}>
              Connected at: {googleStatus?.connected_at || "n/a"}
            </Text>
          </View>
          <View style={styles.actionsRow}>
            <GlassButton
              onPress={() => {
                void onRefreshGoogleStatus();
              }}
              title={googleLoading ? "Refreshing..." : "Refresh Status"}
              variant="secondary"
              disabled={googleLoading || isLoading || isTesting}
              style={styles.actionButton}
            />
            <GlassButton
              onPress={() => {
                void onConnectGoogle();
              }}
              title={googleConnecting ? "Opening..." : "Connect"}
              variant="ghost"
              disabled={googleConnecting || isLoading || isTesting}
              style={styles.actionButton}
            />
            <GlassButton
              onPress={() => {
                void onDisconnectGoogle();
              }}
              title="Disconnect"
              variant="ghost"
              disabled={googleLoading || isLoading || isTesting}
              style={styles.actionButton}
            />
          </View>
        </GlassCard>

        <GlassCard style={styles.card} variant="soft">
          <View style={styles.sectionTitleRow}>
            <Webhook size={16} color={COLORS.text.secondary} />
            <Text style={styles.sectionTitle}>Webhooks</Text>
            <Pressable onPress={onRefreshWebhooks} disabled={webhooksLoading}>
              <Text style={styles.refreshLink}>
                {webhooksLoading ? "Loading..." : "Refresh"}
              </Text>
            </Pressable>
          </View>
          {webhooks.length === 0 ? (
            <Text style={styles.emptyHint}>
              No webhooks registered. Use the API to register webhooks.
            </Text>
          ) : (
            webhooks.map((hook) => (
              <View key={hook.id} style={styles.listItem}>
                <View style={styles.listItemLeft}>
                  <Text style={styles.listItemTitle}>{hook.name}</Text>
                  <Text style={styles.listItemMeta}>
                    {hook.source} · {hook.action.type} · {hook.trigger_count} triggers
                    {hook.has_secret ? " · secret" : ""}
                  </Text>
                </View>
                <Pressable
                  onPress={() => {
                    Alert.alert("Delete webhook?", `Remove "${hook.name}"?`, [
                      { text: "Cancel", style: "cancel" },
                      { text: "Delete", style: "destructive", onPress: () => onDeleteWebhook(hook.id) },
                    ]);
                  }}
                >
                  <Trash2 size={16} color={COLORS.accent.error} />
                </Pressable>
              </View>
            ))
          )}
        </GlassCard>

        <VaultSection
          vaultKeys={vaultKeys}
          vaultLoading={vaultLoading}
          onRefresh={onRefreshVault}
          onStore={onStoreVaultKey}
          onDelete={onDeleteVaultKey}
          disabled={isLoading || isTesting}
        />
      </ScrollView>
    </ScreenLayout>
  );
}

function VaultSection({
  vaultKeys,
  vaultLoading,
  onRefresh,
  onStore,
  onDelete,
  disabled,
}: {
  vaultKeys: string[];
  vaultLoading: boolean;
  onRefresh: () => void;
  onStore: (name: string, value: string) => void;
  onDelete: (name: string) => void;
  disabled: boolean;
}) {
  const [adding, setAdding] = React.useState(false);
  const [newName, setNewName] = React.useState("");
  const [newValue, setNewValue] = React.useState("");

  const handleAdd = () => {
    if (!newName.trim() || !newValue.trim()) return;
    onStore(newName.trim(), newValue.trim());
    setNewName("");
    setNewValue("");
    setAdding(false);
  };

  return (
    <GlassCard style={styles.card} variant="soft">
      <View style={styles.sectionTitleRow}>
        <Key size={16} color={COLORS.text.secondary} />
        <Text style={styles.sectionTitle}>Credential Vault</Text>
        <Pressable onPress={onRefresh} disabled={vaultLoading}>
          <Text style={styles.refreshLink}>
            {vaultLoading ? "Loading..." : "Refresh"}
          </Text>
        </Pressable>
      </View>
      {vaultKeys.length === 0 ? (
        <Text style={styles.emptyHint}>No credentials stored.</Text>
      ) : (
        vaultKeys.map((keyName) => (
          <View key={keyName} style={styles.listItem}>
            <View style={styles.listItemLeft}>
              <Text style={styles.listItemTitle}>{keyName}</Text>
              <Text style={styles.listItemMeta}>encrypted</Text>
            </View>
            <Pressable
              onPress={() => {
                Alert.alert("Delete credential?", `Remove "${keyName}"?`, [
                  { text: "Cancel", style: "cancel" },
                  { text: "Delete", style: "destructive", onPress: () => onDelete(keyName) },
                ]);
              }}
            >
              <Trash2 size={16} color={COLORS.accent.error} />
            </Pressable>
          </View>
        ))
      )}
      {adding ? (
        <View style={styles.addForm}>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={newName}
              onChangeText={setNewName}
              placeholder="Credential name"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
            />
          </View>
          <View style={styles.inputWrap}>
            <TextInput
              style={styles.input}
              value={newValue}
              onChangeText={setNewValue}
              placeholder="Value"
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="none"
              secureTextEntry
            />
          </View>
          <View style={styles.actionsRow}>
            <GlassButton
              onPress={() => setAdding(false)}
              title="Cancel"
              variant="ghost"
              style={styles.actionButton}
            />
            <GlassButton
              onPress={handleAdd}
              title="Store"
              variant="primary"
              disabled={disabled || !newName.trim() || !newValue.trim()}
              style={styles.actionButton}
            />
          </View>
        </View>
      ) : (
        <GlassButton
          onPress={() => setAdding(true)}
          title="Add Credential"
          variant="secondary"
          disabled={disabled}
          style={styles.addButton}
        />
      )}
    </GlassCard>
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
  activeText: {
    color: COLORS.status.online,
    fontSize: 11,
    letterSpacing: 0.8,
    fontWeight: "700",
  },
  card: {
    marginBottom: SPACING.m,
  },
  inputLabel: {
    color: COLORS.text.secondary,
    fontSize: 12,
    marginBottom: SPACING.xs,
    marginTop: SPACING.s,
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
    marginTop: SPACING.m,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  toggleTextWrap: {
    flex: 1,
  },
  toggleTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 2,
  },
  toggleSub: {
    color: COLORS.text.secondary,
    fontSize: 12,
    lineHeight: 17,
  },
  helperText: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    marginTop: SPACING.xs,
  },
  quickFillRow: {
    marginTop: SPACING.xs,
  },
  quickFillButton: {
    minHeight: 42,
  },
  actionsRow: {
    flexDirection: "row",
    gap: SPACING.s,
    marginTop: SPACING.l,
  },
  actionButton: {
    flex: 1,
  },
  googleStatusBox: {
    marginTop: SPACING.s,
    padding: SPACING.m,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(8, 20, 43, 0.78)",
    gap: SPACING.xs,
  },
  googleStatusTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "600",
  },
  googleStatusLine: {
    color: COLORS.text.secondary,
    fontSize: 12,
    lineHeight: 17,
  },
  sectionTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    marginBottom: SPACING.s,
  },
  sectionTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
    flex: 1,
  },
  refreshLink: {
    color: COLORS.accent.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  emptyHint: {
    color: COLORS.text.tertiary,
    fontSize: 12,
    marginTop: SPACING.xs,
  },
  listItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: SPACING.s,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  listItemLeft: {
    flex: 1,
  },
  listItemTitle: {
    color: COLORS.text.primary,
    fontSize: 13,
    fontWeight: "600",
  },
  listItemMeta: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    marginTop: 2,
  },
  addForm: {
    marginTop: SPACING.s,
    gap: SPACING.s,
  },
  addButton: {
    marginTop: SPACING.s,
    minHeight: 44,
  },
});
