import AsyncStorage from "@react-native-async-storage/async-storage";
import { PlanTask, RoutineKey, TaskPriority } from "../types/plan";

const PLAN_TASKS_KEY = "sage.mobile.plan.tasks.v1";
const MAX_TASKS = 800;

function isPriority(value: unknown): value is TaskPriority {
  return value === "low" || value === "medium" || value === "high";
}

function isRoutineKey(value: unknown): value is RoutineKey {
  return (
    value === "hydrate_morning" ||
    value === "hydrate_midday" ||
    value === "hydrate_afternoon" ||
    value === "hydrate_evening" ||
    value === "stand_stretch_midmorning" ||
    value === "stand_stretch_afternoon" ||
    value === "stand_stretch_evening" ||
    value === "skincare_am" ||
    value === "skincare_pm"
  );
}

function isPlanTaskLike(value: unknown): value is PlanTask {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const validSource =
    item.source === "local" ||
    item.source === "google" ||
    typeof item.source === "undefined";
  return (
    typeof item.id === "string" &&
    typeof item.title === "string" &&
    typeof item.dueIso === "string" &&
    typeof item.done === "boolean" &&
    isPriority(item.priority) &&
    (typeof item.tag === "string" || typeof item.tag === "undefined") &&
    (isRoutineKey(item.routineKey) || typeof item.routineKey === "undefined") &&
    validSource &&
    (typeof item.externalId === "string" || typeof item.externalId === "undefined") &&
    (typeof item.externalListId === "string" || typeof item.externalListId === "undefined")
  );
}

export async function loadPlanTasks(): Promise<PlanTask[]> {
  try {
    const raw = await AsyncStorage.getItem(PLAN_TASKS_KEY);
    if (!raw) return [];

    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isPlanTaskLike).slice(-MAX_TASKS);
  } catch {
    return [];
  }
}

export async function savePlanTasks(tasks: PlanTask[]): Promise<void> {
  const safeTasks = tasks
    .filter(isPlanTaskLike)
    .slice(-MAX_TASKS)
    .map((task) => ({
      id: task.id,
      title: task.title,
      dueIso: task.dueIso,
      done: Boolean(task.done),
      priority: task.priority,
      tag: task.tag,
      routineKey: task.routineKey,
      source: task.source,
      externalId: task.externalId,
      externalListId: task.externalListId,
    }));

  await AsyncStorage.setItem(PLAN_TASKS_KEY, JSON.stringify(safeTasks));
}
