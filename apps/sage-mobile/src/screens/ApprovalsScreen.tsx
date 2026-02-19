import React from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import {
  AlertTriangle,
  BadgeDollarSign,
  CheckCircle2,
  CircleDot,
  ShieldAlert,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassButton } from "../components/ui/GlassButton";
import { GlassCard } from "../components/ui/GlassCard";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { ApprovalRecord, ApprovalRisk } from "../types/approvals";

interface ApprovalsScreenProps {
  approvals: ApprovalRecord[];
  isLoading: boolean;
  isRefreshing: boolean;
  onRefresh: () => void;
  onApprove: (id: string, reason?: string) => void;
  onDeny: (id: string, reason?: string) => void;
}

const RISK_THEME: Record<ApprovalRisk, { color: string; label: string }> = {
  low: { color: COLORS.status.online, label: "LOW" },
  medium: { color: COLORS.status.attention, label: "MEDIUM" },
  high: { color: COLORS.status.critical, label: "HIGH" },
  critical: { color: COLORS.status.attention, label: "CRITICAL" },
};

function metadataText(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function metadataNumber(value: unknown, fallback: number): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function renderApprovalCard(
  item: ApprovalRecord,
  onApprove: (id: string, reason?: string) => void,
  onDeny: (id: string, reason?: string) => void
) {
  const risk = RISK_THEME[item.risk];
  const totalCost = metadataNumber(item.metadata.estimated_cost_usd, 6.4);
  const resource = metadataText(item.metadata.resource, item.source.toUpperCase());
  const strategy = metadataText(
    item.metadata.alternative_strategy,
    "Run locally on reserve cluster. Estimated delay: +45m."
  );

  return (
    <GlassCard key={item.id} style={styles.approvalCard} variant="soft">
      <View style={[styles.alertBorder, { backgroundColor: `${risk.color}66` }]} />

      <View style={styles.cardHeader}>
        <View style={styles.headerLeft}>
          <ShieldAlert size={18} color={risk.color} />
          <Text style={[styles.kicker, { color: risk.color }]}>REQUIRES ATTENTION</Text>
        </View>
        <Text style={[styles.riskPill, { borderColor: `${risk.color}66`, color: risk.color }]}>
          {risk.label}
        </Text>
      </View>

      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.subtitle}>{item.summary}</Text>

      <GlassCard style={styles.fullWidthStat} variant="outline">
        <View>
          <Text style={styles.statLabel}>TOTAL COST</Text>
          <Text style={styles.statBig}>
            ${totalCost.toFixed(2)} <Text style={styles.statSuffix}>USD</Text>
          </Text>
        </View>
        <View style={styles.iconBadge}>
          <BadgeDollarSign size={20} color={COLORS.text.secondary} />
        </View>
      </GlassCard>

      <View style={styles.gridRow}>
        <GlassCard style={styles.smallStat} variant="outline">
          <Text style={styles.statLabel}>RISK LEVEL</Text>
          <View style={styles.inlineRow}>
            <CircleDot size={12} color={risk.color} fill={risk.color} />
            <Text style={styles.statText}>{item.risk.toUpperCase()}</Text>
          </View>
        </GlassCard>

        <GlassCard style={styles.smallStat} variant="outline">
          <Text style={styles.statLabel}>RESOURCE</Text>
          <Text style={styles.statText}>{resource}</Text>
        </GlassCard>
      </View>

      <View style={styles.noteBox}>
        <Text style={styles.noteLabel}>ALTERNATIVE STRATEGY</Text>
        <Text style={styles.noteText}>{strategy}</Text>
      </View>

      <GlassButton onPress={() => onApprove(item.id)} variant="primary" style={styles.primaryAction}>
        <View style={styles.primaryActionContent}>
          <View>
            <Text style={styles.primaryActionTitle}>Approve</Text>
            <Text style={styles.primaryActionSubtitle}>Authorize ${totalCost.toFixed(2)}</Text>
          </View>
          <View style={styles.actionIconWrap}>
            <CheckCircle2 size={20} color={COLORS.text.primary} />
          </View>
        </View>
      </GlassButton>

      <View style={styles.secondaryActions}>
        <GlassButton onPress={() => onDeny(item.id, "modify_requested")} variant="secondary" style={styles.secondaryAction}>
          <Text style={styles.secondaryActionText}>Modify</Text>
        </GlassButton>
        <GlassButton onPress={() => onDeny(item.id)} variant="danger" style={styles.secondaryAction}>
          <Text style={styles.denyActionText}>Deny</Text>
        </GlassButton>
      </View>
    </GlassCard>
  );
}

export function ApprovalsScreen({
  approvals,
  isLoading,
  isRefreshing,
  onRefresh,
  onApprove,
  onDeny,
}: ApprovalsScreenProps) {
  return (
    <ScreenLayout>
      <FlatList
        data={approvals}
        keyExtractor={(item) => item.id}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={onRefresh}
            tintColor={COLORS.text.secondary}
          />
        }
        ListHeaderComponent={
          <View style={styles.topArea}>
            <View style={styles.headerRow}>
              <Text style={styles.screenTitle}>Inbox ({approvals.length})</Text>
              <View style={styles.onlinePill}>
                <View style={styles.onlinePillDot} />
                <Text style={styles.onlinePillText}>SYSTEM: ONLINE</Text>
              </View>
            </View>
          </View>
        }
        renderItem={({ item }) => renderApprovalCard(item, onApprove, onDeny)}
        ListEmptyComponent={
          !isLoading ? (
            <GlassCard style={styles.emptyState} variant="outline">
              <AlertTriangle size={20} color={COLORS.text.secondary} />
              <Text style={styles.emptyTitle}>No pending approvals</Text>
              <Text style={styles.emptySubtitle}>Incoming deployment and budget requests will appear here.</Text>
            </GlassCard>
          ) : null
        }
      />
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  listContent: {
    paddingBottom: LAYOUT.tabBarHeight + 70,
  },
  topArea: {
    marginTop: SPACING.s,
    marginBottom: SPACING.m,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  screenTitle: {
    color: COLORS.text.primary,
    fontSize: 20,
    fontWeight: "700",
  },
  onlinePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(20, 38, 73, 0.9)",
  },
  onlinePillDot: {
    width: 10,
    height: 10,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.status.online,
  },
  onlinePillText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    letterSpacing: 0.9,
    fontWeight: "700",
  },
  approvalCard: {
    marginBottom: SPACING.l,
    overflow: "hidden",
    position: "relative",
    paddingTop: SPACING.l,
  },
  alertBorder: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: 3,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: SPACING.s,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  kicker: {
    fontSize: 12,
    letterSpacing: 1.8,
    fontWeight: "800",
  },
  riskPill: {
    borderWidth: 1,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.s + 2,
    paddingVertical: SPACING.xs,
    fontSize: 12,
    letterSpacing: 1,
    fontWeight: "700",
  },
  title: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: SPACING.xs,
  },
  subtitle: {
    color: COLORS.text.secondary,
    fontSize: 15,
    lineHeight: 21,
    marginBottom: SPACING.m,
  },
  fullWidthStat: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: SPACING.m,
  },
  statLabel: {
    color: COLORS.text.tertiary,
    fontSize: 12,
    letterSpacing: 1.6,
    marginBottom: SPACING.xs,
    fontWeight: "700",
  },
  statBig: {
    color: COLORS.text.primary,
    fontSize: 18,
    fontWeight: "700",
  },
  statSuffix: {
    color: COLORS.text.secondary,
    fontSize: 14,
    fontWeight: "500",
  },
  iconBadge: {
    width: 56,
    height: 56,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(18, 31, 56, 0.9)",
    borderWidth: 1,
    borderColor: COLORS.line,
    alignItems: "center",
    justifyContent: "center",
  },
  gridRow: {
    flexDirection: "row",
    gap: SPACING.s,
    marginBottom: SPACING.m,
  },
  smallStat: {
    flex: 1,
    minHeight: 108,
    justifyContent: "center",
  },
  inlineRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  statText: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
  noteBox: {
    borderLeftWidth: 2,
    borderLeftColor: "rgba(125, 152, 198, 0.5)",
    paddingLeft: SPACING.m,
    marginBottom: SPACING.m,
  },
  noteLabel: {
    color: COLORS.text.secondary,
    fontSize: 12,
    letterSpacing: 1.2,
    fontWeight: "700",
    marginBottom: SPACING.xs,
  },
  noteText: {
    color: COLORS.text.secondary,
    fontSize: 16,
    lineHeight: 22,
  },
  primaryAction: {
    marginBottom: SPACING.s,
  },
  primaryActionContent: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  primaryActionTitle: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "700",
  },
  primaryActionSubtitle: {
    color: "rgba(226, 236, 255, 0.85)",
    fontSize: 12,
    marginTop: 2,
  },
  actionIconWrap: {
    width: 40,
    height: 40,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(180, 208, 255, 0.26)",
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryActions: {
    flexDirection: "row",
    gap: SPACING.s,
  },
  secondaryAction: {
    flex: 1,
    minHeight: 54,
  },
  secondaryActionText: {
    color: COLORS.text.secondary,
    fontSize: 15,
    fontWeight: "600",
  },
  denyActionText: {
    color: COLORS.accent.error,
    fontSize: 15,
    fontWeight: "600",
  },
  emptyState: {
    marginTop: SPACING.xxl,
    alignItems: "center",
    gap: SPACING.s,
  },
  emptyTitle: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
  emptySubtitle: {
    color: COLORS.text.secondary,
    fontSize: 13,
    textAlign: "center",
  },
});
