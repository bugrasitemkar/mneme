from pathlib import Path

BASE_DIR = Path("/home/mneme")
DATA_DIR = BASE_DIR / "data"
SYSTEM_DIR = BASE_DIR / "system"
ORCHESTRATOR_DIR = BASE_DIR / "orchestrator"
LOG_DIR = ORCHESTRATOR_DIR / "logs"

STATE_FILE = SYSTEM_DIR / "state.json"
STATE_BACKUP_FILE = SYSTEM_DIR / "state.json.bak"
SELF_FILE = DATA_DIR / "self.md"
MEMORY_FILE = DATA_DIR / "memory.md"
WORLD_FILE = DATA_DIR / "world.md"
LETTER_FILE = DATA_DIR / "letter.md"
LOG_FILE = LOG_DIR / "run.log"
PID_FILE = Path("/tmp/mneme.pid")

DAILY_LIMIT = 6
MAX_TURNS_PER_WAKE = 15
MAX_FILE_CHARS = 8000    # chars read from self.md / memory.md (~2000 tokens)
WORLD_READ_CHARS = 3000  # chars read from world.md
APPEND_HARD_LIMIT_CHARS = 3000  # hard ceiling before truncation (~750 tokens)

MODEL = "claude-haiku-4-5"
