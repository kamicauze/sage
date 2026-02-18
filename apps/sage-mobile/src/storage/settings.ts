import AsyncStorage from "@react-native-async-storage/async-storage";

export interface AppSettings {
  baseUrl: string;
  apiToken: string;
  reviewer: string;
}

export const SETTINGS_KEY = "sage.mobile.settings.v1";

export const DEFAULT_SETTINGS: AppSettings = {
  baseUrl: "http://localhost:8000",
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
    typeof candidate.apiToken === "string" &&
    typeof candidate.reviewer === "string"
  );
}

export async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = await AsyncStorage.getItem(SETTINGS_KEY);
    if (!raw) {
      return DEFAULT_SETTINGS;
    }

    const parsed: unknown = JSON.parse(raw);
    if (!isSettingsLike(parsed)) {
      return DEFAULT_SETTINGS;
    }

    return {
      baseUrl: parsed.baseUrl || DEFAULT_SETTINGS.baseUrl,
      apiToken: parsed.apiToken,
      reviewer: parsed.reviewer || DEFAULT_SETTINGS.reviewer,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}
