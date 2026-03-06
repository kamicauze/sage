import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Constants from "expo-constants";
import {
  CheckCircle2,
  ClipboardList,
  LayoutDashboard,
  Shield,
  LucideIcon,
} from "lucide-react-native";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../../constants/theme";
import { TabName } from "./TabBar";

interface HeaderNavItem {
  name: TabName;
  icon: LucideIcon;
}

const HEADER_TABS: HeaderNavItem[] = [
  { name: "dashboard", icon: LayoutDashboard },
  { name: "approvals", icon: CheckCircle2 },
  { name: "plan", icon: ClipboardList },
  { name: "permissions", icon: Shield },
];

interface HeaderNavProps {
  activeTab: TabName;
  onNavigate: (tab: TabName) => void;
  approvalCount: number;
}

export function HeaderNav({ activeTab, onNavigate, approvalCount }: HeaderNavProps) {
  return (
    <View style={styles.container}>
      {HEADER_TABS.map((item) => {
        const active = item.name === activeTab;
        const Icon = item.icon;
        const showBadge = item.name === "approvals" && approvalCount > 0;

        return (
          <Pressable
            key={item.name}
            style={[styles.iconButton, active && styles.iconButtonActive]}
            onPress={() => onNavigate(item.name)}
          >
            <Icon
              size={18}
              color={active ? COLORS.accent.primary : COLORS.text.secondary}
            />
            {showBadge && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>
                  {approvalCount > 9 ? "9+" : String(approvalCount)}
                </Text>
              </View>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

const STATUS_BAR_HEIGHT = Constants.statusBarHeight ?? 44;

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    top: STATUS_BAR_HEIGHT + 8,
    right: LAYOUT.screenPadding,
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xxs,
    zIndex: 10,
  },
  iconButton: {
    width: 32,
    height: 32,
    borderRadius: RADIUS.xs,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(8, 17, 37, 0.75)",
    borderWidth: 1,
    borderColor: "transparent",
  },
  iconButtonActive: {
    backgroundColor: "rgba(47, 107, 255, 0.12)",
    borderColor: "rgba(47, 107, 255, 0.3)",
  },
  badge: {
    position: "absolute",
    top: -4,
    right: -4,
    minWidth: 16,
    height: 16,
    borderRadius: RADIUS.full,
    backgroundColor: COLORS.accent.error,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  badgeText: {
    color: COLORS.text.primary,
    fontSize: 9,
    fontWeight: "800",
  },
});
