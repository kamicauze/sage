export type PermissionProfile = "safe" | "standard" | "power";

export interface ToolPermission {
  name: string;
  description: string;
  needs_approval: boolean;
  denied: boolean;
  force_approval: boolean;
}

export interface AgentPermissionsResponse {
  success: boolean;
  mode: string;
  active_profile: PermissionProfile | null;
  deny_tools: string[];
  force_approval_tools: string[];
  allow_write_roots: string[];
  tools: ToolPermission[];
}

export interface PermissionProfileDef {
  name: PermissionProfile;
  label: string;
  description: string;
  mode: string;
  deny_tools: string[];
  force_approval_tools: string[];
  allow_write_roots: string[];
}

export interface PermissionsProfilesResponse {
  success: boolean;
  profiles: PermissionProfileDef[];
}

export interface PermissionAuditEntry {
  timestamp: string;
  action: string;
  changes: Record<string, unknown>;
  source: string;
}

export interface PermissionsAuditResponse {
  success: boolean;
  entries: PermissionAuditEntry[];
}

export interface PermissionsUpdateRequest {
  mode?: string;
  deny_tools?: string[];
  force_approval_tools?: string[];
  allow_write_roots?: string[];
}
