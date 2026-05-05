from datetime import datetime
from state_manager import read_state, write_state
from config import DAILY_LIMIT


def budget_gate() -> tuple[bool, dict]:
    """
    Persist the incremented counter to disk BEFORE returning True.
    A crash after this point still counts the wake — limit cannot be bypassed.
    """
    state = read_state()
    now = datetime.now()

    if state.get("last_reset_date") != str(now.date()):
        state["calls_today"] = 0
        state["last_reset_date"] = str(now.date())
        write_state(state)

    if state["calls_today"] >= state.get("daily_limit", DAILY_LIMIT):
        return False, state

    state["calls_today"] += 1
    state["last_call_time"] = now.isoformat()
    state["total_wake_count"] = state.get("total_wake_count", 0) + 1
    state["is_running"] = True
    write_state(state)  # persist before API call

    return True, state
