import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { AlertTriangle } from "lucide-react-native";
import { GlassCard } from "./ui/GlassCard";
import { GlassButton } from "./ui/GlassButton";
import { ScreenLayout } from "./layout/ScreenLayout";
import { COLORS, SPACING } from "../constants/theme";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <ScreenLayout>
          <View style={styles.center}>
            <GlassCard variant="critical" style={styles.card}>
              <AlertTriangle size={28} color={COLORS.accent.error} />
              <Text style={styles.title}>Something went wrong</Text>
              <Text style={styles.message}>
                {this.state.error?.message || "An unexpected error occurred."}
              </Text>
              <GlassButton
                title="Try Again"
                variant="secondary"
                onPress={this.handleReset}
                style={styles.button}
              />
            </GlassCard>
          </View>
        </ScreenLayout>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: SPACING.m,
  },
  card: {
    alignItems: "center",
    gap: SPACING.m,
    width: "100%",
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.text.primary,
    letterSpacing: -0.3,
  },
  message: {
    fontSize: 13,
    color: COLORS.text.secondary,
    textAlign: "center",
    lineHeight: 19,
  },
  button: {
    marginTop: SPACING.s,
    width: "100%",
  },
});
