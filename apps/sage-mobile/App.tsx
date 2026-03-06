import React, { useCallback, useEffect, useState } from "react";
import { Alert, Linking, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { StatusBar } from "expo-status-bar";
import {
  canUseSSEStreamingRuntime,
  checkHealth,
  deleteVaultCredential,
  deleteWebhook,
  fetchAgentTaskDetail,
  fetchAgentTasks,
  fetchAgentTaskStats,
  fetchAiNews,
  fetchBrainControlAudit,
  fetchBrainControlState,
  fetchAvailableModels,
  fetchConversation,
  fetchConversations,
  fetchGmailMessage,
  fetchGmailMessages,
  fetchGoogleAuthUrl,
  fetchGoogleStatus,
  fetchGoogleTaskLists,
  fetchGoogleTasksForList,
  fetchChatHealth,
  fetchPendingApprovals,
  fetchVaultKeys,
  fetchVisionLatest,
  fetchWebhooks,
  modifyGmailMessage,
  sendChatMessage,
  sendGmail,
  disconnectGoogleAccount,
  sendBrainControlCommand,
  requestVisionScan,
  storeVaultCredential,
  streamChatMessage,
  submitProposalDecision,
  updateBrainControlConfig,
  fetchAgentPermissions,
  fetchPermissionProfiles,
  fetchProjectControlCatalog,
  fetchPermissionsAudit,
  applyPermissionProfile,
  handoffProject,
  updateAgentPermissions,
  sendProjectControlChat,
} from "./src/api/architect";
import {
  AppSettings,
  DEFAULT_SETTINGS,
  loadSettings,
  saveSettings,
} from "./src/storage/settings";
import {
  ChatBubble,
  ProviderChatSession,
  loadChatSession,
  saveChatSession,
} from "./src/storage/chatSession";
import { loadPlanTasks, savePlanTasks } from "./src/storage/plan";
import { ApprovalRecord } from "./src/types/approvals";
import { TabBar, TabName } from "./src/components/navigation/TabBar";
import { HeaderNav } from "./src/components/navigation/HeaderNav";
import { ErrorBoundary } from "./src/components/ErrorBoundary";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { ApprovalsScreen } from "./src/screens/ApprovalsScreen";
import { ChatScreen } from "./src/screens/ChatScreen";
import { ControlScreen } from "./src/screens/ControlScreen";
import { GmailScreen } from "./src/screens/GmailScreen";
import { AgentTasksScreen } from "./src/screens/AgentTasksScreen";
import { NewsScreen } from "./src/screens/NewsScreen";
import { PlanScreen } from "./src/screens/PlanScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { PermissionsScreen } from "./src/screens/PermissionsScreen";
import { COLORS } from "./src/constants/theme";
import { ChatHealthResponse } from "./src/types/health";
import { ChatAttachmentPayload, ChatAttachmentPreview, ChatProvider, ProvidersMap } from "./src/types/chat";
import {
  SessionIndexEntry,
  loadSessionIndex,
  upsertSessionEntry,
  removeSessionEntry,
} from "./src/storage/sessionIndex";
import { AiNewsItem } from "./src/types/news";
import {
  BrainControlAuditEntry,
  BrainControlAuditFilter,
  BrainControlState,
} from "./src/types/control";
import { GmailMessageRef, GmailMessage } from "./src/types/gmail";
import { AgentTask, AgentTaskObservation, AgentTaskStatus } from "./src/types/tasks";
import { WebhookHook } from "./src/types/webhooks";
import { NewPlanTaskInput, PlanTask } from "./src/types/plan";
import { VisionLatestResponse } from "./src/types/vision";
import { GoogleStatusResponse } from "./src/types/google";
import type {
  AgentPermissionsResponse,
  PermissionAuditEntry,
  PermissionProfile,
  PermissionProfileDef,
} from "./src/types/permissions";
import type {
  ProjectControlCatalogResponse,
  ProjectThreadContext,
} from "./src/types/projectControl";

type ChatRole = "system" | "user" | "assistant";
interface ChatComposerSubmit {
  text: string;
  attachments?: ChatAttachmentPayload[];
}

const PROVIDER_LABELS: Record<ChatProvider, string> = {
  brain: "Brain",
  codex_cli: "Codex",
  claude_cli: "Claude",
};

const PROVIDER_MODEL_HINTS: Partial<Record<ChatProvider, string>> = {
  codex_cli: "codex",
  claude_cli: "claude",
};
const PROJECT_MODE_DEFAULTS = {
  projectId: "babish",
  preferredNode: "macbook",
} as const;
const APPROVALS_POLL_INTERVAL_MS = 10000;

function makeEmptyProviderSession(): ProviderChatSession {
  return {
    conversationId: null,
    messages: [],
    threadContext: { mode: "conversation" },
  };
}

function makeDefaultSessions(): Record<ChatProvider, ProviderChatSession> {
  return {
    brain: makeEmptyProviderSession(),
    codex_cli: makeEmptyProviderSession(),
    claude_cli: makeEmptyProviderSession(),
  };
}

function makeDefaultThreadContext(): ProjectThreadContext {
  return { mode: "conversation" };
}

function getDefaultProjectSelection(
  catalog: ProjectControlCatalogResponse | null
): Pick<ProjectThreadContext, "project_id" | "preferred_node"> {
  const projects = catalog?.projects || [];
  const preferredProject =
    projects.find((project) => project.project_id === PROJECT_MODE_DEFAULTS.projectId) || projects[0];
  const preferredNode =
    preferredProject?.nodes.find((node) => node.node_id === PROJECT_MODE_DEFAULTS.preferredNode)?.node_id ||
    preferredProject?.nodes[0]?.node_id ||
    catalog?.default_target_node;
  return {
    project_id: preferredProject?.project_id,
    preferred_node: preferredNode,
  };
}

function createMessage(
  role: ChatRole,
  text: string,
  attachments: ChatAttachmentPreview[] = []
): ChatBubble {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    timestamp: new Date().toISOString(),
    attachments: role === "user" && attachments.length ? attachments : undefined,
  };
}

function toAttachmentPreviews(
  attachments: ChatAttachmentPayload[] | undefined
): ChatAttachmentPreview[] {
  if (!attachments || !attachments.length) return [];
  return attachments.map((item) => ({
    name: item.name,
    mime_type: item.mime_type,
    size_bytes: item.size_bytes,
  }));
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const raw = error.message || "";
    if (/network request failed/i.test(raw)) {
      return (
        "Network request failed. Check Settings API URL (use your PC LAN IP, not localhost), " +
        "and ensure Architect API is running on port 8000."
      );
    }
    return raw;
  }
  return "Unexpected error";
}

function parseDateKey(dateKey: string): Date {
  const [yearRaw, monthRaw, dayRaw] = dateKey.split("-");
  const year = Number.parseInt(yearRaw || "", 10);
  const month = Number.parseInt(monthRaw || "", 10);
  const day = Number.parseInt(dayRaw || "", 10);

  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return new Date();
  }

  return new Date(year, month - 1, day);
}

function dateKeyFromIso(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "";
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dueIsoForDateKey(dateKey: string, dueTime?: string): string {
  const date = parseDateKey(dateKey);
  if (dueTime) {
    const [hourRaw, minuteRaw] = dueTime.split(":");
    const hour = Number.parseInt(hourRaw || "", 10);
    const minute = Number.parseInt(minuteRaw || "", 10);
    if (
      Number.isFinite(hour) &&
      Number.isFinite(minute) &&
      hour >= 0 &&
      hour <= 23 &&
      minute >= 0 &&
      minute <= 59
    ) {
      date.setHours(hour, minute, 0, 0);
      return date.toISOString();
    }
  }
  const now = new Date();
  date.setHours(now.getHours(), now.getMinutes(), 0, 0);
  return date.toISOString();
}

function snoozeDueIsoByOneDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  date.setDate(date.getDate() + 1);
  return date.toISOString();
}

function normalizeGoogleDueIso(due?: string): string {
  if (typeof due === "string" && due.trim()) {
    const parsed = new Date(due);
    if (!Number.isNaN(parsed.getTime())) return parsed.toISOString();
  }
  return new Date().toISOString();
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabName>("chat");

  // Settings State
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [connectionTesting, setConnectionTesting] = useState(false);

  // Approvals State
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listRefreshing, setListRefreshing] = useState(false);

  // Chat State
  const [chatProvider, setChatProvider] = useState<ChatProvider>("brain");
  const [chatSessions, setChatSessions] = useState<Record<ChatProvider, ProviderChatSession>>(
    makeDefaultSessions()
  );
  const [chatSending, setChatSending] = useState(false);
  const [chatSyncing, setChatSyncing] = useState(false);
  const [chatHealth, setChatHealth] = useState<ChatHealthResponse | null>(null);
  const [chatPhase, setChatPhase] = useState<string | null>(null);
  const [lastChatModel, setLastChatModel] = useState<string | null>(null);
  const [lastChatLatencyMs, setLastChatLatencyMs] = useState<number | null>(null);
  const [chatModel, setChatModel] = useState("auto");
  const [availableProviders, setAvailableProviders] = useState<ProvidersMap>({});
  const [projectCatalog, setProjectCatalog] = useState<ProjectControlCatalogResponse | null>(null);
  const [sessionIndex, setSessionIndex] = useState<SessionIndexEntry[]>([]);
  const [showSessionList, setShowSessionList] = useState(false);
  const [sessionTotals, setSessionTotals] = useState({ cost: 0, inputTokens: 0, outputTokens: 0 });
  const [chatHealthError, setChatHealthError] = useState<string | null>(null);
  const [controlState, setControlState] = useState<BrainControlState | null>(null);
  const [controlAudit, setControlAudit] = useState<BrainControlAuditEntry[]>([]);
  const [controlAuditFilter, setControlAuditFilter] =
    useState<BrainControlAuditFilter>("all");
  const [controlMqttOnline, setControlMqttOnline] = useState(false);
  const [controlMqttError, setControlMqttError] = useState<string | null>(null);
  const [controlLoading, setControlLoading] = useState(false);
  const [controlMutating, setControlMutating] = useState(false);
  const [newsItems, setNewsItems] = useState<AiNewsItem[]>([]);
  const [newsGeneratedAt, setNewsGeneratedAt] = useState<string | null>(null);
  const [newsSourceErrors, setNewsSourceErrors] = useState<string[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsRefreshing, setNewsRefreshing] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [googleStatus, setGoogleStatus] = useState<GoogleStatusResponse | null>(null);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConnecting, setGoogleConnecting] = useState(false);
  const [planGoogleSyncing, setPlanGoogleSyncing] = useState(false);
  const [planTasks, setPlanTasks] = useState<PlanTask[]>([]);
  const [planLoading, setPlanLoading] = useState(true);
  const [visionLatest, setVisionLatest] = useState<VisionLatestResponse | null>(null);
  const [visionRefreshing, setVisionRefreshing] = useState(false);

  // Gmail State
  const [gmailMessages, setGmailMessages] = useState<GmailMessageRef[]>([]);
  const [gmailDetails, setGmailDetails] = useState<Map<string, GmailMessage>>(new Map());
  const [gmailLoading, setGmailLoading] = useState(false);
  const [gmailRefreshing, setGmailRefreshing] = useState(false);
  const [gmailError, setGmailError] = useState<string | null>(null);

  // Agent Tasks State
  const [agentTasks, setAgentTasks] = useState<AgentTask[]>([]);
  const [agentTaskStats, setAgentTaskStats] = useState<Record<string, number> | null>(null);
  const [agentTaskSelected, setAgentTaskSelected] = useState<AgentTask | null>(null);
  const [agentTaskObservations, setAgentTaskObservations] = useState<AgentTaskObservation[]>([]);
  const [agentTasksLoading, setAgentTasksLoading] = useState(false);
  const [agentTaskStatusFilter, setAgentTaskStatusFilter] = useState<AgentTaskStatus | null>(null);

  // Webhooks State
  const [webhooks, setWebhooks] = useState<WebhookHook[]>([]);
  const [webhooksLoading, setWebhooksLoading] = useState(false);

  // Vault State
  const [vaultKeys, setVaultKeys] = useState<string[]>([]);
  const [vaultLoading, setVaultLoading] = useState(false);

  // Permissions State
  const [permissions, setPermissions] = useState<AgentPermissionsResponse | null>(null);
  const [permissionsProfiles, setPermissionsProfiles] = useState<PermissionProfileDef[]>([]);
  const [permissionsAudit, setPermissionsAudit] = useState<PermissionAuditEntry[]>([]);
  const [permissionsLoading, setPermissionsLoading] = useState(false);

  const activeChatSession = chatSessions[chatProvider] ?? makeEmptyProviderSession();
  const activeConversationId = activeChatSession.conversationId;
  const activeChatMessages = activeChatSession.messages;
  const activeThreadContext = activeChatSession.threadContext ?? makeDefaultThreadContext();

  const setProviderSession = useCallback(
    (
      provider: ChatProvider,
      updater: (current: ProviderChatSession) => ProviderChatSession
    ) => {
      setChatSessions((prev) => ({
        ...prev,
        [provider]: updater(prev[provider] ?? makeEmptyProviderSession()),
      }));
    },
    []
  );

  const setProviderThreadContext = useCallback(
    (provider: ChatProvider, updater: (current: ProjectThreadContext) => ProjectThreadContext) => {
      setProviderSession(provider, (current) => ({
        ...current,
        threadContext: updater(current.threadContext ?? makeDefaultThreadContext()),
      }));
    },
    [setProviderSession]
  );

  // Initial Load
  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      const [loaded, persistedChat, persistedPlan] = await Promise.all([
        loadSettings(),
        loadChatSession(),
        loadPlanTasks(),
      ]);
      if (!active) return;
      setSettings(loaded);
      // MVP ships with Brain-only provider on mobile.
      setChatProvider("brain");
      setChatSessions(persistedChat.sessions);
      setPlanTasks(persistedPlan);
      setPlanLoading(false);
      setSettingsLoading(false);
    };
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  // Fetch Approvals
  const loadApprovals = useCallback(
    async (refresh = false, silent = false) => {
      if (!settings.baseUrl.trim()) return;

      if (!silent) {
        if (refresh) setListRefreshing(true);
        else setListLoading(true);
      }

      try {
        const pending = await fetchPendingApprovals(settings);
        setApprovals(pending);
      } catch (error) {
        console.warn("Failed to load approvals", error);
      } finally {
        if (!silent) {
          setListLoading(false);
          setListRefreshing(false);
        }
      }
    },
    [settings]
  );

  // Auto-refresh when switching to approvals or dashboard
  useEffect(() => {
    if (!settingsLoading && (activeTab === "approvals" || activeTab === "dashboard")) {
      void loadApprovals();
    }
  }, [activeTab, loadApprovals, settingsLoading]);

  useEffect(() => {
    if (settingsLoading || activeTab !== "approvals") {
      return;
    }

    const timer = setInterval(() => {
      void loadApprovals(false, true);
    }, APPROVALS_POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [activeTab, loadApprovals, settingsLoading]);

  const loadNews = useCallback(
    async (refresh = false, silent = false) => {
      if (!settings.baseUrl.trim()) return;
      if (!silent) {
        if (refresh) setNewsRefreshing(true);
        else setNewsLoading(true);
      }

      try {
        const response = await fetchAiNews(settings, {
          limit: 25,
          maxAgeHours: 72,
          includeX: true,
          query: "technology software startup cloud developer ai llm",
        });
        setNewsItems(response.items || []);
        setNewsGeneratedAt(response.generated_at || null);
        setNewsSourceErrors(response.source_errors || []);
        setNewsError(null);
      } catch (error) {
        setNewsError(getErrorMessage(error));
      } finally {
        if (!silent) {
          setNewsLoading(false);
          setNewsRefreshing(false);
        }
      }
    },
    [settings]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "news") {
      return;
    }
    void loadNews(false);
    const timer = setInterval(() => {
      void loadNews(false, true);
    }, 120000);

    return () => clearInterval(timer);
  }, [activeTab, loadNews, settingsLoading]);

  const refreshVision = useCallback(
    async (requestScan = false) => {
      if (!settings.baseUrl.trim()) return;
      setVisionRefreshing(true);
      try {
        if (requestScan) {
          await requestVisionScan(settings, "office");
          await new Promise((resolve) => setTimeout(resolve, 350));
        }
        const latest = await fetchVisionLatest(settings, "office");
        setVisionLatest(latest);
      } catch (error) {
        console.warn("Failed to load vision snapshot", error);
      } finally {
        setVisionRefreshing(false);
      }
    },
    [settings]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "dashboard") {
      return;
    }
    void refreshVision(false);
    const timer = setInterval(() => {
      void refreshVision(false);
    }, 3500);
    return () => clearInterval(timer);
  }, [activeTab, refreshVision, settingsLoading]);

  // Persist chat session for test continuity.
  useEffect(() => {
    if (settingsLoading) return;
    void saveChatSession({
      activeProvider: chatProvider,
      sessions: chatSessions,
    });
  }, [chatProvider, chatSessions, settingsLoading]);

  useEffect(() => {
    if (planLoading) return;
    void savePlanTasks(planTasks);
  }, [planLoading, planTasks]);

  const refreshGoogleStatus = useCallback(async (targetSettings: AppSettings = settings) => {
    if (!targetSettings.baseUrl.trim() && !targetSettings.tailscaleBaseUrl.trim()) {
      setGoogleStatus(null);
      return;
    }
    setGoogleLoading(true);
    try {
      const status = await fetchGoogleStatus(targetSettings);
      setGoogleStatus(status);
    } catch (error) {
      console.warn("Failed to load Google status", error);
    } finally {
      setGoogleLoading(false);
    }
  }, [settings]);

  const refreshChatHealth = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    try {
      const health = await fetchChatHealth(settings);
      setChatHealth(health);
      setChatHealthError(null);
    } catch (error) {
      setChatHealthError(getErrorMessage(error));
    }
  }, [settings]);

  useEffect(() => {
    if (settingsLoading) return;
    void refreshChatHealth();
    const timer = setInterval(() => {
      void refreshChatHealth();
    }, 10000);
    return () => clearInterval(timer);
  }, [settingsLoading, refreshChatHealth]);

  // Load session index + available models on boot
  useEffect(() => {
    void loadSessionIndex().then(setSessionIndex);
  }, []);

  useEffect(() => {
    if (settingsLoading || !settings.baseUrl.trim()) return;
    void fetchAvailableModels(settings).then(setAvailableProviders).catch(() => {});
  }, [settingsLoading, settings]);

  useEffect(() => {
    if (settingsLoading || (!settings.baseUrl.trim() && !settings.tailscaleBaseUrl.trim())) return;
    void fetchProjectControlCatalog(settings).then(setProjectCatalog).catch(() => {});
  }, [settingsLoading, settings]);

  useEffect(() => {
    if (settingsLoading || (activeTab !== "settings" && activeTab !== "plan" && activeTab !== "gmail")) {
      return;
    }
    void refreshGoogleStatus();
  }, [activeTab, refreshGoogleStatus, settingsLoading]);

  const refreshControlState = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    setControlLoading(true);
    try {
      const control = await fetchBrainControlState(settings);
      setControlState(control.state);
      setControlMqttOnline(Boolean(control.mqtt_online));
      setControlMqttError(control.mqtt_error || null);
    } catch (error) {
      setControlMqttError(getErrorMessage(error));
    } finally {
      setControlLoading(false);
    }
  }, [settings]);

  const refreshControlAudit = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    try {
      const audit = await fetchBrainControlAudit(settings, 40, controlAuditFilter);
      setControlAudit(audit.entries || []);
    } catch (error) {
      console.warn("Failed to load control audit", error);
    }
  }, [controlAuditFilter, settings]);

  const refreshControlPanel = useCallback(async () => {
    await Promise.all([refreshControlState(), refreshControlAudit()]);
  }, [refreshControlAudit, refreshControlState]);

  useEffect(() => {
    if (settingsLoading) return;
    void refreshControlPanel();
    const timer = setInterval(() => {
      if (activeTab === "control") {
        void refreshControlPanel();
      }
    }, 12000);
    return () => clearInterval(timer);
  }, [activeTab, refreshControlPanel, settingsLoading]);

  // Gmail data loading
  const loadGmailInbox = useCallback(
    async (query = "", refresh = false) => {
      if (!settings.baseUrl.trim()) return;
      if (refresh) setGmailRefreshing(true);
      else setGmailLoading(true);
      setGmailError(null);
      try {
        const response = await fetchGmailMessages(settings, { query, maxResults: 20 });
        setGmailMessages(response.messages || []);
        // Auto-fetch details for first batch
        const details = new Map(gmailDetails);
        for (const ref of (response.messages || []).slice(0, 10)) {
          if (!details.has(ref.id)) {
            try {
              const detail = await fetchGmailMessage(settings, ref.id, "metadata");
              details.set(ref.id, detail.message);
            } catch { /* skip individual message errors */ }
          }
        }
        setGmailDetails(details);
      } catch (error) {
        setGmailError(getErrorMessage(error));
      } finally {
        setGmailLoading(false);
        setGmailRefreshing(false);
      }
    },
    [settings, gmailDetails]
  );

  const loadGmailMessageDetail = useCallback(
    async (messageId: string) => {
      if (gmailDetails.has(messageId)) return;
      try {
        const response = await fetchGmailMessage(settings, messageId, "full");
        setGmailDetails((prev) => {
          const next = new Map(prev);
          next.set(messageId, response.message);
          return next;
        });
      } catch (error) {
        console.warn("Failed to load Gmail message", error);
      }
    },
    [settings, gmailDetails]
  );

  const handleArchiveGmail = useCallback(
    async (messageId: string) => {
      try {
        await modifyGmailMessage(settings, messageId, { remove_labels: ["INBOX"] });
        setGmailMessages((prev) => prev.filter((m) => m.id !== messageId));
        Alert.alert("Archived", "Message removed from inbox.");
      } catch (error) {
        Alert.alert("Archive failed", getErrorMessage(error));
      }
    },
    [settings]
  );

  const handleComposeGmail = useCallback(
    async (to: string, subject: string, body: string) => {
      try {
        await sendGmail(settings, { to, subject, body });
        Alert.alert("Sent", `Email sent to ${to}`);
      } catch (error) {
        Alert.alert("Send failed", getErrorMessage(error));
      }
    },
    [settings]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "gmail") return;
    void loadGmailInbox("", false);
  }, [activeTab, settingsLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Agent Tasks data loading
  const loadAgentTasks = useCallback(
    async (refresh = false) => {
      if (!settings.baseUrl.trim()) return;
      setAgentTasksLoading(true);
      try {
        const [tasksResp, statsResp] = await Promise.all([
          fetchAgentTasks(settings, {
            status: agentTaskStatusFilter || undefined,
            limit: 30,
          }),
          fetchAgentTaskStats(settings),
        ]);
        setAgentTasks(tasksResp.tasks || []);
        setAgentTaskStats(statsResp.stats || null);
      } catch (error) {
        console.warn("Failed to load agent tasks", error);
      } finally {
        setAgentTasksLoading(false);
      }
    },
    [settings, agentTaskStatusFilter]
  );

  const handleSelectAgentTask = useCallback(
    async (taskId: string) => {
      try {
        const response = await fetchAgentTaskDetail(settings, taskId);
        setAgentTaskSelected(response.task);
        setAgentTaskObservations(response.observations || []);
      } catch (error) {
        console.warn("Failed to load task detail", error);
      }
    },
    [settings]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "tasks") return;
    void loadAgentTasks();
    const timer = setInterval(() => {
      void loadAgentTasks();
    }, 15000);
    return () => clearInterval(timer);
  }, [activeTab, loadAgentTasks, settingsLoading]);

  // Webhooks loading
  const loadWebhooks = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    setWebhooksLoading(true);
    try {
      const response = await fetchWebhooks(settings);
      setWebhooks(response.hooks || []);
    } catch (error) {
      console.warn("Failed to load webhooks", error);
    } finally {
      setWebhooksLoading(false);
    }
  }, [settings]);

  const handleDeleteWebhook = useCallback(
    async (hookId: string) => {
      try {
        await deleteWebhook(settings, hookId);
        setWebhooks((prev) => prev.filter((h) => h.id !== hookId));
      } catch (error) {
        Alert.alert("Delete failed", getErrorMessage(error));
      }
    },
    [settings]
  );

  // Vault loading
  const loadVaultKeys = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    setVaultLoading(true);
    try {
      const response = await fetchVaultKeys(settings);
      setVaultKeys(response.keys || []);
    } catch (error) {
      console.warn("Failed to load vault keys", error);
    } finally {
      setVaultLoading(false);
    }
  }, [settings]);

  const handleStoreVaultKey = useCallback(
    async (name: string, value: string) => {
      try {
        await storeVaultCredential(settings, name, value);
        Alert.alert("Stored", `Credential "${name}" saved.`);
        void loadVaultKeys();
      } catch (error) {
        Alert.alert("Store failed", getErrorMessage(error));
      }
    },
    [settings, loadVaultKeys]
  );

  const handleDeleteVaultKey = useCallback(
    async (name: string) => {
      try {
        await deleteVaultCredential(settings, name);
        setVaultKeys((prev) => prev.filter((k) => k !== name));
      } catch (error) {
        Alert.alert("Delete failed", getErrorMessage(error));
      }
    },
    [settings]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "settings") return;
    void loadWebhooks();
    void loadVaultKeys();
  }, [activeTab, settingsLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Permissions loading
  const loadPermissions = useCallback(async () => {
    if (!settings.baseUrl.trim()) return;
    setPermissionsLoading(true);
    try {
      const [permsResp, profilesResp, auditResp] = await Promise.all([
        fetchAgentPermissions(settings),
        fetchPermissionProfiles(settings),
        fetchPermissionsAudit(settings),
      ]);
      setPermissions(permsResp);
      setPermissionsProfiles(profilesResp.profiles || []);
      setPermissionsAudit(auditResp.entries || []);
    } catch (error) {
      console.warn("Failed to load permissions", error);
    } finally {
      setPermissionsLoading(false);
    }
  }, [settings]);

  const handleApplyProfile = useCallback(
    async (profileName: PermissionProfile) => {
      try {
        const response = await applyPermissionProfile(settings, profileName);
        setPermissions(response);
        // Refresh audit
        try {
          const auditResp = await fetchPermissionsAudit(settings);
          setPermissionsAudit(auditResp.entries || []);
        } catch { /* audit refresh non-critical */ }
        Alert.alert("Profile applied", `Switched to ${profileName} profile.`);
      } catch (error) {
        Alert.alert("Profile failed", getErrorMessage(error));
      }
    },
    [settings]
  );

  const handleToggleTool = useCallback(
    async (toolName: string, next: "allowed" | "approval" | "denied") => {
      if (!permissions) return;
      const deny = new Set(permissions.deny_tools);
      const approval = new Set(permissions.force_approval_tools);

      // Remove from both first
      deny.delete(toolName);
      approval.delete(toolName);

      if (next === "denied") deny.add(toolName);
      if (next === "approval") approval.add(toolName);

      try {
        const response = await updateAgentPermissions(settings, {
          deny_tools: Array.from(deny),
          force_approval_tools: Array.from(approval),
        });
        setPermissions(response);
        // Refresh audit
        try {
          const auditResp = await fetchPermissionsAudit(settings);
          setPermissionsAudit(auditResp.entries || []);
        } catch { /* audit refresh non-critical */ }
      } catch (error) {
        Alert.alert("Update failed", getErrorMessage(error));
      }
    },
    [settings, permissions]
  );

  useEffect(() => {
    if (settingsLoading || activeTab !== "permissions") return;
    void loadPermissions();
  }, [activeTab, settingsLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Actions
  const handleSaveSettings = async (newSettings: AppSettings) => {
    setSettingsSaving(true);
    try {
      await saveSettings(newSettings);
      setSettings(newSettings);
      Alert.alert("Saved", "Settings updated successfully");
      await refreshChatHealth();
      await refreshGoogleStatus(newSettings);
    } catch (error) {
      Alert.alert("Error", getErrorMessage(error));
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleConnectGoogle = async () => {
    if (!settings.baseUrl.trim() && !settings.tailscaleBaseUrl.trim()) {
      Alert.alert("API URL required", "Set Architect API URL before connecting Google.");
      return;
    }
    setGoogleConnecting(true);
    try {
      const auth = await fetchGoogleAuthUrl(settings);
      if (!auth.auth_url) {
        throw new Error("Google auth URL is empty.");
      }
      await Linking.openURL(auth.auth_url);
      Alert.alert("Continue in browser", "Finish OAuth, then tap Refresh Status.");
    } catch (error) {
      Alert.alert("Google connect failed", getErrorMessage(error));
    } finally {
      setGoogleConnecting(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!settings.baseUrl.trim() && !settings.tailscaleBaseUrl.trim()) {
      Alert.alert("API URL required", "Set Architect API URL before disconnecting Google.");
      return;
    }
    setGoogleLoading(true);
    try {
      await disconnectGoogleAccount(settings);
      await refreshGoogleStatus();
      Alert.alert("Disconnected", "Google account disconnected from Sage.");
    } catch (error) {
      Alert.alert("Google disconnect failed", getErrorMessage(error));
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleTestConnection = async (testSettings: AppSettings) => {
    setConnectionTesting(true);
    try {
      const response = await checkHealth(testSettings);
      Alert.alert("Connected", `Status: ${response.status}`);
    } catch (error) {
      Alert.alert("Connection Failed", getErrorMessage(error));
    } finally {
      setConnectionTesting(false);
    }
  };

  const handleSaveControlConfig = async (
    patch: Partial<{
      personality: string;
      raw_mode: boolean;
      voice_input_enabled: boolean;
      voice_output_enabled: boolean;
    }>
  ) => {
    setControlMutating(true);
    try {
      const response = await updateBrainControlConfig(settings, patch);
      setControlState(response.state);
      setControlMqttOnline(Boolean(response.mqtt_online));
      setControlMqttError(response.mqtt_error || null);
      await refreshControlAudit();
      Alert.alert("Applied", "Brain control settings updated.");
    } catch (error) {
      Alert.alert("Control update failed", getErrorMessage(error));
    } finally {
      setControlMutating(false);
    }
  };

  const handleSendControlCommand = async (
    command: "clear_conversation" | "clear_memory" | "clear_episodes" | "kill_switch" | "resume_voice"
  ) => {
    setControlMutating(true);
    try {
      const response = await sendBrainControlCommand(settings, { command });
      setControlState(response.state);
      setControlMqttOnline(Boolean(response.mqtt_online));
      setControlMqttError(response.mqtt_error || null);
      await refreshControlAudit();
      Alert.alert("Command sent", command.split("_").join(" "));
    } catch (error) {
      Alert.alert("Command failed", getErrorMessage(error));
    } finally {
      setControlMutating(false);
    }
  };

  const handleApprove = async (id: string, reason?: string) => {
    try {
      await submitProposalDecision(settings, id, {
        decision: "approve",
        reviewer: settings.reviewer,
        reason,
      });
      await loadApprovals(true);
    } catch (error) {
      Alert.alert("Error", getErrorMessage(error));
    }
  };

  const handleDeny = async (id: string, reason?: string) => {
    try {
      await submitProposalDecision(settings, id, {
        decision: "deny",
        reviewer: settings.reviewer,
        reason,
      });
      await loadApprovals(true);
    } catch (error) {
      Alert.alert("Error", getErrorMessage(error));
    }
  };

  const ensureProjectThreadDefaults = useCallback(
    (provider: ChatProvider) => {
      const defaults = getDefaultProjectSelection(projectCatalog);
      setProviderThreadContext(provider, (current) => ({
        mode: "project",
        project_id: current.project_id || defaults.project_id,
        preferred_node: current.preferred_node || defaults.preferred_node,
        executor:
          current.executor && current.executor !== "brain"
            ? current.executor
            : provider === "brain"
              ? ((projectCatalog?.default_executor as ChatProvider | undefined) || "codex_cli")
              : provider,
      }));
    },
    [projectCatalog, setProviderThreadContext]
  );

  const handleToggleThreadMode = useCallback(() => {
    if (chatSending || chatSyncing) return;
    if (activeThreadContext.mode === "project") {
      setProviderThreadContext(chatProvider, () => ({ mode: "conversation" }));
      return;
    }
    const targetProvider =
      chatProvider === "brain"
        ? (((projectCatalog?.default_executor as ChatProvider | undefined) || "codex_cli") as ChatProvider)
        : chatProvider;
    if (targetProvider !== chatProvider) {
      setChatProvider(targetProvider);
    }
    ensureProjectThreadDefaults(targetProvider);
  }, [activeThreadContext.mode, chatProvider, chatSending, chatSyncing, ensureProjectThreadDefaults, projectCatalog, setProviderThreadContext]);

  const handleCycleProject = useCallback(() => {
    const projects = projectCatalog?.projects || [];
    if (!projects.length) return;
    setProviderThreadContext(chatProvider, (current) => {
      const currentIndex = projects.findIndex((project) => project.project_id === current.project_id);
      const nextProject = projects[(currentIndex + 1 + projects.length) % projects.length] || projects[0];
      const nextNode =
        nextProject.nodes?.find((node) => node.node_id === PROJECT_MODE_DEFAULTS.preferredNode)?.node_id ||
        nextProject.nodes?.[0]?.node_id ||
        projectCatalog?.default_target_node;
      return {
        mode: "project",
        project_id: nextProject.project_id,
        preferred_node: nextNode,
        executor:
          current.executor && current.executor !== "brain"
            ? current.executor
            : ((projectCatalog?.default_executor as ChatProvider | undefined) || "codex_cli"),
      };
    });
  }, [chatProvider, projectCatalog, setProviderThreadContext]);

  const handleCycleProjectNode = useCallback(() => {
    const projects = projectCatalog?.projects || [];
    const project = projects.find((item) => item.project_id === activeThreadContext.project_id);
    const nodes = project?.nodes || [];
    if (!nodes.length) return;
    setProviderThreadContext(chatProvider, (current) => {
      const currentIndex = nodes.findIndex((item) => item.node_id === current.preferred_node);
      const nextNode = nodes[(currentIndex + 1 + nodes.length) % nodes.length] || nodes[0];
      return {
        ...current,
        mode: "project",
        project_id: project?.project_id,
        preferred_node: nextNode.node_id,
        executor:
          current.executor && current.executor !== "brain"
            ? current.executor
            : ((projectCatalog?.default_executor as ChatProvider | undefined) || "codex_cli"),
      };
    });
  }, [activeThreadContext.project_id, chatProvider, projectCatalog, setProviderThreadContext]);

  const handleProjectHandoff = useCallback(async () => {
    if (activeThreadContext.mode !== "project" || !activeThreadContext.project_id) {
      return;
    }
    try {
      const sourceNode = activeThreadContext.preferred_node || undefined;
      const targetNode =
        projectCatalog?.default_target_node && projectCatalog.default_target_node !== sourceNode
          ? projectCatalog.default_target_node
          : undefined;
      const response = await handoffProject(settings, {
        project_id: activeThreadContext.project_id,
        source_node: sourceNode,
        target_node: targetNode,
      });
      Alert.alert(
        "Handoff queued",
        `${response.handoff.project_id} mirrored from ${response.handoff.source_node} to ${response.handoff.target_node}.`
      );
      const catalog = await fetchProjectControlCatalog(settings);
      setProjectCatalog(catalog);
    } catch (error) {
      Alert.alert("Handoff failed", getErrorMessage(error));
    }
  }, [activeThreadContext, projectCatalog, settings]);

  const handleSendChat = async ({ text, attachments = [] }: ChatComposerSubmit) => {
    if (!settings.baseUrl.trim() && !settings.tailscaleBaseUrl.trim()) {
      Alert.alert(
        "API URL required",
        "Set Architect API URL in Settings before sending messages.",
        [
          { text: "Cancel", style: "cancel" },
          { text: "Open Settings", onPress: () => setActiveTab("settings") },
        ]
      );
      return;
    }

    const provider = chatProvider;
    const conversationId = chatSessions[provider]?.conversationId || null;
    const payloadText = text.trim();
    const userMessage = createMessage("user", payloadText, toAttachmentPreviews(attachments));
    const assistantPlaceholder = createMessage("assistant", "");
    setProviderSession(provider, (current) => ({
      ...current,
      messages: [...current.messages, userMessage, assistantPlaceholder],
    }));
    setChatSending(true);
    setChatPhase("starting");
    const startedAt = Date.now();
    let receivedStreamDelta = false;

    try {
      if (activeThreadContext.mode === "project" && activeThreadContext.project_id) {
        const executor =
          (activeThreadContext.executor && activeThreadContext.executor !== "brain"
            ? activeThreadContext.executor
            : provider === "brain"
              ? "codex_cli"
              : provider) as "codex_cli" | "claude_cli";
        const history = (chatSessions[provider]?.messages || [])
          .filter((message) => message.text.trim())
          .slice(-10)
          .map((message) => ({
            role: message.role,
            content: message.text,
          }));
        const response = await sendProjectControlChat(settings, {
          message: attachments.length
            ? `${payloadText}\n\n[Attachments omitted in project mode: ${attachments
                .map((item) => item.name)
                .join(", ")}]`
            : payloadText,
          project_id: activeThreadContext.project_id,
          preferred_node: activeThreadContext.preferred_node,
          executor,
          history,
        });
        setProviderSession(provider, (current) => ({
          ...current,
          messages: current.messages.map((message) =>
            message.id === assistantPlaceholder.id
              ? {
                  ...message,
                  text: response.reply,
                  meta: {
                    latency_ms: response.latency_ms,
                    model: `${response.provider}:${response.model}`,
                  },
                }
              : message
          ),
        }));
        setLastChatModel(`${response.provider}:${response.model}`);
        setLastChatLatencyMs(response.latency_ms);
        if (response.node_id) {
          setProviderThreadContext(provider, (current) => ({
            ...current,
            mode: "project",
            project_id: activeThreadContext.project_id,
            preferred_node: response.node_id,
            executor,
          }));
        }
        const catalog = await fetchProjectControlCatalog(settings);
        setProjectCatalog(catalog);
        return;
      }

      const response = await streamChatMessage(
        settings,
        {
          message: payloadText,
          conversation_id: conversationId || undefined,
          provider,
          model: chatModel !== "auto" ? chatModel : PROVIDER_MODEL_HINTS[provider],
          attachments,
        },
        {
          onMeta: (meta) => {
            const id = typeof meta.conversation_id === "string" ? meta.conversation_id : null;
            if (!id) return;
            setProviderSession(provider, (current) => ({
              ...current,
              conversationId: id,
            }));
          },
          onStatus: (phase) => {
            if (phase) setChatPhase(phase);
          },
          onDelta: (delta) => {
            if (!delta) return;
            receivedStreamDelta = true;
            setProviderSession(provider, (current) => ({
              ...current,
              messages: current.messages.map((message) =>
                message.id === assistantPlaceholder.id
                  ? { ...message, text: `${message.text}${delta}` }
                  : message
              ),
            }));
          },
        }
      );

      setProviderSession(provider, (current) => ({
        ...current,
        conversationId: response.conversation_id,
      }));
      const responseModel = `${response.provider}:${response.model}`;
      setLastChatModel(responseModel);
      setLastChatLatencyMs(Date.now() - startedAt);
      // Attach token metadata to the assistant bubble
      const meta = (response.input_tokens || response.output_tokens || response.cost)
        ? {
            input_tokens: response.input_tokens,
            output_tokens: response.output_tokens,
            cost: response.cost,
            latency_ms: response.latency_ms ?? (Date.now() - startedAt),
            model: response.model,
          }
        : undefined;
      setProviderSession(provider, (current) => ({
        ...current,
        messages: current.messages.map((message) =>
          message.id === assistantPlaceholder.id
            ? { ...message, text: message.text || response.reply, meta }
            : message
        ),
      }));
      // Update session totals
      if (meta) {
        setSessionTotals((prev) => ({
          cost: prev.cost + (meta.cost ?? 0),
          inputTokens: prev.inputTokens + (meta.input_tokens ?? 0),
          outputTokens: prev.outputTokens + (meta.output_tokens ?? 0),
        }));
      }
    } catch (error) {
      if (receivedStreamDelta) {
        const errMsg = getErrorMessage(error);
        setProviderSession(provider, (current) => ({
          ...current,
          messages: current.messages.map((message) =>
            message.id === assistantPlaceholder.id
              ? { ...message, text: `${message.text}\n\n[stream interrupted: ${errMsg}]` }
              : message
          ),
        }));
        return;
      }

      try {
        const response = await sendChatMessage(settings, {
          message: payloadText,
          conversation_id: conversationId || undefined,
          provider,
          model: chatModel !== "auto" ? chatModel : PROVIDER_MODEL_HINTS[provider],
          attachments,
        });
        setProviderSession(provider, (current) => ({
          ...current,
          conversationId: response.conversation_id,
        }));
        setLastChatModel(`${response.provider}:${response.model}`);
        setLastChatLatencyMs(Date.now() - startedAt);
        const fbMeta = (response.input_tokens || response.output_tokens || response.cost)
          ? {
              input_tokens: response.input_tokens,
              output_tokens: response.output_tokens,
              cost: response.cost,
              latency_ms: response.latency_ms ?? (Date.now() - startedAt),
              model: response.model,
            }
          : undefined;
        setProviderSession(provider, (current) => ({
          ...current,
          messages: current.messages.map((message) =>
            message.id === assistantPlaceholder.id ? { ...message, text: response.reply, meta: fbMeta } : message
          ),
        }));
        if (fbMeta) {
          setSessionTotals((prev) => ({
            cost: prev.cost + (fbMeta.cost ?? 0),
            inputTokens: prev.inputTokens + (fbMeta.input_tokens ?? 0),
            outputTokens: prev.outputTokens + (fbMeta.output_tokens ?? 0),
          }));
        }
      } catch (fallbackError) {
        const errMsg = getErrorMessage(fallbackError || error);
        setProviderSession(provider, (current) => ({
          ...current,
          messages: current.messages.map((message) =>
            message.id === assistantPlaceholder.id
              ? { ...message, text: `Error: ${errMsg}` }
              : message
          ),
        }));
      }
    } finally {
      setChatPhase(null);
      setChatSending(false);
      void refreshChatHealth();
    }
  };

  const handleNewChat = async () => {
    // Save current session to index before clearing (if it has messages)
    const currentSession = chatSessions[chatProvider];
    if (currentSession?.conversationId && currentSession.messages.length > 0) {
      const firstUserMsg = currentSession.messages.find((m) => m.role === "user");
      const updated = await upsertSessionEntry({
        conversationId: currentSession.conversationId,
        preview: (firstUserMsg?.text || "").slice(0, 80),
        provider: chatProvider,
        model: chatModel,
        threadMode: currentSession.threadContext?.mode,
        projectId: currentSession.threadContext?.project_id,
        preferredNode: currentSession.threadContext?.preferred_node,
        messageCount: currentSession.messages.length,
        totalCost: sessionTotals.cost,
        updatedAt: new Date().toISOString(),
      });
      setSessionIndex(updated);
    }
    const preservedThreadContext = currentSession?.threadContext || makeDefaultThreadContext();
    setProviderSession(chatProvider, () => ({
      ...makeEmptyProviderSession(),
      threadContext: preservedThreadContext,
    }));
    setLastChatModel(null);
    setLastChatLatencyMs(null);
    setChatPhase(null);
    setSessionTotals({ cost: 0, inputTokens: 0, outputTokens: 0 });
  };

  const handleSyncConversation = async () => {
    if (!activeConversationId) {
      Alert.alert("No thread yet", "Send a message first to start a provider thread.");
      return;
    }

    setChatSyncing(true);
    try {
      const response = await fetchConversation(settings, activeConversationId);
      const nowIso = new Date().toISOString();
      const messages: ChatBubble[] = response.messages.map((message, index) => ({
        id: `${message.role}-${index}-${Date.now()}`,
        role: message.role,
        text: message.content,
        timestamp: nowIso,
      }));
      setProviderSession(chatProvider, (current) => ({
        ...current,
        conversationId: response.conversation_id,
        messages,
      }));
    } catch (error) {
      Alert.alert("Sync failed", getErrorMessage(error));
    } finally {
      setChatSyncing(false);
    }
  };

  const handleProviderChange = (provider: ChatProvider) => {
    if (chatSending || chatSyncing) return;
    setChatProvider(provider);
    if (activeThreadContext.mode === "project" && provider !== "brain") {
      setProviderThreadContext(provider, (current) => ({
        ...current,
        mode: "project",
        executor: provider,
      }));
    }
    setChatPhase(null);
  };

  const handleModelChange = useCallback((provider: string, model: string) => {
    if (chatSending || chatSyncing) return;
    setChatProvider(provider as ChatProvider);
    if (activeThreadContext.mode === "project" && provider !== "brain") {
      setProviderThreadContext(provider as ChatProvider, (current) => ({
        ...current,
        mode: "project",
        executor: provider as ChatProvider,
      }));
    }
    setChatModel(model);
  }, [activeThreadContext.mode, chatSending, chatSyncing, setProviderThreadContext]);

  const handleSwitchSession = useCallback(async (conversationId: string) => {
    // Find matching entry in sessionIndex
    const entry = sessionIndex.find((e) => e.conversationId === conversationId);
    if (!entry) return;

    // Save current session to index first
    const currentSession = chatSessions[chatProvider];
    if (currentSession?.conversationId && currentSession.messages.length > 0) {
      const firstUserMsg = currentSession.messages.find((m) => m.role === "user");
      await upsertSessionEntry({
        conversationId: currentSession.conversationId,
        preview: (firstUserMsg?.text || "").slice(0, 80),
        provider: chatProvider,
        model: chatModel,
        threadMode: currentSession.threadContext?.mode,
        projectId: currentSession.threadContext?.project_id,
        preferredNode: currentSession.threadContext?.preferred_node,
        messageCount: currentSession.messages.length,
        totalCost: sessionTotals.cost,
        updatedAt: new Date().toISOString(),
      });
    }

    // Try to fetch conversation from server
    try {
      const response = await fetchConversation(settings, conversationId);
      const nowIso = new Date().toISOString();
      const messages: ChatBubble[] = response.messages.map((message, index) => ({
        id: `${message.role}-${index}-${Date.now()}`,
        role: message.role,
        text: message.content,
        timestamp: nowIso,
      }));
      setChatProvider(entry.provider as ChatProvider);
      setChatModel(entry.model);
      setProviderSession(entry.provider as ChatProvider, () => ({
        conversationId,
        messages,
        threadContext: {
          mode: entry.threadMode === "project" ? "project" : "conversation",
          project_id: entry.projectId,
          preferred_node: entry.preferredNode,
          executor: entry.provider as ChatProvider,
        },
      }));
      setSessionTotals({ cost: entry.totalCost, inputTokens: 0, outputTokens: 0 });
    } catch {
      // Server doesn't have it — just set the conversationId so new messages continue it
      setChatProvider(entry.provider as ChatProvider);
      setChatModel(entry.model);
      setProviderSession(entry.provider as ChatProvider, () => ({
        conversationId,
        messages: [],
        threadContext: {
          mode: entry.threadMode === "project" ? "project" : "conversation",
          project_id: entry.projectId,
          preferred_node: entry.preferredNode,
          executor: entry.provider as ChatProvider,
        },
      }));
      setSessionTotals({ cost: 0, inputTokens: 0, outputTokens: 0 });
    }
    setShowSessionList(false);
  }, [sessionIndex, chatSessions, chatProvider, chatModel, sessionTotals, settings]);

  const handleDeleteSession = useCallback(async (conversationId: string) => {
    const updated = await removeSessionEntry(conversationId);
    setSessionIndex(updated);
  }, []);

  const handleSyncPlanFromGoogle = async () => {
    if (!settings.baseUrl.trim() && !settings.tailscaleBaseUrl.trim()) {
      Alert.alert("API URL required", "Set Architect API URL before syncing.");
      setActiveTab("settings");
      return;
    }

    setPlanGoogleSyncing(true);
    try {
      const status = await fetchGoogleStatus(settings);
      setGoogleStatus(status);
      if (!status.connected) {
        Alert.alert(
          "Google not connected",
          "Connect Google in Settings first, then run sync."
        );
        setActiveTab("settings");
        return;
      }

      const lists = await fetchGoogleTaskLists(settings);
      const list = (lists.items || [])[0];
      if (!list?.id) {
        Alert.alert("No Google task list", "Create a task list in Google Tasks first.");
        return;
      }

      const tasksResp = await fetchGoogleTasksForList(settings, list.id, 100);
      const remoteItems = tasksResp.items || [];

      let added = 0;
      let updated = 0;
      setPlanTasks((prev) => {
        const next = [...prev];
        const indexByExternal = new Map<string, number>();
        for (let i = 0; i < next.length; i += 1) {
          const ext = next[i].externalId;
          if (ext) indexByExternal.set(ext, i);
        }

        for (const item of remoteItems) {
          if (!item?.id || !item?.title) continue;
          const normalized: PlanTask = {
            id: `google-${list.id}-${item.id}`,
            title: item.title,
            dueIso: normalizeGoogleDueIso(item.due),
            done: String(item.status || "").toLowerCase() === "completed",
            priority: "medium",
            tag: list.title || "Google Tasks",
            source: "google",
            externalId: item.id,
            externalListId: list.id,
          };

          const existingIndex = indexByExternal.get(item.id);
          if (existingIndex === undefined) {
            next.unshift(normalized);
            added += 1;
            continue;
          }

          const existing = next[existingIndex];
          next[existingIndex] = {
            ...existing,
            title: normalized.title,
            done: normalized.done,
            dueIso: normalized.dueIso,
            tag: normalized.tag,
            source: "google",
            externalId: normalized.externalId,
            externalListId: normalized.externalListId,
          };
          updated += 1;
        }

        return next;
      });

      Alert.alert(
        "Google sync complete",
        `List: ${list.title || "Google Tasks"}\nAdded: ${added}\nUpdated: ${updated}`
      );
    } catch (error) {
      Alert.alert("Google sync failed", getErrorMessage(error));
    } finally {
      setPlanGoogleSyncing(false);
    }
  };

  const handleAddPlanTask = (input: NewPlanTaskInput) => {
    const title = input.title.trim();
    if (!title) return;
    const dueIso = dueIsoForDateKey(input.dateKey, input.dueTime);
    setPlanTasks((prev) => {
      const isDuplicateRoutine =
        Boolean(input.routineKey) &&
        prev.some(
          (task) =>
            task.routineKey === input.routineKey && dateKeyFromIso(task.dueIso) === input.dateKey
        );
      if (isDuplicateRoutine) return prev;

      const nextTask: PlanTask = {
        id: `task-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        title,
        dueIso,
        done: false,
        priority: input.priority || "medium",
        tag: input.tag,
        routineKey: input.routineKey,
        source: "local",
      };
      return [nextTask, ...prev];
    });
  };

  const handleTogglePlanTask = (taskId: string) => {
    setPlanTasks((prev) =>
      prev.map((task) => (task.id === taskId ? { ...task, done: !task.done } : task))
    );
  };

  const handleSnoozePlanTask = (taskId: string) => {
    setPlanTasks((prev) =>
      prev.map((task) =>
        task.id === taskId ? { ...task, dueIso: snoozeDueIsoByOneDay(task.dueIso) } : task
      )
    );
  };

  const handleDeletePlanTask = (taskId: string) => {
    setPlanTasks((prev) => prev.filter((task) => task.id !== taskId));
  };

  const renderScreen = () => {
    const brainOnline = Boolean(chatHealth?.services?.brain_ready);
    const mqttOnline = Boolean(chatHealth?.services?.mqtt_broker_online);
    const providerLabel = PROVIDER_LABELS[chatProvider];
    const providerOnline =
      chatProvider === "brain"
        ? brainOnline
        : Boolean(settings.baseUrl.trim()) && !/network request failed/i.test(chatHealthError || "");
    const statusText =
      chatSending && chatPhase
        ? `${providerLabel} ${chatPhase}...`
        : chatProvider === "brain"
          ? providerOnline
            ? "Brain online"
            : "Brain unavailable"
          : `Architect ↔ ${providerLabel}`;
    const statusMetaParts: string[] = [];
    if (lastChatModel) {
      statusMetaParts.push(
        `${lastChatModel}${lastChatLatencyMs ? ` · ${lastChatLatencyMs}ms` : ""}`
      );
    } else if (chatHealthError) {
      statusMetaParts.push(chatHealthError);
    }
    if (sessionTotals.inputTokens + sessionTotals.outputTokens > 0) {
      const totalTok = sessionTotals.inputTokens + sessionTotals.outputTokens;
      const tokLabel = totalTok >= 1000 ? `${(totalTok / 1000).toFixed(1)}k` : `${totalTok}`;
      statusMetaParts.push(`${tokLabel} tok`);
    }
    if (sessionTotals.cost > 0) {
      statusMetaParts.push(`$${sessionTotals.cost.toFixed(4)}`);
    }
    const statusMeta = statusMetaParts.join(" · ") || undefined;

    switch (activeTab) {
      case "dashboard":
        return (
          <DashboardScreen
            brainOnline={brainOnline}
            mqttOnline={mqttOnline}
            apiStatus={chatHealth?.status || (chatHealthError ? "degraded" : "unknown")}
            lastModel={lastChatModel}
            lastLatencyMs={lastChatLatencyMs}
            vision={visionLatest}
            isVisionRefreshing={visionRefreshing}
            onRefreshVision={() => {
              void refreshVision(true);
            }}
            onNavigate={setActiveTab}
            approvalCount={approvals.filter((a) => a.status === "pending").length}
          />
        );
      case "approvals":
        return (
          <ApprovalsScreen
            approvals={approvals}
            isLoading={listLoading}
            isRefreshing={listRefreshing}
            onRefresh={() => loadApprovals(true)}
            onApprove={handleApprove}
            onDeny={handleDeny}
          />
        );
      case "chat":
        return (
          <ChatScreen
            provider={chatProvider}
            model={chatModel}
            onProviderChange={handleProviderChange}
            onModelChange={handleModelChange}
            availableProviders={availableProviders}
            onSyncConversation={handleSyncConversation}
            isSyncingConversation={chatSyncing}
            conversationId={activeConversationId}
            messages={activeChatMessages}
            onSend={handleSendChat}
            isSending={chatSending}
            onNewChat={handleNewChat}
            statusOnline={providerOnline}
            statusText={statusText}
            statusMeta={statusMeta}
            sessionIndex={sessionIndex}
            showSessionList={showSessionList}
            onToggleSessionList={() => setShowSessionList((v) => !v)}
            onSwitchSession={handleSwitchSession}
            onDeleteSession={handleDeleteSession}
            sessionTotals={sessionTotals}
            threadContext={activeThreadContext}
            projectCatalog={projectCatalog}
            onToggleThreadMode={handleToggleThreadMode}
            onCycleProject={handleCycleProject}
            onCycleProjectNode={handleCycleProjectNode}
            onHandoffProject={handleProjectHandoff}
          />
        );
      case "control":
        return (
          <ControlScreen
            controlState={controlState}
            auditEntries={controlAudit}
            auditFilter={controlAuditFilter}
            mqttOnline={controlMqttOnline}
            mqttError={controlMqttError}
            isLoading={controlLoading}
            isMutating={controlMutating}
            onAuditFilterChange={setControlAuditFilter}
            onRefresh={() => {
              void refreshControlPanel();
            }}
            onSaveConfig={handleSaveControlConfig}
            onSendCommand={handleSendControlCommand}
          />
        );
      case "gmail":
        return (
          <GmailScreen
            messages={gmailMessages}
            messageDetails={gmailDetails}
            isLoading={gmailLoading}
            isRefreshing={gmailRefreshing}
            error={gmailError}
            googleConnected={Boolean(googleStatus?.connected)}
            onRefresh={() => {
              void loadGmailInbox("", true);
            }}
            onSearch={(query) => {
              void loadGmailInbox(query, false);
            }}
            onOpenMessage={(id) => {
              void loadGmailMessageDetail(id);
            }}
            onArchiveMessage={(id) => {
              void handleArchiveGmail(id);
            }}
            onCompose={(to, subject, body) => {
              void handleComposeGmail(to, subject, body);
            }}
          />
        );
      case "tasks":
        return (
          <AgentTasksScreen
            tasks={agentTasks}
            stats={agentTaskStats}
            selectedTask={agentTaskSelected}
            selectedObservations={agentTaskObservations}
            isLoading={agentTasksLoading}
            statusFilter={agentTaskStatusFilter}
            onFilterChange={setAgentTaskStatusFilter}
            onRefresh={() => {
              void loadAgentTasks(true);
            }}
            onSelectTask={(id) => {
              void handleSelectAgentTask(id);
            }}
            onDeselectTask={() => {
              setAgentTaskSelected(null);
              setAgentTaskObservations([]);
            }}
          />
        );
      case "plan":
        return (
          <PlanScreen
            tasks={planTasks}
            onAddTask={handleAddPlanTask}
            onToggleTask={handleTogglePlanTask}
            onSnoozeTask={handleSnoozePlanTask}
            onDeleteTask={handleDeletePlanTask}
            onSyncGoogle={handleSyncPlanFromGoogle}
            isSyncingGoogle={planGoogleSyncing}
            googleConnected={Boolean(googleStatus?.connected)}
          />
        );
      case "news":
        return (
          <NewsScreen
            items={newsItems}
            generatedAt={newsGeneratedAt}
            sourceErrors={newsSourceErrors}
            isLoading={newsLoading}
            isRefreshing={newsRefreshing}
            error={newsError}
            onRefresh={() => {
              void loadNews(true);
            }}
          />
        );
      case "permissions":
        return (
          <PermissionsScreen
            permissions={permissions}
            profiles={permissionsProfiles}
            audit={permissionsAudit}
            isLoading={permissionsLoading}
            onRefresh={() => {
              void loadPermissions();
            }}
            onApplyProfile={(name) => {
              void handleApplyProfile(name);
            }}
            onToggleTool={(toolName, next) => {
              void handleToggleTool(toolName, next);
            }}
          />
        );
      case "settings":
        return (
          <SettingsScreen
            settings={settings}
            onSave={handleSaveSettings}
            onTestConnection={handleTestConnection}
            googleStatus={googleStatus}
            googleLoading={googleLoading}
            googleConnecting={googleConnecting}
            onRefreshGoogleStatus={refreshGoogleStatus}
            onConnectGoogle={handleConnectGoogle}
            onDisconnectGoogle={handleDisconnectGoogle}
            isLoading={settingsSaving}
            isTesting={connectionTesting}
            webhooks={webhooks}
            webhooksLoading={webhooksLoading}
            onRefreshWebhooks={() => {
              void loadWebhooks();
            }}
            onDeleteWebhook={(id) => {
              void handleDeleteWebhook(id);
            }}
            vaultKeys={vaultKeys}
            vaultLoading={vaultLoading}
            onRefreshVault={() => {
              void loadVaultKeys();
            }}
            onStoreVaultKey={(name, value) => {
              void handleStoreVaultKey(name, value);
            }}
            onDeleteVaultKey={(name) => {
              void handleDeleteVaultKey(name);
            }}
          />
        );
      default:
        return (
          <DashboardScreen
            brainOnline={brainOnline}
            mqttOnline={mqttOnline}
            apiStatus={chatHealth?.status || "unknown"}
            lastModel={lastChatModel}
            lastLatencyMs={lastChatLatencyMs}
            vision={visionLatest}
            isVisionRefreshing={visionRefreshing}
            onRefreshVision={() => {
              void refreshVision(true);
            }}
            onNavigate={setActiveTab}
            approvalCount={approvals.filter((a) => a.status === "pending").length}
          />
        );
    }
  };

  return (
    <GestureHandlerRootView style={styles.container}>
      <StatusBar style="light" />
      <ErrorBoundary key={activeTab}>
        {renderScreen()}
      </ErrorBoundary>
      <HeaderNav
        activeTab={activeTab}
        onNavigate={setActiveTab}
        approvalCount={approvals.filter((a) => a.status === "pending").length}
      />
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
});
