#!/usr/bin/env python3
"""Acceptance-only Driver entry: shared real-ChatGPT test cadence, no retries."""
from __future__ import annotations

import json
import math
import os
import pathlib
import sys
import time
from typing import Callable, TypeVar

import driver

T = TypeVar("T")
MIN_INTERVAL = 30.0
SHARED_GATE = pathlib.Path.home() / ".codex" / "chatgpt-continuity-real-test-gate.json"


class RealTestGate:
    """Reuse the Continuity operator's shared file and exclusive-create lock.

    Keep the lock through reply validation. A failed/interrupted test leaves a
    persistent stop, also honored by the existing Node operator. This is test
    coordination, never WebCodex Session/Job or browser submission authority.
    """

    def __init__(self, path: pathlib.Path = SHARED_GATE, *, clock=time.time, sleep=time.sleep):
        self.path = path
        self.clock, self.sleep = clock, sleep
        # Other/manual sends may not be represented by this operator's file.
        self.start_not_before = clock() + MIN_INTERVAL

    def run(self, operation: Callable[[], T]) -> T:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_name(self.path.name + ".lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise driver.DriverError("Another real-test operator is active; do not send") from exc
        try:
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                state = {}
            if not isinstance(state, dict):
                raise driver.DriverError("Invalid shared real-test state; do not send")
            if state.get("blocked"):
                raise driver.DriverError("Real testing stopped; reconcile the previous test before sending")
            next_at = state.get("nextAllowedAt", 0)
            if isinstance(next_at, bool) or not isinstance(next_at, (int, float)) or not math.isfinite(next_at):
                raise driver.DriverError("Invalid shared cooldown; do not send")
            deadline = max(self.start_not_before, next_at / 1000)
            while self.clock() < deadline:
                self.sleep(deadline - self.clock())
            # Persist before dispatch so a lost process cannot grant a new send.
            state["blocked"] = "WebCodex real test pending or incomplete; reconcile before further tests"
            state["lastReservationAt"] = int(self.clock() * 1000)
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"[real-test] dispatch_at={self.clock():.3f} minimum_interval_s={MIN_INTERVAL:g}", file=sys.stderr, flush=True)
            result = operation()
            completed_at = self.clock()
            # Called only after positive completed end_turn and exact JSON checks.
            # Completion + 30 also prevents sending while a previous reply is running.
            state.pop("blocked", None)
            state["nextAllowedAt"] = max(next_at, math.ceil((completed_at + MIN_INTERVAL) * 1000))
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            print(f"[real-test] completed_at={completed_at:.3f}", file=sys.stderr, flush=True)
            return result
        finally:
            os.close(fd)
            lock.unlink()


class TestWebModel(driver.WebModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gate = RealTestGate()

    def next(self, history, current_prompt):
        return self.gate.run(lambda: super(TestWebModel, self).next(history, current_prompt))


def main(argv=None) -> int:
    ns = driver.args(argv)
    token = os.environ.get("WEBCODEX_TOKEN", "")
    if not token or "\n" in token or "\r" in token:
        print("WEBCODEX_TOKEN is required in the environment", file=sys.stderr)
        return 2
    try:
        wc = driver.WebCodex(ns.webcodex_url, token, 90)
        web = TestWebModel(ns.relay_url, ns.model, ns.effort, 600)
        allowed = set(driver.ALLOWED_TOOLS) | set(ns.allow_tool)
        result = driver.Driver(wc, web, ns.project, allowed=allowed).run(driver.task(ns), ns.session)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except driver.OutcomeUnknown as exc:
        print(json.dumps({"status": "outcome_unknown", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 3
    except (driver.DriverError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
