import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  ListTodo,
  Mail,
  Newspaper,
  Radio,
  SlidersHorizontal,
  Settings,
  LucideIcon,
} from "lucide-react-native";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../../constants/theme";

export type TabName =
  | "dashboard"
  | "chat"
  | "approvals"
  | "control"
  | "plan"
  | "gmail"
  | "tasks"
  | "news"
  | "permissions"
  | "settings";

interface TabBarProps {
  activeTab: TabName;
  onTabChange: (tab: TabName) => void;
}

interface TabItem {
  name: TabName;
  label: string;
  icon: LucideIcon;
}

const tabs: TabItem[] = [
  { name: "control", label: "Control", icon: SlidersHorizontal },
  { name: "gmail", label: "Gmail", icon: Mail },
  { name: "chat", label: "Chat", icon: Radio },
  { name: "tasks", label: "Tasks", icon: ListTodo },
  { name: "news", label: "News", icon: Newspaper },
  { name: "settings", label: "Settings", icon: Settings },
];

export function TabBar({ activeTab, onTabChange }: TabBarProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.bar}>
        {tabs.map((tab) => {
          const active = tab.name === activeTab;
          const Icon = tab.icon;

          return (
            <Pressable key={tab.name} style={styles.tab} onPress={() => onTabChange(tab.name)}>
              <Icon size={20} color={active ? COLORS.accent.primary : COLORS.text.secondary} />
              <Text style={[styles.label, active && styles.activeLabel]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: SPACING.s,
    right: SPACING.s,
    bottom: SPACING.s,
  },
  bar: {
    height: LAYOUT.tabBarHeight,
    borderRadius: RADIUS.l,
    backgroundColor: "rgba(12, 21, 40, 0.96)",
    borderWidth: 1,
    borderColor: COLORS.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingHorizontal: SPACING.s,
    paddingBottom: SPACING.xs,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.45,
    shadowRadius: 20,
    elevation: 18,
  },
  tab: {
    alignItems: "center",
    justifyContent: "center",
    gap: SPACING.xs,
    minWidth: 52,
  },
  label: {
    fontSize: 11,
    color: COLORS.text.secondary,
    letterSpacing: 0.3,
    fontWeight: "600",
  },
  activeLabel: {
    color: COLORS.accent.primary,
  },
});
