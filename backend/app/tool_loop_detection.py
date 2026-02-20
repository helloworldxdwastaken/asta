"""
Tool Loop Detection - OpenClaw-style loop detection for Asta.

Detects and prevents tool call loops:
- generic_repeat: same tool+args called 10+ times → warning
- known_poll_no_progress: process poll/log with identical results → warning at 10, critical at 20
- ping_pong: alternating A→B→A→B with no progress → warning at 10, critical at 20
- global_circuit_breaker: any tool repeated 30× with same result → hard block

Reference: reference/openclaw/src/agents/tool-loop-detection.ts
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default thresholds
TOOL_CALL_HISTORY_SIZE = 30
WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20
GLOBAL_CIRCUIT_BREAKER_THRESHOLD = 30


@dataclass
class ToolCallRecord:
    """Record of a single tool call for loop detection."""
    tool_name: str
    args_hash: str
    tool_call_id: str | None = None
    result_hash: str | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoopDetectionResult:
    """Result of loop detection check."""
    stuck: bool
    level: str = "warning"  # "warning" or "critical"
    detector: str = "generic_repeat"  # detector type
    count: int = 0
    message: str = ""
    paired_tool_name: str | None = None
    warning_key: str | None = None


def _stable_stringify(value: Any) -> str:
    """Create deterministic JSON-like string for hashing."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        parts = []
        for k in keys:
            parts.append(f"{json.dumps(k)}:{_stable_stringify(value[k])}")
        return "{" + ",".join(parts) + "}"
    return str(value)


def _digest_stable(value: Any) -> str:
    """Create SHA256 hash of a value."""
    serialized = _stable_stringify_fallback(value)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _stable_stringify_fallback(value: Any) -> str:
    """Fallback stringification that handles errors."""
    try:
        return _stable_stringify(value)
    except Exception:
        if value is None:
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, Exception):
            return f"{type(value).__name__}:{str(value)}"
        return repr(value)


def hash_tool_call(tool_name: str, params: Any) -> str:
    """
    Hash a tool call for pattern matching.
    Uses tool name + deterministic JSON serialization digest of params.
    """
    return f"{tool_name}:{_digest_stable(params)}"


def _is_known_poll_tool(tool_name: str, params: Any) -> bool:
    """Check if this is a known polling tool call."""
    if tool_name == "command_status":
        return True
    if tool_name != "process" or not isinstance(params, dict):
        return False
    action = params.get("action")
    return action in ("poll", "log")


def _extract_text_content(result: Any) -> str:
    """Extract text content from tool result."""
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    texts = []
    for entry in content:
        if isinstance(entry, dict) and isinstance(entry.get("text"), str):
            texts.append(entry["text"])
    return "\n".join(texts).strip()


def _format_error_for_hash(error: Any) -> str:
    """Format error for hashing."""
    if isinstance(error, Exception):
        return error.message or error.name
    if isinstance(error, str):
        return error
    if isinstance(error, (int, float, bool)):
        return str(error)
    return _stable_stringify(error)


def hash_tool_outcome(
    tool_name: str,
    params: Any,
    result: Any,
    error: Any | None = None
) -> str | None:
    """Hash the outcome of a tool call for no-progress detection."""
    if error is not None:
        return f"error:{_digest_stable(_format_error_for_hash(error))}"
    
    if result is None:
        return None
    
    if not isinstance(result, dict):
        return _digest_stable(result)

    details = result.get("details", {})
    if not isinstance(details, dict):
        details = {}
    text = _extract_text_content(result)
    
    # Special handling for poll/log actions
    if _is_known_poll_tool(tool_name, params) and isinstance(params, dict):
        action = params.get("action")
        if action == "poll":
            return _digest_stable({
                "action": action,
                "status": details.get("status"),
                "exitCode": details.get("exitCode"),
                "exitSignal": details.get("exitSignal"),
                "aggregated": details.get("aggregated"),
                "text": text,
            })
        if action == "log":
            return _digest_stable({
                "action": action,
                "status": details.get("status"),
                "totalLines": details.get("totalLines"),
                "totalChars": details.get("totalChars"),
                "truncated": details.get("truncated"),
                "exitCode": details.get("exitCode"),
                "exitSignal": details.get("exitSignal"),
                "text": text,
            })
    
    return _digest_stable({"details": details, "text": text})


def _get_no_progress_streak(
    history: list[ToolCallRecord],
    tool_name: str,
    args_hash: str
) -> tuple[int, str | None]:
    """Get the count of consecutive identical no-progress outcomes."""
    streak = 0
    latest_result_hash: str | None = None
    
    for record in reversed(history):
        if record.tool_name != tool_name or record.args_hash != args_hash:
            continue
        if not record.result_hash:
            continue
        if not latest_result_hash:
            latest_result_hash = record.result_hash
            streak = 1
            continue
        if record.result_hash != latest_result_hash:
            break
        streak += 1
    
    return streak, latest_result_hash


def _get_ping_pong_streak(
    history: list[ToolCallRecord],
    current_signature: str
) -> dict:
    """
    Detect alternating ping-pong patterns.
    Returns dict with count, paired_tool_name, paired_signature, no_progress_evidence.
    """
    if not history:
        return {"count": 0, "paired_tool_name": None, "paired_signature": None, "no_progress_evidence": False}
    
    last = history[-1]
    
    # Find the other signature
    other_signature = None
    other_tool_name = None
    for record in reversed(history[:-1]):
        if record.args_hash != last.args_hash:
            other_signature = record.args_hash
            other_tool_name = record.tool_name
            break
    
    if not other_signature or not other_tool_name:
        return {"count": 0, "paired_tool_name": None, "paired_signature": None, "no_progress_evidence": False}
    
    # Count alternating tail
    alternating_count = 0
    for record in reversed(history):
        expected = last.args_hash if alternating_count % 2 == 0 else other_signature
        if record.args_hash != expected:
            break
        alternating_count += 1
    
    if alternating_count < 2:
        return {"count": 0, "paired_tool_name": None, "paired_signature": None, "no_progress_evidence": False}
    
    # Current should match the opposite of last
    expected_current = other_signature
    if current_signature != expected_current:
        return {"count": 0, "paired_tool_name": None, "paired_signature": None, "no_progress_evidence": False}
    
    # Check for no-progress evidence on both sides
    tail_start = max(0, len(history) - alternating_count)
    first_hash_a = None
    first_hash_b = None
    no_progress_evidence = True
    
    for i in range(tail_start, len(history)):
        record = history[i]
        if not record.result_hash:
            no_progress_evidence = False
            break
        if record.args_hash == last.args_hash:
            if not first_hash_a:
                first_hash_a = record.result_hash
            elif first_hash_a != record.result_hash:
                no_progress_evidence = False
                break
        elif record.args_hash == other_signature:
            if not first_hash_b:
                first_hash_b = record.result_hash
            elif first_hash_b != record.result_hash:
                no_progress_evidence = False
                break
        else:
            no_progress_evidence = False
            break
    
    # Need repeated stable outcomes on both sides
    if not first_hash_a or not first_hash_b:
        no_progress_evidence = False
    
    return {
        "count": alternating_count + 1,
        "paired_tool_name": last.tool_name,
        "paired_signature": last.args_hash,
        "no_progress_evidence": no_progress_evidence,
    }


def _canonical_pair_key(sig_a: str, sig_b: str) -> str:
    """Create canonical key for a pair of signatures."""
    return "|".join(sorted([sig_a, sig_b]))


class ToolLoopDetector:
    """
    Tool loop detection manager for a single session/conversation.
    Maintains sliding window of tool calls and detects various loop patterns.
    """
    
    def __init__(
        self,
        history_size: int = TOOL_CALL_HISTORY_SIZE,
        warning_threshold: int = WARNING_THRESHOLD,
        critical_threshold: int = CRITICAL_THRESHOLD,
        global_breaker_threshold: int = GLOBAL_CIRCUIT_BREAKER_THRESHOLD,
        enabled: bool = True,
        detect_generic_repeat: bool = True,
        detect_poll_no_progress: bool = True,
        detect_ping_pong: bool = True,
    ):
        self.history_size = history_size
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.global_breaker_threshold = global_breaker_threshold
        self.enabled = enabled
        self.detect_generic_repeat = detect_generic_repeat
        self.detect_poll_no_progress = detect_poll_no_progress
        self.detect_ping_pong = detect_ping_pong
        self._history: list[ToolCallRecord] = []
    
    @property
    def history(self) -> list[ToolCallRecord]:
        return self._history
    
    def record_tool_call(
        self,
        tool_name: str,
        params: Any,
        tool_call_id: str | None = None
    ) -> None:
        """Record a tool call in the history."""
        if not self.enabled:
            return
        
        args_hash = hash_tool_call(tool_name, params)
        
        self._history.append(ToolCallRecord(
            tool_name=tool_name,
            args_hash=args_hash,
            tool_call_id=tool_call_id,
        ))
        
        # Maintain sliding window
        if len(self._history) > self.history_size:
            self._history.pop(0)
    
    def record_tool_outcome(
        self,
        tool_name: str,
        params: Any,
        tool_call_id: str | None = None,
        result: Any = None,
        error: Any | None = None
    ) -> None:
        """Record the outcome of a tool call for no-progress detection."""
        if not self.enabled:
            return
        
        result_hash = hash_tool_outcome(tool_name, params, result, error)
        if not result_hash:
            return
        
        args_hash = hash_tool_call(tool_name, params)
        
        # Find and update the matching record
        matched = False
        for record in reversed(self._history):
            if tool_call_id and record.tool_call_id != tool_call_id:
                continue
            if record.tool_name != tool_name or record.args_hash != args_hash:
                continue
            if record.result_hash is not None:
                continue
            record.result_hash = result_hash
            matched = True
            break
        
        if not matched:
            self._history.append(ToolCallRecord(
                tool_name=tool_name,
                args_hash=args_hash,
                tool_call_id=tool_call_id,
                result_hash=result_hash,
            ))
        
        # Maintain sliding window
        if len(self._history) > self.history_size:
            # Remove oldest entries
            self._history = self._history[-self.history_size:]
    
    def detect_loop(self, tool_name: str, params: Any) -> LoopDetectionResult:
        """
        Detect if the current tool call is part of a loop.
        Returns a LoopDetectionResult with stuck=True if loop detected.
        """
        if not self.enabled:
            return LoopDetectionResult(stuck=False)
        
        current_hash = hash_tool_call(tool_name, params)
        
        # Get no-progress streak
        no_progress_streak, latest_result_hash = _get_no_progress_streak(
            self._history, tool_name, current_hash
        )
        
        # Check for known poll tool
        known_poll_tool = _is_known_poll_tool(tool_name, params)
        
        # Check for ping-pong pattern
        ping_pong = _get_ping_pong_streak(self._history, current_hash)
        
        # 1. Global circuit breaker (critical)
        if no_progress_streak >= self.global_breaker_threshold:
            logger.error(
                f"Global circuit breaker triggered: {tool_name} repeated {no_progress_streak} times with no progress"
            )
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="global_circuit_breaker",
                count=no_progress_streak,
                message=f"CRITICAL: {tool_name} has repeated identical no-progress outcomes {no_progress_streak} times. Session execution blocked by global circuit breaker to prevent runaway loops.",
                warning_key=f"global:{tool_name}:{current_hash}:{latest_result_hash or 'none'}",
            )
        
        # 2. Known poll no-progress (critical)
        if (
            known_poll_tool
            and self.detect_poll_no_progress
            and no_progress_streak >= self.critical_threshold
        ):
            logger.error(f"Critical polling loop detected: {tool_name} repeated {no_progress_streak} times")
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="known_poll_no_progress",
                count=no_progress_streak,
                message=f"CRITICAL: Called {tool_name} with identical arguments and no progress {no_progress_streak} times. This appears to be a stuck polling loop. Session execution blocked to prevent resource waste.",
                warning_key=f"poll:{tool_name}:{current_hash}:{latest_result_hash or 'none'}",
            )
        
        # 3. Known poll no-progress (warning)
        if (
            known_poll_tool
            and self.detect_poll_no_progress
            and no_progress_streak >= self.warning_threshold
        ):
            logger.warning(f"Polling loop warning: {tool_name} repeated {no_progress_streak} times")
            return LoopDetectionResult(
                stuck=True,
                level="warning",
                detector="known_poll_no_progress",
                count=no_progress_streak,
                message=f"WARNING: You have called {tool_name} {no_progress_streak} times with identical arguments and no progress. Stop polling and either (1) increase wait time between checks, or (2) report the task as failed if the process is stuck.",
                warning_key=f"poll:{tool_name}:{current_hash}:{latest_result_hash or 'none'}",
            )
        
        # 4. Ping-pong (critical)
        ping_pong_warning_key = None
        if ping_pong.get("paired_signature"):
            ping_pong_warning_key = f"pingpong:{_canonical_pair_key(current_hash, ping_pong['paired_signature'])}"
        else:
            ping_pong_warning_key = f"pingpong:{tool_name}:{current_hash}"
        
        if (
            self.detect_ping_pong
            and ping_pong.get("count", 0) >= self.critical_threshold
            and ping_pong.get("no_progress_evidence")
        ):
            logger.error(
                f"Critical ping-pong loop detected: alternating calls count={ping_pong['count']} currentTool={tool_name}"
            )
            return LoopDetectionResult(
                stuck=True,
                level="critical",
                detector="ping_pong",
                count=ping_pong["count"],
                message=f"CRITICAL: You are alternating between repeated tool-call patterns ({ping_pong['count']} consecutive calls) with no progress. This appears to be a stuck ping-pong loop. Session execution blocked to prevent resource waste.",
                paired_tool_name=ping_pong.get("paired_tool_name"),
                warning_key=ping_pong_warning_key,
            )
        
        # 5. Ping-pong (warning)
        if (
            self.detect_ping_pong
            and ping_pong.get("count", 0) >= self.warning_threshold
        ):
            logger.warning(
                f"Ping-pong loop warning: alternating calls count={ping_pong['count']} currentTool={tool_name}"
            )
            return LoopDetectionResult(
                stuck=True,
                level="warning",
                detector="ping_pong",
                count=ping_pong["count"],
                message=f"WARNING: You are alternating between repeated tool-call patterns ({ping_pong['count']} consecutive calls). This looks like a ping-pong loop; stop retrying and report the task as failed.",
                paired_tool_name=ping_pong.get("paired_tool_name"),
                warning_key=ping_pong_warning_key,
            )
        
        # 6. Generic repeat (warning only)
        # Count recent calls with same tool+args
        recent_count = sum(
            1 for r in self._history
            if r.tool_name == tool_name and r.args_hash == current_hash
        )
        
        if (
            not known_poll_tool
            and self.detect_generic_repeat
            and recent_count >= self.warning_threshold
        ):
            logger.warning(f"Loop warning: {tool_name} called {recent_count} times with identical arguments")
            return LoopDetectionResult(
                stuck=True,
                level="warning",
                detector="generic_repeat",
                count=recent_count,
                message=f"WARNING: You have called {tool_name} {recent_count} times with identical arguments. If this is not making progress, stop retrying and report the task as failed.",
                warning_key=f"generic:{tool_name}:{current_hash}",
            )
        
        return LoopDetectionResult(stuck=False)
    
    def get_stats(self) -> dict:
        """Get current statistics for debugging/monitoring."""
        patterns: dict[str, dict] = {}
        
        for call in self._history:
            key = call.args_hash
            if key not in patterns:
                patterns[key] = {"tool_name": call.tool_name, "count": 0}
            patterns[key]["count"] += 1
        
        most_frequent = None
        max_count = 0
        for pattern in patterns.values():
            if pattern["count"] > max_count:
                max_count = pattern["count"]
                most_frequent = {"tool_name": pattern["tool_name"], "count": pattern["count"]}
        
        return {
            "total_calls": len(self._history),
            "unique_patterns": len(patterns),
            "most_frequent": most_frequent,
        }


# Global session state storage
# Key: conversation_id, Value: ToolLoopDetector instance
_session_detectors: dict[str, ToolLoopDetector] = {}


def get_session_detector(
    conversation_id: str,
    create_if_missing: bool = True,
    **config
) -> ToolLoopDetector | None:
    """
    Get or create a tool loop detector for a session.
    """
    global _session_detectors
    
    if conversation_id not in _session_detectors:
        if not create_if_missing:
            return None
        _session_detectors[conversation_id] = ToolLoopDetector(**config)
    
    return _session_detectors[conversation_id]


def clear_session_detector(conversation_id: str) -> None:
    """Clear a session's detector (e.g., when conversation ends)."""
    global _session_detectors
    if conversation_id in _session_detectors:
        del _session_detectors[conversation_id]


def inject_loop_warning(result_text: str, loop_result: LoopDetectionResult) -> str:
    """
    Inject a loop warning message into tool result text.
    """
    if not loop_result.stuck:
        return result_text
    
    warning_prefix = f"\n\n[{loop_result.detector.upper()} LOOP WARNING] "
    warning_text = warning_prefix + loop_result.message
    
    return result_text + warning_text
