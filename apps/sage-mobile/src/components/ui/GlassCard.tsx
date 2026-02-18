
import React from "react";
import { StyleSheet, View, ViewStyle, Platform, StyleProp } from "react-native";
import { BlurView } from "expo-blur";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";

interface GlassCardProps {
    children: React.ReactNode;
    style?: StyleProp<ViewStyle>;
    intensity?: number;
    tint?: "light" | "dark" | "default";
}

export function GlassCard({
    children,
    style,
    intensity = 20,
    tint = "dark",
}: GlassCardProps) {
    if (Platform.OS === "android") {
        // Fallback for Android which has limited BlurView support in some versions/contexts
        // or just to be safe with performance.
        return (
            <View style={[styles.androidContainer, style]}>
                {children}
            </View>
        );
    }

    return (
        <BlurView intensity={intensity} tint={tint} style={[styles.container, style]}>
            {children}
        </BlurView>
    );
}

const styles = StyleSheet.create({
    container: {
        borderRadius: RADIUS.m,
        overflow: "hidden",
        backgroundColor: COLORS.glass.background,
        borderColor: COLORS.glass.border,
        borderWidth: 1,
        padding: SPACING.m,
    },
    androidContainer: {
        borderRadius: RADIUS.m,
        backgroundColor: "rgba(30, 30, 30, 0.85)", // Solid/Semi-transparent dark for Android
        borderColor: COLORS.glass.border,
        borderWidth: 1,
        padding: SPACING.m,
    },
});
