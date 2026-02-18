#!/bin/bash
# Install Node.js 20 LTS using nvm

echo "🔧 Installing Node.js 20 LTS..."
echo ""

# Check if nvm is installed
if [ -d "$HOME/.nvm" ]; then
    echo "✅ nvm already installed"
else
    echo "📥 Installing nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

    # Load nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
fi

# Load nvm if not already loaded
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Install Node.js 20
echo ""
echo "📥 Installing Node.js 20..."
nvm install 20

# Set as default
echo ""
echo "🔧 Setting Node.js 20 as default..."
nvm alias default 20
nvm use 20

# Verify
echo ""
echo "✅ Installation complete!"
echo ""
echo "Node.js version:"
node --version
echo ""
echo "npm version:"
npm --version

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Node.js 20 installed successfully!"
echo ""
echo "Next steps:"
echo "1. Close and reopen your terminal, OR"
echo "2. Run: source ~/.bashrc"
echo ""
echo "Then:"
echo "  cd /home/kamicauze/sage/architect/ui"
echo "  npm install"
echo "  cd ../.."
echo "  ./sage pwa"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
