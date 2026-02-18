/**
 * Architect API Client
 *
 * TypeScript client for the Architect FastAPI backend.
 */

import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// API Client instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 2 minutes for LLM calls
});

// Types
export interface UsageStats {
  current_month: string;
  monthly_spend: number;
  monthly_limit: number;
  daily_spend: number;
  daily_limit: number;
  budget_percentage: number;
  recent_calls: Array<{
    timestamp: string;
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost: number;
    task: string;
  }>;
}

export interface MemoryStats {
  project_id: string;
  total_chunks: number;
  zones: Record<string, number>;
  collection_exists: boolean;
}

export interface RoutingDecision {
  route: 'LOCAL' | 'HYBRID' | 'CLOUD';
  score: number;
  reason: string;
  provider: string;
  model: string;
  estimated_cost_min: number;
  estimated_cost_max: number;
}

export interface PlanResponse {
  status: string;
  plan_content: string;
  plan_path: string;
  routing_decision: RoutingDecision;
  context_snippets: Array<{
    source: string;
    zone_name: string;
    content_preview: string;
  }>;
  summary: string;
}

export interface GitOptions {
  auto_commit: boolean;
  commit_message?: string | null;
  create_branch?: string | null;
  push_to_remote: boolean;
  files?: string[] | null;
}

export interface BuildResponse {
  status: string;
  artifacts: string[];
  files_built: string[];
  test_results: any;
  summary: string;
  git_result?: {
    success: boolean;
    workflow?: Array<[string, any]>;
    commit_hash?: string;
    error?: string;
  } | null;
}

export interface N8NCreateWorkflowRequest {
  name: string;
  nodes: Array<Record<string, any>>;
  connections: Record<string, any>;
  active?: boolean;
  confirm_create: boolean;
}

export interface MemorySearchResult {
  content: string;
  source: string;
  zone_name: string;
  role: string;
  distance: number;
}

export interface MemorySearchResponse {
  results: MemorySearchResult[];
  query: string;
  total_results: number;
}

export interface Zone {
  name: string;
  role: string;
  chunk_count: number;
  files: string[];
}

export interface ZonesResponse {
  project_id: string;
  total_chunks: number;
  zone_count: number;
  zones: Zone[];
}

export interface Project {
  id: string;
  name: string;
  description: string;
  manifest_path: string;
  stack: {
    primary: string;
    tags: string[];
  };
  memory_enabled: boolean;
  zone_count: number;
}

export interface ProjectsResponse {
  total_projects: number;
  projects: Project[];
}

// API Methods
export const architectAPI = {
  // Health check
  async health() {
    const response = await api.get('/');
    return response.data;
  },

  // Project management
  async listProjects(): Promise<ProjectsResponse> {
    const response = await api.get('/projects/');
    return response.data;
  },

  async getProject(projectId: string) {
    const response = await api.get(`/projects/${projectId}`);
    return response.data;
  },

  async getProjectZones(projectId: string) {
    const response = await api.get(`/projects/${projectId}/zones`);
    return response.data;
  },

  async getProjectConfig(projectId: string) {
    const response = await api.get(`/projects/${projectId}/config`);
    return response.data;
  },

  // Usage statistics
  async getUsageStats(dailyLimit = 5.0, monthlyLimit = 120.0): Promise<UsageStats> {
    const response = await api.get('/stats/usage', {
      params: { daily_limit: dailyLimit, monthly_limit: monthlyLimit },
    });
    return response.data;
  },

  async getUsageHistory(limit = 100) {
    const response = await api.get('/stats/usage/history', {
      params: { limit },
    });
    return response.data;
  },

  async getMemoryStats(projectId = 'sage_brain'): Promise<MemoryStats> {
    const response = await api.get('/stats/memory', {
      params: { project_id: projectId },
    });
    return response.data;
  },

  // Build operations
  async generatePlan(
    query: string,
    requestType: string = 'feature',
    manifestPath: string = 'architect/projects/sage.yaml'
  ): Promise<PlanResponse> {
    const response = await api.post('/builds/plan', {
      query,
      request_type: requestType,
      manifest_path: manifestPath,
    });
    return response.data;
  },

  async executeBuild(
    manifestPath: string = 'architect/projects/sage.yaml'
  ): Promise<BuildResponse> {
    const response = await api.post('/builds/build', {
      manifest_path: manifestPath,
    });
    return response.data;
  },

  async executeBuildWithGit(
    manifestPath: string = 'architect/projects/sage.yaml',
    gitOptions: GitOptions | null = null
  ): Promise<BuildResponse> {
    const response = await api.post('/builds/build-with-git', {
      manifest_path: manifestPath,
      git_options: gitOptions,
    });
    return response.data;
  },

  async getPlan(projectId: string) {
    const response = await api.get(`/builds/plan/${projectId}`);
    return response.data;
  },

  async getArtifacts(projectId: string) {
    const response = await api.get(`/builds/artifacts/${projectId}`);
    return response.data;
  },

  async deletePlan(projectId: string) {
    const response = await api.delete(`/builds/plan/${projectId}`);
    return response.data;
  },

  // n8n workflow automation (via MCP routes)
  async n8nTrigger(webhookPath: string, data: Record<string, any>) {
    const response = await api.post('/mcp/n8n/trigger', {
      webhook_path: webhookPath,
      data,
    });
    return response.data;
  },

  async n8nCreateWorkflow(request: N8NCreateWorkflowRequest) {
    const response = await api.post('/mcp/n8n/workflows/create', request);
    return response.data;
  },

  async n8nListWorkflows() {
    const response = await api.get('/mcp/n8n/workflows');
    return response.data;
  },

  async n8nExecuteWorkflow(workflowId: string, data: Record<string, any> = {}) {
    const response = await api.post('/mcp/n8n/workflows/execute', {
      workflow_id: workflowId,
      data,
    });
    return response.data;
  },

  async n8nExecutionStatus(executionId: string) {
    const response = await api.get(`/mcp/n8n/executions/${executionId}`);
    return response.data;
  },

  // Memory operations
  async searchMemory(
    query: string,
    projectId: string = 'sage_brain',
    nResults: number = 5,
    zoneFilter?: string
  ): Promise<MemorySearchResponse> {
    const response = await api.post('/memory/search', {
      query,
      project_id: projectId,
      n_results: nResults,
      zone_filter: zoneFilter,
    });
    return response.data;
  },

  async ingestFiles(
    filePaths: string[],
    manifestPath: string = 'architect/projects/sage.yaml'
  ) {
    const response = await api.post('/memory/ingest', {
      file_paths: filePaths,
      manifest_path: manifestPath,
    });
    return response.data;
  },

  async getZones(projectId: string = 'sage_brain'): Promise<ZonesResponse> {
    const response = await api.get(`/memory/zones/${projectId}`);
    return response.data;
  },

  async getIndexedFiles(projectId: string = 'sage_brain') {
    const response = await api.get(`/memory/files/${projectId}`);
    return response.data;
  },

  async deleteCollection(projectId: string) {
    const response = await api.delete(`/memory/collection/${projectId}`);
    return response.data;
  },
};

// WebSocket helper
export class BuildStreamClient {
  private ws: WebSocket | null = null;
  private clientId: string;
  private messageHandlers: Array<(data: any) => void> = [];

  constructor(clientId: string = `client-${Date.now()}`) {
    this.clientId = clientId;
  }

  connect() {
    const wsUrl = API_BASE_URL.replace('http', 'ws');
    this.ws = new WebSocket(`${wsUrl}/ws/${this.clientId}`);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.messageHandlers.forEach((handler) => handler(data));
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
    };
  }

  onMessage(handler: (data: any) => void) {
    this.messageHandlers.push(handler);
  }

  send(action: string, data: any = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...data }));
    }
  }

  startBuild(buildId: string) {
    this.send('start_build', { build_id: buildId });
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export default architectAPI;
