import React from "react";
import {
  FlatList,
  Linking,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { ExternalLink, Newspaper, RefreshCw, TriangleAlert } from "lucide-react-native";
import { ScreenLayout } from "../components/layout/ScreenLayout";
import { GlassButton } from "../components/ui/GlassButton";
import { GlassCard } from "../components/ui/GlassCard";
import { COLORS, LAYOUT, RADIUS, SPACING } from "../constants/theme";
import { AiNewsItem } from "../types/news";

interface NewsScreenProps {
  items: AiNewsItem[];
  generatedAt: string | null;
  sourceErrors: string[];
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  onRefresh: () => void;
}

function relativeTime(iso: string | null): string {
  if (!iso) return "Unknown time";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "Unknown time";
  const diffMs = Date.now() - ts;
  const diffMin = Math.max(1, Math.floor(diffMs / 60000));
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function isAiFocused(item: AiNewsItem): boolean {
  const tags = (item.tags || []).map((tag) => tag.toLowerCase());
  if (tags.some((tag) => tag.includes("ai") || tag.includes("llm") || tag.includes("gpt"))) {
    return true;
  }
  const corpus = `${item.title} ${item.summary}`.toLowerCase();
  return (
    corpus.includes("artificial intelligence") ||
    corpus.includes("generative ai") ||
    corpus.includes("llm") ||
    corpus.includes("openai") ||
    corpus.includes("anthropic") ||
    corpus.includes("xai")
  );
}

async function openUrl(url: string) {
  try {
    await Linking.openURL(url);
  } catch {
    // no-op; this should not crash rendering if URL open fails
  }
}

function renderNewsCard(item: AiNewsItem) {
  const aiFocused = isAiFocused(item);
  return (
    <GlassCard
      key={item.id}
      style={[styles.itemCard, aiFocused && styles.itemCardAi]}
      variant="soft"
    >
      <View style={styles.itemHeader}>
        <View style={styles.sourceRow}>
          <Text style={styles.source}>{item.source}</Text>
          {aiFocused ? (
            <View style={styles.aiBadge}>
              <Text style={styles.aiBadgeText}>AI</Text>
            </View>
          ) : null}
        </View>
        <Text style={styles.score}>Score {item.relevance_score.toFixed(1)}</Text>
      </View>

      <Text style={styles.title}>{item.title}</Text>
      {item.summary ? <Text style={styles.summary}>{item.summary}</Text> : null}

      <View style={styles.footerRow}>
        <Text style={styles.time}>{relativeTime(item.published_at)}</Text>
        <Pressable style={styles.linkButton} onPress={() => void openUrl(item.url)}>
          <ExternalLink size={14} color={COLORS.accent.info} />
          <Text style={styles.linkText}>Open</Text>
        </Pressable>
      </View>
    </GlassCard>
  );
}

export function NewsScreen({
  items,
  generatedAt,
  sourceErrors,
  isLoading,
  isRefreshing,
  error,
  onRefresh,
}: NewsScreenProps) {
  const aiCount = React.useMemo(
    () => items.reduce((total, item) => (isAiFocused(item) ? total + 1 : total), 0),
    [items]
  );

  return (
    <ScreenLayout>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={onRefresh}
            tintColor={COLORS.text.secondary}
          />
        }
        ListHeaderComponent={
          <View style={styles.headerArea}>
            <View style={styles.headerTop}>
              <View style={styles.titleWrap}>
                <Newspaper size={18} color={COLORS.accent.info} />
                <Text style={styles.screenTitle}>Tech News</Text>
              </View>
              <GlassButton onPress={onRefresh} variant="ghost" style={styles.refreshButton}>
                <View style={styles.refreshInner}>
                  <RefreshCw size={14} color={COLORS.text.secondary} />
                  <Text style={styles.refreshText}>Refresh</Text>
                </View>
              </GlassButton>
            </View>
            <Text style={styles.subhead}>
              {generatedAt
                ? `Updated ${relativeTime(generatedAt)} - ${items.length} items (${aiCount} AI)`
                : "Pulling latest tech updates (AI highlighted)"}
            </Text>
            {error ? (
              <GlassCard style={styles.errorCard} variant="critical">
                <View style={styles.errorRow}>
                  <TriangleAlert size={16} color={COLORS.accent.error} />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              </GlassCard>
            ) : null}
            {sourceErrors.length > 0 ? (
              <GlassCard style={styles.partialCard} variant="outline">
                <Text style={styles.partialText}>
                  Partial fetch: {sourceErrors.length} source{sourceErrors.length > 1 ? "s" : ""} unavailable.
                </Text>
              </GlassCard>
            ) : null}
          </View>
        }
        renderItem={({ item }) => renderNewsCard(item)}
        ListEmptyComponent={
          !isLoading ? (
            <GlassCard style={styles.emptyCard} variant="outline">
              <Text style={styles.emptyTitle}>No tech headlines right now.</Text>
              <Text style={styles.emptySub}>
                Pull again in a minute, or check backend source availability.
              </Text>
            </GlassCard>
          ) : null
        }
      />
    </ScreenLayout>
  );
}

const styles = StyleSheet.create({
  listContent: {
    paddingBottom: LAYOUT.tabBarHeight + 70,
  },
  headerArea: {
    marginTop: SPACING.s,
    marginBottom: SPACING.m,
    gap: SPACING.s,
  },
  headerTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: SPACING.s,
  },
  titleWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  screenTitle: {
    color: COLORS.text.primary,
    fontSize: 21,
    fontWeight: "700",
  },
  subhead: {
    color: COLORS.text.secondary,
    fontSize: 13,
  },
  refreshButton: {
    minHeight: 38,
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.s,
  },
  refreshInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
  },
  refreshText: {
    color: COLORS.text.secondary,
    fontSize: 12,
    letterSpacing: 0.4,
    fontWeight: "600",
  },
  itemCard: {
    marginBottom: SPACING.m,
    gap: SPACING.s,
  },
  itemHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
  },
  source: {
    color: COLORS.accent.info,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  itemCardAi: {
    borderColor: "rgba(106, 159, 255, 0.55)",
  },
  aiBadge: {
    borderWidth: 1,
    borderColor: "rgba(106, 159, 255, 0.7)",
    backgroundColor: "rgba(37, 76, 150, 0.4)",
    borderRadius: RADIUS.s,
    paddingHorizontal: SPACING.xs + 2,
    paddingVertical: 1,
  },
  aiBadgeText: {
    color: COLORS.accent.info,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  score: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  title: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 22,
  },
  summary: {
    color: COLORS.text.secondary,
    fontSize: 14,
    lineHeight: 20,
  },
  footerRow: {
    marginTop: SPACING.xs,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  time: {
    color: COLORS.text.tertiary,
    fontSize: 12,
  },
  linkButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.xs,
    paddingHorizontal: SPACING.s,
    paddingVertical: SPACING.xs,
    borderRadius: RADIUS.s,
    borderWidth: 1,
    borderColor: COLORS.line,
    backgroundColor: "rgba(15, 27, 48, 0.7)",
  },
  linkText: {
    color: COLORS.accent.info,
    fontSize: 12,
    fontWeight: "700",
  },
  errorCard: {
    marginTop: SPACING.xs,
  },
  errorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: SPACING.s,
  },
  errorText: {
    color: COLORS.text.primary,
    flex: 1,
    fontSize: 13,
  },
  partialCard: {
    marginTop: SPACING.xs,
  },
  partialText: {
    color: COLORS.text.secondary,
    fontSize: 12,
  },
  emptyCard: {
    marginTop: SPACING.xl,
  },
  emptyTitle: {
    color: COLORS.text.primary,
    fontSize: 15,
    fontWeight: "700",
    marginBottom: SPACING.xs,
  },
  emptySub: {
    color: COLORS.text.secondary,
    fontSize: 13,
    lineHeight: 18,
  },
});
