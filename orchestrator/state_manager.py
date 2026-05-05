import json
import os
import shutil
from datetime import datetime
from config import STATE_FILE, STATE_BACKUP_FILE

DEFAULT_STATE = {
    "birth_datetime": datetime.now().isoformat(),
    "calls_today": 0,
    "daily_limit": 6,
    "last_reset_date": str(datetime.now().date()),
    "last_call_time": None,
    "next_wake_time": datetime.now().isoformat(),
    "total_wake_count": 0,
    "silent_wake_count": 0,
    "last_sleep_hours": 4,
    "is_running": False,
}


def read_state() -> dict:
    if not STATE_FILE.exists():
        state = DEFAULT_STATE.copy()
        write_state(state)
        return state
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        if STATE_BACKUP_FILE.exists():
            with open(STATE_BACKUP_FILE, "r") as f:
                return json.load(f)
        return DEFAULT_STATE.copy()


def write_state(state: dict):
    tmp = str(STATE_FILE) + ".tmp"
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    if STATE_FILE.exists():
        shutil.copy2(STATE_FILE, STATE_BACKUP_FILE)
    os.replace(tmp, STATE_FILE)
