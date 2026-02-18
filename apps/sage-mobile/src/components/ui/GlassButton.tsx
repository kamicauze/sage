
import React from "react";
import { StyleSheet, Pressable, Text, ViewStyle, TextStyle } from "react-native";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";

interface GlassButtonProps {
    onPress: () => void;
    title?: string;
    variant?: "primary" | "secondary" | "danger";
    style?: ViewStyle;
    textStyle?: TextStyle;
    disabled?: boolean;
}

export function GlassButton({
    onPress,
    title,
    variant = "primary",
    style,
    textStyle,
    disabled,
    children,
}: GlassButtonProps & { children?: React.ReactNode }) {
    const getBackgroundColor = () => {
        if (disabled) return "rgba(100, 100, 100, 0.3)";
        switch (variant) {
            case "primary":
                return COLORS.accent.primary;
            case "danger":
                return COLORS.accent.error;
            case "secondary":
            default:
                return COLORS.glass.background;
        }
    };

    const getTextColor = () => {
        if (disabled) return "rgba(255, 255, 255, 0.5)";
        return COLORS.text.primary;
    };

    return (
        <Pressable
            onPress={onPress}
            disabled={disabled}
            style={({ pressed }) => [
                styles.button,
                { backgroundColor: getBackgroundColor(), opacity: pressed ? 0.8 : 1 },
                style,
            ]}
        >
            {children || (
                <Text style={[styles.text, { color: getTextColor() }, textStyle]}>
                    {title}
                </Text>
            )}
        </Pressable>
    );
}

const styles = StyleSheet.create({
    button: {
        paddingVertical: SPACING.s + 4,
        paddingHorizontal: SPACING.m,
        borderRadius: RADIUS.m,
        alignItems: "center",
        justifyContent: "center",
    },
    text: {
        fontWeight: "600",
        fontSize: 16,
    },
});
