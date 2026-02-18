# Node.js Upgrade Required

Your current Node.js version is **v16.20.2**, but Next.js 15 requires **Node.js 18.18+**.

## Quick Upgrade (Recommended: nvm)

### Option 1: Using nvm (Node Version Manager)

```bash
# Install nvm if not already installed
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc if using zsh

# Install Node.js 20 LTS (recommended)
nvm install 20

# Use Node.js 20
nvm use 20

# Set as default
nvm alias default 20

# Verify
node --version  # Should show v20.x.x
npm --version   # Should show 10.x.x

# Now you can build
cd /home/kamicauze/sage/architect/ui
npm install
npm run dev:network
```

### Option 2: Using NodeSource Repository (Ubuntu/Debian)

```bash
# Add NodeSource repository for Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Install Node.js
sudo apt-get install -y nodejs

# Verify
node --version
npm --version

# Build the app
cd /home/kamicauze/sage/architect/ui
npm install
npm run dev:network
```

### Option 3: Using Snap (Ubuntu)

```bash
# Install Node.js 20 via snap
sudo snap install node --classic --channel=20

# Verify
node --version

# Build the app
cd /home/kamicauze/sage/architect/ui
npm install
npm run dev:network
```

## After Upgrading

```bash
cd /home/kamicauze/sage/architect/ui

# Clean install
rm -rf node_modules package-lock.json
npm install

# Start the server
npm run dev:network

# Visit: http://localhost:3000
```

## Troubleshooting

### nvm command not found after install
```bash
# Add to your shell profile
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Reload
source ~/.bashrc
```

### Multiple Node.js versions installed
```bash
# List all versions
nvm list

# Switch to specific version
nvm use 20

# Remove old version
nvm uninstall 16
```

### Permission errors during npm install
```bash
# Fix npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

## Why Upgrade?

- **Next.js 15** requires modern Node.js features
- **Better performance** with newer V8 engine
- **Security updates** and bug fixes
- **ESM support** for modern JavaScript modules

---

**Recommended:** Use nvm for easy version switching between projects.
