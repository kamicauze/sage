import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

export interface AppSettings {
  baseUrl: string;
  tailscaleBaseUrl: string;
  preferTailscale: boolean;
  apiToken: string;
  reviewer: string;
}

export const SETTINGS_KEY = "sage.mobile.settings.v2";
const LEGACY_SETTINGS_KEY = "sage.mobile.settings.v1";
const TOKEN_KEY = "sage.mobile.api_token.v1";
const FALLBACK_TOKEN_KEY = "sage.mobile.api_token.fallback.v1";

const ENV_BASE_URL = (
  ((globalThis as unknown as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.EXPO_PUBLIC_SAGE_API_BASE_URL ?? "")
).trim();
const ENV_TAILSCALE_BASE_URL = (
  ((globalThis as unknown as { process?: { env?: Record<string, string | undefined> } })
    .process?.env?.EXPO_PUBLIC_SAGE_TAILSCALE_API_BASE_URL ?? "")
).trim();

const FALLBACK_BASE_URL = ENV_BASE_URL || "";
const FALLBACK_SECONDARY_BASE_URL = ENV_TAILSCALE_BASE_URL || "";

export const DEFAULT_SETTINGS: AppSettings = {
  baseUrl: FALLBACK_BASE_URL,
  tailscaleBaseUrl: FALLBACK_SECONDARY_BASE_URL,
  preferTailscale: false,
  apiToken: "",
  reviewer: "mobile_user",
};

function isSettingsLike(value: unknown): value is AppSettings {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.baseUrl === "string" &&
    (typeof candidate.apiToken === "string" || typeof candidate.apiToken === "undefined") &&
    (typeof candidate.tailscaleBaseUrl === "string" ||
      typeof candidate.tailscaleBaseUrl === "undefined") &&
    (typeof candidate.preferTailscale === "boolean" ||
      typeof candidate.preferTailscale === "undefined") &&
    typeof candidate.reviewer === "string"
  );
}

async function loadToken(): Promise<string> {
  try {
    const secure = await SecureStore.getItemAsync(TOKEN_KEY);
    if (secure && secure.trim()) {
      return secure;
    }
  } catch {
    // Fall through to AsyncStorage fallback for runtimes without secure store support.
  }
  return (await AsyncStorage.getItem(FALLBACK_TOKEN_KEY)) ?? "";
}

async function saveToken(token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
    await AsyncStorage.removeItem(FALLBACK_TOKEN_KEY);
    return;
  } catch {
    await AsyncStorage.setItem(FALLBACK_TOKEN_KEY, token);
  }
}

export async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = (await AsyncStorage.getItem(SETTINGS_KEY)) ?? (await AsyncStorage.getItem(LEGACY_SETTINGS_KEY));
    if (!raw) {
      return DEFAULT_SETTINGS;
    }

    const parsed: unknown = JSON.parse(raw);
    if (!isSettingsLike(parsed)) {
      return DEFAULT_SETTINGS;
    }

    const savedBaseUrl = parsed.baseUrl || DEFAULT_SETTINGS.baseUrl;
    const normalizedSavedBase = savedBaseUrl.trim().toLowerCase();
    const isLoopbackBase =
      normalizedSavedBase.startsWith("http://localhost") ||
      normalizedSavedBase.startsWith("https://localhost") ||
      normalizedSavedBase.startsWith("http://127.0.0.1") ||
      normalizedSavedBase.startsWith("https://127.0.0.1");
    const baseUrl = ENV_BASE_URL && isLoopbackBase ? ENV_BASE_URL : savedBaseUrl;

    const tailscaleBaseUrl = parsed.tailscaleBaseUrl || ENV_TAILSCALE_BASE_URL;
    const token = await loadToken();
    const legacyToken = typeof parsed.apiToken === "string" ? parsed.apiToken : "";
    if (!token && legacyToken) {
      await saveToken(legacyToken);
    }

    return {
      baseUrl,
      tailscaleBaseUrl,
      preferTailscale:
        typeof parsed.preferTailscale === "boolean"
          ? parsed.preferTailscale
          : false,
      apiToken: token || legacyToken,
      reviewer: parsed.reviewer || DEFAULT_SETTINGS.reviewer,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  await saveToken(settings.apiToken || "");
  await AsyncStorage.setItem(
    SETTINGS_KEY,
    JSON.stringify({
      ...settings,
      apiToken: "",
    })
  );
}
