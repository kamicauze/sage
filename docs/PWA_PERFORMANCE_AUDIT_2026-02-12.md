# PWA Performance Audit (2026-02-12)

Scope: `apps/architect-studio/ui`

## Build Measurements

Measured with `npm run build` before and after targeted code-splitting changes.

| Route | Before first-load JS | After first-load JS | Delta |
|---|---:|---:|---:|
| `/build` | 232 kB | 140 kB | -92 kB |
| `/stats` | 228 kB | 128 kB | -100 kB |
| `/brain` | 217 kB | 115 kB | -102 kB |

## Changes Applied

1. `apps/architect-studio/ui/next.config.js`
- Enabled `experimental.optimizePackageImports` for `lucide-react`.

2. `apps/architect-studio/ui/src/lib/mqtt-bridge.ts`
- Replaced top-level `mqtt` import with dynamic import inside connect path.
- Prevents MQTT client code from being bundled on pages that never use it.

3. `apps/architect-studio/ui/src/app/stats/page.tsx`
- Moved `recharts` graph code into a lazily-loaded component.
- New component: `apps/architect-studio/ui/src/components/charts/DailySpendingChart.tsx`.

4. `apps/architect-studio/ui/src/app/build/page.tsx`
- Dynamically loaded heavy components:
  - `react-markdown`
  - `FlowchartEditor`
  - `TemplateSelector`
  - `GlossarySidebar`

## Impact

- Large first-load drop on the routes most used for planning/building.
- Better mobile behavior on slow links due to lower initial script transfer.
- Lower parse/execute time on weaker CPUs, improving time-to-interactive.

## Remaining Bottlenecks

1. Shared global bundles still include code for routes not needed on first paint.
2. Some screens still fetch data eagerly instead of when tabs/sections are opened.
3. Build page keeps multiple optional feature blocks in memory after load.

## Next Optimizations

1. Add per-tab lazy loading in `build` and `memory` pages.
2. Add server caching for frequently-read API payloads (`projects`, `stats/usage`).
3. Introduce route-level prefetch policy tuning for mobile (disable eager prefetch on expensive pages).
