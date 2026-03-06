export interface WebhookActionConfig {
  type: "start_agent" | "brain_query" | "mqtt_publish";
  agent?: string;
  goal_template?: string;
  topic?: string;
  text_template?: string;
}

export interface WebhookHook {
  id: string;
  name: string;
  source: string;
  action: WebhookActionConfig;
  enabled: boolean;
  has_secret: boolean;
  created_at: string;
  last_triggered: string | null;
  trigger_count: number;
}

export interface WebhookListResponse {
  success: boolean;
  count: number;
  hooks: WebhookHook[];
}

export interface WebhookRegisterResponse {
  success: boolean;
  id: string;
  url: string;
}

export interface WebhookDeleteResponse {
  success: boolean;
  deleted: string;
}
