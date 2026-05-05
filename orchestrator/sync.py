import os
import subprocess
from pathlib import Path

REPO_DIR = Path("/home/mneme")
DATA_FILES = [
    "data/self.md",
    "data/memory.md",
    "data/world.md",
    "data/letter.md",
]


def sync_to_github(wake_num: int, log):
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "")

    if not token or not repo:
        return

    def run(cmd):
        env = os.environ.copy()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "safe.directory"
        env["GIT_CONFIG_VALUE_0"] = str(REPO_DIR)
        return subprocess.run(
            cmd, cwd=REPO_DIR, capture_output=True, text=True, env=env
        )

    try:
        # Embed token in remote URL each time — never stored in git config
        remote = f"https://{token}@github.com/{repo}.git"
        run(["git", "remote", "set-url", "origin", remote])

        run(["git", "add"] + DATA_FILES)

        # Check if there's actually anything new to commit
        diff = run(["git", "diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            log("[SYNC] No changes since last push.")
            return

        run(["git", "commit", "-m", f"Wake #{wake_num}"])

        result = run(["git", "push", "origin", "main"])
        if result.returncode == 0:
            log(f"[SYNC] Pushed Wake #{wake_num} to GitHub.")
        else:
            log(f"[SYNC ERROR] Push failed: {result.stderr.strip()}")

    except Exception as exc:
        log(f"[SYNC ERROR] {exc}")
