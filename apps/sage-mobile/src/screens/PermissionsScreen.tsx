import React from "react";
import {
  FlatList,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  RefreshCw,
  Shield,
  ShieldCheck,
  ShieldX,
  FolderOpen,
  History,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { COLORS, LAYOUT, RADIUS, SPACING, TYPO } from "../constants/theme";
import type {
  AgentPermissionsResponse,
  PermissionAuditEntry,
  PermissionProfile,
  PermissionProfileDef,
  ToolPermission,
} from "../types/permissions";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PermissionsScreenProps {
  permissions: AgentPermissionsResponse | null;
  profiles: PermissionProfileDef[];
  audit: PermissionAuditEntry[];
  isLoading: boolean;
  onRefresh: () => void;
  onApplyProfile: (name: PermissionProfile) => void;
  onToggleTool: (
    toolName: string,
    next: "allowed" | "approval" | "denied"
  ) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PROFILE_META: Record<
  PermissionProfile,
  { icon: typeof Shield; color: string }
> = {
  safe: { icon: ShieldCheck, color: COLORS.accent.success },
  standard: { icon: Shield, color: COLORS.accent.primary },
  power: { icon: ShieldX, color: COLORS.accent.warning },
};

function toolStatus(
  tool: ToolPermission
): "allowed" | "approval" | "denied" {
  if (tool.denied) return "denied";
  if (tool.force_approval) return "approval";
  return "allowed";
}

function nextStatus(
  current: "allowed" | "approval" | "denied"
): "allowed" | "approval" | "denied" {
  if (current === "allowed") return "approval";
  if (current === "approval") return "denied";
  return "allowed";
}

const STATUS_CHIP: Record<
  "allowed" | "approval" | "denied",
  { label: string; bg: string; fg: string }
> = {
  allowed: {
    label: "Allowed",
    bg: "rgba(34, 211, 139, 0.15)",
    fg: COLORS.accent.success,
  },
  approval: {
    label: "Approval",
    bg: "rgba(247, 183, 49, 0.15)",
    fg: COLORS.accent.warning,
  },
  denied: {
    label: "Denied",
    bg: "rgba(255, 92, 98, 0.15)",
    fg: COLORS.accent.error,
  },
};

function formatAuditTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PermissionsScreen({
  permissions,
  profiles,
  audit,
  isLoading,
  onRefresh,
  onApplyProfile,
  onToggleTool,
}: PermissionsScreenProps) {
  const activeProfile = permissions?.active_profile ?? null;
  const tools = permissions?.tools ?? [];
  const writeRoots = permissions?.allow_write_roots ?? [];

  return (
    <ScreenLayout>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Agent Permissions</Text>
            <Text style={styles.subtitle}>
              {permissions
                ? `Mode: ${permissions.mode} • ${tools.length} tools`
                : "Loading…"}
            </Text>
          </View>
          <Pressable onPress={onRefresh} disabled={isLoading}>
            <RefreshCw
              size={20}
              color={COLORS.text.secondary}
              style={{ opacity: isLoading ? 0.4 : 1 }}
            />
          </Pressable>
        </View>

        {/* Profile Cards */}
        <Text style={styles.sectionTitle}>PROFILES</Text>
        <View style={styles.profileRow}>
          {(profiles.length > 0
            ? profiles
            : ([
                { name: "safe", label: "Safe", description: "Read-only focus" },
                {
                  name: "standard",
                  label: "Standard",
                  description: "Balanced defaults",
                },
                {
                  name: "power",
                  label: "Power",
                  description: "Most auto-approved",
                },
              ] as PermissionProfileDef[])
          ).map((profile) => {
            const isActive = activeProfile === profile.name;
            const meta = PROFILE_META[profile.name] ?? PROFILE_META.standard;
            const Icon = meta.icon;
            return (
              <Pressable
                key={profile.name}
                style={[
                  styles.profileCard,
                  isActive && {
                    borderColor: meta.color,
                    backgroundColor: `${meta.color}12`,
                  },
                ]}
                onPress={() => onApplyProfile(profile.name)}
              >
                <Icon
                  size={22}
                  color={isActive ? meta.color : COLORS.text.secondary}
                />
                <Text
                  style={[
                    styles.profileLabel,
                    isActive && { color: meta.color },
                  ]}
                >
                  {profile.label}
                </Text>
                <Text style={styles.profileDesc} numberOfLines={2}>
                  {profile.description}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Tools Section */}
        <Text style={styles.sectionTitle}>TOOL PERMISSIONS</Text>
        <GlassCard padded={false}>
          {tools.map((tool, idx) => {
            const status = toolStatus(tool);
            const chip = STATUS_CHIP[status];
            return (
              <Pressable
                key={tool.name}
                style={[
                  styles.toolRow,
                  idx < tools.length - 1 && styles.toolRowBorder,
                ]}
                onPress={() => onToggleTool(tool.name, nextStatus(status))}
              >
                <View style={styles.toolInfo}>
                  <Text style={styles.toolName}>{tool.name}</Text>
                  <Text style={styles.toolDesc} numberOfLines={1}>
                    {tool.description}
                  </Text>
                </View>
                <View style={[styles.statusChip, { backgroundColor: chip.bg }]}>
                  <Text style={[styles.statusChipText, { color: chip.fg }]}>
                    {chip.label}
                  </Text>
                </View>
              </Pressable>
            );
          })}
          {tools.length === 0 && (
            <View style={styles.emptyRow}>
              <Text style={styles.emptyText}>
                {isLoading ? "Loading tools…" : "No tools available"}
              </Text>
            </View>
          )}
        </GlassCard>

        {/* Write Roots */}
        <Text style={styles.sectionTitle}>WRITE DIRECTORIES</Text>
        <GlassCard>
          <View style={styles.chipWrap}>
            {writeRoots.map((root) => (
              <View key={root} style={styles.rootChip}>
                <FolderOpen size={13} color={COLORS.accent.info} />
                <Text style={styles.rootChipText}>{root}</Text>
              </View>
            ))}
            {writeRoots.length === 0 && (
              <Text style={styles.emptyText}>
                {isLoading ? "Loading…" : "No write directories configured"}
              </Text>
            )}
          </View>
        </GlassCard>

        {/* Audit Section */}
        <Text style={styles.sectionTitle}>RECENT CHANGES</Text>
        <GlassCard padded={false}>
          {audit.slice(0, 10).map((entry, idx) => (
            <View
              key={`${entry.timestamp}-${idx}`}
              style={[
                styles.auditRow,
                idx < Math.min(audit.length, 10) - 1 && styles.toolRowBorder,
              ]}
            >
              <History size={14} color={COLORS.text.dim} />
              <View style={styles.auditInfo}>
                <Text style={styles.auditAction}>
                  {entry.action === "apply_profile"
                    ? `Applied ${(entry.changes as Record<string, string>).profile ?? "profile"}`
                    : "Policy updated"}
                </Text>
                <Text style={styles.auditMeta}>
                  {formatAuditTime(entry.timestamp)} • via {entry.source}
                </Text>
              </View>
            </View>
          ))}
          {audit.length === 0 && (
            <View style={styles.emptyRow}>
              <Text style={styles.emptyText}>No changes recorded</Text>
            </View>
          )}
        </GlassCard>

        {/* Bottom spacer for tab bar */}
        <View style={{ height: LAYOUT.tabBarHeight + 20 }} />
      </ScrollView>
    </ScreenLayout>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  scrollContent: { paddingTop: SPACING.xs, gap: SPACING.s },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: SPACING.xs,
  },
  title: {
    fontSize: TYPO.section,
    fontWeight: "800",
    color: COLORS.text.primary,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 13,
    color: COLORS.text.tertiary,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: COLORS.text.dim,
    letterSpacing: 1.2,
    marginTop: SPACING.m,
    marginBottom: SPACING.xs,
  },
  // Profiles
  profileRow: {
    flexDirection: "row",
    gap: SPACING.s,
  },
  profileCard: {
    flex: 1,
    alignItems: "center",
    gap: SPACING.xs,
    paddingVertical: SPACING.m,
    paddingHorizontal: SPACING.xs,
    borderRadius: RADIUS.m,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.panel,
  },
  profileLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: COLORS.text.primary,
  },
  profileDesc: {
    fontSize: 10,
    color: COLORS.text.tertiary,
    textAlign: "center",
    lineHeight: 13,
  },
  // Tools
  toolRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s + 2,
  },
  toolRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: COLORS.line,
  },
  toolInfo: {
    flex: 1,
    marginRight: SPACING.s,
  },
  toolName: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.text.primary,
  },
  toolDesc: {
    fontSize: 11,
    color: COLORS.text.tertiary,
    marginTop: 1,
  },
  statusChip: {
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xxs,
    borderRadius: RADIUS.full,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: "700",
  },
  // Write roots
  chipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
  },
  rootChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xxs + 1,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(76, 147, 255, 0.12)",
    borderWidth: 1,
    borderColor: "rgba(76, 147, 255, 0.25)",
  },
  rootChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: COLORS.accent.info,
  },
  // Audit
  auditRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
  },
  auditInfo: { flex: 1 },
  auditAction: {
    fontSize: 13,
    fontWeight: "600",
    color: COLORS.text.primary,
  },
  auditMeta: {
    fontSize: 11,
    color: COLORS.text.dim,
    marginTop: 1,
  },
  // Empty
  emptyRow: {
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.l,
    alignItems: "center",
  },
  emptyText: {
    fontSize: 13,
    color: COLORS.text.dim,
  },
});
