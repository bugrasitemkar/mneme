#!/usr/bin/env bash
# Mneme — Pi setup script
# Run as root on Raspberry Pi OS Lite (Pi Zero W/H)
set -euo pipefail

echo "=== Mneme Setup ==="

# 1. System users
# mneme_sys owns the orchestrator and state.json
# mneme_ai is reserved for future sandboxed tool execution
# Current implementation runs tools in-process as mneme_sys
sudo useradd -r -s /bin/false mneme_sys || echo "mneme_sys already exists"
sudo useradd -r -s /bin/false mneme_ai  || echo "mneme_ai already exists"

# 2. Directory structure
sudo mkdir -p /home/mneme/{orchestrator,system,data,orchestrator/logs}
sudo chown -R mneme_sys:mneme_sys /home/mneme/orchestrator
sudo chown -R mneme_sys:mneme_sys /home/mneme/system
sudo chown -R mneme_sys:mneme_sys /home/mneme/data

# 3. Copy orchestrator files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo cp "$SCRIPT_DIR/../orchestrator/"*.py /home/mneme/orchestrator/
sudo chown mneme_sys:mneme_sys /home/mneme/orchestrator/*.py

# 4. Create data files with initial headers
# Must be done BEFORE chattr +a
sudo tee /home/mneme/data/self.md   > /dev/null <<'EOF'
# self.md — Mneme's own findings
EOF

sudo tee /home/mneme/data/memory.md > /dev/null <<'EOF'
# memory.md — Things Mneme chose to remember
EOF

sudo tee /home/mneme/data/world.md  > /dev/null <<'EOF'
# world.md — System log of wakes
EOF

sudo tee /home/mneme/data/letter.md > /dev/null <<'EOF'
# letter.md — Notes to the founder
EOF

sudo chown mneme_sys:mneme_sys /home/mneme/data/*.md

# 5. Append-only lock — AFTER initial content is written
sudo chattr +a /home/mneme/data/self.md
sudo chattr +a /home/mneme/data/memory.md
sudo chattr +a /home/mneme/data/world.md
sudo chattr +a /home/mneme/data/letter.md
echo "chattr +a applied to all data files."

# 6. Initialise state.json
NOW=$(date -Iseconds)
TODAY=$(date +%Y-%m-%d)
sudo tee /home/mneme/system/state.json > /dev/null <<EOF
{
  "birth_datetime": "$NOW",
  "calls_today": 0,
  "daily_limit": 6,
  "last_reset_date": "$TODAY",
  "last_call_time": null,
  "next_wake_time": "$NOW",
  "total_wake_count": 0,
  "silent_wake_count": 0,
  "last_sleep_hours": 4,
  "is_running": false
}
EOF
sudo chown mneme_sys:mneme_sys /home/mneme/system/state.json
sudo chmod 600 /home/mneme/system/state.json
echo "state.json initialised."

# 7. Python dependencies (minimal for Pi Zero W)
sudo pip3 install anthropic langfuse --break-system-packages

# 8. .env file (edit this with your real keys before running)
sudo tee /home/mneme/orchestrator/.env > /dev/null <<'EOF'
ANTHROPIC_API_KEY=sk-ant-REPLACE_ME
LANGFUSE_PUBLIC_KEY=pk-lf-REPLACE_ME
LANGFUSE_SECRET_KEY=sk-lf-REPLACE_ME
EOF
sudo chown mneme_sys:mneme_sys /home/mneme/orchestrator/.env
sudo chmod 600 /home/mneme/orchestrator/.env
echo "IMPORTANT: Edit /home/mneme/orchestrator/.env with your actual API keys before starting."

# 9. Systemd service
sudo cp "$SCRIPT_DIR/../systemd/mneme.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mneme.service
echo "mneme.service enabled (will start on next boot)."

# 10. network-online.target — ensure it actually waits for WiFi on Pi Zero W
sudo systemctl enable NetworkManager-wait-online.service 2>/dev/null || \
sudo systemctl enable dhcpcd.service 2>/dev/null || \
echo "Note: verify network-online.target is active with: systemctl is-active network-online.target"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit /home/mneme/orchestrator/.env with your API keys"
echo "  2. Run scripts/verify.sh to confirm permissions"
echo "  3. sudo systemctl start mneme.service"
echo "  4. sudo journalctl -fu mneme.service"
