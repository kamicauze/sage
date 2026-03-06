import type { ChatProvider } from "./chat";

export type ThreadMode = "conversation" | "project";

export interface ProjectThreadContext {
  mode: ThreadMode;
  project_id?: string;
  preferred_node?: string;
  executor?: ChatProvider;
}

export interface ProjectControlNode {
  id: string;
  label?: string;
  transport: string;
  online?: boolean;
  ssh_host?: string;
  host?: string;
}

export interface ProjectControlProjectNode {
  node_id: string;
  path: string;
  branch: string;
  head_sha: string;
  head_subject: string;
  dirty: boolean | null;
  dirty_count: number;
  last_seen: string;
  online?: boolean;
  transport?: string;
  dirty_probe_error?: string;
}

export interface ProjectGoogleAsset {
  asset_id: string;
  title: string;
  kind: string;
  url: string;
  mime_type?: string;
  role?: string;
  source?: string;
  updated_at?: string;
}

export interface ProjectControlProject {
  project_id: string;
  aliases: string[];
  remote_url?: string;
  google_assets: ProjectGoogleAsset[];
  nodes: ProjectControlProjectNode[];
}

export interface ProjectControlCatalogResponse {
  success: boolean;
  current_node_id: string;
  default_executor: string;
  default_target_node: string;
  nodes: ProjectControlNode[];
  projects: ProjectControlProject[];
}

export interface ProjectControlChatPayload {
  message: string;
  project_id: string;
  preferred_node?: string;
  executor: "codex_cli" | "claude_cli";
  history?: Array<{ role: "system" | "user" | "assistant"; content: string }>;
}

export interface ProjectControlChatResponse {
  success: boolean;
  reply: string;
  provider: string;
  model: string;
  project_id: string;
  node_id: string;
  latency_ms: number;
  branch?: string;
  head?: string;
  dirty_count?: number;
}

export interface ProjectHandoffResponse {
  success: boolean;
  handoff: {
    project_id: string;
    source_node: string;
    target_node: string;
    backup_ref: string;
    backup_url: string;
    stdout?: string;
  };
}

export interface ProjectGoogleAssetsResponse {
  success: boolean;
  project_id: string;
  google_assets: ProjectGoogleAsset[];
}
