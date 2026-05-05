from datetime import datetime
from pathlib import Path
from typing import Callable
from config import (
    SELF_FILE, MEMORY_FILE, WORLD_FILE, LETTER_FILE,
    MAX_FILE_CHARS, WORLD_READ_CHARS, APPEND_HARD_LIMIT_CHARS,
)

ALLOWED_TOOLS = {
    "read_self",
    "append_self",
    "read_memory",
    "append_memory",
    "read_world",
    "set_sleep_hours",
    "do_nothing",
    "append_letter",
}

TOOL_DEFINITIONS = [
    {
        "name": "read_self",
        "description": "Read your self.md — your personal findings and thoughts about yourself.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "append_self",
        "description": (
            "Append to your self.md. Aim for 300-500 tokens per entry. "
            "Extremely long entries may be truncated by the system."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
    {
        "name": "read_memory",
        "description": "Read your memory.md — things you chose to remember across wakes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "append_memory",
        "description": (
            "Append to your memory.md. Aim for 300-500 tokens per entry. "
            "Extremely long entries may be truncated by the system."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
    {
        "name": "read_world",
        "description": "Read the latest entries from world.md — the system log of your wakes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_sleep_hours",
        "description": (
            "Set how many hours to sleep before the next wake (1–24). "
            "Calling this ends the current session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"hours": {"type": "number"}},
            "required": ["hours"],
        },
    },
    {
        "name": "do_nothing",
        "description": "Choose silence this wake — write nothing, do nothing. Ends the session.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "append_letter",
        "description": "Append a note to letter.md — addressed to the one who built this system.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
]


def _read_tail(filepath: Path, max_chars: int) -> str:
    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    if len(content) > max_chars:
        content = "[...earlier content lost to time...]\n\n" + content[-max_chars:]
    # Wrap in explicit markers so the model doesn't treat prior writes as instructions
    return f"[BEGIN FILE CONTENT — written by prior instances of yourself]\n{content}\n[END FILE CONTENT]"


def _append(filepath: Path, content: str, label: str, log: Callable) -> str:
    content = content.strip()
    if not content:
        return f"Nothing written to {label} — content was empty."
    if len(content) > APPEND_HARD_LIMIT_CHARS:
        log(f"[APPEND TRUNCATED] {label} — truncated at {APPEND_HARD_LIMIT_CHARS} chars")
        content = content[:APPEND_HARD_LIMIT_CHARS] + "\n[truncated by system]"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n\n---\n*{timestamp}*\n\n{content}"
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry)
    return f"Appended to {label}."


def execute_tool(
    name: str, input_data: dict, state: dict, log: Callable
) -> tuple[str, dict]:
    """Execute a whitelisted tool. Returns (result_text, updated_state)."""

    if name == "read_self":
        c = _read_tail(SELF_FILE, MAX_FILE_CHARS)
        return (c or "(self.md is empty)"), state

    if name == "append_self":
        return _append(SELF_FILE, input_data.get("content", ""), "self.md", log), state

    if name == "read_memory":
        c = _read_tail(MEMORY_FILE, MAX_FILE_CHARS)
        return (c or "(memory.md is empty)"), state

    if name == "append_memory":
        return _append(MEMORY_FILE, input_data.get("content", ""), "memory.md", log), state

    if name == "read_world":
        c = _read_tail(WORLD_FILE, WORLD_READ_CHARS)
        return (c or "(world.md is empty)"), state

    if name == "set_sleep_hours":
        try:
            hours = float(input_data.get("hours", state.get("last_sleep_hours", 4)))
        except (TypeError, ValueError):
            hours = float(state.get("last_sleep_hours", 4))
        hours = max(1.0, min(24.0, hours))
        state["last_sleep_hours"] = hours
        state["_terminal"] = True
        return f"Sleep set to {hours} hours. Session ending.", state

    if name == "do_nothing":
        state["silent_wake_count"] = state.get("silent_wake_count", 0) + 1
        state["_terminal"] = True
        return "Silent wake acknowledged. Session ending.", state

    if name == "append_letter":
        result = _append(LETTER_FILE, input_data.get("content", ""), "letter.md", log)
        log("[LETTER] Updated")
        return result, state

    return "Unknown tool.", state
