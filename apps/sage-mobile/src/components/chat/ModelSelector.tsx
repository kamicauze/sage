import React, { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ChevronDown, X, Zap, Cpu, Brain } from "lucide-react-native";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";
import type { ProvidersMap } from "../../types/chat";

interface ModelSelectorProps {
  provider: string;
  model: string;
  availableProviders: ProvidersMap;
  onSelect: (provider: string, model: string) => void;
  disabled?: boolean;
}

const TIER_COLORS: Record<string, string> = {
  fast: COLORS.status.online,
  mid: COLORS.accent.primary,
  deep: COLORS.accent.warning,
  auto: COLORS.text.secondary,
};

const TIER_LABELS: Record<string, string> = {
  fast: "Fast",
  mid: "Mid",
  deep: "Deep",
  auto: "Auto",
};

export function ModelSelector({
  provider,
  model,
  availableProviders,
  onSelect,
  disabled,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);

  const providerConfig = availableProviders[provider];
  const modelConfig = providerConfig?.models.find((m) => m.id === model);
  const chipLabel = providerConfig
    ? `${providerConfig.label} / ${modelConfig?.label || model}`
    : `${provider} / ${model}`;

  return (
    <>
      <Pressable
        onPress={() => !disabled && setOpen(true)}
        style={[styles.chip, disabled && styles.chipDisabled]}
      >
        <Cpu size={12} color={COLORS.accent.primary} />
        <Text style={styles.chipText} numberOfLines={1}>
          {chipLabel}
        </Text>
        <ChevronDown size={12} color={COLORS.text.secondary} />
      </Pressable>

      <Modal
        visible={open}
        transparent
        animationType="fade"
        onRequestClose={() => setOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <View style={styles.sheet} onStartShouldSetResponder={() => true}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Select Model</Text>
              <Pressable onPress={() => setOpen(false)} style={styles.closeBtn}>
                <X size={18} color={COLORS.text.secondary} />
              </Pressable>
            </View>

            <ScrollView style={styles.list} showsVerticalScrollIndicator={false}>
              {Object.entries(availableProviders).map(([provKey, config]) => (
                <View key={provKey} style={styles.providerGroup}>
                  <Text style={styles.providerLabel}>{config.label}</Text>
                  {config.models.map((m) => {
                    const isActive = provKey === provider && m.id === model;
                    return (
                      <Pressable
                        key={`${provKey}-${m.id}`}
                        onPress={() => {
                          onSelect(provKey, m.id);
                          setOpen(false);
                        }}
                        style={[styles.modelRow, isActive && styles.modelRowActive]}
                      >
                        <View style={styles.modelInfo}>
                          <Text
                            style={[styles.modelName, isActive && styles.modelNameActive]}
                          >
                            {m.label}
                          </Text>
                          <Text style={styles.modelId}>{m.id}</Text>
                        </View>
                        <View
                          style={[
                            styles.tierBadge,
                            { backgroundColor: `${TIER_COLORS[m.tier] || COLORS.text.dim}22` },
                          ]}
                        >
                          <Text
                            style={[
                              styles.tierText,
                              { color: TIER_COLORS[m.tier] || COLORS.text.dim },
                            ]}
                          >
                            {TIER_LABELS[m.tier] || m.tier}
                          </Text>
                        </View>
                      </Pressable>
                    );
                  })}
                </View>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: `${COLORS.panel}cc`,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: RADIUS.full,
    borderWidth: 1,
    borderColor: COLORS.border,
    maxWidth: 220,
  },
  chipDisabled: { opacity: 0.5 },
  chipText: {
    color: COLORS.text.primary,
    fontSize: 12,
    fontWeight: "500",
    flexShrink: 1,
  },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(4,12,28,0.85)",
    justifyContent: "center",
    alignItems: "center",
    padding: SPACING.xl,
  },
  sheet: {
    width: "100%",
    maxHeight: "80%",
    backgroundColor: COLORS.panel,
    borderRadius: RADIUS.l,
    borderWidth: 1,
    borderColor: COLORS.border,
    overflow: "hidden",
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  sheetTitle: {
    color: COLORS.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
  closeBtn: {
    padding: 4,
  },
  list: {
    paddingHorizontal: SPACING.m,
    paddingVertical: SPACING.s,
  },
  providerGroup: {
    marginBottom: SPACING.m,
  },
  providerLabel: {
    color: COLORS.text.tertiary,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: SPACING.xs,
  },
  modelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 10,
    paddingHorizontal: SPACING.s,
    borderRadius: RADIUS.s,
    marginBottom: 2,
  },
  modelRowActive: {
    backgroundColor: `${COLORS.accent.primary}18`,
  },
  modelInfo: {
    flex: 1,
    marginRight: SPACING.s,
  },
  modelName: {
    color: COLORS.text.primary,
    fontSize: 14,
    fontWeight: "500",
  },
  modelNameActive: {
    color: COLORS.accent.primary,
  },
  modelId: {
    color: COLORS.text.dim,
    fontSize: 11,
    marginTop: 1,
  },
  tierBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: RADIUS.full,
  },
  tierText: {
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
  },
});
