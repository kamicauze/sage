import React from "react";
import {
  Pressable,
  StyleProp,
  StyleSheet,
  Text,
  TextStyle,
  View,
  ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";

interface GlassButtonProps {
  onPress: () => void;
  title?: string;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  disabled?: boolean;
  children?: React.ReactNode;
}

const VARIANT_TEXT: Record<NonNullable<GlassButtonProps["variant"]>, string> = {
  primary: COLORS.text.primary,
  secondary: COLORS.text.primary,
  danger: COLORS.accent.error,
  ghost: COLORS.text.secondary,
};

export function GlassButton({
  onPress,
  title,
  variant = "primary",
  style,
  textStyle,
  disabled,
  children,
}: GlassButtonProps) {
  const isPrimary = variant === "primary";

  const renderBackground = () => {
    if (isPrimary) {
      return (
        <LinearGradient
          colors={COLORS.gradients.cta}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={StyleSheet.absoluteFillObject}
        />
      );
    }

    if (variant === "danger") {
      return (
        <View
          style={[
            StyleSheet.absoluteFillObject,
            { backgroundColor: "rgba(255, 93, 95, 0.09)" },
          ]}
        />
      );
    }

    return (
      <View
        style={[
          StyleSheet.absoluteFillObject,
          {
            backgroundColor:
              variant === "ghost"
                ? "rgba(15, 26, 49, 0.35)"
                : "rgba(23, 39, 66, 0.9)",
          },
        ]}
      />
    );
  };

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        variant === "danger" && styles.danger,
        variant === "ghost" && styles.ghost,
        { opacity: disabled ? 0.45 : pressed ? 0.82 : 1 },
        style,
      ]}
    >
      {renderBackground()}
      <View style={styles.content}>
        {children ?? (
          <Text style={[styles.text, { color: VARIANT_TEXT[variant] }, textStyle]}>{title}</Text>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    borderRadius: RADIUS.s,
    overflow: "hidden",
    minHeight: 56,
    justifyContent: "center",
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: COLORS.accent.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.18,
    shadowRadius: 14,
    elevation: 4,
  },
  content: {
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s + 2,
  },
  text: {
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  danger: {
    borderColor: "rgba(255, 93, 95, 0.45)",
    shadowColor: COLORS.accent.error,
    shadowOpacity: 0.12,
  },
  ghost: {
    borderColor: COLORS.line,
    shadowOpacity: 0,
    elevation: 0,
  },
});
