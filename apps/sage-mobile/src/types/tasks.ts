export type AgentTaskStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface AgentTask {
  id: string;
  agent_name: string;
  goal: string;
  status: AgentTaskStatus;
  config_json?: string | null;
  created_at: number;
  started_at?: number | null;
  completed_at?: number | null;
  error?: string | null;
  result_summary?: string | null;
}

export interface AgentTaskObservation {
  id: number;
  task_id: string;
  tool: string;
  params_json: string;
  result_text: string;
  timestamp: number;
}

export interface AgentTaskListResponse {
  success: boolean;
  count: number;
  tasks: AgentTask[];
}

export interface AgentTaskDetailResponse {
  success: boolean;
  task: AgentTask;
  observations: AgentTaskObservation[];
}

export interface AgentTaskStatsResponse {
  success: boolean;
  stats: Record<AgentTaskStatus, number>;
}
