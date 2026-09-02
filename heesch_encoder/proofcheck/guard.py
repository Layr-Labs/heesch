"""Wall-clock guard for the in-process ENCODING step of a proof check.

The checkers are separate processes and are bounded by `checkers.CheckBudget`
(per-checker caps + an overall deadline, enforced at spawn with
`subprocess.run(timeout=...)`). The Python encoder is not a subprocess, so it
gets its own guard: SIGALRM on a POSIX main thread, a no-op elsewhere (Windows,
worker threads). The portable layer is the monotonic `deadline` the encoder
checks itself (`encode_multilevel_stream(deadline=)`, between universe levels
and every 4096 clauses, raising the same EncodeTimeout), and the outer
backstop is `CheckBudget.deadline`, which the budget-aware pipeline consults
before every spawn.

Audit 2026-08-19 Medium 5: this guard used to wrap the whole check (encode +
checkers), silently capping the documented 1500 s checker deadline at 600 s;
it now wraps only the encoder (see pipeline.check_proof_v2)."""

from __future__ import annotations


class EncodeTimeout(Exception):
    """Raised inside the guarded block when the wall-clock limit elapses."""


class wall_clock_guard:
    def __init__(self, seconds: float | None):
        # None / inf / non-positive -> disabled (the caller decides the limit).
        self.seconds = None
        if seconds is not None and seconds != float("inf") and seconds > 0:
            # signal.alarm takes whole seconds; never round a positive limit to 0.
            self.seconds = max(1, int(seconds + 0.999))
        self.armed = False
        self._old = None

    def __enter__(self):
        import signal
        import threading

        if (self.seconds is not None and hasattr(signal, "SIGALRM")
                and threading.current_thread() is threading.main_thread()):
            def handler(signum, frame):
                raise EncodeTimeout()
            self._old = signal.signal(signal.SIGALRM, handler)
            signal.alarm(self.seconds)
            self.armed = True
        return self

    def __exit__(self, *exc):
        if self.armed:
            import signal

            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._old)
            self.armed = False
        return False
