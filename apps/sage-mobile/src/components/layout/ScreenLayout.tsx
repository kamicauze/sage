import React from "react";
import {
  SafeAreaView,
  StatusBar,
  StyleSheet,
  View,
  ViewStyle,
  StyleProp,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { COLORS, LAYOUT } from "../../constants/theme";

interface ScreenLayoutProps {
  children: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
}

function GridOverlay() {
  const columns = Array.from({ length: 8 });
  const rows = Array.from({ length: 11 });

  return (
    <View pointerEvents="none" style={styles.gridWrap}>
      <View style={styles.columnLayer}>
        {columns.map((_, index) => (
          <View key={`col-${index}`} style={styles.columnLine} />
        ))}
      </View>
      <View style={styles.rowLayer}>
        {rows.map((_, index) => (
          <View key={`row-${index}`} style={styles.rowLine} />
        ))}
      </View>
    </View>
  );
}

export function ScreenLayout({ children, contentStyle }: ScreenLayoutProps) {
  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />
      <LinearGradient
        colors={COLORS.gradients.screen}
        locations={[0.02, 0.45, 0.98]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFillObject}
      />
      <GridOverlay />
      <SafeAreaView style={styles.safeArea}>
        <View style={[styles.content, contentStyle]}>{children}</View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  safeArea: {
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: LAYOUT.screenPadding,
  },
  gridWrap: {
    ...StyleSheet.absoluteFillObject,
    opacity: 0.33,
  },
  columnLayer: {
    ...StyleSheet.absoluteFillObject,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  columnLine: {
    width: 1,
    backgroundColor: COLORS.line,
  },
  rowLayer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "space-between",
  },
  rowLine: {
    height: 1,
    backgroundColor: COLORS.line,
  },
});
