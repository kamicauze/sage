import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import {
  Bell,
  ChevronRight,
  Cloud,
  Cpu,
  Menu,
  Monitor,
  Server,
  Zap,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";

interface NodeItem {
  name: string;
  detail: string;
  icon: React.ComponentType<{ size?: number; color?: string }>;
  state: "online" | "active" | "sleep" | "spend";
  rightText?: string;
  rightSubText?: string;
}

const NODES: NodeItem[] = [
  {
    name: "Mini",
    detail: "Online",
    icon: Server,
    state: "online",
  },
  {
    name: "Jetson",
    detail: "Summarizing...",
    icon: Cpu,
    state: "active",
  },
  {
    name: "Workstation",
    detail: "Sleeping",
    icon: Monitor,
    state: "sleep",
  },
  {
    name: "Cloud Cluster",
    detail: "us-east-1",
    icon: Cloud,
    state: "spend",
    rightText: "$4.20",
    rightSubText: "DAILY SPEND",
  },
];

function getStatusColor(state: NodeItem["state"]) {
  switch (state) {
    case "online":
      return COLORS.status.online;
    case "active":
      return COLORS.accent.primary;
    case "sleep":
      return COLORS.status.offline;
    case "spend":
      return COLORS.status.online;
    default:
      return COLORS.status.offline;
  }
}

export function DashboardScreen() {
  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.topBar}>
          <Pressable style={styles.iconButton}>
            <Menu size={22} color={COLORS.text.secondary} />
          </Pressable>
          <Pressable style={styles.iconButton}>
            <Bell size={20} color={COLORS.text.secondary} />
            <View style={styles.notificationDot} />
          </Pressable>
        </View>

        <View style={styles.hero}>
          <View style={styles.statusOrb} />
          <Text style={styles.heroTitle}>Sage: Idle</Text>
          <Text style={styles.heroSubtitle}>ALL SYSTEMS NOMINAL</Text>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>NODES</Text>
          <Text style={styles.sectionMeta}>4 Active</Text>
        </View>

        {NODES.map((node) => {
          const Icon = node.icon;
          const stateColor = getStatusColor(node.state);

          return (
            <GlassCard key={node.name} style={styles.nodeCard} variant="soft">
              <View style={styles.nodeLeft}>
                <View style={styles.nodeIconWrap}>
                  <Icon size={20} color={COLORS.text.secondary} />
                </View>
                <View style={styles.nodeTextWrap}>
                  <Text style={styles.nodeName}>{node.name}</Text>
                  <Text
                    style={[
                      styles.nodeDetail,
                      node.state === "online" && styles.onlineDetail,
                      node.state === "active" && styles.activeDetail,
                    ]}
                  >
                    {node.detail}
                  </Text>
                </View>
              </View>

              <View style={styles.nodeRight}>
                {node.rightText ? (
                  <>
                    <Text style={styles.nodeAmount}>{node.rightText}</Text>
                    <Text style={styles.nodeAmountSub}>{node.rightSubText}</Text>
                  </>
                ) : (
                  <>
                    <View style={[styles.stateDot, { backgroundColor: stateColor }]} />
                    <ChevronRight size={18} color={COLORS.text.tertiary} />
                  </>
                )}
              </View>
            </GlassCard>
          );
        })}

        <GlassButton
          onPress={() => undefined}
          variant="secondary"
          style={styles.diagnosticsButton}
        >
          <View style={styles.diagnosticsContent}>
            <Zap size={18} color={COLORS.text.secondary} />
            <Text style={styles.diagnosticsText}>System Diagnostics</Text>
          </View>
        </GlassButton>
      </ScrollView>
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: LAYOUT.tabBarHeight + 70,
  },
  topBar: {
    marginTop: SPACING.s,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  iconButton: {
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
  },
  notificationDot: {
    position: "absolute",
    top: 4,
    right: 5,
    width: 8,
    height: 8,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.accent.primary,
  },
  hero: {
    marginTop: SPACING.xxl,
    alignItems: "center",
    marginBottom: SPACING.xl,
  },
  statusOrb: {
    width: 28,
    height: 28,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.status.online,
    shadowColor: COLORS.status.online,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.9,
    shadowRadius: 14,
    elevation: 10,
    marginBottom: SPACING.l,
  },
  heroTitle: {
    fontSize: 26,
    fontWeight: "300",
    color: COLORS.text.primary,
    letterSpacing: -0.8,
  },
  heroSubtitle: {
    marginTop: SPACING.s,
    fontSize: 12,
    color: COLORS.text.secondary,
    letterSpacing: 0.9,
    fontWeight: "700",
  },
  sectionHeader: {
    marginBottom: SPACING.m,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionLabel: {
    color: COLORS.text.secondary,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 2.2,
  },
  sectionMeta: {
    color: COLORS.text.secondary,
    fontSize: 14,
    letterSpacing: 0.8,
  },
  nodeCard: {
    marginBottom: SPACING.m,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 108,
    borderRadius: RADIUS.l,
  },
  nodeLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  nodeIconWrap: {
    width: 56,
    height: 56,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(34, 58, 97, 0.35)",
    alignItems: "center",
    justifyContent: "center",
    marginRight: SPACING.m,
  },
  nodeTextWrap: {
    flex: 1,
  },
  nodeName: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 2,
  },
  nodeDetail: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  onlineDetail: {
    color: COLORS.status.online,
  },
  activeDetail: {
    color: COLORS.accent.primary,
  },
  nodeRight: {
    minWidth: 90,
    alignItems: "flex-end",
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: SPACING.s,
  },
  stateDot: {
    width: 18,
    height: 18,
    borderRadius: RADIUS.full,
  },
  nodeAmount: {
    color: COLORS.text.primary,
    fontSize: 18,
    fontWeight: "700",
  },
  nodeAmountSub: {
    color: COLORS.text.secondary,
    fontSize: 8,
    letterSpacing: 1,
  },
  diagnosticsButton: {
    width: "72%",
    alignSelf: "center",
    marginTop: SPACING.l,
    borderRadius: RADIUS.full,
  },
  diagnosticsContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  diagnosticsText: {
    color: COLORS.text.secondary,
    fontSize: 18,
    fontWeight: "600",
  },
});
