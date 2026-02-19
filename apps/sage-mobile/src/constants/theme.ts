export const COLORS = {
  background: "#040c1c",
  panel: "#111d34",
  panelSoft: "#172742",
  panelMuted: "#0b152d",
  border: "rgba(116, 150, 214, 0.25)",
  line: "rgba(125, 163, 234, 0.18)",
  text: {
    primary: "#f5f7ff",
    secondary: "#9ca9c2",
    tertiary: "#6f7e9f",
    dim: "#56627e",
  },
  accent: {
    primary: "#2f6bff",
    primaryStrong: "#1f53d7",
    info: "#4c93ff",
    success: "#22d38b",
    warning: "#f7b731",
    error: "#ff5c62",
  },
  status: {
    online: "#20d68f",
    attention: "#ffc439",
    critical: "#ff5a54",
    offline: "#536384",
  },
  glow: {
    blue: "rgba(45, 107, 255, 0.45)",
    green: "rgba(32, 214, 143, 0.45)",
  },
  gradients: {
    screen: ["#04102a", "#071734", "#030b19"] as const,
    card: ["#1b2c4a", "#13203a"] as const,
    cta: ["#2f6bff", "#1d4fc9"] as const,
    danger: ["#341423", "#250d18"] as const,
  },
};

export const SPACING = {
  xxs: 4,
  xs: 6,
  s: 10,
  m: 16,
  l: 24,
  xl: 32,
  xxl: 40,
};

export const RADIUS = {
  xs: 8,
  s: 12,
  m: 18,
  l: 24,
  xl: 30,
  full: 999,
};

export const LAYOUT = {
  screenPadding: 20,
  tabBarHeight: 88,
};

export const TYPO = {
  header: 40,
  section: 22,
  title: 32,
  body: 17,
  label: 13,
};
