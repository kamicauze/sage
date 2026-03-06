import AsyncStorage from "@react-native-async-storage/async-storage";

const INDEX_KEY = "sage.chat.session.index.v1";
const MAX_SESSIONS = 50;

export interface SessionIndexEntry {
  conversationId: string;
  preview: string; // first user message, truncated to 80 chars
  provider: string;
  model: string;
  threadMode?: "conversation" | "project";
  projectId?: string;
  preferredNode?: string;
  messageCount: number;
  totalCost: number;
  updatedAt: string;
}

function isEntry(value: unknown): value is SessionIndexEntry {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return typeof v.conversationId === "string" && typeof v.preview === "string";
}

export async function loadSessionIndex(): Promise<SessionIndexEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry).slice(0, MAX_SESSIONS);
  } catch {
    return [];
  }
}

export async function saveSessionIndex(entries: SessionIndexEntry[]): Promise<void> {
  const capped = entries.slice(0, MAX_SESSIONS);
  await AsyncStorage.setItem(INDEX_KEY, JSON.stringify(capped));
}

export async function upsertSessionEntry(entry: SessionIndexEntry): Promise<SessionIndexEntry[]> {
  const entries = await loadSessionIndex();
  const idx = entries.findIndex((e) => e.conversationId === entry.conversationId);
  if (idx >= 0) {
    entries[idx] = entry;
  } else {
    entries.unshift(entry); // newest first
  }
  const capped = entries.slice(0, MAX_SESSIONS);
  await saveSessionIndex(capped);
  return capped;
}

export async function removeSessionEntry(conversationId: string): Promise<SessionIndexEntry[]> {
  const entries = await loadSessionIndex();
  const filtered = entries.filter((e) => e.conversationId !== conversationId);
  await saveSessionIndex(filtered);
  return filtered;
}
