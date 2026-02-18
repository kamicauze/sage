
import React from "react";
import { StyleSheet, View, Text, FlatList, Pressable } from "react-native";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { COLORS, SPACING, RADIUS } from "../constants/theme";
import { ApprovalRecord, ApprovalRisk } from "../types/approvals";
import { AlertCircle, Check, X } from "lucide-react-native";

interface ApprovalsScreenProps {
    approvals: ApprovalRecord[];
    isLoading: boolean;
    isRefreshing: boolean;
    onRefresh: () => void;
    onApprove: (id: string, reason?: string) => void;
    onDeny: (id: string, reason?: string) => void;
}

const RISK_COLORS: Record<ApprovalRisk, string> = {
    low: COLORS.accent.success,
    medium: COLORS.accent.warning,
    high: COLORS.accent.error,
    critical: "#8e24aa",
};

export function ApprovalsScreen({
    approvals,
    isLoading,
    isRefreshing,
    onRefresh,
    onApprove,
    onDeny,
}: ApprovalsScreenProps) {
    const [selectedId, setSelectedId] = React.useState<string | null>(null);

    const renderItem = ({ item }: { item: ApprovalRecord }) => {
        const isExpanded = selectedId === item.id;

        return (
            <GlassCard style={styles.card}>
                <Pressable onPress={() => setSelectedId(isExpanded ? null : item.id)}>
                    <View style={styles.header}>
                        <View style={styles.titleRow}>
                            <AlertCircle size={20} color={RISK_COLORS[item.risk]} />
                            <Text style={styles.title}>{item.title}</Text>
                        </View>
                        <View
                            style={[
                                styles.badge,
                                { backgroundColor: RISK_COLORS[item.risk] + "40" },
                            ]}
                        >
                            <Text
                                style={[styles.badgeText, { color: RISK_COLORS[item.risk] }]}
                            >
                                {item.risk.toUpperCase()}
                            </Text>
                        </View>
                    </View>
                    <Text style={styles.summary} numberOfLines={isExpanded ? undefined : 2}>
                        {item.summary}
                    </Text>
                    {isExpanded && (
                        <View style={styles.actions}>
                            <GlassButton
                                title="Deny"
                                onPress={() => onDeny(item.id)}
                                variant="danger"
                                style={styles.actionBtn}
                            />
                            <GlassButton
                                title="Approve"
                                onPress={() => onApprove(item.id)}
                                variant="primary"
                                style={styles.actionBtn}
                            />
                        </View>
                    )}
                </Pressable>
            </GlassCard>
        );
    };

    return (
        <ScreenLayout>
            <View style={styles.headerContainer}>
                <Text style={styles.screenTitle}>Pending Approvals</Text>
            </View>
            <FlatList
                data={approvals}
                renderItem={renderItem}
                keyExtractor={(item) => item.id}
                contentContainerStyle={styles.list}
                refreshing={isRefreshing}
                onRefresh={onRefresh}
                ListEmptyComponent={
                    !isLoading ? (
                        <View style={styles.empty}>
                            <Text style={styles.emptyText}>No pending approvals</Text>
                        </View>
                    ) : null
                }
            />
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
    list: {
        paddingBottom: 100,
        gap: SPACING.m,
    },
    card: {
        marginBottom: SPACING.s,
    },
    header: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: SPACING.s,
    },
    titleRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: SPACING.s,
        flex: 1,
    },
    title: {
        fontSize: 16,
        fontWeight: "600",
        color: COLORS.text.primary,
        flexShrink: 1,
    },
    badge: {
        paddingHorizontal: SPACING.s,
        paddingVertical: 2,
        borderRadius: RADIUS.full,
    },
    badgeText: {
        fontSize: 10,
        fontWeight: "bold",
    },
    summary: {
        fontSize: 14,
        color: COLORS.text.secondary,
        lineHeight: 20,
    },
    actions: {
        flexDirection: "row",
        gap: SPACING.m,
        marginTop: SPACING.m,
    },
    actionBtn: {
        flex: 1,
    },
    empty: {
        alignItems: "center",
        marginTop: SPACING.xl,
    },
    emptyText: {
        color: COLORS.text.secondary,
    },
});
