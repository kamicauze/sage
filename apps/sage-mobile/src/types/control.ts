export interface BrainControlState {
  personality: string;
  raw_mode: boolean;
  voice_input_enabled: boolean;
  voice_output_enabled: boolean;
  last_command?: string | null;
  updated_at: string;
}

export interface BrainControlStateResponse {
  success: boolean;
  state: BrainControlState;
  mqtt_online: boolean;
  mqtt_error?: string | null;
}

export interface BrainControlAuditEntry {
  ts: string;
  action: string;
  source: string;
  payload: Record<string, unknown>;
  status: string;
  error?: string | null;
}

export interface BrainControlAuditResponse {
  success: boolean;
  entries: BrainControlAuditEntry[];
}

export type BrainControlAuditFilter = "all" | "config" | "command" | "error";

export interface BrainControlConfigRequest {
  personality?: string;
  raw_mode?: boolean;
  voice_input_enabled?: boolean;
  voice_output_enabled?: boolean;
}

export interface BrainControlCommandRequest {
  command:
    | "clear_conversation"
    | "clear_memory"
    | "clear_episodes"
    | "kill_switch"
    | "resume_voice";
}
