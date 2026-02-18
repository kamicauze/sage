
import React from "react";
import { StyleSheet, Pressable, View } from "react-native";
import { Home, MessageSquare, CheckCircle, Settings } from "lucide-react-native";
import { BlurView } from "expo-blur";
import { COLORS, SPACING, RADIUS } from "../../constants/theme";

export type TabName = "dashboard" | "chat" | "approvals" | "settings";

interface TabBarProps {
    activeTab: TabName;
    onTabChange: (tab: TabName) => void;
}

export function TabBar({ activeTab, onTabChange }: TabBarProps) {
    const tabs: { name: TabName; icon: any }[] = [
        { name: "dashboard", icon: Home },
        { name: "approvals", icon: CheckCircle },
        { name: "chat", icon: MessageSquare },
        { name: "settings", icon: Settings },
    ];

    return (
        <View style={styles.container}>
            <BlurView intensity={30} tint="dark" style={styles.blur}>
                {tabs.map((tab) => {
                    const isActive = activeTab === tab.name;
                    const Icon = tab.icon;
                    return (
                        <Pressable
                            key={tab.name}
                            onPress={() => onTabChange(tab.name)}
                            style={styles.tab}
                        >
                            <Icon
                                size={24}
                                color={isActive ? COLORS.accent.primary : COLORS.text.secondary}
                            />
                            {isActive && <View style={styles.indicator} />}
                        </Pressable>
                    );
                })}
            </BlurView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        position: "absolute",
        bottom: SPACING.l,
        left: SPACING.l,
        right: SPACING.l,
        borderRadius: RADIUS.full,
        overflow: "hidden",
        elevation: 10,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 10,
    },
    blur: {
        flexDirection: "row",
        justifyContent: "space-around",
        alignItems: "center",
        paddingVertical: SPACING.m,
    },
    tab: {
        alignItems: "center",
        justifyContent: "center",
        padding: SPACING.s,
    },
    indicator: {
        position: "absolute",
        bottom: -8,
        width: 4,
        height: 4,
        borderRadius: 2,
        backgroundColor: COLORS.accent.primary,
    },
});
