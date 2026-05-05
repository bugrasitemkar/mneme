#!/usr/bin/env bash
# Mneme — Post-setup verification (post-implementation checklist)
set -euo pipefail
PASS=0; FAIL=0

check() {
    local desc="$1"; local cmd="$2"; local expect_success="${3:-true}"
    if eval "$cmd" &>/dev/null; then
        if [ "$expect_success" = "true" ]; then
            echo "  PASS  $desc"
            ((PASS++))
        else
            echo "  FAIL  $desc (expected failure but succeeded)"
            ((FAIL++))
        fi
    else
        if [ "$expect_success" = "false" ]; then
            echo "  PASS  $desc (correctly rejected)"
            ((PASS++))
        else
            echo "  FAIL  $desc"
            ((FAIL++))
        fi
    fi
}

echo "=== Mneme Verification ==="

echo ""
echo "-- chattr flags --"
check "self.md has +a flag"   "lsattr /home/mneme/data/self.md   | grep -q '\-a\-'"
check "memory.md has +a flag" "lsattr /home/mneme/data/memory.md | grep -q '\-a\-'"
check "world.md has +a flag"  "lsattr /home/mneme/data/world.md  | grep -q '\-a\-'"
check "letter.md has +a flag" "lsattr /home/mneme/data/letter.md | grep -q '\-a\-'"

echo ""
echo "-- File permission: truncation blocked --"
check "Cannot truncate self.md (as root)"   "truncate -s 0 /home/mneme/data/self.md"   false
check "Cannot truncate memory.md (as root)" "truncate -s 0 /home/mneme/data/memory.md" false

echo ""
echo "-- File permission: append allowed --"
check "Can append to self.md (as mneme_sys)" \
    "sudo -u mneme_sys bash -c 'echo test >> /home/mneme/data/self.md'"

echo ""
echo "-- state.json access control --"
check "mneme_sys can read state.json"  "sudo -u mneme_sys cat /home/mneme/system/state.json"
check "mneme_ai cannot read state.json" \
    "sudo -u mneme_ai cat /home/mneme/system/state.json" false

echo ""
echo "-- Systemd --"
check "mneme.service is enabled" "systemctl is-enabled mneme.service"
check "network-online.target exists" "systemctl cat network-online.target"

echo ""
echo "-- Python imports --"
check "anthropic importable" "python3 -c 'import anthropic'"
check "langfuse importable"  "python3 -c 'import langfuse'"

echo ""
echo "-- state.json is valid JSON --"
check "state.json parses" "python3 -m json.tool /home/mneme/system/state.json"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "All checks passed." || echo "Fix failures before starting the service."
