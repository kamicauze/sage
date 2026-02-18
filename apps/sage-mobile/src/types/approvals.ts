export type ApprovalRisk = "low" | "medium" | "high" | "critical";

export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

export interface ApprovalAction {
  type: string;
  target?: string | null;
  payload: Record<string, unknown>;
}

export interface ApprovalRecord {
  id: string;
  status: ApprovalStatus;
  title: string;
  summary: string;
  source: string;
  risk: ApprovalRisk;
  actions: ApprovalAction[];
  metadata: Record<string, unknown>;
  created_at: string;
  expires_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_reason?: string | null;
}

export interface PendingApprovalsResponse {
  success: boolean;
  count: number;
  items: ApprovalRecord[];
}

export interface ProposalResponse {
  success: boolean;
  proposal: ApprovalRecord;
}

export interface ApprovalDecisionRequest {
  decision: "approve" | "deny";
  reviewer: string;
  reason?: string;
}
