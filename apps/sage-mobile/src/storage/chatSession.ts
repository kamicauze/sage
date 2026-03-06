import AsyncStorage from "@react-native-async-storage/async-storage";
import { ChatAttachmentPreview, ChatProvider } from "../types/chat";
import { ProjectThreadContext } from "../types/projectControl";

export interface ChatBubbleMeta {
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  latency_ms?: number;
  model?: string;
}

export interface ChatBubble {
  id: string;
  role: "system" | "user" | "assistant";
  text: string;
  timestamp: string;
  attachments?: ChatAttachmentPreview[];
  meta?: ChatBubbleMeta;
}

export interface ProviderChatSession {
  conversationId: string | null;
  messages: ChatBubble[];
  threadContext?: ProjectThreadContext;
}

export interface PersistedChatSession {
  activeProvider: ChatProvider;
  sessions: Record<ChatProvider, ProviderChatSession>;
}

const CHAT_SESSION_KEY = "sage.mobile.chat.session.v1";
const MAX_PERSISTED_MESSAGES = 200;

const PROVIDERS: ChatProvider[] = ["brain", "codex_cli", "claude_cli"];

function makeEmptySession(): ProviderChatSession {
  return { conversationId: null, messages: [], threadContext: { mode: "conversation" } };
}

function makeDefaultPersistedSession(): PersistedChatSession {
  return {
    activeProvider: "brain",
    sessions: {
      brain: makeEmptySession(),
      codex_cli: makeEmptySession(),
      claude_cli: makeEmptySession(),
    },
  };
}

function isChatProvider(value: unknown): value is ChatProvider {
  return typeof value === "string" && PROVIDERS.includes(value as ChatProvider);
}

function isAttachmentPreview(value: unknown): value is ChatAttachmentPreview {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.name === "string" &&
    typeof item.mime_type === "string" &&
    typeof item.size_bytes === "number"
  );
}

function isChatBubble(value: unknown): value is ChatBubble {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  const attachments =
    item.attachments === undefined ||
    (Array.isArray(item.attachments) && item.attachments.every(isAttachmentPreview));
  const meta =
    item.meta === undefined || (typeof item.meta === "object" && item.meta !== null);
  return (
    typeof item.id === "string" &&
    (item.role === "system" || item.role === "user" || item.role === "assistant") &&
    typeof item.text === "string" &&
    typeof item.timestamp === "string" &&
    attachments &&
    meta
  );
}

function parseProviderSession(value: unknown): ProviderChatSession {
  if (!value || typeof value !== "object") {
    return makeEmptySession();
  }

  const item = value as Record<string, unknown>;
  const conversationId = typeof item.conversationId === "string" ? item.conversationId : null;
  const messages = Array.isArray(item.messages)
    ? item.messages.filter(isChatBubble).slice(-MAX_PERSISTED_MESSAGES)
    : [];
  const rawThreadContext = item.threadContext;
  const threadContext =
    rawThreadContext &&
    typeof rawThreadContext === "object" &&
    (((rawThreadContext as Record<string, unknown>).mode === "conversation") ||
      ((rawThreadContext as Record<string, unknown>).mode === "project"))
      ? {
          mode: (rawThreadContext as Record<string, unknown>).mode as "conversation" | "project",
          project_id:
            typeof (rawThreadContext as Record<string, unknown>).project_id === "string"
              ? ((rawThreadContext as Record<string, unknown>).project_id as string)
              : undefined,
          preferred_node:
            typeof (rawThreadContext as Record<string, unknown>).preferred_node === "string"
              ? ((rawThreadContext as Record<string, unknown>).preferred_node as string)
              : undefined,
          executor:
            typeof (rawThreadContext as Record<string, unknown>).executor === "string"
              ? ((rawThreadContext as Record<string, unknown>).executor as ChatProvider)
              : undefined,
        }
      : { mode: "conversation" as const };
  return { conversationId, messages, threadContext };
}

function parseProviderSessions(rawSessions: unknown): Record<ChatProvider, ProviderChatSession> {
  const defaults = makeDefaultPersistedSession().sessions;
  if (!rawSessions || typeof rawSessions !== "object") {
    return defaults;
  }

  const sessions = rawSessions as Record<string, unknown>;
  return {
    brain: parseProviderSession(sessions.brain),
    codex_cli: parseProviderSession(sessions.codex_cli),
    claude_cli: parseProviderSession(sessions.claude_cli),
  };
}

export async function loadChatSession(): Promise<PersistedChatSession> {
  try {
    const raw = await AsyncStorage.getItem(CHAT_SESSION_KEY);
    if (!raw) {
      return makeDefaultPersistedSession();
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>;

    // New shape: provider-aware sessions.
    const activeProvider = isChatProvider(parsed.activeProvider)
      ? parsed.activeProvider
      : "brain";
    if (parsed.sessions && typeof parsed.sessions === "object") {
      return {
        activeProvider,
        sessions: parseProviderSessions(parsed.sessions),
      };
    }

    // Legacy shape fallback: single session maps to brain provider.
    const legacyConversationId =
      typeof parsed.conversationId === "string" ? parsed.conversationId : null;
    const legacyMessages = Array.isArray(parsed.messages)
      ? parsed.messages.filter(isChatBubble).slice(-MAX_PERSISTED_MESSAGES)
      : [];

    const session = makeDefaultPersistedSession();
    session.sessions.brain = {
      conversationId: legacyConversationId,
      messages: legacyMessages,
    };
    return session;
  } catch {
    return makeDefaultPersistedSession();
  }
}

export async function saveChatSession(session: PersistedChatSession): Promise<void> {
  const safeSession: PersistedChatSession = {
    activeProvider: isChatProvider(session.activeProvider) ? session.activeProvider : "brain",
    sessions: {
      brain: {
        conversationId:
          typeof session.sessions.brain?.conversationId === "string"
            ? session.sessions.brain.conversationId
            : null,
        messages: (session.sessions.brain?.messages || []).slice(-MAX_PERSISTED_MESSAGES),
        threadContext: session.sessions.brain?.threadContext || { mode: "conversation" },
      },
      codex_cli: {
        conversationId:
          typeof session.sessions.codex_cli?.conversationId === "string"
            ? session.sessions.codex_cli.conversationId
            : null,
        messages: (session.sessions.codex_cli?.messages || []).slice(-MAX_PERSISTED_MESSAGES),
        threadContext: session.sessions.codex_cli?.threadContext || { mode: "conversation" },
      },
      claude_cli: {
        conversationId:
          typeof session.sessions.claude_cli?.conversationId === "string"
            ? session.sessions.claude_cli.conversationId
            : null,
        messages: (session.sessions.claude_cli?.messages || []).slice(-MAX_PERSISTED_MESSAGES),
        threadContext: session.sessions.claude_cli?.threadContext || { mode: "conversation" },
      },
    },
  };
  await AsyncStorage.setItem(CHAT_SESSION_KEY, JSON.stringify(safeSession));
}

export async function clearChatSession(): Promise<void> {
  await AsyncStorage.removeItem(CHAT_SESSION_KEY);
}
