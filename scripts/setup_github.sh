#!/usr/bin/env bash
# Mneme — GitHub sync setup
# Run AFTER setup.sh, AFTER filling in .env
set -euo pipefail

echo "=== Mneme GitHub Setup ==="

# Load env
source /home/mneme/orchestrator/.env

if [ -z "${GITHUB_TOKEN:-}" ] || [ -z "${GITHUB_REPO:-}" ]; then
    echo "ERROR: GITHUB_TOKEN and GITHUB_REPO must be set in .env first."
    exit 1
fi

# Install git
sudo apt-get install -y git

# Configure git identity for mneme_sys
sudo -u mneme_sys git config --global user.email "mneme@localhost"
sudo -u mneme_sys git config --global user.name "Mneme"

# Initialise repo in /home/mneme if not already done
if [ ! -d /home/mneme/.git ]; then
    sudo -u mneme_sys git -C /home/mneme init
    echo "Git repo initialised."
fi

# Copy site files from the uploaded mneme/ folder (assumes scp'd to ~/mneme/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo cp "$SCRIPT_DIR/../index.md"    /home/mneme/index.md
sudo cp "$SCRIPT_DIR/../_config.yml" /home/mneme/_config.yml
sudo chown mneme_sys:mneme_sys /home/mneme/index.md /home/mneme/_config.yml

# Create Pi-specific .gitignore — only push data files and site config
sudo tee /home/mneme/.gitignore > /dev/null <<'EOF'
orchestrator/
system/
scripts/
systemd/
__pycache__/
*.pyc
.env
EOF
sudo chown mneme_sys:mneme_sys /home/mneme/.gitignore

# Set remote (token embedded — never stored in plain git config)
REMOTE="https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"
sudo -u mneme_sys git -C /home/mneme remote remove origin 2>/dev/null || true
sudo -u mneme_sys git -C /home/mneme remote add origin "$REMOTE"

# Initial commit and push
sudo -u mneme_sys git -C /home/mneme add index.md _config.yml .gitignore data/
sudo -u mneme_sys git -C /home/mneme commit -m "Mneme: first light"
sudo -u mneme_sys git -C /home/mneme branch -M main
sudo -u mneme_sys git -C /home/mneme push -u origin main

echo ""
echo "=== GitHub sync ready ==="
echo "Repo: https://github.com/${GITHUB_REPO}"
echo ""
echo "Next: enable GitHub Pages in the repo settings:"
echo "  Settings → Pages → Source: Deploy from branch → main → / (root)"
