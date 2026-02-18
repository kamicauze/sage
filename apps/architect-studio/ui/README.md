# Architect UI

Modern Next.js 15 frontend for the Architect AI-powered code generation system.

![Architect UI](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![React](https://img.shields.io/badge/React-19-blue?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue?logo=typescript)
![Tailwind](https://img.shields.io/badge/Tailwind-3.4-38bdf8?logo=tailwind-css)

## Features

### 🎛️ Dashboard
- **Real-time budget tracking** - Monthly and daily spend visualization
- **Memory statistics** - Cognitive zone distribution and chunk counts
- **Recent activity** - Latest API calls with token counts and costs
- **Quick actions** - Jump to build, search, or stats

### 🏗️ Build Interface
- **Natural language requests** - Describe what to build in plain English
- **Routing transparency** - See which LLM route (LOCAL/HYBRID/CLOUD) was chosen and why
- **Cost estimation** - Upfront cost estimates before generating code
- **Context retrieval** - View which code snippets were used for context
- **Markdown plan rendering** - Beautiful rendered implementation plans
- **Request types** - Feature, bugfix, refactor, or test requests

### 🔍 Memory Search
- **Semantic code search** - Vector similarity search across codebase
- **Zone filtering** - Filter by cognitive zones (Truth, Soul, Hands, Body)
- **Relevance scoring** - See match percentages for each result
- **Zone visualization** - Interactive zone explorer with file mappings
- **Syntax highlighting** - Properly formatted code snippets

### 📊 Statistics
- **Usage analytics** - Detailed breakdowns by provider and model
- **Cost tracking** - Historical spending charts
- **API call logs** - Full audit trail of all requests
- **Provider comparison** - See which providers you use most

### ⚙️ Settings
- Budget limit configuration
- Routing threshold tuning
- Notification preferences
- API endpoint management

## Tech Stack

- **Framework:** Next.js 15 with App Router
- **Language:** TypeScript 5.7
- **Styling:** Tailwind CSS 3.4
- **Charts:** Recharts 2.15
- **Markdown:** react-markdown 9.0
- **Icons:** Lucide React
- **HTTP Client:** Axios

## Getting Started

### Prerequisites

- Node.js 18+ or 20+
- The Architect API running on `http://localhost:8000`
- npm or yarn package manager

### Installation

```bash
# Navigate to UI directory
cd architect/ui

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at **http://localhost:3000**

### Build for Production

```bash
# Create optimized build
npm run build

# Start production server
npm start
```

## Project Structure

```
architect/ui/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── page.tsx           # Dashboard
│   │   ├── build/page.tsx     # Build request interface
│   │   ├── memory/page.tsx    # Memory search
│   │   ├── stats/page.tsx     # Usage statistics
│   │   ├── settings/page.tsx  # Settings
│   │   ├── layout.tsx         # Root layout with sidebar
│   │   └── globals.css        # Global styles
│   │
│   ├── components/             # React components
│   │   └── Sidebar.tsx        # Navigation sidebar
│   │
│   └── lib/                    # Utilities
│       └── api.ts             # API client & TypeScript types
│
├── public/                     # Static assets
├── next.config.js             # Next.js configuration
├── tailwind.config.js         # Tailwind configuration
├── tsconfig.json              # TypeScript configuration
└── package.json               # Dependencies
```

## Configuration

### Environment Variables

Create `.env.local` in the UI directory:

```bash
# API endpoint (defaults to localhost:8000)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### API Proxy

The Next.js config includes a proxy rewrite rule:

```javascript
// next.config.js
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://localhost:8000/:path*',
    },
  ]
}
```

This allows the frontend to make requests to `/api/*` which get proxied to the backend.

## Key Components

### API Client (`src/lib/api.ts`)

TypeScript client for the Architect API with full type safety:

```typescript
import { architectAPI } from '@/lib/api';

// Generate a plan
const plan = await architectAPI.generatePlan(
  "Add MQTT reconnection logic",
  "feature"
);

// Search memory
const results = await architectAPI.searchMemory(
  "MQTT connection",
  "sage_brain",
  5,
  "The Hands" // Optional zone filter
);

// Get usage stats
const usage = await architectAPI.getUsageStats();
```

### WebSocket Client

For real-time build updates:

```typescript
import { BuildStreamClient } from '@/lib/api';

const client = new BuildStreamClient('my-session');

client.connect();
client.onMessage((data) => {
  console.log('Build update:', data);
});

client.startBuild('build-123');
```

## Features in Detail

### Dashboard

The dashboard provides an at-a-glance view of your Architect system:

- **Budget widget** - Visual progress bar showing monthly spend
- **Zone distribution** - Pie chart of cognitive zones
- **Recent calls** - Last 5 API requests with cost
- **Memory stats** - Total chunks and zone counts

### Build Request Flow

1. User enters natural language request
2. Select request type (feature/bugfix/refactor/test)
3. Click "Generate Plan"
4. System shows routing decision with reasoning
5. Display retrieved context snippets (if any)
6. Render full implementation plan in markdown
7. User can approve or cancel

### Memory Search Flow

1. Enter search query
2. Optionally filter by cognitive zone
3. Click "Search"
4. Results show with relevance scores
5. Click result to view full code snippet
6. Zone badge shows which zone the code belongs to

### Statistics Dashboard

- **Budget overview** - Current spend vs limits
- **Daily chart** - Spending over time
- **Provider breakdown** - Cost by provider (Ollama, Google, Anthropic, etc.)
- **Model breakdown** - Cost by model (gemma3:12b, claude-opus, etc.)
- **Call table** - Full audit log with timestamps, tokens, and costs

## Styling

### Custom Tailwind Classes

The app uses custom utility classes defined in `globals.css`:

```css
/* Cards */
.card - Consistent card styling

/* Buttons */
.btn-primary - Primary action button
.btn-secondary - Secondary button

/* Form inputs */
.input - Text inputs and textareas

/* Badges */
.badge - Base badge style
.badge-local - Green (LOCAL route)
.badge-hybrid - Blue (HYBRID route)
.badge-cloud - Purple (CLOUD route)
```

### Color Palette

```javascript
// Dark theme colors
'architect-dark': '#0a0a0a',    // Background
'architect-gray': '#1a1a1a',    // Cards/elements
'architect-border': '#2a2a2a',  // Borders
'architect-accent': '#3b82f6',  // Primary blue
'architect-success': '#10b981', // Green
'architect-warning': '#f59e0b', // Orange
'architect-error': '#ef4444',   // Red
```

## Development

### Adding a New Page

1. Create file in `src/app/your-page/page.tsx`
2. Add route to sidebar navigation in `src/components/Sidebar.tsx`
3. Implement page with TypeScript and Tailwind

Example:

```typescript
// src/app/your-page/page.tsx
'use client';

export default function YourPage() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">Your Page</h1>
      {/* Your content */}
    </div>
  );
}
```

### Adding New API Methods

Add methods to `src/lib/api.ts`:

```typescript
export const architectAPI = {
  // ... existing methods

  async yourNewMethod(param: string) {
    const response = await api.get(`/your-endpoint/${param}`);
    return response.data;
  },
};
```

### Hot Reload

Next.js provides instant hot reload during development. Changes to any file will automatically refresh the browser.

## Troubleshooting

### API Connection Issues

**Problem:** "Failed to fetch" errors

**Solution:**
1. Ensure Architect API is running on port 8000
2. Check `NEXT_PUBLIC_API_URL` environment variable
3. Verify CORS is enabled in API (`allow_origins=["*"]`)

### Port Conflicts

**Problem:** Port 3000 already in use

**Solution:**
```bash
# Use a different port
npm run dev -- -p 3001
```

### Build Errors

**Problem:** TypeScript errors during build

**Solution:**
```bash
# Check types
npx tsc --noEmit

# Fix any errors, then rebuild
npm run build
```

### Styling Not Applied

**Problem:** Tailwind classes not working

**Solution:**
```bash
# Ensure PostCSS and Tailwind are installed
npm install -D tailwindcss postcss autoprefixer

# Restart dev server
npm run dev
```

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

Set environment variable:
- `NEXT_PUBLIC_API_URL` - Your production API URL

### Docker

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

### Static Export

```bash
# Add to next.config.js
output: 'export'

# Build
npm run build

# Deploy 'out/' directory to any static host
```

## Performance

- **Code splitting** - Automatic route-based code splitting
- **Image optimization** - Next.js Image component (when images added)
- **API caching** - Consider adding React Query for advanced caching
- **Bundle analysis** - Use `@next/bundle-analyzer` to optimize

## Roadmap

- [ ] Real-time build progress with WebSocket streaming
- [ ] File diff viewer for code review
- [ ] Build artifact browser
- [ ] Advanced routing configuration UI
- [ ] Cost projections and trends
- [ ] Export reports (PDF/CSV)
- [ ] Dark/light theme toggle
- [ ] Keyboard shortcuts
- [ ] Mobile responsive improvements
- [ ] Test execution UI

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly (both dev and production builds)
4. Submit a pull request

## License

Part of the Sage Architect project.

---

**Built with ❤️ using Next.js 15 and React 19**
