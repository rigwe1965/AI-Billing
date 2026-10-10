"""Tiny in-memory login throttle: after MAX_FAILURES failed attempts for the same
(email, client IP) inside WINDOW_SECONDS, further attempts are rejected until the
window passes. Per-process state -- fine for a single-instance deployment; use a
shared store (e.g. Redis) if the API is ever scaled to multiple workers."""

import threading
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

_failures: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def _recent(key: tuple[str, str], now: float) -> list[float]:
    recent = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
    if recent:
        _failures[key] = recent
    else:
        _failures.pop(key, None)
    return recent


def is_blocked(email: str, ip: str) -> bool:
    with _lock:
        return len(_recent((email.lower(), ip), time.monotonic())) >= MAX_FAILURES


def record_failure(email: str, ip: str) -> None:
    with _lock:
        now = time.monotonic()
        key = (email.lower(), ip)
        _recent(key, now)
        _failures.setdefault(key, []).append(now)


def reset(email: str, ip: str) -> None:
    with _lock:
        _failures.pop((email.lower(), ip), None)


def clear_all() -> None:
    with _lock:
        _failures.clear()
