import { AppSettings } from "../storage/settings";
import {
  ApprovalDecisionRequest,
  ApprovalRecord,
  PendingApprovalsResponse,
  ProposalResponse,
} from "../types/approvals";
import { ChatRequestPayload, ChatResponse } from "../types/chat";

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

async function requestJSON<T>(
  settings: AppSettings,
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const baseUrl = normalizeBaseUrl(settings.baseUrl);
  const cleanPath = path.replace(/^\/+/, "");
  const url = `${baseUrl}${cleanPath}`;
  const token = settings.apiToken.trim();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
    headers["x-architect-token"] = token;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  const rawBody = await response.text();
  const body = rawBody ? tryParseJSON(rawBody) : null;

  if (!response.ok) {
    const maybeMessage =
      body && typeof body === "object"
        ? (body as Record<string, unknown>).detail ||
          (body as Record<string, unknown>).error ||
          (body as Record<string, unknown>).message
        : undefined;

    throw new Error(
      typeof maybeMessage === "string"
        ? maybeMessage
        : `Architect request failed (${response.status})`
    );
  }

  return body as T;
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
