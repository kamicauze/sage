import { AppSettings } from "../storage/settings";
import {
  ApprovalDecisionRequest,
  ApprovalRecord,
  PendingApprovalsResponse,
  ProposalResponse,
} from "../types/approvals";
import {
  ChatConversationResponse,
  ChatRequestPayload,
  ChatResponse,
  ConversationSummary,
  ProvidersMap,
} from "../types/chat";
import { ChatHealthResponse } from "../types/health";
import { AiNewsResponse } from "../types/news";
import { VisionLatestResponse, VisionScanResponse } from "../types/vision";
import {
  GoogleAuthUrlResponse,
  GoogleDisconnectResponse,
  GoogleStatusResponse,
  GoogleTaskListsResponse,
  GoogleTasksResponse,
} from "../types/google";
import {
  GmailMessageResponse,
  GmailMessagesResponse,
  GmailModifyResponse,
  GmailSendResponse,
} from "../types/gmail";
import {
  AgentTaskDetailResponse,
  AgentTaskListResponse,
  AgentTaskStatsResponse,
} from "../types/tasks";
import { WebhookActionConfig } from "../types/webhooks";
import type {
  WebhookDeleteResponse,
  WebhookListResponse,
  WebhookRegisterResponse,
} from "../types/webhooks";
import type {
  VaultDeleteResponse,
  VaultKeysResponse,
  VaultStoreResponse,
} from "../types/vault";
import {
  BrainControlAuditFilter,
  BrainControlAuditResponse,
  BrainControlConfigRequest,
  BrainControlCommandRequest,
  BrainControlStateResponse,
} from "../types/control";
import type {
  AgentPermissionsResponse,
  PermissionsAuditResponse,
  PermissionsProfilesResponse,
  PermissionsUpdateRequest,
} from "../types/permissions";
import type {
  ProjectControlCatalogResponse,
  ProjectControlChatPayload,
  ProjectControlChatResponse,
  ProjectGoogleAssetsResponse,
  ProjectHandoffResponse,
} from "../types/projectControl";

interface BaseUrlAttempt {
  primary: string;
  all: string[];
}

interface ChatStreamHandlers {
  onMeta?: (payload: Record<string, unknown>) => void | Promise<void>;
  onStatus?: (phase: string) => void | Promise<void>;
  onDelta?: (text: string) => void | Promise<void>;
}

export function canUseSSEStreamingRuntime(): boolean {
  const g = globalThis as unknown as {
    ReadableStream?: { prototype?: { getReader?: unknown } };
    TextDecoder?: unknown;
  };
  return (
    typeof g.TextDecoder === "function" &&
    typeof g.ReadableStream?.prototype?.getReader === "function"
  );
}

function normalizeBaseUrl(rawBaseUrl: string): string {
  const baseUrl = rawBaseUrl.trim().replace(/\/+$/, "");
  if (!baseUrl) {
    throw new Error("Architect API URL is required");
  }
  if (!/^https?:\/\//i.test(baseUrl)) {
    throw new Error("Architect API URL must start with http:// or https://");
  }
  return `${baseUrl}/`;
}

function getBaseUrlAttempt(settings: AppSettings): BaseUrlAttempt {
  const primary = normalizeBaseUrl(settings.baseUrl);
  const tailscaleRaw = settings.tailscaleBaseUrl?.trim() ?? "";
  const tailscale = tailscaleRaw ? normalizeBaseUrl(tailscaleRaw) : "";
  const ordered = settings.preferTailscale
    ? [tailscale, primary]
    : [primary, tailscale];

  const all = Array.from(new Set(ordered.filter(Boolean)));
  return {
    primary: all[0] || primary,
    all,
  };
}

function isNetworkError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return /network request failed|failed to fetch|timeout|timed out/i.test(error.message || "");
}

async function parseErrorMessage(response: Response): Promise<string> {
  const rawBody = await response.text();
  const body = rawBody ? tryParseJSON(rawBody) : null;
  const maybeMessage =
    body && typeof body === "object"
      ? (body as Record<string, unknown>).detail ||
        (body as Record<string, unknown>).error ||
        (body as Record<string, unknown>).message
      : undefined;

  return typeof maybeMessage === "string"
    ? maybeMessage
    : `Architect request failed (${response.status})`;
}

async function requestJSON<T>(
  settings: AppSettings,
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const cleanPath = path.replace(/^\/+/, "");
  const token = settings.apiToken.trim();
  const { all: baseUrls } = getBaseUrlAttempt(settings);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers["x-architect-token"] = token;
  }

  let lastNetworkError: Error | null = null;
  for (const baseUrl of baseUrls) {
    const url = `${baseUrl}${cleanPath}`;
    try {
      const response = await fetch(url, {
        ...init,
        headers,
      });
      if (!response.ok) {
        throw new Error(await parseErrorMessage(response));
      }

      const rawBody = await response.text();
      const body = rawBody ? tryParseJSON(rawBody) : null;
      return body as T;
    } catch (error) {
      if (isNetworkError(error)) {
        lastNetworkError = error as Error;
        continue;
      }
      throw error;
    }
  }

  if (lastNetworkError) {
    throw lastNetworkError;
  }
  throw new Error("Architect request failed");
}

function tryParseJSON(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export async function checkHealth(settings: AppSettings): Promise<{ status: string }> {
  return requestJSON<{ status: string }>(settings, "/");
}

export async function fetchPendingApprovals(settings: AppSettings): Promise<ApprovalRecord[]> {
  const response = await requestJSON<PendingApprovalsResponse>(settings, "/approvals/pending");
  return response.items;
}

export async function fetchProposal(
  settings: AppSettings,
  proposalId: string
): Promise<ApprovalRecord> {
  const response = await requestJSON<ProposalResponse>(settings, `/approvals/${proposalId}`);
  return response.proposal;
}

export async function submitProposalDecision(
  settings: AppSettings,
  proposalId: string,
  decision: ApprovalDecisionRequest
): Promise<ApprovalRecord> {
  const response = await requestJSON<ProposalResponse>(
    settings,
    `/approvals/${proposalId}/decision`,
    {
      method: "POST",
      body: JSON.stringify(decision),
    }
  );

  return response.proposal;
}

export async function sendChatMessage(
  settings: AppSettings,
  payload: ChatRequestPayload
): Promise<ChatResponse> {
  return requestJSON<ChatResponse>(settings, "/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchProjectControlCatalog(
  settings: AppSettings
): Promise<ProjectControlCatalogResponse> {
  return requestJSON<ProjectControlCatalogResponse>(settings, "/project-control/catalog");
}

export async function sendProjectControlChat(
  settings: AppSettings,
  payload: ProjectControlChatPayload
): Promise<ProjectControlChatResponse> {
  return requestJSON<ProjectControlChatResponse>(settings, "/project-control/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function handoffProject(
  settings: AppSettings,
  payload: { project_id: string; source_node?: string; target_node?: string }
): Promise<ProjectHandoffResponse> {
  return requestJSON<ProjectHandoffResponse>(settings, "/project-control/projects/handoff", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchProjectGoogleAssets(
  settings: AppSettings,
  projectId: string
): Promise<ProjectGoogleAssetsResponse> {
  return requestJSON<ProjectGoogleAssetsResponse>(
    settings,
    `/project-control/projects/${encodeURIComponent(projectId)}/google-assets`
  );
}

export async function linkProjectGoogleAsset(
  settings: AppSettings,
  projectId: string,
  payload: {
    drive_url?: string;
    asset_id?: string;
    title?: string;
    kind?: string;
    mime_type?: string;
    role?: string;
    source?: string;
  }
): Promise<ProjectGoogleAssetsResponse> {
  return requestJSON<ProjectGoogleAssetsResponse>(
    settings,
    `/project-control/projects/${encodeURIComponent(projectId)}/google-assets`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

function parseSSEBlock(block: string): Record<string, unknown> | null {
  const lines = block
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (!lines.length) return null;
  const dataLines = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim());
  if (!dataLines.length) return null;

  const raw = dataLines.join("\n");
  const parsed = tryParseJSON(raw);
  if (!parsed || typeof parsed !== "object") return null;
  return parsed as Record<string, unknown>;
}

function nextSSEBlock(buffer: string): { block: string; rest: string } | null {
  const idxCrlf = buffer.indexOf("\r\n\r\n");
  const idxLf = buffer.indexOf("\n\n");

  if (idxCrlf === -1 && idxLf === -1) return null;

  const useCrlf = idxCrlf !== -1 && (idxLf === -1 || idxCrlf < idxLf);
  const index = useCrlf ? idxCrlf : idxLf;
  const sepLength = useCrlf ? 4 : 2;
  return {
    block: buffer.slice(0, index),
    rest: buffer.slice(index + sepLength),
  };
}

async function yieldToUIThread(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}

function parseStreamingDonePayload(event: Record<string, unknown>): ChatResponse {
  return {
    success: true,
    conversation_id: typeof event.conversation_id === "string" ? event.conversation_id : "",
    reply: typeof event.reply === "string" ? event.reply : "",
    provider: typeof event.provider === "string" ? event.provider : "unknown",
    model: typeof event.model === "string" ? event.model : "unknown",
    message_count: typeof event.message_count === "number" ? event.message_count : 0,
    input_tokens: typeof event.input_tokens === "number" ? event.input_tokens : undefined,
    output_tokens: typeof event.output_tokens === "number" ? event.output_tokens : undefined,
    cost: typeof event.cost === "number" ? event.cost : undefined,
    latency_ms: typeof event.latency_ms === "number" ? event.latency_ms : undefined,
  };
}

async function processSSEBuffer(
  buffer: string,
  handlers: ChatStreamHandlers,
  options: { yieldBetweenTokens?: boolean } = {}
): Promise<{ rest: string; donePayload: ChatResponse | null }> {
  let current = buffer;
  let donePayload: ChatResponse | null = null;

  while (true) {
    const next = nextSSEBlock(current);
    if (!next) break;
    const block = next.block;
    current = next.rest;
    const event = parseSSEBlock(block);
    if (!event) continue;

    const type = typeof event.type === "string" ? event.type : "";
    if (type === "meta") {
      await handlers.onMeta?.(event);
    } else if (type === "status") {
      const phase = typeof event.phase === "string" ? event.phase : "";
      await handlers.onStatus?.(phase);
    } else if (type === "delta") {
      const text = typeof event.text === "string" ? event.text : "";
      if (text) {
        await handlers.onDelta?.(text);
        if (options.yieldBetweenTokens) {
          await yieldToUIThread();
        }
      }
    } else if (type === "done") {
      donePayload = parseStreamingDonePayload(event);
    } else if (type === "error") {
      const errorText =
        typeof event.error === "string" ? event.error : "Chat stream failed";
      throw new Error(errorText);
    }
  }

  return { rest: current, donePayload };
}

function parseXHRErrorMessage(responseText: string, status: number): string {
  const parsed = responseText ? tryParseJSON(responseText) : null;
  if (parsed && typeof parsed === "object") {
    const body = parsed as Record<string, unknown>;
    const detail = body.detail || body.error || body.message;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return `Architect request failed (${status})`;
}

async function streamChatMessageViaXHR(
  url: string,
  headers: Record<string, string>,
  payload: ChatRequestPayload,
  handlers: ChatStreamHandlers = {}
): Promise<ChatResponse> {
  return new Promise<ChatResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let buffer = "";
    let consumed = 0;
    let donePayload: ChatResponse | null = null;
    let parseChain: Promise<void> = Promise.resolve();
    let settled = false;

    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      reject(error);
    };

    const succeed = (response: ChatResponse) => {
      if (settled) return;
      settled = true;
      resolve(response);
    };

    const queueProcessPending = () => {
      const raw = xhr.responseText || "";
      if (raw.length <= consumed) return;
      const chunk = raw.slice(consumed);
      consumed = raw.length;
      buffer += chunk;
      parseChain = parseChain
        .then(() => processSSEBuffer(buffer, handlers, { yieldBetweenTokens: false }))
        .then((result) => {
          buffer = result.rest;
          if (result.donePayload) {
            donePayload = result.donePayload;
          }
        })
        .catch((error) => fail(error instanceof Error ? error : new Error("Chat stream failed")));
    };

    xhr.open("POST", url, true);
    xhr.timeout = 120000;
    Object.entries(headers).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });

    xhr.onprogress = queueProcessPending;
    xhr.onerror = () => fail(new Error("Network request failed"));
    xhr.ontimeout = () => fail(new Error("Request timed out"));
    xhr.onreadystatechange = () => {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        queueProcessPending();
        void parseChain
          .then(() => {
            if (xhr.status < 200 || xhr.status >= 300) {
              fail(new Error(parseXHRErrorMessage(xhr.responseText || "", xhr.status)));
              return;
            }
            if (donePayload) {
              succeed(donePayload);
              return;
            }
            fail(new Error("Chat stream ended before completion"));
          })
          .catch((error) =>
            fail(error instanceof Error ? error : new Error("Chat stream failed"))
          );
      }
    };

    try {
      xhr.send(JSON.stringify(payload));
    } catch (error) {
      fail(error instanceof Error ? error : new Error("Chat stream failed"));
    }
  });
}

export async function streamChatMessage(
  settings: AppSettings,
  payload: ChatRequestPayload,
  handlers: ChatStreamHandlers = {}
): Promise<ChatResponse> {
  const token = settings.apiToken.trim();
  const cleanPath = "chat/stream";
  const { all: baseUrls } = getBaseUrlAttempt(settings);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers["x-architect-token"] = token;
  }

  let lastNetworkError: Error | null = null;
  for (const baseUrl of baseUrls) {
    const url = `${baseUrl}${cleanPath}`;
    try {
      const nativeRuntimeStreaming = canUseSSEStreamingRuntime();
      if (!nativeRuntimeStreaming) {
        return await streamChatMessageViaXHR(url, headers, payload, handlers);
      }

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(await parseErrorMessage(response));
      }

      if (!response.body || typeof response.body.getReader !== "function") {
        return await streamChatMessageViaXHR(url, headers, payload, handlers);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let donePayload: ChatResponse | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const result = await processSSEBuffer(buffer, handlers, {
          yieldBetweenTokens: true,
        });
        buffer = result.rest;
        if (result.donePayload) {
          donePayload = result.donePayload;
        }
      }

      buffer += decoder.decode();
      const finalResult = await processSSEBuffer(buffer, handlers);
      donePayload = finalResult.donePayload || donePayload;

      if (donePayload) return donePayload;
      throw new Error("Chat stream ended before completion");
    } catch (error) {
      if (isNetworkError(error)) {
        lastNetworkError = error as Error;
        continue;
      }
      throw error;
    }
  }

  if (lastNetworkError) throw lastNetworkError;
  throw new Error("Failed to stream chat");
}

export async function fetchChatHealth(settings: AppSettings): Promise<ChatHealthResponse> {
  return requestJSON<ChatHealthResponse>(settings, "/chat/health");
}

export async function fetchConversation(
  settings: AppSettings,
  conversationId: string
): Promise<ChatConversationResponse> {
  const id = encodeURIComponent(conversationId.trim());
  return requestJSON<ChatConversationResponse>(settings, `/chat/${id}`);
}

export async function fetchConversations(
  settings: AppSettings,
  limit = 50
): Promise<ConversationSummary[]> {
  const data = await requestJSON<{ success: boolean; conversations: ConversationSummary[] }>(
    settings,
    `/chat/conversations?limit=${limit}`
  );
  return data.conversations;
}

export async function fetchAvailableModels(
  settings: AppSettings
): Promise<ProvidersMap> {
  const data = await requestJSON<{ success: boolean; providers: ProvidersMap }>(
    settings,
    "/chat/models"
  );
  return data.providers;
}

export async function fetchBrainControlState(
  settings: AppSettings
): Promise<BrainControlStateResponse> {
  return requestJSON<BrainControlStateResponse>(settings, "/chat/control");
}

export async function fetchBrainControlAudit(
  settings: AppSettings,
  limit = 50,
  auditType: BrainControlAuditFilter = "all"
): Promise<BrainControlAuditResponse> {
  const safeLimit = Math.max(1, Math.min(limit, 200));
  const safeType = encodeURIComponent(auditType);
  return requestJSON<BrainControlAuditResponse>(
    settings,
    `/chat/control/audit?limit=${safeLimit}&type=${safeType}`
  );
}

export async function updateBrainControlConfig(
  settings: AppSettings,
  payload: BrainControlConfigRequest
): Promise<BrainControlStateResponse> {
  return requestJSON<BrainControlStateResponse>(settings, "/chat/control/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function sendBrainControlCommand(
  settings: AppSettings,
  payload: BrainControlCommandRequest
): Promise<BrainControlStateResponse> {
  return requestJSON<BrainControlStateResponse>(settings, "/chat/control/command", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAiNews(
  settings: AppSettings,
  options: Partial<{ limit: number; maxAgeHours: number; includeX: boolean; query: string }> = {}
): Promise<AiNewsResponse> {
  const limit = Math.max(1, Math.min(options.limit ?? 25, 80));
  const maxAgeHours = Math.max(1, Math.min(options.maxAgeHours ?? 72, 336));
  const includeX = options.includeX ?? true;
  const query = encodeURIComponent((options.query ?? "ai news").trim() || "ai news");
  const path = `/news/ai?limit=${limit}&max_age_hours=${maxAgeHours}&include_x=${includeX ? "true" : "false"}&query=${query}`;
  return requestJSON<AiNewsResponse>(settings, path);
}

export async function fetchVisionLatest(
  settings: AppSettings,
  location = "office"
): Promise<VisionLatestResponse> {
  const room = encodeURIComponent(location.trim() || "office");
  return requestJSON<VisionLatestResponse>(settings, `/chat/vision/latest?location=${room}`);
}

export async function requestVisionScan(
  settings: AppSettings,
  location = "office"
): Promise<VisionScanResponse> {
  return requestJSON<VisionScanResponse>(settings, "/chat/vision/request", {
    method: "POST",
    body: JSON.stringify({ location }),
  });
}

export async function fetchGoogleStatus(
  settings: AppSettings
): Promise<GoogleStatusResponse> {
  return requestJSON<GoogleStatusResponse>(settings, "/google/status");
}

export async function fetchGoogleAuthUrl(
  settings: AppSettings
): Promise<GoogleAuthUrlResponse> {
  return requestJSON<GoogleAuthUrlResponse>(settings, "/google/auth/url");
}

export async function disconnectGoogleAccount(
  settings: AppSettings
): Promise<GoogleDisconnectResponse> {
  return requestJSON<GoogleDisconnectResponse>(settings, "/google/disconnect", {
    method: "POST",
  });
}

export async function fetchGoogleTaskLists(
  settings: AppSettings
): Promise<GoogleTaskListsResponse> {
  return requestJSON<GoogleTaskListsResponse>(settings, "/google/tasks/lists");
}

export async function fetchGoogleTasksForList(
  settings: AppSettings,
  taskListId: string,
  maxResults = 100
): Promise<GoogleTasksResponse> {
  const encoded = encodeURIComponent(taskListId);
  const safeMax = Math.max(1, Math.min(maxResults, 100));
  return requestJSON<GoogleTasksResponse>(
    settings,
    `/google/tasks/list/${encoded}?max_results=${safeMax}`
  );
}

// --- Gmail ---

export async function fetchGmailMessages(
  settings: AppSettings,
  options: Partial<{ query: string; maxResults: number; label: string }> = {}
): Promise<GmailMessagesResponse> {
  const maxResults = Math.max(1, Math.min(options.maxResults ?? 10, 50));
  const label = encodeURIComponent((options.label ?? "INBOX").trim());
  const q = options.query ? `&q=${encodeURIComponent(options.query)}` : "";
  return requestJSON<GmailMessagesResponse>(
    settings,
    `/google/gmail/messages?max_results=${maxResults}&label=${label}${q}`
  );
}

export async function fetchGmailMessage(
  settings: AppSettings,
  messageId: string,
  format: "full" | "metadata" | "minimal" = "full"
): Promise<GmailMessageResponse> {
  const encoded = encodeURIComponent(messageId);
  return requestJSON<GmailMessageResponse>(
    settings,
    `/google/gmail/messages/${encoded}?format=${format}`
  );
}

export async function sendGmail(
  settings: AppSettings,
  payload: { to: string; subject: string; body: string; cc?: string; bcc?: string }
): Promise<GmailSendResponse> {
  return requestJSON<GmailSendResponse>(settings, "/google/gmail/send", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function modifyGmailMessage(
  settings: AppSettings,
  messageId: string,
  payload: { add_labels?: string[]; remove_labels?: string[] }
): Promise<GmailModifyResponse> {
  const encoded = encodeURIComponent(messageId);
  return requestJSON<GmailModifyResponse>(
    settings,
    `/google/gmail/messages/${encoded}/modify`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

// --- Agent Tasks ---

export async function fetchAgentTasks(
  settings: AppSettings,
  options: Partial<{ status: string; limit: number }> = {}
): Promise<AgentTaskListResponse> {
  const limit = Math.max(1, Math.min(options.limit ?? 20, 100));
  const statusParam = options.status ? `&status=${encodeURIComponent(options.status)}` : "";
  return requestJSON<AgentTaskListResponse>(
    settings,
    `/tasks/?limit=${limit}${statusParam}`
  );
}

export async function fetchAgentTaskDetail(
  settings: AppSettings,
  taskId: string
): Promise<AgentTaskDetailResponse> {
  return requestJSON<AgentTaskDetailResponse>(
    settings,
    `/tasks/${encodeURIComponent(taskId)}`
  );
}

export async function fetchAgentTaskStats(
  settings: AppSettings
): Promise<AgentTaskStatsResponse> {
  return requestJSON<AgentTaskStatsResponse>(settings, "/tasks/stats");
}

// --- Webhooks ---

export async function fetchWebhooks(
  settings: AppSettings
): Promise<WebhookListResponse> {
  return requestJSON<WebhookListResponse>(settings, "/webhooks/");
}

export async function registerWebhook(
  settings: AppSettings,
  payload: { name: string; source?: string; secret?: string; action: WebhookActionConfig; enabled?: boolean }
): Promise<WebhookRegisterResponse> {
  return requestJSON<WebhookRegisterResponse>(settings, "/webhooks/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteWebhook(
  settings: AppSettings,
  hookId: string
): Promise<WebhookDeleteResponse> {
  return requestJSON<WebhookDeleteResponse>(
    settings,
    `/webhooks/${encodeURIComponent(hookId)}`,
    { method: "DELETE" }
  );
}

// --- Vault ---

export async function fetchVaultKeys(
  settings: AppSettings
): Promise<VaultKeysResponse> {
  return requestJSON<VaultKeysResponse>(settings, "/vault/keys");
}

export async function storeVaultCredential(
  settings: AppSettings,
  name: string,
  value: string
): Promise<VaultStoreResponse> {
  return requestJSON<VaultStoreResponse>(settings, "/vault/store", {
    method: "POST",
    body: JSON.stringify({ name, value }),
  });
}

export async function deleteVaultCredential(
  settings: AppSettings,
  name: string
): Promise<VaultDeleteResponse> {
  return requestJSON<VaultDeleteResponse>(
    settings,
    `/vault/${encodeURIComponent(name)}`,
    { method: "DELETE" }
  );
}

// --- Agent Permissions ---

export async function fetchAgentPermissions(
  settings: AppSettings
): Promise<AgentPermissionsResponse> {
  return requestJSON<AgentPermissionsResponse>(settings, "/agent/permissions");
}

export async function updateAgentPermissions(
  settings: AppSettings,
  patch: PermissionsUpdateRequest
): Promise<AgentPermissionsResponse> {
  return requestJSON<AgentPermissionsResponse>(settings, "/agent/permissions", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export async function fetchPermissionProfiles(
  settings: AppSettings
): Promise<PermissionsProfilesResponse> {
  return requestJSON<PermissionsProfilesResponse>(
    settings,
    "/agent/permissions/profiles"
  );
}

export async function applyPermissionProfile(
  settings: AppSettings,
  profileName: string
): Promise<AgentPermissionsResponse> {
  return requestJSON<AgentPermissionsResponse>(
    settings,
    `/agent/permissions/profile/${encodeURIComponent(profileName)}`,
    { method: "PUT" }
  );
}

export async function fetchPermissionsAudit(
  settings: AppSettings
): Promise<PermissionsAuditResponse> {
  return requestJSON<PermissionsAuditResponse>(
    settings,
    "/agent/permissions/audit?limit=20"
  );
}
