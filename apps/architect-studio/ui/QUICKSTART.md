# Architect UI - Quick Start Guide

Get the UI running in 5 minutes!

## Prerequisites

- ✅ Node.js 18+ installed
- ✅ Architect API running on http://localhost:8000
- ✅ npm or yarn

## Step 1: Install Dependencies (2 minutes)

```bash
cd architect/ui
npm install
```

This installs:
- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- Recharts (for graphs)
- Axios (for API calls)

## Step 2: Start Development Server (10 seconds)

```bash
npm run dev
```

You'll see:
```
  ▲ Next.js 15.1.4
  - Local:        http://localhost:3000
  - Network:      http://192.168.1.x:3000

 ✓ Ready in 2.5s
```

## Step 3: Open in Browser (5 seconds)

Navigate to **http://localhost:3000**

You should see the Architect dashboard! 🎉

## What You'll See

### Dashboard (Home Page)
- Monthly budget: $0 / $120
- Memory chunks: 202 across 5 zones
- Recent API calls with costs
- Cognitive zone distribution
- Quick action buttons

### Navigation Sidebar

Click through the pages:

1. **🏠 Dashboard** - Overview and stats
2. **🔨 Build** - Create new plans
3. **🔍 Memory** - Search codebase
4. **📊 Stats** - Detailed analytics
5. **⚙️ Settings** - Configuration

## Quick Tour

### Generate Your First Plan

1. Click **"Build"** in sidebar
2. Enter a request:
   ```
   Add error logging to MQTT client
   ```
3. Select type: **Feature**
4. Click **"Generate Plan"**
5. Wait ~30 seconds (local LLM)
6. View the implementation plan!

### Search Memory

1. Click **"Memory"** in sidebar
2. Enter query:
   ```
   MQTT connection
   ```
3. Click **"Search"**
4. See relevant code snippets with similarity scores!

### View Statistics

1. Click **"Stats"** in sidebar
2. See:
   - Monthly/daily spending charts
   - Provider breakdown (Ollama, Google, etc.)
   - Model usage (gemma3:12b, etc.)
   - Full API call history

## Common Issues

### Port 3000 Already in Use

```bash
# Use different port
npm run dev -- -p 3001
```

Then visit http://localhost:3001

### API Connection Failed

**Check if API is running:**
```bash
curl http://localhost:8000/
```

**Expected response:**
```json
{"status":"healthy","timestamp":"...","architect_version":"1.0.0"}
```

**If not running:**
```bash
# Start the API (in another terminal)
cd architect/api
uvicorn server:app --port 8000
```

### Dependencies Installation Failed

**Clear cache and retry:**
```bash
rm -rf node_modules package-lock.json
npm install
```

### TypeScript Errors

**Check configuration:**
```bash
npx tsc --noEmit
```

Fix any errors in the output, then restart the dev server.

## Development Tips

### Hot Reload

Any changes you make to files will automatically reload the page. No need to restart!

### TypeScript Autocomplete

Use VSCode for best experience:
- Install "TypeScript and JavaScript Language Features"
- Cmd/Ctrl + Space for autocomplete
- Hover over variables to see types

### Tailwind IntelliSense

Install VSCode extension:
```
Tailwind CSS IntelliSense
```

Get autocomplete for Tailwind classes!

### DevTools

Open browser DevTools (F12):
- **Console** - See API requests and errors
- **Network** - Monitor API calls
- **React DevTools** - Inspect component state

## Next Steps

### Customize the UI

**Change colors:**
Edit `tailwind.config.js`:
```javascript
colors: {
  'architect-accent': '#your-color',
}
```

**Add a new page:**
1. Create `src/app/your-page/page.tsx`
2. Add to sidebar in `src/components/Sidebar.tsx`

**Modify API client:**
Edit `src/lib/api.ts` to add new endpoints

### Build for Production

```bash
# Create optimized build
npm run build

# Test production build locally
npm start
```

### Deploy

**Vercel (easiest):**
```bash
npm i -g vercel
vercel
```

**Docker:**
```bash
docker build -t architect-ui .
docker run -p 3000:3000 architect-ui
```

## File Structure Overview

```
architect/ui/
├── src/
│   ├── app/              # Pages (Next.js App Router)
│   │   ├── page.tsx     # Dashboard
│   │   ├── build/       # Build interface
│   │   ├── memory/      # Memory search
│   │   ├── stats/       # Statistics
│   │   └── settings/    # Settings
│   ├── components/       # React components
│   └── lib/
│       └── api.ts       # API client
├── public/              # Static files
└── package.json         # Dependencies
```

## Keyboard Shortcuts (Coming Soon)

- `Cmd/Ctrl + K` - Quick search
- `Cmd/Ctrl + B` - New build request
- `Cmd/Ctrl + /` - Command palette

## Troubleshooting Commands

```bash
# Check if everything is installed
npm list

# Clear Next.js cache
rm -rf .next

# Reinstall everything
rm -rf node_modules package-lock.json
npm install

# Check TypeScript
npx tsc --noEmit

# Build for production (to test)
npm run build
```

## Getting Help

- **README.md** - Full documentation
- **API Docs** - http://localhost:8000/docs
- **Console** - Check browser console for errors

## Success Checklist

- [ ] Dependencies installed
- [ ] Dev server running on port 3000
- [ ] Dashboard loads in browser
- [ ] API status shows "Connected" in sidebar
- [ ] Budget and memory stats visible
- [ ] Can generate a plan
- [ ] Can search memory
- [ ] Stats page shows data

If all checked, you're ready to go! 🚀

---

**Need more help?** Check the full README.md or explore the API docs at http://localhost:8000/docs
