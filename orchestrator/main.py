import fcntl
import logging
import logging.handlers
import os
import signal
import sys
import time
from datetime import datetime, timedelta

import anthropic

from budget import budget_gate
from config import (
    DAILY_LIMIT,
    LOG_DIR,
    LOG_FILE,
    MAX_TURNS_PER_WAKE,
    MODEL,
    PID_FILE,
)
from prompts import build_status_message, build_system_prompt
from state_manager import read_state, write_state
from sync import sync_to_github
from tools import ALLOWED_TOOLS, TOOL_DEFINITIONS, execute_tool
from world_writer import write_world_log

# ---------------------------------------------------------------------------
# Logging — rotating to cap disk use on Pi Zero W SD card
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("mneme")

# ---------------------------------------------------------------------------
# Langfuse (optional — disabled gracefully on any failure, including init)
# ---------------------------------------------------------------------------
_langfuse = None
try:
    from langfuse import Langfuse

    _lf_pub = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    _lf_sec = os.getenv("LANGFUSE_SECRET_KEY", "")
    if _lf_pub and _lf_sec:
        _langfuse = Langfuse(public_key=_lf_pub, secret_key=_lf_sec)
        log.info("Langfuse observability enabled")
    else:
        log.info("Langfuse keys not set — observability disabled")
except Exception:
    log.info("Langfuse init failed — observability disabled")


def _scrub_for_trace(messages: list) -> list:
    """Strip file content from tool_result blocks — keep structure, not AI writing."""
    scrubbed = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            new_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    new_blocks.append({**block, "content": "[file content redacted]"})
                else:
                    new_blocks.append(block)
            scrubbed.append({**m, "content": new_blocks})
        else:
            scrubbed.append(m)
    return scrubbed


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------
_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# ---------------------------------------------------------------------------
# PID file lock — prevents two instances running simultaneously
# ---------------------------------------------------------------------------
_pid_fh = None


def _acquire_lock():
    global _pid_fh
    _pid_fh = open(PID_FILE, "w")
    try:
        fcntl.flock(_pid_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _pid_fh.write(str(os.getpid()))
        _pid_fh.flush()
    except IOError:
        log.error("Another Mneme instance is already running — exiting.")
        sys.exit(1)


def _release_lock():
    if _pid_fh:
        fcntl.flock(_pid_fh, fcntl.LOCK_UN)
        _pid_fh.close()
        try:
            PID_FILE.unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = False


def _on_signal(signum, _frame):
    global _shutdown
    log.info(f"Signal {signum} received — will shut down after current wake.")
    _shutdown = True
    state = read_state()
    state["is_running"] = False
    write_state(state)


signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT, _on_signal)

# ---------------------------------------------------------------------------
# Wake cycle (inner — raises on unhandled error, outer handles recovery)
# ---------------------------------------------------------------------------


def _run_wake_cycle_inner(trace):
    prev_state = read_state()
    prev_call_time = prev_state.get("last_call_time")

    allowed, state = budget_gate()
    if not allowed:
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        state["next_wake_time"] = midnight.isoformat()
        state["is_running"] = False
        write_state(state)
        log.info("Budget exhausted — sleeping until midnight.")
        return

    wake_num = state.get("total_wake_count", 0)
    log.info(f"--- Wake #{wake_num} start ({state['calls_today']}/{state.get('daily_limit', DAILY_LIMIT)} today) ---")

    if trace:
        trace.update(metadata={"wake_number": wake_num, "calls_today": state["calls_today"]})

    system_prompt = build_system_prompt()
    status_msg = build_status_message(state, prev_call_time)
    messages = [{"role": "user", "content": status_msg}]

    state["_terminal"] = False
    tool_calls_made: list[str] = []
    input_tokens_total = 0
    output_tokens_total = 0
    last_turn = 0

    for turn in range(MAX_TURNS_PER_WAKE):
        last_turn = turn + 1
        log.info(f"Turn {last_turn}/{MAX_TURNS_PER_WAKE}")

        generation = None
        if trace:
            generation = trace.generation(
                name=f"turn-{last_turn}",
                model=MODEL,
                input=_scrub_for_trace(messages),  # file contents redacted from cloud
                system=system_prompt,
            )

        try:
            response = _client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            log.error(f"API error on turn {last_turn}: {exc}")
            if generation:
                generation.end(level="ERROR", status_message=str(exc))
            break

        input_tokens_total += response.usage.input_tokens
        output_tokens_total += response.usage.output_tokens

        if generation:
            generation.end(
                output=[b.model_dump() if hasattr(b, "model_dump") else str(b) for b in response.content],
                usage={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
            )

        assistant_content = []
        tool_results = []

        for block in response.content:
            if block.type == "text":
                log.info(f"[TEXT] {block.text[:200]}")
                assistant_content.append({"type": "text", "text": block.text})

            elif block.type == "tool_use":
                assistant_content.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
                if block.name not in ALLOWED_TOOLS:
                    log.warning(f"[REJECTED TOOL] {block.name}")
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": "This tool is not available."}
                    )
                else:
                    log.info(f"[TOOL] {block.name} {block.input}")
                    result, state = execute_tool(block.name, block.input, state, log.info)
                    tool_calls_made.append(block.name)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result}
                    )

        messages.append({"role": "assistant", "content": assistant_content})
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        if state.get("_terminal"):
            log.info("Terminal tool called — ending wake.")
            break
        if response.stop_reason == "end_turn" and not tool_results:
            log.info("Model finished naturally — ending wake.")
            break

    log.info(
        f"Wake #{wake_num} complete. "
        f"Turns: {last_turn}. "
        f"Tokens: {input_tokens_total} in / {output_tokens_total} out."
    )

    if trace:
        trace.update(
            output=f"Wake #{wake_num} complete",
            metadata={
                "input_tokens": input_tokens_total,
                "output_tokens": output_tokens_total,
                "tools_used": tool_calls_made,
                "turns": last_turn,
            },
        )

    sleep_hours = state.get("last_sleep_hours", 4)
    next_wake = datetime.now() + timedelta(hours=sleep_hours)
    state["next_wake_time"] = next_wake.isoformat()
    state["is_running"] = False
    state.pop("_terminal", None)
    write_state(state)

    write_world_log(state, tool_calls_made)
    sync_to_github(wake_num, log.info)
    log.info(f"Next wake at {next_wake.strftime('%H:%M')} ({sleep_hours}h from now).")


def _run_wake_cycle():
    """Outer wrapper: creates Langfuse trace, catches unhandled exceptions,
    writes a 1-hour recovery delay so a crash doesn't burn the daily budget."""
    trace = None
    if _langfuse:
        trace = _langfuse.trace(name="mneme-wake")
    try:
        _run_wake_cycle_inner(trace)
    except Exception as exc:
        log.error(f"Unhandled exception in wake cycle: {exc}", exc_info=True)
        try:
            state = read_state()
            state["next_wake_time"] = (datetime.now() + timedelta(hours=1)).isoformat()
            state["is_running"] = False
            write_state(state)
        except Exception:
            pass
        raise
    finally:
        if _langfuse:
            _langfuse.flush()


# ---------------------------------------------------------------------------
# Main loop — sleep until next_wake_time, wake, repeat; handles reboots cleanly
# ---------------------------------------------------------------------------


def main():
    _acquire_lock()

    # Clear stale is_running left by a hard shutdown (power cut mid-wake)
    state = read_state()
    if state.get("is_running"):
        log.info("Clearing stale is_running flag from unclean shutdown.")
        state["is_running"] = False
        write_state(state)

    log.info("Mneme online.")

    try:
        while not _shutdown:
            state = read_state()
            now = datetime.now()

            try:
                next_wake = datetime.fromisoformat(state.get("next_wake_time", now.isoformat()))
            except ValueError:
                next_wake = now

            sleep_seconds = (next_wake - now).total_seconds()

            if sleep_seconds > 60:
                if sleep_seconds > 300:
                    log.info(f"Sleeping until {next_wake.strftime('%H:%M')} ({sleep_seconds / 3600:.1f}h).")
                deadline = now + timedelta(seconds=sleep_seconds)
                while datetime.now() < deadline and not _shutdown:
                    remaining = (deadline - datetime.now()).total_seconds()
                    time.sleep(min(30, remaining))
            elif sleep_seconds < -300:
                log.info(f"Overdue by {-sleep_seconds:.0f}s — waking immediately (likely rebooted).")

            if not _shutdown:
                _run_wake_cycle()

    finally:
        _release_lock()
        log.info("Mneme offline.")


if __name__ == "__main__":
    main()
