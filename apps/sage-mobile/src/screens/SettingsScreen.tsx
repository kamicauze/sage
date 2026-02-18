
import React from "react";
import { StyleSheet, Text, View, TextInput, ScrollView, Alert } from "react-native";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { COLORS, SPACING, RADIUS } from "../constants/theme";
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

    const handleSave = () => {
        if (!draft.baseUrl) {
            Alert.alert("Error", "Base URL is required");
            return;
        }
        onSave(draft);
    };

    return (
        <ScreenLayout>
            <View style={styles.headerContainer}>
                <Text style={styles.screenTitle}>Settings</Text>
            </View>

            <ScrollView contentContainerStyle={styles.scroll}>
                <GlassCard style={styles.card}>
                    <Text style={styles.label}>Architect API URL</Text>
                    <GlassCard intensity={10} tint="light" style={styles.inputContainer}>
                        <TextInput
                            style={styles.input}
                            value={draft.baseUrl}
                            onChangeText={(text) => setDraft({ ...draft, baseUrl: text })}
                            placeholder="http://192.168.1.40:8000"
                            placeholderTextColor={COLORS.text.tertiary}
                            autoCapitalize="none"
                            autoCorrect={false}
                            keyboardType="url"
                        />
                    </GlassCard>
                    <Text style={styles.helper}>
                        Use LAN IP for real devices. Localhost only works on emulators.
                    </Text>

                    <Text style={styles.label}>API Token (Optional)</Text>
                    <GlassCard intensity={10} tint="light" style={styles.inputContainer}>
                        <TextInput
                            style={styles.input}
                            value={draft.apiToken}
                            onChangeText={(text) => setDraft({ ...draft, apiToken: text })}
                            placeholder="Secret Token"
                            placeholderTextColor={COLORS.text.tertiary}
                            secureTextEntry
                            autoCapitalize="none"
                        />
                    </GlassCard>

                    <Text style={styles.label}>Reviewer Name</Text>
                    <GlassCard intensity={10} tint="light" style={styles.inputContainer}>
                        <TextInput
                            style={styles.input}
                            value={draft.reviewer}
                            onChangeText={(text) => setDraft({ ...draft, reviewer: text })}
                            placeholder="mobile_user"
                            placeholderTextColor={COLORS.text.tertiary}
                            autoCapitalize="none"
                        />
                    </GlassCard>

                    <View style={styles.actions}>
                        <GlassButton
                            title={isTesting ? "Testing..." : "Test Connection"}
                            onPress={() => onTestConnection(draft)}
                            variant="secondary"
                            disabled={isTesting || isLoading}
                            style={styles.actionBtn}
                        />
                        <GlassButton
                            title={isLoading ? "Saving..." : "Save Settings"}
                            onPress={handleSave}
                            variant="primary"
                            disabled={isLoading || isTesting}
                            style={styles.actionBtn}
                        />
                    </View>
                </GlassCard>
            </ScrollView>
        </ScreenLayout>
    );
}

const styles = StyleSheet.create({
    headerContainer: {
        marginTop: SPACING.l,
        marginBottom: SPACING.m,
    },
    screenTitle: {
        fontSize: 24,
        fontWeight: "bold",
        color: COLORS.text.primary,
    },
    scroll: {
        paddingBottom: 100,
    },
    card: {
        gap: SPACING.m,
    },
    label: {
        fontSize: 14,
        fontWeight: "600",
        color: COLORS.text.primary,
        marginBottom: 4,
    },
    inputContainer: {
        padding: 0,
        borderRadius: RADIUS.s,
        backgroundColor: "rgba(0,0,0,0.2)",
        borderWidth: 0,
    },
    input: {
        padding: SPACING.m,
        color: COLORS.text.primary,
        fontSize: 16,
    },
    helper: {
        fontSize: 12,
        color: COLORS.text.secondary,
        marginTop: -8,
        marginBottom: 8,
    },
    actions: {
        flexDirection: "row",
        gap: SPACING.m,
        marginTop: SPACING.s,
    },
    actionBtn: {
        flex: 1,
    },
});
