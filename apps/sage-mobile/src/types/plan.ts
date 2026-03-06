export type TaskPriority = "low" | "medium" | "high";
export type RoutineKey =
  | "hydrate_morning"
  | "hydrate_midday"
  | "hydrate_afternoon"
  | "hydrate_evening"
  | "stand_stretch_midmorning"
  | "stand_stretch_afternoon"
  | "stand_stretch_evening"
  | "skincare_am"
  | "skincare_pm";

export interface PlanTask {
  id: string;
  title: string;
  dueIso: string;
  done: boolean;
  priority: TaskPriority;
  tag?: string;
  routineKey?: RoutineKey;
  source?: "local" | "google";
  externalId?: string;
  externalListId?: string;
}

export interface NewPlanTaskInput {
  title: string;
  dateKey: string;
  priority?: TaskPriority;
  dueTime?: string;
  tag?: string;
  routineKey?: RoutineKey;
}
