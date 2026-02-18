#!/bin/bash
# Start the Architect API server

echo "🏗️  Starting Architect API Server..."
echo ""

# Check if we're in the right directory
if [ ! -f "architect/api/server.py" ]; then
    echo "❌ Error: Must be run from project root directory"
    echo "   cd /path/to/sage && ./architect/api/start.sh"
    exit 1
fi

# Check if dependencies are installed
python3 -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  FastAPI not installed. Installing dependencies..."
    pip install -r architect/api/requirements.txt
fi

# Start server
echo "🚀 Starting server on http://localhost:8000"
echo "📚 API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn architect.api.server:app --reload --host 0.0.0.0 --port 8000
