export interface GoogleStatusResponse {
  configured: boolean;
  connected: boolean;
  redirect_uri?: string | null;
  connected_at?: string | null;
  scopes: string[];
}

export interface GoogleAuthUrlResponse {
  auth_url: string;
  state: string;
  scopes: string[];
}

export interface GoogleDisconnectResponse {
  success: boolean;
}

export interface GoogleTaskListItem {
  id: string;
  title: string;
  updated?: string;
}

export interface GoogleTaskListsResponse {
  success: boolean;
  count: number;
  items: GoogleTaskListItem[];
}

export interface GoogleTaskItem {
  id: string;
  title: string;
  status?: string;
  due?: string;
  updated?: string;
  notes?: string;
}

export interface GoogleTasksResponse {
  success: boolean;
  count: number;
  items: GoogleTaskItem[];
}
