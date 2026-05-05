from datetime import datetime, timedelta
from config import WORLD_FILE

_SEASONS = {
    (3, 4, 5): "Spring",
    (6, 7, 8): "Summer",
    (9, 10, 11): "Autumn",
    (12, 1, 2): "Winter",
}


def _season(month: int) -> str:
    for months, name in _SEASONS.items():
        if month in months:
            return name
    return ""


def write_world_log(state: dict, tool_calls: list[str]):
    now = datetime.now()
    wake_num = state.get("total_wake_count", 0)

    birth_str = state.get("birth_datetime", now.isoformat())
    birth = datetime.fromisoformat(birth_str)
    alive = now - birth
    alive_days, alive_h = alive.days, alive.seconds // 3600

    last_call = state.get("last_call_time")
    if last_call:
        since = now - datetime.fromisoformat(last_call)
        since_str = f"{since.seconds // 3600}h {(since.seconds % 3600) // 60}m"
    else:
        since_str = "first wake"

    calls_today = state.get("calls_today", 0)
    daily_limit = state.get("daily_limit", 6)
    next_wake = datetime.fromisoformat(state["next_wake_time"])
    next_wake_str = next_wake.strftime("%H:%M")

    tool_lines = "\n".join(f"- {t}" for t in tool_calls) if tool_calls else "- (none)"

    entry = (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Wake #{wake_num} — {now.strftime('%A, %d %B %Y, %H:%M')}\n"
        f"Alive: {alive_days}d {alive_h}h\n"
        f"Since last wake: {since_str}\n"
        f"Wakes used today: {calls_today} / {daily_limit}\n"
        f"Season: {_season(now.month)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"This wake:\n{tool_lines}\n"
        f"Next wake: {next_wake_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    with open(WORLD_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
