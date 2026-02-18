import React, { useCallback, useEffect, useState } from "react";
import { Alert, StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import {
  checkHealth,
  fetchPendingApprovals,
  sendChatMessage,
  submitProposalDecision,
} from "./src/api/architect";
import {
  AppSettings,
  DEFAULT_SETTINGS,
  loadSettings,
  saveSettings,
} from "./src/storage/settings";
import { ApprovalRecord } from "./src/types/approvals";
import { TabBar, TabName } from "./src/components/navigation/TabBar";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { ApprovalsScreen } from "./src/screens/ApprovalsScreen";
import { ChatScreen } from "./src/screens/ChatScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { COLORS } from "./src/constants/theme";

type ChatRole = "user" | "assistant";

interface ChatBubble {
  id: string;
  role: ChatRole;
  text: string;
  timestamp: string;
}

function createMessage(role: ChatRole, text: string): ChatBubble {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    timestamp: new Date().toISOString(),
  };
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

export default function App() {
  const [activeTab, setActiveTab] = useState<TabName>("dashboard");

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
  const [chatMessages, setChatMessages] = useState<ChatBubble[]>([]);
  const [chatSending, setChatSending] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Initial Load
  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      const loaded = await loadSettings();
      if (!active) return;
      setSettings(loaded);
      setSettingsLoading(false);
    };
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  // Fetch Approvals
  const loadApprovals = useCallback(
    async (refresh = false) => {
      if (!settings.baseUrl.trim()) return;

      if (refresh) setListRefreshing(true);
      else setListLoading(true);

      try {
        const pending = await fetchPendingApprovals(settings);
        setApprovals(pending);
      } catch (error) {
        console.warn("Failed to load approvals", error);
      } finally {
        setListLoading(false);
        setListRefreshing(false);
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

  // Actions
  const handleSaveSettings = async (newSettings: AppSettings) => {
    setSettingsSaving(true);
    try {
      await saveSettings(newSettings);
      setSettings(newSettings);
      Alert.alert("Saved", "Settings updated successfully");
    } catch (error) {
      Alert.alert("Error", getErrorMessage(error));
    } finally {
      setSettingsSaving(false);
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

  const handleSendChat = async (text: string) => {
    setChatMessages((prev) => [...prev, createMessage("user", text)]);
    setChatSending(true);

    try {
      const response = await sendChatMessage(settings, {
        message: text,
        conversation_id: conversationId || undefined,
        provider: "brain",
      });
      setConversationId(response.conversation_id);
      setChatMessages((prev) => [...prev, createMessage("assistant", response.reply)]);
    } catch (error) {
      const errMsg = getErrorMessage(error);
      setChatMessages((prev) => [
        ...prev,
        createMessage("assistant", `Error: ${errMsg}`),
      ]);
    } finally {
      setChatSending(false);
    }
  };

  const renderScreen = () => {
    switch (activeTab) {
      case "dashboard":
        return <DashboardScreen />;
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
            messages={chatMessages}
            onSend={handleSendChat}
            isSending={chatSending}
          />
        );
      case "settings":
        return (
          <SettingsScreen
            settings={settings}
            onSave={handleSaveSettings}
            onTestConnection={handleTestConnection}
            isLoading={settingsSaving}
            isTesting={connectionTesting}
          />
        );
      default:
        return <DashboardScreen />;
    }
  };

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      {renderScreen()}
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
});
