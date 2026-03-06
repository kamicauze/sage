export interface ChatHealthResponse {
  status: string;
  timestamp: string;
  services: Record<string, unknown>;
  capabilities: Record<string, unknown>;
}
