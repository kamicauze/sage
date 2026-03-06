import React from "react";
import {
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Animated, {
  FadeInDown,
  FadeIn,
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withRepeat,
  withSequence,
  withTiming,
  withDelay,
} from "react-native-reanimated";
import { ArrowUp, List, Paperclip, RefreshCcw, RotateCcw, X } from "lucide-react-native";
import { BlurView } from "expo-blur";
import { LinearGradient } from "expo-linear-gradient";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import Constants from "expo-constants";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import {
  ChatAttachmentPayload,
  ChatAttachmentPreview,
  ChatProvider,
  ProvidersMap,
} from "../types/chat";
import type { ProjectControlCatalogResponse, ProjectThreadContext } from "../types/projectControl";
import type { ChatBubbleMeta } from "../storage/chatSession";
import type { SessionIndexEntry } from "../storage/sessionIndex";
import { ModelSelector } from "../components/chat/ModelSelector";
import { SessionListSheet } from "../components/chat/SessionListSheet";

const MAX_ATTACHMENTS = 4;
const MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024;

interface ChatComposerSubmit {
  text: string;
  attachments?: ChatAttachmentPayload[];
}

interface ChatScreenProps {
  provider: ChatProvider;
  model: string;
  onProviderChange: (provider: ChatProvider) => void;
  onModelChange: (provider: string, model: string) => void;
  availableProviders: ProvidersMap;
  onSyncConversation: () => void;
  isSyncingConversation: boolean;
  conversationId?: string | null;
  messages: Array<{
    id: string;
    role: "system" | "user" | "assistant";
    text: string;
    timestamp?: string;
    attachments?: ChatAttachmentPreview[];
    meta?: ChatBubbleMeta;
  }>;
  onSend: (payload: ChatComposerSubmit) => void;
  onNewChat: () => void;
  isSending: boolean;
  statusOnline: boolean;
  statusText: string;
  statusMeta?: string;
  sessionIndex: SessionIndexEntry[];
  showSessionList: boolean;
  onToggleSessionList: () => void;
  onSwitchSession: (conversationId: string) => void;
  onDeleteSession: (conversationId: string) => void;
  sessionTotals: { cost: number; inputTokens: number; outputTokens: number };
  threadContext: ProjectThreadContext;
  projectCatalog: ProjectControlCatalogResponse | null;
  onToggleThreadMode: () => void;
  onCycleProject: () => void;
  onCycleProjectNode: () => void;
  onHandoffProject: () => void;
}

const QUICK_PROMPTS = [
  { emoji: "📊", text: "Give me a quick system summary" },
  { emoji: "🎯", text: "What should I focus on next?" },
  { emoji: "📥", text: "Any pending approvals I should review?" },
];

const PROVIDER_OPTIONS: Array<{ value: ChatProvider; label: string }> = [
  { value: "brain", label: "Brain" },
];

// Animated bouncing dots for the typing indicator
function TypingDots() {
  const d0 = useSharedValue(0);
  const d1 = useSharedValue(0);
  const d2 = useSharedValue(0);

  React.useEffect(() => {
    const bounce = (sv: typeof d0, delay: number) => {
      sv.value = withDelay(
        delay,
        withRepeat(
          withSequence(
            withTiming(-5, { duration: 260 }),
            withTiming(0, { duration: 260 })
          ),
          -1
        )
      );
    };
    bounce(d0, 0);
    bounce(d1, 130);
    bounce(d2, 260);
  }, []);

  const s0 = useAnimatedStyle(() => ({ transform: [{ translateY: d0.value }] }));
  const s1 = useAnimatedStyle(() => ({ transform: [{ translateY: d1.value }] }));
  const s2 = useAnimatedStyle(() => ({ transform: [{ translateY: d2.value }] }));

  return (
    <View style={styles.typingDots}>
      <Animated.View style={[styles.typingDot, s0]} />
      <Animated.View style={[styles.typingDot, s1]} />
      <Animated.View style={[styles.typingDot, s2]} />
    </View>
  );
}

// Send button with spring scale feedback and gradient fill
function SendButton({ onPress, disabled }: { onPress: () => void; disabled: boolean }) {
  const scale = useSharedValue(1);

  const animStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  const handlePressIn = () => {
    scale.value = withSpring(0.86, { damping: 12, stiffness: 220 });
  };

  const handlePressOut = () => {
    scale.value = withSpring(1, { damping: 12, stiffness: 220 });
  };

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={disabled}
    >
      <Animated.View style={[styles.sendButton, animStyle]}>
        <LinearGradient
          colors={disabled ? ["rgba(47,107,255,0.3)", "rgba(29,79,201,0.3)"] : [...COLORS.gradients.cta]}
          style={[StyleSheet.absoluteFill, { borderRadius: RADIUS.full }]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        />
        <ArrowUp size={19} color={disabled ? COLORS.text.dim : COLORS.text.primary} />
      </Animated.View>
    </Pressable>
  );
}

function AttachButton({
  onPress,
  disabled,
}: {
  onPress: () => void;
  disabled: boolean;
}) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={[styles.attachButton, disabled && styles.attachButtonDisabled]}>
      <Paperclip size={17} color={disabled ? COLORS.text.dim : COLORS.text.secondary} />
    </Pressable>
  );
}

function formatBytes(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes}B`;
  if (sizeBytes < 1024 * 1024) return `${Math.round(sizeBytes / 1024)}KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)}MB`;
}

function estimateBase64Size(dataBase64: string): number {
  if (!dataBase64) return 0;
  return Math.floor((dataBase64.length * 3) / 4);
}

export function ChatScreen({
  provider,
  model,
  onProviderChange,
  onModelChange,
  availableProviders,
  onSyncConversation,
  isSyncingConversation,
  conversationId,
  messages,
  onSend,
  onNewChat,
  isSending,
  statusOnline,
  statusText,
  statusMeta,
  sessionIndex,
  showSessionList,
  onToggleSessionList,
  onSwitchSession,
  onDeleteSession,
  sessionTotals,
  threadContext,
  projectCatalog,
  onToggleThreadMode,
  onCycleProject,
  onCycleProjectNode,
  onHandoffProject,
}: ChatScreenProps) {
  const [text, setText] = React.useState("");
  const [attachments, setAttachments] = React.useState<ChatAttachmentPayload[]>([]);
  const [isPickingAttachment, setIsPickingAttachment] = React.useState(false);
  const [keyboardVisible, setKeyboardVisible] = React.useState(false);
  const scrollRef = React.useRef<ScrollView>(null);
  const providerLabel =
    availableProviders[provider]?.label ||
    PROVIDER_OPTIONS.find((option) => option.value === provider)?.label ||
    "Agent";
  const activeProject = projectCatalog?.projects.find(
    (project) => project.project_id === threadContext.project_id
  );
  const activeProjectNode = activeProject?.nodes.find(
    (node) => node.node_id === threadContext.preferred_node
  );
  const linkedDocs = activeProject?.google_assets || [];

  const send = React.useCallback(() => {
    const payload = text.trim();
    if ((!payload && attachments.length === 0) || isSending) return;

    // Slash command detection
    if (payload.startsWith("/")) {
      const cmd = payload.split(/\s+/)[0].toLowerCase();
      const arg = payload.slice(cmd.length).trim();
      switch (cmd) {
        case "/new":
          onNewChat();
          setText("");
          return;
        case "/clear":
          Alert.alert("Clear chat?", "This will start a new conversation.", [
            { text: "Cancel", style: "cancel" },
            { text: "Clear", style: "destructive", onPress: () => onNewChat() },
          ]);
          setText("");
          return;
        case "/model":
          if (arg) {
            onModelChange(provider, arg);
            setText("");
            return;
          }
          break;
        case "/status": {
          const statusMsg = [
            `Provider: ${provider} / ${model}`,
            `Session: ${sessionTotals.inputTokens + sessionTotals.outputTokens} tokens · $${sessionTotals.cost.toFixed(4)}`,
            `Messages: ${messages.length}`,
            conversationId ? `Thread: ${conversationId}` : "Thread: none",
          ].join("\n");
          onSend({ text: statusMsg });
          setText("");
          return;
        }
        default:
          break;
      }
    }

    onSend({
      text: payload || "Please use the attachment context to respond.",
      attachments,
    });
    setText("");
    setAttachments([]);
  }, [attachments, isSending, onSend, text, provider, model, sessionTotals, messages.length, conversationId, onNewChat, onModelChange]);

  const removeAttachment = React.useCallback((id: string) => {
    setAttachments((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const addAttachment = React.useCallback(
    (next: ChatAttachmentPayload) => {
      setAttachments((prev) => {
        if (prev.length >= MAX_ATTACHMENTS) {
          return prev;
        }
        return [...prev, next].slice(0, MAX_ATTACHMENTS);
      });
    },
    []
  );

  const pickAttachment = React.useCallback(async () => {
    if (isSending || isPickingAttachment) return;
    if (attachments.length >= MAX_ATTACHMENTS) {
      Alert.alert("Attachment limit", `You can attach up to ${MAX_ATTACHMENTS} files per message.`);
      return;
    }

    try {
      setIsPickingAttachment(true);
      const result = await DocumentPicker.getDocumentAsync({
        multiple: true,
        copyToCacheDirectory: true,
        type: ["image/*", "text/*", "application/pdf", "application/json"],
      });

      if (result.canceled) return;

      const next: ChatAttachmentPayload[] = [];
      const remainingSlots = MAX_ATTACHMENTS - attachments.length;
      for (const asset of result.assets.slice(0, remainingSlots)) {
        const name = asset.name || "attachment";
        const mime = asset.mimeType || "application/octet-stream";
        const uri = asset.uri;
        if (!uri) continue;

        const info = await FileSystem.getInfoAsync(uri);
        const sizeBytes = Number(info.exists ? info.size || asset.size || 0 : asset.size || 0);
        if (!sizeBytes || sizeBytes > MAX_ATTACHMENT_BYTES) {
          Alert.alert(
            "Attachment too large",
            `${name} must be under ${formatBytes(MAX_ATTACHMENT_BYTES)}.`
          );
          continue;
        }

        const dataBase64 = await FileSystem.readAsStringAsync(uri, {
          encoding: "base64",
        });
        if (!dataBase64) continue;

        next.push({
          id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name,
          mime_type: mime,
          size_bytes: sizeBytes,
          data_base64: dataBase64,
        });
      }

      if (next.length) {
        setAttachments((prev) => [...prev, ...next].slice(0, MAX_ATTACHMENTS));
      }
    } catch (error) {
      Alert.alert("Attach failed", "Could not read the selected file.");
    } finally {
      setIsPickingAttachment(false);
    }
  }, [attachments.length, isSending, isPickingAttachment]);

  const pickImageFromLibrary = React.useCallback(async () => {
    if (isSending || isPickingAttachment) return;
    if (attachments.length >= MAX_ATTACHMENTS) {
      Alert.alert("Attachment limit", `You can attach up to ${MAX_ATTACHMENTS} files per message.`);
      return;
    }

    try {
      setIsPickingAttachment(true);
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert("Permission needed", "Allow photo library access to attach images.");
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.7,
        base64: true,
      });
      if (result.canceled || !result.assets?.length) return;

      const asset = result.assets[0];
      const dataBase64 = asset.base64 || "";
      if (!dataBase64) {
        Alert.alert("Attach failed", "Could not read selected image.");
        return;
      }

      const sizeBytes = Number(asset.fileSize || estimateBase64Size(dataBase64));
      if (!sizeBytes || sizeBytes > MAX_ATTACHMENT_BYTES) {
        Alert.alert(
          "Attachment too large",
          `Image must be under ${formatBytes(MAX_ATTACHMENT_BYTES)}.`
        );
        return;
      }

      addAttachment({
        id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: asset.fileName || `photo-${Date.now()}.jpg`,
        mime_type: asset.mimeType || "image/jpeg",
        size_bytes: sizeBytes,
        data_base64: dataBase64,
      });
    } catch {
      Alert.alert("Attach failed", "Could not open photo library.");
    } finally {
      setIsPickingAttachment(false);
    }
  }, [addAttachment, attachments.length, isPickingAttachment, isSending]);

  const captureImageFromCamera = React.useCallback(async () => {
    if (isSending || isPickingAttachment) return;
    if (attachments.length >= MAX_ATTACHMENTS) {
      Alert.alert("Attachment limit", `You can attach up to ${MAX_ATTACHMENTS} files per message.`);
      return;
    }

    try {
      setIsPickingAttachment(true);
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert("Permission needed", "Allow camera access to take a photo.");
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: ["images"],
        quality: 0.7,
        base64: true,
      });
      if (result.canceled || !result.assets?.length) return;

      const asset = result.assets[0];
      const dataBase64 = asset.base64 || "";
      if (!dataBase64) {
        Alert.alert("Attach failed", "Could not read captured photo.");
        return;
      }

      const sizeBytes = Number(asset.fileSize || estimateBase64Size(dataBase64));
      if (!sizeBytes || sizeBytes > MAX_ATTACHMENT_BYTES) {
        Alert.alert(
          "Attachment too large",
          `Photo must be under ${formatBytes(MAX_ATTACHMENT_BYTES)}.`
        );
        return;
      }

      addAttachment({
        id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: asset.fileName || `camera-${Date.now()}.jpg`,
        mime_type: asset.mimeType || "image/jpeg",
        size_bytes: sizeBytes,
        data_base64: dataBase64,
      });
    } catch {
      Alert.alert("Attach failed", "Could not open camera.");
    } finally {
      setIsPickingAttachment(false);
    }
  }, [addAttachment, attachments.length, isPickingAttachment, isSending]);

  const chooseAttachmentSource = React.useCallback(() => {
    if (isSending || isPickingAttachment) return;
    Alert.alert("Attach", "Choose source", [
      { text: "Camera", onPress: () => void captureImageFromCamera() },
      { text: "Photo Library", onPress: () => void pickImageFromLibrary() },
      { text: "Files", onPress: () => void pickAttachment() },
      { text: "Cancel", style: "cancel" },
    ]);
  }, [
    captureImageFromCamera,
    isPickingAttachment,
    isSending,
    pickAttachment,
    pickImageFromLibrary,
  ]);

  React.useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, () => setKeyboardVisible(true));
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardVisible(false));

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

  React.useEffect(() => {
    const id = setTimeout(() => {
      scrollRef.current?.scrollToEnd({ animated: true });
    }, 60);
    return () => clearTimeout(id);
  }, [messages, isSending]);

  const submitQuickPrompt = React.useCallback(
    (prompt: string) => {
      if (isSending) return;
      onSend({ text: prompt });
    },
    [isSending, onSend]
  );

  const renderTime = React.useCallback((iso?: string) => {
    if (!iso) return "";
    const parsed = new Date(iso);
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }, []);

  const renderAuthor = React.useCallback(
    (role: "system" | "user" | "assistant") => {
      if (role === "user") return "You";
      if (role === "system") return "Architect system";
      if (provider === "brain") return "Sage";
      return `Architect ↔ ${providerLabel}`;
    },
    [provider, providerLabel]
  );

  return (
    <ScreenLayout>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? (Constants.statusBarHeight || 0) : 0}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerTitleWrap}>
            <Text style={styles.headerEmoji}>✨</Text>
            <Text style={styles.headerTitle}>Sage</Text>
          </View>
          <View style={styles.headerRight}>
            <View style={styles.headerStatus}>
              <View
                style={[
                  styles.onlineDot,
                  { backgroundColor: statusOnline ? COLORS.status.online : COLORS.status.critical },
                ]}
              />
              <Text style={styles.headerStatusText}>{statusText}</Text>
            </View>
            <View style={styles.headerActions}>
              <Pressable onPress={onToggleSessionList} style={styles.sessionListButton}>
                <List size={13} color={COLORS.text.secondary} />
              </Pressable>
              <Pressable onPress={onNewChat} style={styles.newChatButton}>
                <RotateCcw size={13} color={COLORS.text.secondary} />
                <Text style={styles.newChatButtonText}>New</Text>
              </Pressable>
            </View>
          </View>
        </View>
        {statusMeta ? (
          <Text style={styles.statusMeta}>⚡ {statusMeta}</Text>
        ) : null}
        <View style={styles.providerPanel}>
          <View style={styles.providerRow}>
            <ModelSelector
              provider={provider}
              model={model}
              availableProviders={availableProviders}
              onSelect={(p, m) => {
                if (p !== provider) onProviderChange(p as ChatProvider);
                onModelChange(p, m);
              }}
              disabled={isSending || isSyncingConversation}
            />
            <Pressable
              onPress={onSyncConversation}
              style={styles.syncButton}
              disabled={isSending || isSyncingConversation}
            >
              <RefreshCcw size={12} color={COLORS.text.secondary} />
              <Text style={styles.syncButtonText}>
                {isSyncingConversation ? "Syncing..." : "Sync"}
              </Text>
            </Pressable>
          </View>
          <View style={styles.providerActions}>
            <Text style={styles.threadIdText}>
              {threadContext.mode === "project" && threadContext.project_id
                ? `${threadContext.project_id} · ${threadContext.preferred_node || "auto"}`
                : sessionTotals.cost > 0
                ? `${sessionTotals.inputTokens + sessionTotals.outputTokens} tok · $${sessionTotals.cost.toFixed(4)}`
                : conversationId
                  ? `Thread: ${conversationId.slice(0, 12)}...`
                  : "New conversation"}
            </Text>
          </View>
          <View style={styles.threadModeRow}>
            <Pressable onPress={onToggleThreadMode} style={styles.contextChip}>
              <Text style={styles.contextChipText}>
                {threadContext.mode === "project" ? "Project" : "Conversation"}
              </Text>
            </Pressable>
            {threadContext.mode === "project" ? (
              <>
                <Pressable onPress={onCycleProject} style={styles.contextChip}>
                  <Text style={styles.contextChipText}>
                    {threadContext.project_id || "Pick project"}
                  </Text>
                </Pressable>
                <Pressable onPress={onCycleProjectNode} style={styles.contextChip}>
                  <Text style={styles.contextChipText}>
                    {threadContext.preferred_node || "Pick node"}
                  </Text>
                </Pressable>
                <Pressable onPress={onHandoffProject} style={styles.contextChipAccent}>
                  <Text style={styles.contextChipAccentText}>Handoff</Text>
                </Pressable>
                {linkedDocs.length ? (
                  <View style={styles.contextChip}>
                    <Text style={styles.contextChipText}>{linkedDocs.length} docs</Text>
                  </View>
                ) : null}
              </>
            ) : null}
          </View>
          {threadContext.mode === "project" && activeProjectNode ? (
            <>
              <Text style={styles.projectMetaText}>
                {activeProjectNode.branch} · {activeProjectNode.head_sha} ·{" "}
                {activeProjectNode.dirty ? `${activeProjectNode.dirty_count} dirty` : "clean"} ·{" "}
                {activeProjectNode.online ? "online" : "offline"}
              </Text>
              {linkedDocs.length ? (
                <View style={styles.projectDocsRow}>
                  {linkedDocs.slice(0, 4).map((asset) => (
                    <Pressable
                      key={`${asset.asset_id}-${asset.role || asset.title}`}
                      onPress={() => {
                        if (asset.url) {
                          void Linking.openURL(asset.url);
                        }
                      }}
                      style={styles.projectDocChip}
                    >
                      <Text style={styles.projectDocChipText}>
                        {asset.role ? `${asset.role}: ` : ""}
                        {asset.title}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
            </>
          ) : null}
        </View>

        {/* Message thread */}
        <View style={styles.threadWrap}>
          <ScrollView
            ref={scrollRef}
            contentContainerStyle={styles.threadContent}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {messages.length === 0 ? (
              <Animated.View entering={FadeIn.duration(400)} style={styles.emptyWrap}>
                <Text style={styles.emptyIcon}>🤖</Text>
                <Text style={styles.emptyTitle}>Start a conversation</Text>
                <Text style={styles.emptySubtitle}>
                  {threadContext.mode === "project" && threadContext.project_id
                    ? `Run ${threadContext.executor || providerLabel} on ${threadContext.project_id} from mobile.`
                    : `Send prompts into the Architect + ${providerLabel} thread from mobile.`}
                </Text>
                <View style={styles.promptChips}>
                  {QUICK_PROMPTS.map((prompt) => (
                    <Pressable
                      key={prompt.text}
                      onPress={() => submitQuickPrompt(prompt.text)}
                      style={styles.promptChip}
                    >
                      <Text style={styles.promptChipEmoji}>{prompt.emoji}</Text>
                      <Text style={styles.promptChipText}>{prompt.text}</Text>
                    </Pressable>
                  ))}
                </View>
              </Animated.View>
            ) : (
              messages.map((message) => {
                const isUser = message.role === "user";
                const isSystem = message.role === "system";
                if (!isSystem && !isUser && !message.text.trim()) return null;
                return (
                  <Animated.View
                    key={message.id}
                    entering={FadeInDown.duration(280).springify().damping(16)}
                    style={[
                      styles.messageRow,
                      isSystem
                        ? styles.messageRowSystem
                        : isUser
                          ? styles.messageRowUser
                          : styles.messageRowAssistant,
                    ]}
                  >
                    <View
                      style={[
                        styles.bubble,
                        isSystem
                          ? styles.bubbleSystem
                          : isUser
                            ? styles.bubbleUser
                            : styles.bubbleAssistant,
                      ]}
                    >
                      {isUser && (
                        <LinearGradient
                          colors={["rgba(47,107,255,0.18)", "rgba(29,79,201,0.08)"]}
                          style={StyleSheet.absoluteFill}
                          start={{ x: 0, y: 0 }}
                          end={{ x: 1, y: 1 }}
                        />
                      )}
                      <Text style={styles.bubbleText}>{message.text}</Text>
                      {!isUser && !isSystem && message.meta ? (
                        <Text style={styles.tokenMeta}>
                          {[
                            message.meta.model || provider,
                            message.meta.input_tokens || message.meta.output_tokens
                              ? `${message.meta.input_tokens ?? 0}+${message.meta.output_tokens ?? 0} tok`
                              : null,
                            message.meta.cost ? `$${message.meta.cost.toFixed(4)}` : null,
                            message.meta.latency_ms ? `${message.meta.latency_ms}ms` : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </Text>
                      ) : null}
                      {isUser && message.attachments?.length ? (
                        <View style={styles.messageAttachmentList}>
                          {message.attachments.map((attachment) => (
                            <View key={`${message.id}-${attachment.name}`} style={styles.messageAttachmentChip}>
                              <Paperclip size={12} color={COLORS.text.secondary} />
                              <Text style={styles.messageAttachmentText}>
                                {attachment.name} · {formatBytes(attachment.size_bytes)}
                              </Text>
                            </View>
                          ))}
                        </View>
                      ) : null}
                    </View>
                    <Text
                      style={[
                        styles.metaText,
                        isSystem
                          ? styles.metaTextSystem
                          : isUser
                            ? styles.metaTextUser
                            : styles.metaTextAssistant,
                      ]}
                    >
                      {renderAuthor(message.role)}
                      {renderTime(message.timestamp) ? ` · ${renderTime(message.timestamp)}` : ""}
                    </Text>
                  </Animated.View>
                );
              })
            )}

            {isSending ? (
              <Animated.View
                entering={FadeInDown.duration(200)}
                style={[styles.messageRow, styles.messageRowAssistant]}
              >
                <View style={[styles.bubble, styles.bubbleAssistant]}>
                  <TypingDots />
                </View>
                <Text style={[styles.metaText, styles.metaTextAssistant]}>
                  {provider === "brain" ? "Sage" : `Architect ↔ ${providerLabel}`}
                </Text>
              </Animated.View>
            ) : null}
          </ScrollView>
        </View>

        {/* Composer */}
        <View
          style={[
            styles.composerWrap,
            keyboardVisible ? styles.composerWrapKeyboardOpen : styles.composerWrapKeyboardClosed,
          ]}
        >
          {attachments.length ? (
            <View style={styles.attachmentTray}>
              {attachments.map((attachment) => (
                <View key={attachment.id} style={styles.attachmentChip}>
                  <Paperclip size={12} color={COLORS.text.secondary} />
                  <Text style={styles.attachmentChipText} numberOfLines={1}>
                    {attachment.name} · {formatBytes(attachment.size_bytes)}
                  </Text>
                  <Pressable
                    onPress={() => removeAttachment(attachment.id)}
                    disabled={isSending}
                    hitSlop={8}
                    style={styles.attachmentRemove}
                  >
                    <X size={12} color={COLORS.text.tertiary} />
                  </Pressable>
                </View>
              ))}
            </View>
          ) : null}
          <View style={styles.composerOuter}>
            {Platform.OS === "ios" ? (
              <BlurView
                tint="systemUltraThinMaterialDark"
                intensity={72}
                style={[StyleSheet.absoluteFill, { borderRadius: RADIUS.l }]}
              />
            ) : (
              <View style={[StyleSheet.absoluteFill, styles.composerAndroidBg]} />
            )}
            <AttachButton
              onPress={chooseAttachmentSource}
              disabled={isSending || isPickingAttachment || attachments.length >= MAX_ATTACHMENTS}
            />
            <TextInput
              style={styles.input}
              value={text}
              onChangeText={setText}
              placeholder={
                attachments.length
                  ? "Add context for these files (optional)..."
                  : `Message ${provider === "brain" ? "Sage" : `Architect + ${providerLabel}`}...`
              }
              placeholderTextColor={COLORS.text.tertiary}
              autoCapitalize="sentences"
              autoCorrect
              multiline
              maxLength={1000}
            />
            <SendButton onPress={send} disabled={(!text.trim() && attachments.length === 0) || isSending} />
          </View>
        </View>
      </KeyboardAvoidingView>
      <SessionListSheet
        visible={showSessionList}
        onClose={onToggleSessionList}
        sessions={sessionIndex}
        activeSessionId={conversationId ?? null}
        onSwitchSession={(id) => {
          onSwitchSession(id);
          onToggleSessionList();
        }}
        onDeleteSession={onDeleteSession}
        onNewChat={() => {
          onNewChat();
          onToggleSessionList();
        }}
      />
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: SPACING.s,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingBottom: SPACING.s,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.line,
  },
  headerTitleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
  },
  headerEmoji: {
    fontSize: 17,
  },
  headerTitle: {
    color: COLORS.text.primary,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  headerStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
  },
  headerRight: {
    alignItems: "flex-end",
    gap: SPACING.xs,
  },
  headerStatusText: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
  },
  sessionListButton: {
    width: 30,
    height: 30,
    borderRadius: RADIUS.full,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(18, 34, 64, 0.72)",
  },
  newChatButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(18, 34, 64, 0.72)",
  },
  newChatButtonText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "600",
  },
  onlineDot: {
    width: 7,
    height: 7,
    borderRadius: RADIUS.full,
  },
  statusMeta: {
    marginTop: SPACING.xs,
    color: COLORS.text.tertiary,
    fontSize: 11,
  },
  providerPanel: {
    marginTop: SPACING.s,
    gap: SPACING.xs,
  },
  providerRow: {
    flexDirection: "row",
    gap: SPACING.xs,
  },
  providerChip: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.xs,
    backgroundColor: "rgba(12, 26, 51, 0.7)",
  },
  providerChipActive: {
    borderColor: "rgba(120, 166, 255, 0.8)",
    backgroundColor: "rgba(38, 88, 214, 0.35)",
  },
  providerChipText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    fontWeight: "600",
  },
  providerChipTextActive: {
    color: COLORS.text.primary,
  },
  providerActions: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  threadIdText: {
    color: COLORS.text.tertiary,
    fontSize: 11,
  },
  threadModeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
  },
  contextChip: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: 6,
    backgroundColor: "rgba(12, 26, 51, 0.72)",
  },
  contextChipText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "600",
  },
  contextChipAccent: {
    borderWidth: 1,
    borderColor: `${COLORS.accent.primary}88`,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: 6,
    backgroundColor: `${COLORS.accent.primary}18`,
  },
  contextChipAccentText: {
    color: COLORS.accent.primary,
    fontSize: 11,
    fontWeight: "700",
  },
  projectMetaText: {
    color: COLORS.text.dim,
    fontSize: 11,
  },
  projectDocsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACING.xs,
    marginTop: SPACING.xs,
  },
  projectDocChip: {
    borderWidth: 1,
    borderColor: `${COLORS.accent.info}55`,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: 6,
    backgroundColor: "rgba(18, 54, 99, 0.72)",
  },
  projectDocChipText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "600",
  },
  syncButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
    backgroundColor: "rgba(12, 26, 51, 0.72)",
  },
  syncButtonText: {
    color: COLORS.text.secondary,
    fontSize: 11,
    fontWeight: "600",
  },

  // Thread
  threadWrap: {
    flex: 1,
    marginTop: SPACING.s,
  },
  threadContent: {
    paddingBottom: SPACING.m,
    gap: SPACING.s,
  },

  // Empty state
  emptyWrap: {
    marginTop: SPACING.xl,
    gap: SPACING.s,
  },
  emptyIcon: {
    fontSize: 36,
    marginBottom: SPACING.xs,
  },
  emptyTitle: {
    color: COLORS.text.primary,
    fontSize: 18,
    fontWeight: "700",
  },
  emptySubtitle: {
    color: COLORS.text.secondary,
    fontSize: 14,
    lineHeight: 20,
  },
  promptChips: {
    marginTop: SPACING.s,
    gap: SPACING.s,
  },
  promptChip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: SPACING.xs,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(18, 34, 64, 0.82)",
  },
  promptChipEmoji: {
    fontSize: 14,
  },
  promptChipText: {
    color: COLORS.text.secondary,
    fontSize: 13,
  },

  // Messages
  messageRow: {
    maxWidth: "88%",
    gap: SPACING.xs,
  },
  messageRowAssistant: {
    alignSelf: "flex-start",
  },
  messageRowUser: {
    alignSelf: "flex-end",
    alignItems: "flex-end",
  },
  messageRowSystem: {
    alignSelf: "center",
    maxWidth: "95%",
  },
  bubble: {
    borderRadius: RADIUS.m,
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    borderWidth: 1,
    overflow: "hidden",
  },
  bubbleAssistant: {
    backgroundColor: "rgba(18, 34, 64, 0.88)",
    borderColor: COLORS.border,
  },
  bubbleUser: {
    backgroundColor: "rgba(38, 88, 214, 0.88)",
    borderColor: "rgba(120, 166, 255, 0.65)",
  },
  bubbleSystem: {
    backgroundColor: "rgba(28, 36, 55, 0.9)",
    borderColor: "rgba(162, 176, 210, 0.4)",
  },
  bubbleText: {
    color: COLORS.text.primary,
    fontSize: 15,
    lineHeight: 22,
  },
  tokenMeta: {
    marginTop: 6,
    color: COLORS.text.dim,
    fontSize: 10,
    letterSpacing: 0.3,
  },
  metaText: {
    fontSize: 11,
    color: COLORS.text.tertiary,
    letterSpacing: 0.2,
  },
  metaTextAssistant: {
    textAlign: "left",
  },
  metaTextUser: {
    textAlign: "right",
  },
  metaTextSystem: {
    textAlign: "center",
  },

  // Typing dots
  typingDots: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingVertical: 2,
  },
  typingDot: {
    width: 7,
    height: 7,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.text.secondary,
  },

  // Composer
  composerWrap: {
    paddingTop: SPACING.s,
    gap: SPACING.s,
  },
  composerWrapKeyboardClosed: {
    paddingBottom: LAYOUT.tabBarHeight - SPACING.s,
  },
  composerWrapKeyboardOpen: {
    paddingBottom: SPACING.s,
  },
  attachmentTray: {
    gap: SPACING.xs,
  },
  attachmentChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(18, 34, 64, 0.92)",
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
  },
  attachmentChipText: {
    flex: 1,
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  attachmentRemove: {
    width: 20,
    height: 20,
    borderRadius: RADIUS.full,
    alignItems: "center",
    justifyContent: "center",
  },
  composerOuter: {
    minHeight: 54,
    borderRadius: RADIUS.l,
    borderWidth: 1,
    borderColor: COLORS.border,
    overflow: "hidden",
    flexDirection: "row",
    alignItems: "center",
    paddingLeft: SPACING.s,
    paddingRight: SPACING.s,
    paddingVertical: SPACING.xs,
    gap: SPACING.s,
  },
  composerAndroidBg: {
    backgroundColor: "rgba(12, 22, 40, 0.96)",
    borderRadius: RADIUS.l,
  },
  attachButton: {
    width: 34,
    height: 34,
    borderRadius: RADIUS.full,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: "rgba(18, 34, 64, 0.85)",
  },
  attachButtonDisabled: {
    opacity: 0.55,
  },
  input: {
    flex: 1,
    color: COLORS.text.primary,
    fontSize: 15,
    lineHeight: 22,
    maxHeight: 140,
    minHeight: 40,
    paddingTop: Platform.OS === "ios" ? 8 : 6,
    paddingBottom: Platform.OS === "ios" ? 8 : 6,
    textAlignVertical: "center",
  },
  messageAttachmentList: {
    marginTop: SPACING.xs,
    gap: SPACING.xs,
  },
  messageAttachmentChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    borderWidth: 1,
    borderColor: "rgba(120, 166, 255, 0.45)",
    borderRadius: RADIUS.full,
    paddingHorizontal: SPACING.s,
    paddingVertical: 4,
    backgroundColor: "rgba(15, 30, 58, 0.45)",
    alignSelf: "flex-start",
  },
  messageAttachmentText: {
    color: COLORS.text.secondary,
    fontSize: 11,
  },

  // Send button
  sendButton: {
    width: 38,
    height: 38,
    borderRadius: RADIUS.full,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(47, 107, 255, 0.4)",
  },
});
