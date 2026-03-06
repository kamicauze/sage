import React from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
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
import { VisionLatestResponse } from "../types/vision";
import { TabName } from "../components/navigation/TabBar";

interface NodeItem {
  name: string;
  detail: string;
  icon: React.ComponentType<{ size?: number; color?: string }>;
  state: "online" | "active" | "sleep" | "offline" | "spend";
  rightText?: string;
  rightSubText?: string;
}

interface DashboardScreenProps {
  brainOnline: boolean;
  mqttOnline: boolean;
  apiStatus: string;
  lastModel: string | null;
  lastLatencyMs: number | null;
  vision: VisionLatestResponse | null;
  onRefreshVision: () => void;
  isVisionRefreshing: boolean;
  onNavigate: (tab: TabName) => void;
  approvalCount: number;
}

function getStatusColor(state: NodeItem["state"]) {
  switch (state) {
    case "online":
      return COLORS.status.online;
    case "active":
      return COLORS.accent.primary;
    case "sleep":
      return COLORS.status.offline;
    case "offline":
      return COLORS.status.critical;
    case "spend":
      return COLORS.status.online;
    default:
      return COLORS.status.offline;
  }
}

export function DashboardScreen({
  brainOnline,
  mqttOnline,
  apiStatus,
  lastModel,
  lastLatencyMs,
  vision,
  onRefreshVision,
  isVisionRefreshing,
  onNavigate,
  approvalCount,
}: DashboardScreenProps) {
  const nodes: NodeItem[] = [
    {
      name: "Mac Mini Brain",
      detail: brainOnline ? "Online" : "Unavailable",
      icon: Server,
      state: brainOnline ? "online" : "offline",
    },
    {
      name: "MQTT Event Bus",
      detail: mqttOnline ? "Connected" : "Broker unreachable",
      icon: Cloud,
      state: mqttOnline ? "active" : "offline",
    },
    {
      name: "4070 Ti Worker",
      detail: "Waiting for distributed link",
      icon: Monitor,
      state: "sleep",
    },
    {
      name: "Jetson Edge",
      detail: "Waiting for distributed link",
      icon: Cpu,
      state: "sleep",
    },
  ];
  const activeCount = nodes.filter((node) => node.state === "online" || node.state === "active").length;
  const apiHealthy = apiStatus === "healthy";
  const frameUri = React.useMemo(() => {
    if (!vision?.frame_available || !vision?.image_base64) {
      return null;
    }
    const mime = vision.mime_type || "image/jpeg";
    return `data:${mime};base64,${vision.image_base64}`;
  }, [vision]);
  const staleLabel =
    typeof vision?.stale_seconds === "number"
      ? `${Math.round(vision.stale_seconds)}s ago`
      : "No timestamp";

  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.topBar}>
          <Pressable style={styles.iconButton} onPress={() => onNavigate("settings")}>
            <Menu size={22} color={COLORS.text.secondary} />
          </Pressable>
          <Pressable style={styles.iconButton} onPress={() => onNavigate("approvals")}>
            <Bell size={20} color={COLORS.text.secondary} />
            {approvalCount > 0 && <View style={styles.notificationDot} />}
          </Pressable>
        </View>

        <View style={styles.hero}>
          <View
            style={[
              styles.statusOrb,
              { backgroundColor: apiHealthy ? COLORS.status.online : COLORS.status.critical },
            ]}
          />
          <Text style={styles.heroTitle}>{apiHealthy ? "Sage: Ready" : "Sage: Degraded"}</Text>
          <Text style={styles.heroSubtitle}>
            {lastModel
              ? `${lastModel}${lastLatencyMs ? ` • ${lastLatencyMs}ms` : ""}`
              : "No recent model response"}
          </Text>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>VISION</Text>
          <Pressable onPress={onRefreshVision} disabled={isVisionRefreshing}>
            <Text style={styles.sectionAction}>
              {isVisionRefreshing ? "Refreshing..." : "Scan now"}
            </Text>
          </Pressable>
        </View>

        <GlassCard style={styles.visionCard} variant="soft">
          <View style={styles.visionHeader}>
            <Text style={styles.visionTitle}>
              {vision?.location ? `Camera: ${vision.location}` : "Camera feed"}
            </Text>
            <Text style={styles.visionMeta}>{staleLabel}</Text>
          </View>
          {frameUri ? (
            <Image source={{ uri: frameUri }} style={styles.visionImage} resizeMode="cover" />
          ) : (
            <View style={styles.visionPlaceholder}>
              <Text style={styles.visionPlaceholderText}>
                No frame yet. Enable `VISION_PUBLISH_FRAMES=1` on Jetson.
              </Text>
            </View>
          )}
          <Text style={styles.visionSummary}>
            {vision?.scene_description || "Waiting for scene description..."}
          </Text>
          <View style={styles.visionStatsRow}>
            <Text style={styles.visionStat}>People: {vision?.people_count ?? 0}</Text>
            <Text style={styles.visionStat}>Activity: {vision?.activity || "unknown"}</Text>
            <Text style={styles.visionStat}>Mood: {vision?.mood || "unknown"}</Text>
          </View>
          <Text style={styles.visionObjects}>
            Objects: {vision?.objects?.length ? vision.objects.slice(0, 6).join(", ") : "none"}
          </Text>
        </GlassCard>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionLabel}>NODES</Text>
          <Text style={styles.sectionMeta}>{activeCount}/4 Active</Text>
        </View>

        {nodes.map((node) => {
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
          onPress={() => onNavigate("control")}
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
  sectionAction: {
    color: COLORS.accent.primary,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  visionCard: {
    marginBottom: SPACING.l,
    borderRadius: RADIUS.l,
  },
  visionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: SPACING.s,
  },
  visionTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
  },
  visionMeta: {
    color: COLORS.text.secondary,
    fontSize: 11,
  },
  visionImage: {
    width: "100%",
    aspectRatio: 16 / 9,
    borderRadius: RADIUS.m,
    backgroundColor: "rgba(9, 18, 38, 0.6)",
    marginBottom: SPACING.s,
  },
  visionPlaceholder: {
    width: "100%",
    aspectRatio: 16 / 9,
    borderRadius: RADIUS.m,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(9, 18, 38, 0.55)",
    borderWidth: 1,
    borderColor: "rgba(56, 88, 145, 0.4)",
    marginBottom: SPACING.s,
    paddingHorizontal: SPACING.m,
  },
  visionPlaceholderText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    textAlign: "center",
    lineHeight: 18,
  },
  visionSummary: {
    color: COLORS.text.primary,
    fontSize: 13,
    lineHeight: 19,
    marginBottom: SPACING.s,
  },
  visionStatsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.m,
    marginBottom: SPACING.xs,
  },
  visionStat: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  visionObjects: {
    color: COLORS.text.secondary,
    fontSize: 12,
    lineHeight: 18,
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
