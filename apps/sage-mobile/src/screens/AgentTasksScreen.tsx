import React from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { AgentTask, AgentTaskObservation, AgentTaskStatus } from "../types/tasks";

interface AgentTasksScreenProps {
  tasks: AgentTask[];
  stats: Record<string, number> | null;
  selectedTask: AgentTask | null;
  selectedObservations: AgentTaskObservation[];
  isLoading: boolean;
  statusFilter: AgentTaskStatus | null;
  onFilterChange: (filter: AgentTaskStatus | null) => void;
  onRefresh: () => void;
  onSelectTask: (taskId: string) => void;
  onDeselectTask: () => void;
}

const STATUS_FILTERS: Array<{ key: AgentTaskStatus | null; label: string }> = [
  { key: null, label: "All" },
  { key: "RUNNING", label: "Running" },
  { key: "QUEUED", label: "Queued" },
  { key: "COMPLETED", label: "Done" },
  { key: "FAILED", label: "Failed" },
];

function statusColor(status: AgentTaskStatus): string {
  switch (status) {
    case "RUNNING":
      return COLORS.accent.primary;
    case "COMPLETED":
      return COLORS.status.online;
    case "FAILED":
      return COLORS.status.critical;
    case "CANCELLED":
      return COLORS.text.tertiary;
    case "QUEUED":
    default:
      return COLORS.status.attention;
  }
}

function StatusIcon({ status, size = 16 }: { status: AgentTaskStatus; size?: number }) {
  const color = statusColor(status);
  switch (status) {
    case "RUNNING":
      return <Loader2 size={size} color={color} />;
    case "COMPLETED":
      return <CheckCircle2 size={size} color={color} />;
    case "FAILED":
    case "CANCELLED":
      return <XCircle size={size} color={color} />;
    case "QUEUED":
    default:
      return <Clock size={size} color={color} />;
  }
}

function formatTimestamp(ts?: number | null): string {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatDuration(start?: number | null, end?: number | null): string {
  if (!start) return "";
  const endTs = end || Date.now() / 1000;
  const seconds = Math.round(endTs - start);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function AgentTasksScreen({
  tasks,
  stats,
  selectedTask,
  selectedObservations,
  isLoading,
  statusFilter,
  onFilterChange,
  onRefresh,
  onSelectTask,
  onDeselectTask,
}: AgentTasksScreenProps) {
  const runningCount = stats?.RUNNING ?? 0;
  const queuedCount = stats?.QUEUED ?? 0;
  const completedCount = stats?.COMPLETED ?? 0;
  const failedCount = stats?.FAILED ?? 0;

  return (
    <ScreenLayout>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <Text style={styles.screenTitle}>AGENT TASKS</Text>
          <Pressable onPress={onRefresh} disabled={isLoading}>
            <RefreshCw
              size={18}
              color={isLoading ? COLORS.text.tertiary : COLORS.accent.primary}
            />
          </Pressable>
        </View>

        <View style={styles.statsRow}>
          <View style={[styles.statBadge, { borderColor: "rgba(47, 107, 255, 0.4)" }]}>
            <Text style={[styles.statCount, { color: COLORS.accent.primary }]}>
              {runningCount}
            </Text>
            <Text style={styles.statLabel}>Running</Text>
          </View>
          <View style={[styles.statBadge, { borderColor: "rgba(255, 196, 57, 0.4)" }]}>
            <Text style={[styles.statCount, { color: COLORS.status.attention }]}>
              {queuedCount}
            </Text>
            <Text style={styles.statLabel}>Queued</Text>
          </View>
          <View style={[styles.statBadge, { borderColor: "rgba(32, 214, 143, 0.4)" }]}>
            <Text style={[styles.statCount, { color: COLORS.status.online }]}>
              {completedCount}
            </Text>
            <Text style={styles.statLabel}>Done</Text>
          </View>
          <View style={[styles.statBadge, { borderColor: "rgba(255, 90, 84, 0.4)" }]}>
            <Text style={[styles.statCount, { color: COLORS.status.critical }]}>
              {failedCount}
            </Text>
            <Text style={styles.statLabel}>Failed</Text>
          </View>
        </View>

        <View style={styles.filterRow}>
          {STATUS_FILTERS.map((filter) => {
            const active = filter.key === statusFilter;
            return (
              <Pressable
                key={filter.label}
                onPress={() => onFilterChange(filter.key)}
                style={[styles.filterChip, active && styles.filterChipActive]}
              >
                <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                  {filter.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {selectedTask && (
          <GlassCard style={styles.detailCard} variant="soft">
            <Pressable onPress={onDeselectTask} style={styles.detailHeaderRow}>
              <View style={styles.detailLeft}>
                <StatusIcon status={selectedTask.status} size={20} />
                <Text style={styles.detailAgent}>{selectedTask.agent_name}</Text>
              </View>
              <ChevronDown size={18} color={COLORS.text.secondary} />
            </Pressable>
            <Text style={styles.detailGoal}>{selectedTask.goal}</Text>
            <View style={styles.detailMeta}>
              <Text style={styles.detailMetaText}>
                Status: {selectedTask.status}
              </Text>
              <Text style={styles.detailMetaText}>
                Created: {formatTimestamp(selectedTask.created_at)}
              </Text>
              {selectedTask.started_at && (
                <Text style={styles.detailMetaText}>
                  Duration: {formatDuration(selectedTask.started_at, selectedTask.completed_at)}
                </Text>
              )}
              {selectedTask.error && (
                <Text style={styles.detailError}>{selectedTask.error}</Text>
              )}
              {selectedTask.result_summary && (
                <Text style={styles.detailResult}>{selectedTask.result_summary}</Text>
              )}
            </View>
            {selectedObservations.length > 0 && (
              <View style={styles.obsSection}>
                <Text style={styles.obsSectionTitle}>
                  Tool calls ({selectedObservations.length})
                </Text>
                {selectedObservations.map((obs, i) => (
                  <View key={obs.id ?? i} style={styles.obsItem}>
                    <Text style={styles.obsToolName}>{obs.tool}</Text>
                    <Text style={styles.obsResult} numberOfLines={3}>
                      {obs.result_text}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </GlassCard>
        )}

        {isLoading && !tasks.length ? (
          <View style={styles.centerWrap}>
            <ActivityIndicator color={COLORS.accent.primary} size="large" />
          </View>
        ) : tasks.length === 0 ? (
          <View style={styles.centerWrap}>
            <Text style={styles.emptyText}>No tasks found</Text>
          </View>
        ) : (
          tasks.map((task) => {
            const isSelected = selectedTask?.id === task.id;
            return (
              <Pressable key={task.id} onPress={() => onSelectTask(task.id)}>
                <GlassCard
                  style={[styles.taskCard, isSelected && styles.taskCardSelected]}
                  variant="soft"
                >
                  <View style={styles.taskRow}>
                    <StatusIcon status={task.status} />
                    <View style={styles.taskTextWrap}>
                      <Text style={styles.taskAgent}>{task.agent_name}</Text>
                      <Text style={styles.taskGoal} numberOfLines={2}>
                        {task.goal}
                      </Text>
                    </View>
                    <View style={styles.taskRight}>
                      <Text style={styles.taskTime}>
                        {formatTimestamp(task.created_at)}
                      </Text>
                      {task.started_at && (
                        <Text style={styles.taskDuration}>
                          {formatDuration(task.started_at, task.completed_at)}
                        </Text>
                      )}
                      <ChevronRight size={14} color={COLORS.text.tertiary} />
                    </View>
                  </View>
                  {task.error && (
                    <Text style={styles.taskError} numberOfLines={1}>
                      {task.error}
                    </Text>
                  )}
                </GlassCard>
              </Pressable>
            );
          })
        )}
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
    marginBottom: SPACING.m,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  screenTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 1.8,
  },
  statsRow: {
    flexDirection: "row",
    gap: SPACING.s,
    marginBottom: SPACING.m,
  },
  statBadge: {
    flex: 1,
    alignItems: "center",
    paddingVertical: SPACING.s,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    backgroundColor: "rgba(8, 20, 43, 0.6)",
  },
  statCount: {
    fontSize: 20,
    fontWeight: "700",
  },
  statLabel: {
    color: COLORS.text.secondary,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
    marginTop: 2,
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
    marginBottom: SPACING.m,
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
  detailCard: {
    marginBottom: SPACING.m,
  },
  detailHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: SPACING.s,
  },
  detailLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  detailAgent: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "700",
  },
  detailGoal: {
    color: COLORS.text.secondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: SPACING.s,
  },
  detailMeta: {
    gap: SPACING.xxs,
  },
  detailMetaText: {
    color: COLORS.text.tertiary,
    fontSize: 12,
  },
  detailError: {
    color: COLORS.accent.error,
    fontSize: 12,
    marginTop: SPACING.xs,
  },
  detailResult: {
    color: COLORS.status.online,
    fontSize: 12,
    marginTop: SPACING.xs,
  },
  obsSection: {
    marginTop: SPACING.m,
    paddingTop: SPACING.s,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  obsSectionTitle: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.5,
    marginBottom: SPACING.s,
  },
  obsItem: {
    marginBottom: SPACING.s,
    paddingLeft: SPACING.s,
    borderLeftWidth: 2,
    borderLeftColor: "rgba(47, 107, 255, 0.3)",
  },
  obsToolName: {
    color: COLORS.accent.info,
    fontSize: 12,
    fontWeight: "700",
    marginBottom: 2,
  },
  obsResult: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    lineHeight: 16,
  },
  centerWrap: {
    marginTop: SPACING.xxl * 2,
    alignItems: "center",
  },
  emptyText: {
    color: COLORS.text.secondary,
    fontSize: 14,
  },
  taskCard: {
    marginBottom: SPACING.s,
  },
  taskCardSelected: {
    borderColor: "rgba(47, 107, 255, 0.5)",
  },
  taskRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  taskTextWrap: {
    flex: 1,
  },
  taskAgent: {
    color: COLORS.text.primary,
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 2,
  },
  taskGoal: {
    color: COLORS.text.secondary,
    fontSize: 12,
    lineHeight: 17,
  },
  taskRight: {
    alignItems: "flex-end",
    gap: 2,
  },
  taskTime: {
    color: COLORS.text.tertiary,
    fontSize: 10,
  },
  taskDuration: {
    color: COLORS.text.dim,
    fontSize: 10,
  },
  taskError: {
    color: COLORS.accent.error,
    fontSize: 11,
    marginTop: SPACING.xs,
  },
});
