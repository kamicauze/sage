import React from "react";
import {
  Alert,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import Constants from "expo-constants";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDot,
  Clock,
} from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassCard } from "../components/ui/GlassCard";
import { SwipeableTaskCard } from "../components/ui/SwipeableTaskCard";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { NewPlanTaskInput, PlanTask, RoutineKey, TaskPriority } from "../types/plan";

interface PlanScreenProps {
  tasks: PlanTask[];
  onAddTask: (input: NewPlanTaskInput) => void;
  onToggleTask: (id: string) => void;
  onSnoozeTask: (id: string) => void;
  onDeleteTask: (id: string) => void;
  onSyncGoogle?: () => void;
  isSyncingGoogle?: boolean;
  googleConnected?: boolean;
}

const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface RoutinePreset {
  key: RoutineKey;
  title: string;
  dueTime: string;
  priority: TaskPriority;
  tag: string;
}

type PlanViewMode = "open" | "all" | "routines" | "done";

interface PlanViewOption {
  key: PlanViewMode;
  label: string;
}

const PLAN_VIEW_OPTIONS: PlanViewOption[] = [
  { key: "open", label: "Open" },
  { key: "routines", label: "Routines" },
  { key: "done", label: "Done" },
  { key: "all", label: "All" },
];

const DAILY_ROUTINE_PRESETS: RoutinePreset[] = [
  { key: "hydrate_morning", title: "Drink water", dueTime: "09:00", priority: "low", tag: "Hydrate" },
  { key: "hydrate_midday", title: "Drink water", dueTime: "12:00", priority: "low", tag: "Hydrate" },
  { key: "hydrate_afternoon", title: "Drink water", dueTime: "15:00", priority: "low", tag: "Hydrate" },
  { key: "hydrate_evening", title: "Drink water", dueTime: "18:00", priority: "low", tag: "Hydrate" },
  {
    key: "stand_stretch_midmorning",
    title: "Stand and stretch",
    dueTime: "11:00",
    priority: "medium",
    tag: "Mobility",
  },
  {
    key: "stand_stretch_afternoon",
    title: "Stand and stretch",
    dueTime: "14:00",
    priority: "medium",
    tag: "Mobility",
  },
  {
    key: "stand_stretch_evening",
    title: "Stand and stretch",
    dueTime: "17:00",
    priority: "medium",
    tag: "Mobility",
  },
  { key: "skincare_am", title: "Skincare (AM)", dueTime: "07:30", priority: "medium", tag: "Skincare" },
  { key: "skincare_pm", title: "Skincare (PM)", dueTime: "21:00", priority: "medium", tag: "Skincare" },
];

const QUICK_TIMES = [
  "07:00", "08:00", "09:00", "10:00", "11:00",
  "12:00", "13:00", "14:00", "15:00", "16:00",
  "17:00", "18:00", "19:00", "20:00", "21:00",
];

function toDateKeyLocal(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateKey(dateKey: string): Date {
  const [yearRaw, monthRaw, dayRaw] = dateKey.split("-");
  const year = Number.parseInt(yearRaw || "", 10);
  const month = Number.parseInt(monthRaw || "", 10);
  const day = Number.parseInt(dayRaw || "", 10);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return new Date();
  }
  return new Date(year, month - 1, day);
}

function todayDateKey(): string {
  return toDateKeyLocal(new Date());
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function startOfWeekMonday(date: Date): Date {
  const shift = (date.getDay() + 6) % 7;
  return addDays(date, -shift);
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function dateKeyFromIso(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return toDateKeyLocal(parsed);
}

function formatDayNumber(dateKey: string): string {
  return String(parseDateKey(dateKey).getDate());
}

function formatTime(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "No time";
  return parsed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function monthLabel(date: Date): string {
  return date.toLocaleDateString([], { month: "long", year: "numeric" });
}

function compareByDueDate(a: PlanTask, b: PlanTask): number {
  if (a.done !== b.done) return a.done ? 1 : -1;
  const aTs = new Date(a.dueIso).getTime();
  const bTs = new Date(b.dueIso).getTime();
  if (!Number.isFinite(aTs) && !Number.isFinite(bTs)) return 0;
  if (!Number.isFinite(aTs)) return 1;
  if (!Number.isFinite(bTs)) return -1;
  return aTs - bTs;
}

function priorityColor(priority: TaskPriority): string {
  if (priority === "high") return COLORS.accent.warning;
  if (priority === "medium") return COLORS.accent.info;
  return COLORS.text.tertiary;
}

function nextPriority(current: TaskPriority): TaskPriority {
  if (current === "low") return "medium";
  if (current === "medium") return "high";
  return "low";
}

function dueIsoForDateKey(dateKey: string): string {
  const date = parseDateKey(dateKey);
  const now = new Date();
  date.setHours(now.getHours(), now.getMinutes(), 0, 0);
  return date.toISOString();
}

function hourMinuteFromIso(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "";
  const hour = String(parsed.getHours()).padStart(2, "0");
  const minute = String(parsed.getMinutes()).padStart(2, "0");
  return `${hour}:${minute}`;
}

export function PlanScreen({
  tasks,
  onAddTask,
  onToggleTask,
  onSnoozeTask,
  onDeleteTask,
  onSyncGoogle,
  isSyncingGoogle = false,
  googleConnected = false,
}: PlanScreenProps) {
  const [selectedDate, setSelectedDate] = React.useState<string>(todayDateKey());
  const [calendarExpanded, setCalendarExpanded] = React.useState(false);
  const [extrasExpanded, setExtrasExpanded] = React.useState(false);
  const [viewMode, setViewMode] = React.useState<PlanViewMode>("open");
  const [draftTitle, setDraftTitle] = React.useState("");
  const [draftPriority, setDraftPriority] = React.useState<TaskPriority>("medium");
  const [draftTime, setDraftTime] = React.useState<string | null>(null);
  const [showTimePicker, setShowTimePicker] = React.useState(false);
  const [keyboardVisible, setKeyboardVisible] = React.useState(false);

  const selectedDateObj = React.useMemo(() => parseDateKey(selectedDate), [selectedDate]);

  React.useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";

    const showSub = Keyboard.addListener(showEvent, () => {
      setKeyboardVisible(true);
      setShowTimePicker(false);
    });
    const hideSub = Keyboard.addListener(hideEvent, () => {
      setKeyboardVisible(false);
    });

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

  const tasksByDate = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of tasks) {
      const key = dateKeyFromIso(task.dueIso);
      if (!key) continue;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [tasks]);

  const weekDays = React.useMemo(() => {
    const start = startOfWeekMonday(selectedDateObj);
    return Array.from({ length: 7 }, (_, index) => toDateKeyLocal(addDays(start, index)));
  }, [selectedDateObj]);

  const monthDays = React.useMemo(() => {
    const first = startOfMonth(selectedDateObj);
    const start = startOfWeekMonday(first);
    return Array.from({ length: 42 }, (_, index) => toDateKeyLocal(addDays(start, index)));
  }, [selectedDateObj]);

  const dayTasks = React.useMemo(
    () =>
      tasks
        .filter((task) => dateKeyFromIso(task.dueIso) === selectedDate)
        .sort(compareByDueDate),
    [selectedDate, tasks]
  );

  const completedCount = React.useMemo(
    () => dayTasks.filter((task) => task.done).length,
    [dayTasks]
  );
  const openCount = React.useMemo(
    () => dayTasks.filter((task) => !task.done).length,
    [dayTasks]
  );
  const completionRatio = dayTasks.length ? completedCount / dayTasks.length : 0;

  const routineTasksForDay = React.useMemo(
    () => dayTasks.filter((task) => Boolean(task.routineKey)),
    [dayTasks]
  );

  const routineCompletedCount = React.useMemo(
    () => routineTasksForDay.filter((task) => task.done).length,
    [routineTasksForDay]
  );

  const filteredTasks = React.useMemo(() => {
    if (viewMode === "open") return dayTasks.filter((task) => !task.done);
    if (viewMode === "routines") return dayTasks.filter((task) => Boolean(task.routineKey));
    if (viewMode === "done") return dayTasks.filter((task) => task.done);
    return dayTasks;
  }, [dayTasks, viewMode]);

  const hasRoutineTaskForPreset = React.useCallback(
    (preset: RoutinePreset) =>
      dayTasks.some(
        (task) =>
          task.routineKey === preset.key ||
          (task.title === preset.title && hourMinuteFromIso(task.dueIso) === preset.dueTime)
      ),
    [dayTasks]
  );

  const addRoutinePreset = React.useCallback(
    (preset: RoutinePreset) => {
      if (hasRoutineTaskForPreset(preset)) return;
      onAddTask({
        title: preset.title,
        dateKey: selectedDate,
        dueTime: preset.dueTime,
        priority: preset.priority,
        tag: preset.tag,
        routineKey: preset.key,
      });
    },
    [hasRoutineTaskForPreset, onAddTask, selectedDate]
  );

  const handleAddDailyRoutines = React.useCallback(() => {
    for (const preset of DAILY_ROUTINE_PRESETS) {
      if (hasRoutineTaskForPreset(preset)) continue;
      onAddTask({
        title: preset.title,
        dateKey: selectedDate,
        dueTime: preset.dueTime,
        priority: preset.priority,
        tag: preset.tag,
        routineKey: preset.key,
      });
    }
  }, [hasRoutineTaskForPreset, onAddTask, selectedDate]);

  const handleAddTask = React.useCallback(() => {
    const title = draftTitle.trim();
    if (!title) return;
    onAddTask({
      title,
      dateKey: selectedDate,
      priority: draftPriority,
      dueTime: draftTime ?? undefined,
    });
    setDraftTitle("");
    setDraftTime(null);
    setShowTimePicker(false);
  }, [draftPriority, draftTime, draftTitle, onAddTask, selectedDate]);

  const confirmDelete = React.useCallback(
    (taskId: string) => {
      Alert.alert("Delete task", "This cannot be undone.", [
        { text: "Cancel", style: "cancel" },
        { text: "Delete", style: "destructive", onPress: () => onDeleteTask(taskId) },
      ]);
    },
    [onDeleteTask]
  );

  const toggleTimePicker = React.useCallback(() => {
    Keyboard.dismiss();
    setShowTimePicker((prev) => !prev);
  }, []);

  return (
    <ScreenLayout>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? (Constants.statusBarHeight || 0) : 0}
      >
        <FlatList
          style={styles.taskList}
          data={filteredTasks}
          keyExtractor={(item) => item.id}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={
            <View style={styles.headerArea}>
              {/* Tier 1: Title + score */}
              <View style={styles.headerRow}>
                <View>
                  <Text style={styles.title}>PLAN</Text>
                  <Text style={styles.subtitle}>
                    {selectedDateObj.toLocaleDateString([], {
                      weekday: "long",
                      month: "short",
                      day: "numeric",
                    })}
                  </Text>
                </View>
                <View style={styles.headerRightCol}>
                  <View style={styles.scorePill}>
                    <CircleDot size={10} color={COLORS.status.online} fill={COLORS.status.online} />
                    <Text style={styles.scoreText}>
                      {completedCount}/{dayTasks.length || 0} done
                    </Text>
                  </View>
                  <Pressable
                    style={[
                      styles.syncButton,
                      !googleConnected && styles.syncButtonDisconnected,
                    ]}
                    onPress={onSyncGoogle}
                    disabled={isSyncingGoogle || !onSyncGoogle}
                  >
                    <Text style={styles.syncButtonText}>
                      {isSyncingGoogle
                        ? "Syncing..."
                        : googleConnected
                          ? "Sync Google"
                          : "Connect Google"}
                    </Text>
                  </Pressable>
                  {selectedDate !== todayDateKey() ? (
                    <Pressable style={styles.todayButton} onPress={() => setSelectedDate(todayDateKey())}>
                      <Text style={styles.todayButtonText}>Jump to today</Text>
                    </Pressable>
                  ) : null}
                </View>
              </View>

              {/* Tier 2: Week strip (no card wrapper) */}
              <View style={styles.weekStrip}>
                {weekDays.map((dateKey, index) => {
                  const active = dateKey === selectedDate;
                  const count = tasksByDate.get(dateKey) ?? 0;
                  return (
                    <Pressable
                      key={dateKey}
                      onPress={() => setSelectedDate(dateKey)}
                      style={[styles.weekDay, active && styles.weekDayActive]}
                    >
                      <Text style={[styles.weekDayLabel, active && styles.weekDayLabelActive]}>
                        {WEEKDAY_SHORT[index]}
                      </Text>
                      <Text style={[styles.weekDayNumber, active && styles.weekDayNumberActive]}>
                        {formatDayNumber(dateKey)}
                      </Text>
                      <View
                        style={[
                          styles.weekDot,
                          count > 0 && styles.weekDotFilled,
                          active && styles.weekDotActive,
                        ]}
                      />
                    </Pressable>
                  );
                })}
              </View>

              {/* Tier 2b: Filter chips (inline) */}
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.filterRow}
              >
                {PLAN_VIEW_OPTIONS.map((option) => {
                  const active = option.key === viewMode;
                  return (
                    <Pressable
                      key={option.key}
                      onPress={() => setViewMode(option.key)}
                      style={[styles.filterChip, active && styles.filterChipActive]}
                    >
                      <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                        {option.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </ScrollView>

              {/* Tier 3: Collapsible extras toggle */}
              <Pressable
                onPress={() => setExtrasExpanded((prev) => !prev)}
                style={styles.extrasToggle}
              >
                <View style={styles.extrasToggleLeft}>
                  <View style={styles.miniProgressTrack}>
                    <View style={[styles.miniProgressFill, { width: `${Math.round(completionRatio * 100)}%` }]} />
                  </View>
                  <Text style={styles.extrasToggleText}>
                    {openCount} open · {routineTasksForDay.length} routines
                  </Text>
                </View>
                {extrasExpanded ? (
                  <ChevronUp size={16} color={COLORS.text.secondary} />
                ) : (
                  <ChevronDown size={16} color={COLORS.text.secondary} />
                )}
              </Pressable>

              {/* Collapsible: Progress, Month calendar, Routines */}
              {extrasExpanded ? (
                <Animated.View entering={FadeInDown.duration(200)} style={styles.extrasContent}>
                  <GlassCard style={styles.progressCard} variant="soft">
                    <View style={styles.progressRow}>
                      <Text style={styles.progressTitle}>Daily focus</Text>
                      <Text style={styles.progressMeta}>
                        {openCount} open · {routineTasksForDay.length} routines
                      </Text>
                    </View>
                    <View style={styles.progressTrack}>
                      <View style={[styles.progressFill, { width: `${Math.round(completionRatio * 100)}%` }]} />
                    </View>
                  </GlassCard>

                  <GlassCard style={styles.calendarCard} variant="soft">
                    <Pressable
                      onPress={() => setCalendarExpanded((prev) => !prev)}
                      style={styles.expandToggle}
                    >
                      <Text style={styles.expandToggleText}>
                        {calendarExpanded ? "Collapse month" : "Expand month"}
                      </Text>
                    </Pressable>

                    {calendarExpanded ? (
                      <View style={styles.monthWrap}>
                        <Text style={styles.monthTitle}>{monthLabel(selectedDateObj)}</Text>
                        <View style={styles.monthHeaderRow}>
                          {WEEKDAY_SHORT.map((label) => (
                            <Text key={`head-${label}`} style={styles.monthHeaderText}>
                              {label[0]}
                            </Text>
                          ))}
                        </View>
                        <View style={styles.monthGrid}>
                          {monthDays.map((dateKey) => {
                            const date = parseDateKey(dateKey);
                            const inCurrentMonth = date.getMonth() === selectedDateObj.getMonth();
                            const active = dateKey === selectedDate;
                            const count = tasksByDate.get(dateKey) ?? 0;

                            return (
                              <Pressable
                                key={dateKey}
                                style={[
                                  styles.monthCell,
                                  active && styles.monthCellActive,
                                  !inCurrentMonth && styles.monthCellMuted,
                                ]}
                                onPress={() => setSelectedDate(dateKey)}
                              >
                                <Text
                                  style={[
                                    styles.monthCellText,
                                    active && styles.monthCellTextActive,
                                    !inCurrentMonth && styles.monthCellTextMuted,
                                  ]}
                                >
                                  {date.getDate()}
                                </Text>
                                {count > 0 ? <View style={styles.monthCellDot} /> : null}
                              </Pressable>
                            );
                          })}
                        </View>
                      </View>
                    ) : null}
                  </GlassCard>

                  <GlassCard style={styles.routinesCard} variant="soft">
                    <View style={styles.routinesHeader}>
                      <Text style={styles.routinesTitle}>Daily routines</Text>
                      <Text style={styles.routinesSubtitle}>
                        {routineCompletedCount}/{routineTasksForDay.length || 0} done
                      </Text>
                    </View>
                    <Pressable style={styles.addRoutinesButton} onPress={handleAddDailyRoutines}>
                      <Text style={styles.addRoutinesText}>Add default routine pack</Text>
                    </Pressable>
                    <ScrollView
                      horizontal
                      showsHorizontalScrollIndicator={false}
                      contentContainerStyle={styles.routineChipsRow}
                    >
                      {DAILY_ROUTINE_PRESETS.map((preset) => {
                        const active = hasRoutineTaskForPreset(preset);
                        return (
                          <Pressable
                            key={preset.key}
                            onPress={() => addRoutinePreset(preset)}
                            style={[styles.routineChip, active && styles.routineChipActive]}
                          >
                            <Text style={[styles.routineChipTitle, active && styles.routineChipTitleActive]}>
                              {preset.title}
                            </Text>
                            <Text style={[styles.routineChipMeta, active && styles.routineChipMetaActive]}>
                              {preset.dueTime} · {preset.tag}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </ScrollView>
                  </GlassCard>
                </Animated.View>
              ) : null}
            </View>
          }
          renderItem={({ item }) => (
            <SwipeableTaskCard
              onDelete={() => confirmDelete(item.id)}
              onSnooze={() => onSnoozeTask(item.id)}
              enabled={!item.done}
            >
              <GlassCard
                style={[
                  styles.taskCard,
                  item.priority === "high" && !item.done ? styles.taskCardHigh : null,
                ]}
                variant={item.done ? "outline" : "default"}
              >
                <View style={styles.taskRow}>
                  <Pressable onPress={() => onToggleTask(item.id)} style={styles.checkWrap}>
                    {item.done ? (
                      <CheckCircle2 size={21} color={COLORS.status.online} />
                    ) : (
                      <View style={styles.emptyCheck} />
                    )}
                  </Pressable>
                  <View style={styles.taskTextWrap}>
                    <Text style={[styles.taskTitle, item.done && styles.taskDone]}>{item.title}</Text>
                    <View style={styles.taskMetaRow}>
                      <Text style={styles.taskTime}>{formatTime(item.dueIso)}</Text>
                      {item.tag ? (
                        <View style={styles.tagPill}>
                          <Text style={styles.tagText}>{item.tag}</Text>
                        </View>
                      ) : null}
                      {item.routineKey ? (
                        <View style={styles.routinePill}>
                          <Text style={styles.routinePillText}>ROUTINE</Text>
                        </View>
                      ) : null}
                      <View
                        style={[
                          styles.priorityPill,
                          { borderColor: `${priorityColor(item.priority)}66` },
                        ]}
                      >
                        <Text style={[styles.priorityText, { color: priorityColor(item.priority) }]}>
                          {item.priority.toUpperCase()}
                        </Text>
                      </View>
                    </View>
                  </View>
                </View>
              </GlassCard>
            </SwipeableTaskCard>
          )}
          ListEmptyComponent={
            <GlassCard style={styles.emptyCard} variant="outline">
              <AlertTriangle size={18} color={COLORS.text.secondary} />
              <Text style={styles.emptyTitle}>
                {viewMode === "open"
                  ? "No open tasks"
                  : viewMode === "routines"
                    ? "No routine tasks"
                    : viewMode === "done"
                      ? "Nothing completed yet"
                      : "No tasks for this day"}
              </Text>
              <Text style={styles.emptySubtitle}>
                {viewMode === "done"
                  ? "Complete something and it will show here."
                  : "Add your top 3 items below and time-block the rest."}
              </Text>
            </GlassCard>
          }
        />

        {/* Quick add */}
        <View style={styles.quickAddWrap}>
          <GlassCard style={styles.quickAddCard} padded={false} variant="default">
            <View style={styles.quickAddRow}>
              <Pressable
                style={styles.prioritySelector}
                onPress={() => setDraftPriority((prev) => nextPriority(prev))}
              >
                <Text style={[styles.prioritySelectorText, { color: priorityColor(draftPriority) }]}>
                  {draftPriority[0].toUpperCase()}
                </Text>
              </Pressable>

              <Pressable style={styles.timeChip} onPress={toggleTimePicker}>
                <Clock size={12} color={draftTime ? COLORS.accent.info : COLORS.text.tertiary} />
                <Text style={[styles.timeChipText, draftTime && styles.timeChipTextActive]}>
                  {draftTime ?? "Now"}
                </Text>
              </Pressable>

              <TextInput
                value={draftTitle}
                onChangeText={setDraftTitle}
                style={styles.quickInput}
                placeholder="Add next task..."
                placeholderTextColor={COLORS.text.tertiary}
                returnKeyType="done"
                onSubmitEditing={handleAddTask}
              />

              <Pressable
                style={[styles.addButton, !draftTitle.trim() && styles.addButtonDisabled]}
                onPress={handleAddTask}
                disabled={!draftTitle.trim()}
                accessibilityLabel="Add task"
              >
                <Text style={styles.addButtonText}>Add</Text>
              </Pressable>
            </View>
            <Text style={styles.quickMeta}>
              Adding to {selectedDate} · {draftTime ? `at ${draftTime}` : `default time ${formatTime(dueIsoForDateKey(selectedDate))}`}
            </Text>
          </GlassCard>
        </View>

        {/* Time picker grid */}
        {showTimePicker ? (
          <Animated.View entering={FadeInDown.duration(150)} style={styles.timePickerWrap}>
            <View style={styles.timePickerGrid}>
              <Pressable
                style={[styles.timePreset, !draftTime && styles.timePresetActive]}
                onPress={() => {
                  setDraftTime(null);
                  setShowTimePicker(false);
                }}
              >
                <Text style={[styles.timePresetText, !draftTime && styles.timePresetTextActive]}>Now</Text>
              </Pressable>
              {QUICK_TIMES.map((time) => {
                const active = draftTime === time;
                return (
                  <Pressable
                    key={time}
                    style={[styles.timePreset, active && styles.timePresetActive]}
                    onPress={() => {
                      setDraftTime(time);
                      setShowTimePicker(false);
                    }}
                  >
                    <Text style={[styles.timePresetText, active && styles.timePresetTextActive]}>
                      {time}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </Animated.View>
        ) : null}

        {!keyboardVisible && !showTimePicker && <View style={styles.tabBarSpacer} />}
      </KeyboardAvoidingView>
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  listContent: {
    paddingBottom: SPACING.m,
  },
  taskList: {
    flex: 1,
  },
  headerArea: {
    marginTop: SPACING.s,
    marginBottom: SPACING.s,
    gap: SPACING.s,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  headerRightCol: {
    alignItems: "flex-end",
    gap: SPACING.xs,
  },
  title: {
    color: COLORS.text.primary,
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  subtitle: {
    marginTop: 2,
    color: COLORS.text.secondary,
    fontSize: 13,
  },
  scorePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: "rgba(32, 214, 143, 0.35)",
    backgroundColor: "rgba(7, 71, 46, 0.35)",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.xs + 1,
  },
  scoreText: {
    color: COLORS.status.online,
    fontSize: 11,
    letterSpacing: 0.8,
    fontWeight: "700",
  },
  todayButton: {
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(10, 23, 46, 0.72)",
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
  },
  todayButtonText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  syncButton: {
    borderWidth: 1,
    borderColor: "rgba(106, 159, 255, 0.65)",
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(37, 76, 150, 0.35)",
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
  },
  syncButtonDisconnected: {
    borderColor: COLORS.line,
    backgroundColor: "rgba(10, 23, 46, 0.72)",
  },
  syncButtonText: {
    color: COLORS.text.primary,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.4,
  },

  // Week strip (no GlassCard)
  weekStrip: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: SPACING.xs,
  },
  weekDay: {
    flex: 1,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "rgba(10, 23, 46, 0.7)",
    alignItems: "center",
    paddingVertical: SPACING.s,
    gap: 2,
  },
  weekDayActive: {
    borderColor: "rgba(106, 159, 255, 0.75)",
    backgroundColor: "rgba(37, 76, 150, 0.35)",
  },
  weekDayLabel: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "600",
  },
  weekDayLabelActive: {
    color: COLORS.text.primary,
  },
  weekDayNumber: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
  },
  weekDayNumberActive: {
    color: COLORS.accent.info,
  },
  weekDot: {
    width: 5,
    height: 5,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(125, 163, 234, 0.3)",
  },
  weekDotFilled: {
    backgroundColor: COLORS.accent.info,
  },
  weekDotActive: {
    backgroundColor: COLORS.accent.primary,
  },

  // Filter chips (inline)
  filterRow: {
    gap: SPACING.xs,
  },
  filterChip: {
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.xs + 1,
    backgroundColor: "rgba(10, 23, 46, 0.72)",
  },
  filterChipActive: {
    borderColor: "rgba(106, 159, 255, 0.75)",
    backgroundColor: "rgba(37, 76, 150, 0.35)",
  },
  filterChipText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "700",
  },
  filterChipTextActive: {
    color: COLORS.accent.info,
  },

  // Collapsible extras toggle
  extrasToggle: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: SPACING.xs,
    paddingHorizontal: SPACING.xs,
    borderRadius: RADIUS.s,
    backgroundColor: "rgba(10, 23, 46, 0.5)",
    borderWidth: 1,
    borderColor: COLORS.line,
  },
  extrasToggleLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    flex: 1,
  },
  extrasToggleText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "600",
  },
  miniProgressTrack: {
    width: 48,
    height: 4,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(125, 163, 234, 0.22)",
    overflow: "hidden",
  },
  miniProgressFill: {
    height: "100%",
    backgroundColor: COLORS.status.online,
    borderRadius: RADIUS.full,
  },
  extrasContent: {
    gap: SPACING.s,
  },

  // Progress card
  progressCard: {
    gap: SPACING.s,
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  progressTitle: {
    color: COLORS.text.primary,
    fontSize: 13,
    fontWeight: "700",
  },
  progressMeta: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  progressTrack: {
    width: "100%",
    height: 7,
    borderRadius: RADIUS.full,
    backgroundColor: "rgba(125, 163, 234, 0.22)",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: COLORS.status.online,
    borderRadius: RADIUS.full,
  },

  // Calendar
  calendarCard: {
    gap: SPACING.s,
  },
  expandToggle: {
    alignSelf: "flex-start",
    paddingVertical: SPACING.xs,
  },
  expandToggleText: {
    color: COLORS.accent.info,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  monthWrap: {
    borderTopWidth: 1,
    borderTopColor: COLORS.line,
    paddingTop: SPACING.s,
    gap: SPACING.s,
  },
  monthTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
  },
  monthHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.xs,
  },
  monthHeaderText: {
    width: 34,
    textAlign: "center",
    color: COLORS.text.tertiary,
    fontSize: 11,
    letterSpacing: 0.6,
    fontWeight: "600",
  },
  monthGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
  },
  monthCell: {
    width: 34,
    height: 34,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.line,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(10, 23, 46, 0.55)",
  },
  monthCellActive: {
    borderColor: "rgba(106, 159, 255, 0.75)",
    backgroundColor: "rgba(37, 76, 150, 0.35)",
  },
  monthCellMuted: {
    opacity: 0.45,
  },
  monthCellText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "600",
  },
  monthCellTextActive: {
    color: COLORS.text.primary,
    fontWeight: "700",
  },
  monthCellTextMuted: {
    color: COLORS.text.tertiary,
  },
  monthCellDot: {
    position: "absolute",
    bottom: 4,
    width: 4,
    height: 4,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.accent.info,
  },

  // Routines
  routinesCard: {
    gap: SPACING.s,
  },
  routinesHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  routinesTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
  },
  routinesSubtitle: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "600",
  },
  addRoutinesButton: {
    borderWidth: 1,
    borderColor: "rgba(106, 159, 255, 0.45)",
    backgroundColor: "rgba(37, 76, 150, 0.28)",
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs + 1,
    alignSelf: "flex-start",
  },
  addRoutinesText: {
    color: COLORS.accent.info,
    fontSize: 12,
    fontWeight: "700",
  },
  routineChipsRow: {
    gap: SPACING.s,
    paddingRight: SPACING.xs,
  },
  routineChip: {
    minWidth: 132,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "rgba(10, 23, 46, 0.7)",
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.s,
    gap: 2,
  },
  routineChipActive: {
    borderColor: "rgba(32, 214, 143, 0.55)",
    backgroundColor: "rgba(7, 71, 46, 0.3)",
  },
  routineChipTitle: {
    color: COLORS.text.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  routineChipTitleActive: {
    color: COLORS.status.online,
  },
  routineChipMeta: {
    color: COLORS.text.secondary,
    fontSize: 11,
  },
  routineChipMetaActive: {
    color: COLORS.text.primary,
  },

  // Task cards
  taskCard: {
    gap: SPACING.s,
  },
  taskCardHigh: {
    borderColor: "rgba(255, 173, 78, 0.55)",
  },
  taskRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  checkWrap: {
    width: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyCheck: {
    width: 20,
    height: 20,
    borderRadius: RADIUS.full,
    borderWidth: 2,
    borderColor: COLORS.border,
    backgroundColor: "rgba(8, 20, 43, 0.65)",
  },
  taskTextWrap: {
    flex: 1,
    gap: SPACING.xs,
  },
  taskTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 20,
  },
  taskDone: {
    color: COLORS.text.tertiary,
    textDecorationLine: "line-through",
  },
  taskMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    flexWrap: "wrap",
  },
  taskTime: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  tagPill: {
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.xs + 2,
    paddingVertical: 1,
    backgroundColor: "rgba(17, 33, 58, 0.8)",
  },
  tagText: {
    color: COLORS.text.secondary,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  routinePill: {
    borderWidth: 1,
    borderColor: "rgba(32, 214, 143, 0.4)",
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.xs + 2,
    paddingVertical: 1,
    backgroundColor: "rgba(7, 71, 46, 0.35)",
  },
  routinePillText: {
    color: COLORS.status.online,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  priorityPill: {
    borderWidth: 1,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.xs + 2,
    paddingVertical: 1,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.6,
  },

  // Empty state
  emptyCard: {
    marginTop: SPACING.s,
    alignItems: "center",
    gap: SPACING.s,
    paddingVertical: SPACING.l,
  },
  emptyTitle: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "700",
  },
  emptySubtitle: {
    color: COLORS.text.secondary,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 19,
  },

  // Quick add
  quickAddWrap: {
    paddingTop: SPACING.s,
  },
  tabBarSpacer: {
    height: LAYOUT.tabBarHeight,
  },
  quickAddCard: {
    borderRadius: RADIUS.m,
    overflow: "hidden",
  },
  quickAddRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
    paddingHorizontal: SPACING.m,
    paddingTop: SPACING.s,
    paddingBottom: SPACING.s,
  },
  prioritySelector: {
    width: 32,
    height: 32,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "rgba(11, 22, 44, 0.85)",
    alignItems: "center",
    justifyContent: "center",
  },
  prioritySelectorText: {
    fontSize: 13,
    fontWeight: "800",
  },
  timeChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xxs,
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
    backgroundColor: "rgba(10, 23, 46, 0.72)",
  },
  timeChipText: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    fontWeight: "700",
  },
  timeChipTextActive: {
    color: COLORS.accent.info,
  },
  quickInput: {
    flex: 1,
    color: COLORS.text.primary,
    fontSize: 15,
    paddingVertical: SPACING.s,
  },
  addButton: {
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(47, 107, 255, 0.35)",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
  },
  addButtonDisabled: {
    opacity: 0.45,
  },
  addButtonText: {
    color: COLORS.text.primary,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  quickMeta: {
    paddingHorizontal: SPACING.m,
    paddingBottom: SPACING.s,
    color: COLORS.text.tertiary,
    fontSize: 11,
  },

  // Time picker
  timePickerWrap: {
    paddingTop: SPACING.xs,
    paddingBottom: LAYOUT.tabBarHeight + SPACING.s,
  },
  timePickerGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
  },
  timePreset: {
    borderWidth: 1,
    borderColor: COLORS.line,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs + 1,
    backgroundColor: "rgba(10, 23, 46, 0.72)",
  },
  timePresetActive: {
    borderColor: "rgba(106, 159, 255, 0.75)",
    backgroundColor: "rgba(37, 76, 150, 0.35)",
  },
  timePresetText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "700",
  },
  timePresetTextActive: {
    color: COLORS.accent.info,
  },
});
