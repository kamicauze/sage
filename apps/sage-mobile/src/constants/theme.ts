
export const COLORS = {
    background: "#000000",
    text: {
        primary: "#FFFFFF",
        secondary: "rgba(255, 255, 255, 0.7)",
        tertiary: "rgba(255, 255, 255, 0.5)",
    },
    accent: {
        primary: "#3b82f6", // Blue
        secondary: "#8b5cf6", // Purple
        success: "#10b981", // Green
        warning: "#f59e0b", // Amber
        error: "#ef4444", // Red
    },
    glass: {
        background: "rgba(255, 255, 255, 0.1)",
        border: "rgba(255, 255, 255, 0.2)",
        text: "#FFFFFF",
    },
    gradients: {
        primary: ["#3b82f6", "#06b6d4"] as const, // Blue to Cyan
        secondary: ["#8b5cf6", "#d946ef"] as const, // Purple to Pink
        dark: ["#1f2937", "#111827"] as const, // Dark Gray to Black
    },
};

export const SPACING = {
    xs: 4,
    s: 8,
    m: 16,
    l: 24,
    xl: 32,
};

export const RADIUS = {
    s: 8,
    m: 16,
    l: 24,
    full: 9999,
};

export const LAYOUT = {
    screenPadding: 20,
};
