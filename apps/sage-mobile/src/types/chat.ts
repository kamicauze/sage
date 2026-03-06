export type ChatProvider = "brain" | "codex_cli" | "claude_cli";

export interface ChatAttachmentPayload {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  data_base64: string;
}

export interface ChatAttachmentPreview {
  name: string;
  mime_type: string;
  size_bytes: number;
}

export interface ChatRequestPayload {
  message: string;
  conversation_id?: string;
  provider?: ChatProvider | string;
  model?: string;
  system_prompt?: string;
  max_history_turns?: number;
  attachments?: ChatAttachmentPayload[];
}

export interface ChatResponse {
  success: boolean;
  conversation_id: string;
  reply: string;
  provider: string;
  model: string;
  message_count: number;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  latency_ms?: number;
}

export interface ChatHistoryMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatConversationResponse {
  success: boolean;
  conversation_id: string;
  messages: ChatHistoryMessage[];
  message_count: number;
}

// ── Session listing ──────────────────────────────────────────────────

export interface ConversationSummary {
  conversation_id: string;
  message_count: number;
  first_message: string;
}

// ── Model / provider registry ────────────────────────────────────────

export interface ModelOption {
  id: string;
  label: string;
  tier: "fast" | "mid" | "deep" | "auto";
}

export interface ProviderConfig {
  label: string;
  models: ModelOption[];
}

export type ProvidersMap = Record<string, ProviderConfig>;
