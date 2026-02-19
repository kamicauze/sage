import React from "react";
import { StyleProp, StyleSheet, View, ViewStyle } from "react-native";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";

interface GlassCardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  padded?: boolean;
  variant?: "default" | "soft" | "outline" | "critical";
}

const VARIANT_STYLE: Record<NonNullable<GlassCardProps["variant"]>, ViewStyle> = {
  default: {
    backgroundColor: COLORS.panel,
    borderColor: COLORS.border,
  },
  soft: {
    backgroundColor: COLORS.panelSoft,
    borderColor: COLORS.border,
  },
  outline: {
    backgroundColor: "rgba(8, 17, 37, 0.65)",
    borderColor: COLORS.line,
  },
  critical: {
    backgroundColor: "rgba(46, 19, 31, 0.85)",
    borderColor: "rgba(255, 95, 97, 0.4)",
  },
};

export function GlassCard({
  children,
  style,
  padded = true,
  variant = "default",
}: GlassCardProps) {
  return (
    <View
      style={[
        styles.container,
        VARIANT_STYLE[variant],
        padded ? styles.padded : styles.unpadded,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: RADIUS.m,
    borderWidth: 1,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.25,
    shadowRadius: 18,
    elevation: 8,
  },
  padded: {
    padding: SPACING.m,
  },
  unpadded: {
    padding: 0,
  },
});
