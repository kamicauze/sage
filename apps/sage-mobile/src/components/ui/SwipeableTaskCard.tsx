import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  runOnJS,
} from "react-native-reanimated";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import { Clock, Trash2 } from "lucide-react-native";
import { COLORS, RADIUS, SPACING } from "../../constants/theme";

const ACTION_WIDTH = 140;
const SPRING_CONFIG = { damping: 20, stiffness: 200 };

interface SwipeableTaskCardProps {
  children: React.ReactNode;
  onDelete: () => void;
  onSnooze: () => void;
  enabled?: boolean;
}

export function SwipeableTaskCard({
  children,
  onDelete,
  onSnooze,
  enabled = true,
}: SwipeableTaskCardProps) {
  const translateX = useSharedValue(0);
  const contextX = useSharedValue(0);

  const close = React.useCallback(() => {
    translateX.value = withSpring(0, SPRING_CONFIG);
  }, [translateX]);

  const handleSnooze = React.useCallback(() => {
    close();
    onSnooze();
  }, [close, onSnooze]);

  const handleDelete = React.useCallback(() => {
    close();
    onDelete();
  }, [close, onDelete]);

  const panGesture = React.useMemo(
    () =>
      Gesture.Pan()
        .enabled(enabled)
        .activeOffsetX([-10, 10])
        .failOffsetY([-5, 5])
        .onStart(() => {
          contextX.value = translateX.value;
        })
        .onUpdate((event) => {
          const next = contextX.value + event.translationX;
          translateX.value = Math.min(0, Math.max(-ACTION_WIDTH, next));
        })
        .onEnd(() => {
          if (translateX.value < -ACTION_WIDTH / 2) {
            translateX.value = withSpring(-ACTION_WIDTH, SPRING_CONFIG);
          } else {
            translateX.value = withSpring(0, SPRING_CONFIG);
          }
        }),
    [contextX, enabled, translateX]
  );

  const cardStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  return (
    <View style={styles.container}>
      <View style={styles.actionsContainer}>
        <Pressable style={styles.snoozeAction} onPress={handleSnooze}>
          <Clock size={18} color={COLORS.accent.info} />
          <Text style={styles.snoozeText}>Snooze</Text>
        </Pressable>
        <Pressable style={styles.deleteAction} onPress={handleDelete}>
          <Trash2 size={18} color={COLORS.accent.error} />
          <Text style={styles.deleteText}>Delete</Text>
        </Pressable>
      </View>
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.cardWrapper, cardStyle]}>
          {children}
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: SPACING.s,
    overflow: "hidden",
    borderRadius: RADIUS.m,
  },
  actionsContainer: {
    position: "absolute",
    top: 0,
    bottom: 0,
    right: 0,
    width: ACTION_WIDTH,
    flexDirection: "row",
  },
  snoozeAction: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(12, 30, 60, 0.92)",
    gap: SPACING.xxs,
  },
  deleteAction: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(46, 19, 31, 0.92)",
    gap: SPACING.xxs,
  },
  snoozeText: {
    color: COLORS.accent.info,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  deleteText: {
    color: COLORS.accent.error,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  cardWrapper: {
    backgroundColor: COLORS.background,
  },
});
