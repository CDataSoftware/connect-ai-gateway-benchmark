"""Liveness signal for a running matrix: touches results/.heartbeat on model calls, streamed chunks
and MCP calls (at most every 30 seconds unless forced). A watchdog can then tell a slow run that's
still working from one stuck on a request that will never answer, which the run log can't show:
it only gets a line when a run finishes.
"""
import os, time

PATH = os.environ.get("BENCH_HEARTBEAT") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", ".heartbeat")
_last = 0.0


def beat(force=False):
    global _last
    now = time.time()
    if force or now - _last >= 30:
        _last = now
        try:
            with open(PATH, "a"):
                pass
            os.utime(PATH, None)
        except OSError:
            pass  # a heartbeat must never break a run


def iter_beat(items):
    """Yield from items, beating as they arrive (for streamed responses)."""
    for item in items:
        beat()
        yield item
