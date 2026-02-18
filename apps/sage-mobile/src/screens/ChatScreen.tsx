
import React, { useRef, useEffect } from "react";
import {
    StyleSheet,
    View,
    Text,
    TextInput,
    FlatList,
    KeyboardAvoidingView,
    Platform,
} from "react-native";
import { GlassCard } from "../components/ui/GlassCard";
import { GlassButton } from "../components/ui/GlassButton";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { COLORS, SPACING, RADIUS } from "../constants/theme";
import { Send } from "lucide-react-native";

interface ChatScreenProps {
    messages: Array<{ id: string; role: "user" | "assistant"; text: string }>;
    onSend: (text: string) => void;
    isSending: boolean;
}

export function ChatScreen({ messages, onSend, isSending }: ChatScreenProps) {
    const [text, setText] = React.useState("");
    const flatListRef = useRef<FlatList>(null);

    useEffect(() => {
        if (messages.length > 0) {
            setTimeout(() => {
                flatListRef.current?.scrollToEnd({ animated: true });
            }, 100);
        }
    }, [messages]);

    const handleSend = () => {
        if (text.trim() && !isSending) {
            onSend(text);
            setText("");
        }
    };

    const renderItem = ({
        item,
    }: {
        item: { id: string; role: "user" | "assistant"; text: string };
    }) => {
        const isUser = item.role === "user";
        return (
            <View
                style={[
                    styles.bubbleWrapper,
                    isUser ? styles.userWrapper : styles.assistantWrapper,
                ]}
            >
                <GlassCard
                    style={[
                        styles.bubble,
                        isUser ? styles.userBubble : styles.assistantBubble,
                    ]}
                    tint={isUser ? "light" : "dark"}
                    intensity={30}
                >
                    <Text style={styles.msgText}>{item.text}</Text>
                </GlassCard>
            </View>
        );
    };

    return (
        <ScreenLayout>
            <View style={styles.headerContainer}>
                <Text style={styles.screenTitle}>Chat with Sage</Text>
            </View>

            <FlatList
                ref={flatListRef}
                data={messages}
                renderItem={renderItem}
                keyExtractor={(item) => item.id}
                contentContainerStyle={styles.list}
            />

            <KeyboardAvoidingView
                behavior={Platform.OS === "ios" ? "padding" : "height"}
                keyboardVerticalOffset={Platform.OS === "ios" ? 100 : 0}
                style={styles.composerContainer}
            >
                <GlassCard style={styles.composer} intensity={50}>
                    <TextInput
                        style={styles.input}
                        placeholder="Ask Sage..."
                        placeholderTextColor={COLORS.text.tertiary}
                        value={text}
                        onChangeText={setText}
                        multiline
                    />
                    <GlassButton
                        onPress={handleSend}
                        disabled={!text.trim() || isSending}
                        style={styles.sendBtn}
                        variant="primary"
                    >
                        <Send size={20} color="#FFF" />
                    </GlassButton>
                </GlassCard>
            </KeyboardAvoidingView>
        </ScreenLayout>
    );
}

const styles = StyleSheet.create({
    headerContainer: {
        marginTop: SPACING.l,
        marginBottom: SPACING.s,
    },
    screenTitle: {
        fontSize: 24,
        fontWeight: "bold",
        color: COLORS.text.primary,
    },
    list: {
        paddingBottom: 120, // Space for composer
    },
    bubbleWrapper: {
        marginBottom: SPACING.s,
        flexDirection: "row",
    },
    userWrapper: {
        justifyContent: "flex-end",
    },
    assistantWrapper: {
        justifyContent: "flex-start",
    },
    bubble: {
        maxWidth: "80%",
        borderRadius: RADIUS.l,
        padding: SPACING.m,
    },
    userBubble: {
        borderBottomRightRadius: 4,
        backgroundColor: "rgba(59, 130, 246, 0.3)", // Blue tint
    },
    assistantBubble: {
        borderBottomLeftRadius: 4,
        backgroundColor: "rgba(255, 255, 255, 0.1)",
    },
    msgText: {
        color: COLORS.text.primary,
        fontSize: 16,
        lineHeight: 22,
    },
    composerContainer: {
        position: "absolute",
        bottom: 90, // Above tab bar
        left: 0,
        right: 0,
        paddingHorizontal: SPACING.m,
    },
    composer: {
        flexDirection: "row",
        alignItems: "center",
        padding: SPACING.s,
        borderRadius: RADIUS.full,
    },
    input: {
        flex: 1,
        color: COLORS.text.primary,
        paddingHorizontal: SPACING.s,
        maxHeight: 100,
    },
    sendBtn: {
        width: 40,
        height: 40,
        borderRadius: 20,
        paddingHorizontal: 0, // Override
        paddingVertical: 0, // Override
    },
});
