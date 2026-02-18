export interface ChatRequestPayload {
  message: string;
  conversation_id?: string;
  provider?: string;
  model?: string;
  system_prompt?: string;
  max_history_turns?: number;
}

export interface ChatResponse {
  success: boolean;
  conversation_id: string;
  reply: string;
  provider: string;
  model: string;
  message_count: number;
}
